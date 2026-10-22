"""LLM 规划器 × 实时异步环境 × 可选动态事件 × 可选快速监控（同一模型，关闭思考）。
用法: python run_llm_episode.py Ideal/case6 [--thinking=on|off] [--image=on|off] [--events=configs/events/x.json]
                                [--monitor=on|off] [--rtr=1.0] [--max_calls=25] [--max_sim=240] [--video] [--tag=NAME] [--seed=0]
"""
import sys, time, threading, json, random
import numpy as np
import rc_env as R
from realtime_env import RealtimeSim
from llm_client import LLMClient
from llm_planner import SYSTEM, scene_text, parse_action, validate_action, to_executor_call
from events import EventManager, load_specs

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
flags = {a[2:] for a in sys.argv[1:] if a.startswith("--") and "=" not in a}
tt, cn = (args[0] if args else "Ideal/case6").split("/")
thinking = opt.get("thinking", "on") == "on"; use_image = opt.get("image", "on") == "on"; monitor = opt.get("monitor", "off") == "on"
rtr = float(opt.get("rtr", 1.0)); max_calls = int(opt.get("max_calls", 25)); max_sim = float(opt.get("max_sim", 240))
ev_path = opt.get("events"); seed = int(opt.get("seed", 0))
ev_name = (ev_path.split("/")[-1].replace(".json", "") if ev_path else "noevent")
tag = opt.get("tag", f"{ev_name}_{'think' if thinking else 'nothink'}{'_mon' if monitor else ''}_s{seed}")
import os as _os
out = R.RUNS_ROOT / _os.environ.get("RUNS_SUBDIR", "llm") / f"{tt}_{cn}" / tag; out.mkdir(parents=True, exist_ok=True)
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
sim = RealtimeSim(case, rtr=rtr, camera=True, max_sim_time=max_sim)
frames = []
def grab(s):
    snap = s.latest()
    if "video" in flags and snap is not None and snap.agentview is not None and snap.step % 4 == 0: frames.append(snap.agentview)
sim.on_tick = grab
mgr = None
if ev_path:
    mgr = EventManager(load_specs(ev_path)); mgr.attach(sim)
client = LLMClient(); client.seed = seed
client.chat(client.build_messages(None, "ok"), max_tokens=1, thinking=False); client.log.clear()   # 开局前预热连接
llm_log = []; history = []; monitor_log = []

MON_SYSTEM = """You monitor a robot skill that is currently executing. Decide quickly whether it should CONTINUE or be CANCELLED so the planner can replan.
Cancel only if a new message or observation makes the current skill wrong or harmful for the task. Reply ONLY with JSON: {"decision": "continue" | "cancel", "reason": "<short>"}"""


def fast_check(snap, cur_skill: str):
    msgs_txt = "\n".join(f"  [{m['t']:.1f}s] {m['text']}" for m in snap.messages[-4:])
    user = (f"TASK: {case.task_line}\nObject in hand: {snap.held or 'none'}\nCurrently executing: {cur_skill}\n"
            f"Recent skills: " + "; ".join(f"{h['call']}->{'OK' if h['ok'] else 'FAIL'}" for h in history[-4:]) +
            f"\nNEW MESSAGES:\n{msgs_txt}\nShould the current skill continue or be cancelled?")
    r = client.chat(client.build_messages(MON_SYSTEM, user), max_tokens=80, thinking=False)
    dec = "continue"
    try:
        d = json.loads(r.text[r.text.index("{"):r.text.rindex("}") + 1]); dec = str(d.get("decision", "continue")).lower()
    except Exception:
        pass
    return dec, r


