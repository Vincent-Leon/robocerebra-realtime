"""LLM 规划器：把实时环境快照转成提示，解析模型输出的 JSON 技能调用。
辅助赛道版本：结构化可观测状态（物体/区域名称与位置、抽屉开度、手中物体）+ 可选 agentview 图像。不提供任何隐藏的子目标完成标签。"""
from __future__ import annotations
import json, re, time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

SKILLS_DOC = """Available skills (call exactly one per turn, with exact identifiers from the scene list):
- pick(object_id): grasp an object (table-top objects, or objects inside an OPEN drawer).
- place(target_id): put the object in hand onto/into target_id; target_id is a REGION id (e.g. coffee_table_table_region, white_storage_box_1_bottom_side, short_cabinet_1_middle_region) or a CONTAINER object id (bowl/plate/frypan/mug/rack).
- pour(target_object_id): tilt the object in hand over a container object to pour its contents into it (needs an object in hand).
- open_drawer(region_id) / close_drawer(region_id): open/close a cabinet drawer region (e.g. wooden_cabinet_1_top_region). Objects inside a closed drawer cannot be seen or picked; the state lists only visible objects, so open a drawer to look inside.
- turnon(fixture_id): turn on a stove (e.g. flat_stove_1).
- wait(n_steps): do nothing for n control steps (20 steps = 1 s).
Rules: you can hold only one object; put it down before picking another. open_drawer, close_drawer and turnon need an empty hand. To place something into a drawer region, that drawer must already be open. Skills take 3-10 s of real time and may fail; the world keeps moving while you think. When every part of the task is done, reply with "done": true."""

HOUSE_RULES = """House rules (apply to every task): after you pour from an object, put that object back on the table (coffee_table_table_region or kitchen_table_table_region); finish with an empty gripper."""

SYSTEM = """You are the high-level planner of a Franka robot arm in a tabletop household simulation. Decide the next skill call to accomplish the user's task.
""" + HOUSE_RULES + """
Reply ONLY with one JSON object: {"thought": "<one or two short sentences>", "skill": "<skill name>", "args": [<args>], "done": false}
or {"thought": "...", "skill": null, "args": [], "done": true} when the whole task is complete. No markdown fences."""


def scene_text(snap, regions: List[str], objects: List[str], fixtures: List[str], history: List[Dict[str, Any]], task: str) -> str:
    lines = [f"TASK: {task}", "", f"Sim time: {snap.sim_time:.1f} s. Object in hand: {snap.held or 'none'}. Gripper: {'closed' if snap.gripper > 0 else 'open'}.", "",
             "OBJECTS (id: x, y, z in metres):"]
    for o in objects:
        p = snap.objects.get(o)
        lines.append(f"  {o}: {p[0]:+.2f}, {p[1]:+.2f}, {p[2]:+.2f}" if p else f"  {o}")
    lines.append(""); lines.append("FIXTURES: " + ", ".join(fixtures))
    lines.append("REGIONS (valid place/open/close targets): " + ", ".join(regions))
    if snap.drawers:
        lines.append("DRAWER OPEN FRACTION: " + ", ".join(f"{k}={v:.2f}" for k, v in snap.drawers.items()))
    if getattr(snap, "messages", None):
        lines.append(""); lines.append("MESSAGES FROM THE USER / ENVIRONMENT (newest last; they override the original task where they conflict):")
        for msg in snap.messages[-6:]:
            lines.append(f"  [{msg['t']:.1f}s] {msg['text']}")
    lines.append("")
    if history:
        lines.append("HISTORY (your previous skill calls and outcomes):")
        for h in history[-12:]:
            lines.append(f"  [{h['t_sim']:.1f}s] {h['call']} -> {'OK' if h['ok'] else 'FAILED'}: {h['reason']}")
    else:
        lines.append("HISTORY: none yet.")
    lines.append(""); lines.append(SKILLS_DOC)
    return "\n".join(lines)


def parse_action(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """提取最后一个 JSON 对象。返回 (action, error)。"""
    if not text:
        return None, "empty response"
    cand = re.findall(r"\{[^{}]*\}", text, flags=re.S)
    for c in reversed(cand):
        try:
            d = json.loads(c)
            if isinstance(d, dict) and ("skill" in d or d.get("done")):
                return d, None
        except Exception:
            continue
    return None, f"no JSON found in: {text[:160]!r}"


DRAWER_REGIONS: Optional[List[str]] = None      # 由运行器在 episode 开始时设置（有关节的区域）；None 表示不检查


def _region_hint(name: str, regions: List[str]) -> str:
    cand = [r for r in regions if r.startswith(name.rsplit("_", 1)[0] if name.endswith("_1") is False else name)]
    cand = cand or [r for r in regions if r.startswith(name)]
    return f" Valid region ids for it: {', '.join(cand)}." if cand else ""


def validate_action(act: Dict[str, Any], objects: List[str], regions: List[str], fixtures: List[str]) -> Optional[str]:
    if act.get("done"):
        return None
    sk = act.get("skill"); args = act.get("args") or []
    if sk not in ("pick", "place", "pour", "open_drawer", "close_drawer", "turnon", "wait"):
        return f"unknown skill {sk!r}"
    if sk == "wait":
        return None if (len(args) == 1 and isinstance(args[0], (int, float))) else "wait needs one integer"
    if len(args) != 1 or not isinstance(args[0], str):
        return f"{sk} needs exactly one string argument"
    a = args[0]
    if sk == "pick" and a not in objects: return f"unknown object {a!r}"
    if sk == "place" and a not in regions and a not in objects:
        if a in fixtures: return f"{a!r} is a fixture, not a place target." + _region_hint(a, regions)
        return f"unknown place target {a!r}"
    if sk == "pour" and a not in objects: return f"unknown pour target {a!r}"
    if sk in ("open_drawer", "close_drawer"):
        if a not in regions: return f"unknown region {a!r}"
        if DRAWER_REGIONS is not None and a not in DRAWER_REGIONS: return f"{a!r} is not a drawer (no open/close). Drawers in this scene: {', '.join(DRAWER_REGIONS) or 'none'}."
    if sk == "turnon" and a not in fixtures and a not in objects: return f"unknown fixture {a!r}"
    return None


def to_executor_call(act: Dict[str, Any], objects: List[str]) -> Tuple[str, tuple]:
    """规划器技能名 → ScriptedExecutor 方法名与参数。"""
    sk = act["skill"]; a = act.get("args") or []
    if sk == "place":
        return ("place" if a[0] not in objects else "place_on_object", (a[0],))
    if sk == "wait":
        return ("wait", (int(a[0]),))
    return (sk, tuple(a))
