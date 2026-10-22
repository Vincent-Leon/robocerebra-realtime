"""同模型快慢双分支（远程 API 版：同一模型权重，思考开=慢分支，思考关=快分支；不共享 KV）。

慢分支（后台线程）：基于观测版本 v 生成"剩余计划"（技能列表），发布 Plan(plan_id, obs_version, sim_time, steps)。
协调器（主规划线程）：
  1. 取当前计划的下一步；做程序化前置条件检查（可观测谓词）。
  2. 若计划生成后出现了新消息（计划可能过时），调用快分支（思考关）做语义检查：执行 / 跳过此步 / 等待新计划。
  3. 提交技能；执行期间若到达新消息，快分支判断是否取消（与 run_llm_episode 的 monitor 相同）。
  4. 新计划到达时与"计划观测时刻之后已执行的动作"对账：去掉新计划开头已完成的步骤。
  5. 技能失败 / 计划耗尽 / 新消息 → 请求重新规划；慢分支思考期间协调器继续执行旧计划中仍有效的步骤（推理与执行重叠）。
"""
from __future__ import annotations
import json, re, threading, time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from llm_planner import HOUSE_RULES, SKILLS_DOC, scene_text, validate_action

PLAN_SYSTEM = """You are the deliberate high-level planner of a Franka robot arm in a tabletop household simulation.
""" + HOUSE_RULES + """
Produce the COMPLETE remaining plan from the current state to finish the task, as a list of skill calls in execution order.
Reply ONLY with JSON: {"thought": "<short>", "plan": [{"skill": "<name>", "args": [<args>]}, ...]}
Use an empty plan [] only if the whole task is already complete. No markdown fences."""

CHECK_SYSTEM = """You quickly check whether the robot's NEXT planned step is still correct given NEW messages that arrived after the plan was made.
Reply ONLY with JSON: {"decision": "execute" | "skip" | "wait_for_replan", "reason": "<short>"}
- execute: the step is still useful and consistent with the new messages.
- skip: the step is now wrong (e.g. it uses a target the user cancelled) but later steps may still be fine.
- wait_for_replan: the plan is invalid; wait for the planner to replan."""


@dataclass
class Plan:
    plan_id: int
    obs_version: int
    sim_time: float
    n_messages: int
    steps: List[Dict[str, Any]]
    thought: str = ""
    latency: float = 0.0
    executed_since_obs: List[str] = field(default_factory=list)


def parse_plan(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not text: return None, "empty response"
    try:
        i, j = text.index("{"), text.rindex("}")
        d = json.loads(text[i:j + 1])
        if isinstance(d, dict) and isinstance(d.get("plan"), list): return d, None
    except Exception as e:
        return None, f"json error {e!r}"[:120]
    return None, "no plan field"


def call_str(step: Dict[str, Any]) -> str:
    return f"{step.get('skill')}({', '.join(map(str, step.get('args') or []))})"


def precondition_ok(step: Dict[str, Any], snap, objects, regions) -> Tuple[bool, str]:
    """程序化前置条件（只用可观测量）。"""
    sk = step.get("skill"); a = (step.get("args") or [None])[0]
    if sk == "pick":
        if snap.held is not None: return False, f"hand busy with {snap.held}"
        for r, frac in (snap.drawers or {}).items():
            pass
        return True, ""
    if sk in ("place", "pour"):
        if snap.held is None: return False, "nothing in hand"
        return True, ""
    if sk == "open_drawer":
        if (snap.drawers or {}).get(a, 0.0) >= 0.5: return False, "already open"
        return True, ""
    if sk == "close_drawer":
        if (snap.drawers or {}).get(a, 1.0) <= 0.1: return False, "already closed"
        return True, ""
    return True, ""


# ---------- 基于可观测状态的计划步骤检查与符号化验证（2026-10-17 第二轮） ----------
# 只用快照里可观测的量：手中物体、抽屉开度。不读计分器，不泄露子目标完成标签。

def step_status(step: Dict[str, Any], held: Optional[str], drawers: Dict[str, float], drawer_regions) -> Tuple[str, str]:
    """返回 ("done", why)：效果已成立，跳过即可；("blocked", why)：前置条件不满足；("ready", "")。"""
    sk = step.get("skill"); a = (step.get("args") or [None])[0]
    if sk == "pick":
        if held is not None and held == a: return "done", f"already holding {a}"
        if held is not None: return "blocked", f"hand busy with {held}"
        return "ready", ""
    if sk in ("place", "pour"):
        if held is None: return "blocked", "nothing in hand"
        if sk == "place" and a in drawer_regions and drawers.get(a, 0.0) < 0.5: return "blocked", f"drawer {a} is closed"
        return "ready", ""
    if sk in ("open_drawer", "close_drawer"):
        frac = drawers.get(a)
        if frac is not None and sk == "open_drawer" and frac >= 0.5: return "done", "already open"
        if frac is not None and sk == "close_drawer" and frac <= 0.1: return "done", "already closed"
        if held is not None: return "blocked", f"hand must be empty to operate a drawer (holding {held})"
        return "ready", ""
    if sk == "turnon":
        if held is not None: return "blocked", f"hand must be empty to turn a knob (holding {held})"
        return "ready", ""
    return "ready", ""


def apply_effect(step: Dict[str, Any], held: Optional[str], drawers: Dict[str, float]) -> Tuple[Optional[str], Dict[str, float]]:
    """假设技能成功时的符号化效果。"""
    sk = step.get("skill"); a = (step.get("args") or [None])[0]
    drawers = dict(drawers)
    if sk == "pick": held = a
    elif sk == "place": held = None
    elif sk == "open_drawer": drawers[a] = 1.0
    elif sk == "close_drawer": drawers[a] = 0.0
    return held, drawers


def check_plan(steps: List[Dict[str, Any]], held: Optional[str], drawers: Dict[str, float], drawer_regions) -> Optional[str]:
    """从给定状态符号化走一遍计划，返回第一处不可执行步骤的说明；全部可执行则返回 None。"""
    for i, s in enumerate(steps):
        stt, why = step_status(s, held, drawers, drawer_regions)
        if stt == "blocked":
            return f"step {i + 1} {call_str(s)} is not executable at that point ({why})"
        if stt == "ready":
            held, drawers = apply_effect(s, held, drawers)
    return None


def align_prefix(steps: List[Dict[str, Any]], done_after: List[str]) -> Tuple[int, int]:
    """计划观测之后成功执行的动作按顺序与计划开头匹配。返回 (k, 未被解释的动作数)。"""
    k = 0; unexplained = 0
    for c in done_after:
        if k < len(steps) and call_str(steps[k]) == c: k += 1
        else: unexplained += 1
    return k, unexplained