def planner():
    while sim.latest() is None: time.sleep(0.05)
    env = sim.env
    objects = list(env.objects_dict.keys()); fixtures = list(env.fixtures_dict.keys()); regions = list(env.regions)
    import llm_planner as LP
    LP.DRAWER_REGIONS = [r for r in regions if env.object_sites_dict.get(r) is not None and (env.object_sites_dict[r].joints or [])]
    n_calls = 0; consecutive_invalid = 0
    while sim.running and n_calls < max_calls:
        snap = sim.latest()
        user = scene_text(snap, regions, objects, fixtures, history, case.task_line)
        msgs = client.build_messages(SYSTEM, user, images=[snap.agentview] if use_image and snap.agentview is not None else None)
        sim.log_event("think_start", step_idx=n_calls, obs_version=snap.version, sim_time_obs=snap.sim_time, thinking=thinking, branch="slow" if thinking else "fast")
        r = client.chat(msgs, max_tokens=int(opt.get('think_max_tokens', 4096)) if thinking else 256, thinking=thinking)
        n_calls += 1
        sim.log_event("think_end", step_idx=n_calls - 1, latency=round(r.latency, 3), completion_tokens=r.usage.get("completion_tokens"), error=r.error)
        act, perr = parse_action(r.text)
        verr = validate_action(act, objects, regions, fixtures) if act else None
        llm_log.append({"call": n_calls, "sim_time_obs": snap.sim_time, "obs_version": snap.version, "n_messages_seen": len(snap.messages),
                        "latency": r.latency, "ttft": r.ttft, "usage": r.usage, "response": r.text, "error": r.error,
                        "parse_error": perr, "validation_error": verr, "action": act, "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
        if r.error or act is None or verr:
            consecutive_invalid += 1
            history.append({"t_sim": snap.sim_time - sim.sim_t0, "call": "<invalid reply>", "ok": False, "reason": str(r.error or perr or verr)[:220]})
            sim.log_event("invalid_action", reason=str(r.error or perr or verr)[:120])
            if consecutive_invalid >= 5: sim.log_event("abort", reason="5 consecutive invalid replies"); break
            continue
        consecutive_invalid = 0
        if act.get("done"):
            sim.log_event("planner_done", thought=act.get("thought", "")[:200]); break
        name, cargs = to_executor_call(act, objects)
        call_str = f"{act['skill']}({', '.join(map(str, act['args']))})"
        cid = sim.submit_skill(name, *cargs, obs_version=snap.version, plan_id=f"c{n_calls}")
        seen_msgs = len(snap.messages); oc = None; t_wait0 = time.time()
        while time.time() - t_wait0 < 90:
            with sim._lock: oc = sim.outcomes.get(cid)
            if oc is not None or not sim.running: break
            cur = sim.latest()
            if monitor and cur is not None and len(cur.messages) > seen_msgs and cur.current_skill is not None:
                seen_msgs = len(cur.messages)
                sim.log_event("think_start", step_idx=f"mon{n_calls}", obs_version=cur.version, branch="monitor")
                dec, mr = fast_check(cur, call_str)
                sim.log_event("think_end", step_idx=f"mon{n_calls}", latency=round(mr.latency, 3), decision=dec)
                monitor_log.append({"t_sim": cur.sim_time, "skill": call_str, "decision": dec, "latency": mr.latency, "response": mr.text})
                if dec == "cancel": sim.cancel(reason=f"monitor: {mr.text[:80]}", source="fast monitor")
            time.sleep(0.05)
        if oc is None:
            history.append({"t_sim": sim.latest().sim_time - sim.sim_t0, "call": call_str, "ok": False, "reason": "timeout"}); continue
        reason = oc["reason"][:100] + (f" (interrupted: {oc.get('cancel_source') or 'unknown'})" if oc.get("cancelled") else "")
        history.append({"t_sim": oc["finished_sim"] - sim.sim_t0, "call": call_str, "ok": bool(oc["ok"]), "reason": reason})
    time.sleep(0.3)
    if sim.running: sim.stop()


th = threading.Thread(target=planner, daemon=True)
t0 = time.time()
sim.run(planner_thread=th)
sim.dump(out / "timeline.json")
ev_report = mgr.report() if mgr else {}
final = {"original": int(sim.scorer.last[0]), "repaired": int(sim.scorer.last[2]), "n_goals": int(sim.scorer.n_goals), "all_done": bool(sim.scorer.last[3])}
ends = [e for e in sim.events if e["type"] == "episode_end"]
summary = {"case": f"{tt}/{cn}", "events": ev_name, "thinking": thinking, "monitor": monitor, "image": use_image, "seed": seed, "final": final,
           "sim_time": round(float(sim.env.sim.data.time - sim.sim_t0), 2), "wall": round(time.time() - t0, 1),
           "realized_rtr": ends[0]["realized_rtr"] if ends else None, "n_calls": len(llm_log),
           "latency_mean": float(np.mean([c["latency"] for c in llm_log])) if llm_log else None,
           "latency_p50": float(np.median([c["latency"] for c in llm_log])) if llm_log else None,
           "event_report": ev_report, "history": history, "monitor_log": monitor_log,
           "subgoal_events": [(round(t - sim.sim_t0, 2), what) for t, what in sim.scorer.rep.events]}
json.dump(summary | {"calls": llm_log}, open(out / "episode.json", "w"), indent=1, ensure_ascii=False, default=str)
if "video" in flags and frames:
    import imageio.v2 as imageio; imageio.mimsave(out / "video.mp4", frames, fps=5)
print(f"[EP] {tt}/{cn} {tag}: final repaired {final['repaired']}/{final['n_goals']} original {final['original']} all={final['all_done']} | sim={summary['sim_time']}s calls={len(llm_log)} lat_p50={summary['latency_p50']} rtr={summary['realized_rtr']}")
for h in history: print(f"   [{h['t_sim']:6.1f}s] {h['call']:46s} {'OK ' if h['ok'] else 'FAIL'} {h['reason'][:80]}")
for m in monitor_log: print(f"   [monitor {m['t_sim']:6.1f}s] {m['skill']} -> {m['decision']} ({m['latency']:.1f}s)")
if ev_report: print("   events:", json.dumps(ev_report, ensure_ascii=False)[:400])
print("out:", out)
