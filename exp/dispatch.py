"""把 goal.json 的一个状态 (verb, obj, target) 映射为执行器技能调用（GT 计划运行器与 Original 协议运行器共用）。"""
from __future__ import annotations
from skills import ScriptedExecutor, SkillResult


def execute_goal_state(ex: ScriptedExecutor, obj: str, act, site_names, log=print, auto_pick: bool = True):
    """返回 (SkillResult 列表)。verb in/on/pour 若手中无物且 auto_pick 则先抓取。"""
    verb = act[0]; tgt = act[2] if len(act) > 2 else (act[1] if len(act) > 1 else None)
    results = []
    def recover():
        ex.hold(5, -1.0, "recover"); ex.gripper = -1.0; ex.held = None; ex.go_home(-1.0, "recover")
    if verb == "pick":
        r = ex.pick(obj); results.append(r)
        if not r.ok: recover()
        return results
    if verb in ("in", "on", "pour"):
        if ex.held != obj:
            if ex.held is not None:
                log(f"[warn] 手中是 {ex.held}，目标物体是 {obj}；先放回桌面")
                r0 = ex.place("coffee_table_table_region") if "coffee_table_table_region" in site_names else ex.place_on_object(ex.held)
                results.append(r0)
            if auto_pick:
                r0 = ex.pick(obj); results.append(r0)
                if not r0.ok:
                    recover(); log(f"[skip] {act}: 抓取失败，跳过"); return results
            else:
                results.append(SkillResult(f"{verb}({obj})", False, "nothing in hand", 0, ex.n_done, ex.n_done)); return results
        if verb == "pour":
            results.append(ex.pour(tgt))
        else:
            results.append(ex.place(tgt) if tgt in site_names else ex.place_on_object(tgt))
        return results
    if verb == "open":
        results.append(ex.open_drawer(tgt) if tgt in site_names else SkillResult(f"open({tgt})", False, "door opening not implemented", 0, ex.n_done, ex.n_done)); return results
    if verb == "close":
        results.append(ex.close_drawer(tgt) if tgt in site_names else SkillResult(f"close({tgt})", False, "door closing not implemented", 0, ex.n_done, ex.n_done)); return results
    if verb == "turnon":
        results.append(ex.turnon(tgt)); return results
    results.append(SkillResult(f"{verb}", False, "unknown verb", 0, ex.n_done, ex.n_done)); return results
