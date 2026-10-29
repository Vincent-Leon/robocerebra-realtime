"""缓存友好的共享前缀提示（计划文档 §6.1–6.2：同一模型、共享前缀、分支指令后缀）。

所有分支（慢分支 PLAN、快分支 ACT、快速检查 CHECK / MONITOR）共用：
  system  = SHARED_SYSTEM（角色 + 家务规则 + 技能说明 + 各模式的输出格式）
  user    = [静态块] → [历史（只追加）] → [当前图像] → [当前状态] → [本次调用的模式指令]
其中静态块在 episode 开始时生成一次（任务、物体 / 装置 / 区域 id、固定装置区域中心坐标），
历史只在末尾追加（较早条目在前），因此前缀在跨调用之间保持逐 token 一致，可被 vLLM 前缀缓存按块复用
（Qwen3.8 混合架构的块大小为 784 token，见 E3.1）。易变内容（图像、位置、消息、时间）放在最后。
cache_bust=True 时在系统提示开头放随机串，内容完全相同但无法复用缓存——用于分离共享 KV 的效果（r2/r3 的做法）。
r3b 起运行器默认改用请求级 cache_salt（llm_client / jev_fast 的 cache_salt_per_request），输入 token 与实验组完全一致。
r5（2026-10-26）新增 VERIFY 模式：快分支判"完成"时由慢分支开思考逐条核实。
第三轮（2026-10-20）新增 ADVISE 模式：慢分支关闭思维链，只输出一两句建议；建议放在快分支调用的当前状态之后、
模式指令之前（历史之后），不破坏可缓存前缀。
"""
from __future__ import annotations
import json, uuid
from typing import Any, Dict, List, Optional
import numpy as np

from llm_planner import HOUSE_RULES, SKILLS_DOC
from llm_client import _img_to_data_url

SHARED_SYSTEM = """You are the high-level controller of a Franka robot arm in a tabletop household simulation. The same model serves several call modes; the LAST instruction in the user message says which mode this call is.
""" + HOUSE_RULES + """
""" + SKILLS_DOC + """
Output formats (reply with exactly one JSON object, no markdown fences):
- PLAN mode: {"thought": "<short>", "plan": [{"skill": "<name>", "args": [<args>]}, ...]}  (the complete remaining plan in execution order; [] if the task is already complete)
- ACT mode: {"thought": "<one or two short sentences>", "skill": "<skill name>", "args": [<args>], "done": false}  or  {"thought": "...", "skill": null, "args": [], "done": true}
- CHECK mode: {"decision": "execute" | "skip" | "wait_for_replan", "reason": "<short>"}
- MONITOR mode: {"decision": "continue" | "cancel", "reason": "<short>"}
- RESUME mode: {"resume_step": <number of the plan step to execute next, or 0 if the plan no longer fits the current state>, "reason": "<short>"}
- ADVISE mode: {"advice": "<at most two short sentences for the fast controller: the next sub-goal(s) and what to avoid>"}
- CHOOSE / DECIDE mode: answer with a single option letter only (no JSON).
- VERIFY mode: {"complete": true | false, "missing": "<short list of the unmet requirements; empty if complete>"}
General guidance: use exact identifiers from the lists below; prefer distinct target regions when several objects go into the same container; do not repeat a failed call unchanged more than twice; if a skill keeps failing, try a different region or recover first."""


def static_block(task: str, objects: List[str], fixtures: List[str], regions: List[str], region_centers: Dict[str, List[float]],
                 drawer_regions: List[str]) -> str:
    lines = [f"TASK: {task}", "", "OBJECT IDS: " + ", ".join(objects), "FIXTURE IDS: " + ", ".join(fixtures),
             "REGION IDS with centers (x, y, z in metres; fixed in the scene):"]
    for r in regions:
        c = region_centers.get(r)
        lines.append(f"  {r}: {c[0]:+.2f}, {c[1]:+.2f}, {c[2]:+.2f}" if c else f"  {r}")
    lines.append("DRAWER REGIONS (open_drawer / close_drawer only these): " + (", ".join(drawer_regions) or "none"))
    return "\n".join(lines)


