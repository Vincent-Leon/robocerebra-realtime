"""诊断 oracle 规划器 × 实时异步环境 × 可选事件：按 GT 计划（goal.json 的 task_step 顺序）下发技能，每步前固定"思考"延迟。
不读消息（事件后仍执行旧计划）——用于测量：E3 截止时间在不同决策延迟下是否可行；E1 不响应更新时的代价下界。
用法: python run_oracle_episode.py Ideal/case6 [--think=0] [--events=...] [--tag=NAME]
"""
import sys, time, threading, json
import numpy as np
import rc_env as R
from realtime_env import RealtimeSim
from events import EventManager, load_specs

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
tt, cn = (args[0] if args else "Ideal/case6").split("/")
think = float(opt.get("think", 0.0)); ev_path = opt.get("events")
ev_name = ev_path.split("/")[-1].replace(".json", "") if ev_path else "noevent"
tag = opt.get("tag", f"{ev_name}_oracle_think{think:g}")
out = R.RUNS_ROOT / "oracle" / f"{tt}_{cn}" / tag; out.mkdir(parents=True, exist_ok=True)
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
sim = RealtimeSim(case, rtr=1.0, camera=False, max_sim_time=float(opt.get("max_sim", 150)))
if opt.get("track") == "on": sim.ex_attrs = {"track_targets": True}; tag = tag + "_track"; out = R.RUNS_ROOT / "oracle" / f"{tt}_{cn}" / tag; out.mkdir(parents=True, exist_ok=True)
mgr = None
if ev_path: mgr = EventManager(load_specs(ev_path)); mgr.attach(sim)
plan = sorted([(stp, obj, act) for obj, acts in case.goal.items() for act, stp in zip(acts, case.goal_steps[obj])], key=lambda x: x[0])
history = []


def oracle():
    while sim.latest() is None: time.sleep(0.05)
    site_names = set(sim.env.sim.model.site_names); objects = set(sim.env.objects_dict)
    for stp, obj, act in plan:
        if not sim.running: break
        verb = act[0]; tgt = act[2] if len(act) > 2 else act[1]
        if verb == "pick": name, a = "pick", (obj,)
        elif verb in ("in", "on"): name, a = ("place" if tgt in site_names else "place_on_object"), (tgt,)
        elif verb == "pour": name, a = "pour", (tgt,)
        elif verb == "open": name, a = "open_drawer", (tgt,)
        elif verb == "close": name, a = "close_drawer", (tgt,)
        elif verb == "turnon": name, a = "turnon", (tgt,)
        else: continue
        snap = sim.latest()
        sim.log_event("think_start", step_idx=stp, obs_version=snap.version, branch="oracle")
        time.sleep(think)
        sim.log_event("think_end", step_idx=stp)
        cid = sim.submit_skill(name, *a, obs_version=snap.version, plan_id=f"gt{stp}")
        oc = sim.wait_outcome(cid, timeout=90)
        history.append({"t_sim": (oc["finished_sim"] - sim.sim_t0) if oc else None, "call": f"{name}{a}", "ok": bool(oc and oc["ok"]), "reason": (oc or {}).get("reason", "timeout")[:80]})
    time.sleep(0.3)
    if sim.running: sim.stop()


th = threading.Thread(target=oracle, daemon=True)
sim.run(planner_thread=th)
sim.dump(out / "timeline.json")
final = {"original": int(sim.scorer.last[0]), "repaired": int(sim.scorer.last[2]), "n_goals": int(sim.scorer.n_goals), "all_done": bool(sim.scorer.last[3])}
rep = mgr.report() if mgr else {}
summary = {"case": f"{tt}/{cn}", "events": ev_name, "think": think, "final": final, "sim_time": round(float(sim.env.sim.data.time - sim.sim_t0), 2),
           "event_report": rep, "history": history, "subgoal_events": [(round(t - sim.sim_t0, 2), w) for t, w in sim.scorer.rep.events]}
json.dump(summary, open(out / "episode.json", "w"), indent=1, default=str)
print(f"[ORACLE] {tt}/{cn} {tag}: repaired {final['repaired']}/{final['n_goals']} all={final['all_done']} sim={summary['sim_time']}s")