def history_block(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "HISTORY (append-only): none yet."
    return "HISTORY (append-only, oldest first):\n" + "\n".join(
        f"  [{h['t_sim']:.1f}s] {h['call']} -> {'OK' if h['ok'] else 'FAILED'}: {h['reason']}" for h in history)


def state_block(snap, objects: List[str]) -> str:
    lines = [f"CURRENT STATE at sim time {snap.sim_time:.1f} s (observation version {snap.version}):",
             f"  object in hand: {snap.held or 'none'}; gripper {'closed' if snap.gripper > 0 else 'open'}"]
    hid = set(getattr(snap, "hidden", None) or [])
    for o in objects:
        p = snap.objects.get(o)
        if p and o not in hid: lines.append(f"  {o}: {p[0]:+.2f}, {p[1]:+.2f}, {p[2]:+.2f}")
    if snap.drawers:
        lines.append("  drawer open fraction: " + ", ".join(f"{k}={v:.2f}" for k, v in snap.drawers.items()))
    if getattr(snap, "messages", None):
        lines.append("  MESSAGES FROM THE USER / ENVIRONMENT (they override the original task where they conflict):")
        for m in snap.messages[-6:]:
            lines.append(f"    [{m['t']:.1f}s] {m['text']}")
    return "\n".join(lines)


MODE_INSTR = {
    "PLAN": "MODE: PLAN. Think carefully, then output the complete remaining plan (PLAN-mode JSON).",
    "ACT": "MODE: ACT. Decide the single next skill call now (ACT-mode JSON).",
    "CHECK": "MODE: CHECK. New messages arrived after the plan was made. Is the NEXT PLANNED STEP still correct? (CHECK-mode JSON)",
    "MONITOR": "MODE: MONITOR. A skill is executing right now. Should it continue or be cancelled given the newest messages? (MONITOR-mode JSON)",
    "RESUME": "MODE: RESUME. A new plan arrived (listed above) while other actions were being executed. Which plan step should be executed next so that nothing already achieved is repeated and nothing still needed is skipped? (RESUME-mode JSON)",
    "CHOOSE": "MODE: CHOOSE. Pick the best next action from the candidate list above. Answer with its single letter only.",
    "DECIDE": "MODE: DECIDE. Pick the correct option from the list above. Answer with its single letter only.",
    "VERIFY": ("MODE: VERIFY. The fast controller believes the whole task is complete. Check every requirement of the TASK (and of any newer messages) "
               "against the CURRENT STATE (object positions versus region centers, drawer open fractions, object in hand) and the HISTORY. "
               "Set complete to false if any requirement is not clearly satisfied (VERIFY-mode JSON)."),
    "ADVISE": ("MODE: ADVISE. A fast controller picks one action at a time and will read your advice. Do not write a full plan. "
               "In at most two short sentences, say what the next sub-goal is and what to avoid (ADVISE-mode JSON)."),
}


class SharedPromptBuilder:
    def __init__(self, static_text: str, use_image: bool = True, cache_bust: bool = False):
        self.static_text = static_text; self.use_image = use_image; self.cache_bust = cache_bust

    def messages(self, snap, objects: List[str], history: List[Dict[str, Any]], mode: str, extra: str = "") -> List[Dict[str, Any]]:
        system = SHARED_SYSTEM if not self.cache_bust else f"[nonce {uuid.uuid4().hex}]\n" + SHARED_SYSTEM
        parts: List[Dict[str, Any]] = [{"type": "text", "text": self.static_text + "\n\n" + history_block(history) + "\n"}]
        if self.use_image and snap.agentview is not None:
            parts.append({"type": "image_url", "image_url": {"url": _img_to_data_url(snap.agentview)}})
        tail = state_block(snap, objects) + ("\n\n" + extra if extra else "") + "\n\n" + MODE_INSTR[mode]
        parts.append({"type": "text", "text": tail})
        return [{"role": "system", "content": system}, {"role": "user", "content": parts}]
