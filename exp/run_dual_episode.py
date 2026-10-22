"""同模型快慢双分支 × 实时异步环境 × 可选事件。
用法: python run_dual_episode.py Ideal/case6 [--events=...] [--fast_fallback=on|off] [--semantic_check=on|off] [--monitor=on|off]
                                 [--image=on|off] [--max_sim=240] [--max_skills=30] [--video] [--tag=NAME] [--seed=0]
"""
import sys, time, threading, json
import numpy as np
import rc_env as R
from realtime_env import RealtimeSim
from llm_client import LLMClient
from llm_planner import SYSTEM, scene_text, parse_action, validate_action, to_executor_call
from dual_planner import PLAN_SYSTEM, CHECK_SYSTEM, Plan, parse_plan, call_str, precondition_ok
from events import EventManager, load_specs

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
flags = {a[2:] for a in sys.argv[1:] if a.startswith("--") and "=" not in a}
tt, cn = (args[0] if args else "Ideal/case6").split("/")
fast_fallback = opt.get("fast_fallback", "on") == "on"; semantic_check = opt.get("semantic_check", "on") == "on"
monitor = opt.get("monitor", "on") == "on"; use_image = opt.get("image", "on") == "on"
max_sim = float(opt.get("max_sim", 240)); max_skills = int(opt.get("max_skills", 30)); seed = int(opt.get("seed", 0))
ev_path = opt.get("events"); ev_name = ev_path.split("/")[-1].replace(".json", "") if ev_path else "noevent"
tag = opt.get("tag", f"{ev_name}_dual{'_ff' if fast_fallback else ''}{'_sc' if semantic_check else ''}{'_mon' if monitor else ''}_s{seed}")
import os as _os
out = R.RUNS_ROOT / _os.environ.get("RUNS_SUBDIR", "llm") / f"{tt}_{cn}" / tag; out.mkdir(parents=True, exist_ok=True)
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
sim = RealtimeSim(case, rtr=1.0, camera=True, max_sim_time=max_sim)
frames = []
def grab(s):
    snap = s.latest()
    if "video" in flags and snap is not None and snap.agentview is not None and snap.step % 4 == 0: frames.append(snap.agentview)
sim.on_tick = grab
mgr = None
if ev_path: mgr = EventManager(load_specs(ev_path)); mgr.attach(sim)
slow_client, fast_client = LLMClient(), LLMClient()
slow_client.seed = seed; fast_client.seed = seed + 1000
for _c in (slow_client, fast_client):                    # 开局前预热连接，避免首个请求与仿真主线程争用 GIL
    _c.chat(_c.build_messages(None, "ok"), max_tokens=1, thinking=False); _c.log.clear()

lock = threading.Lock()
st = {"plan": None, "cursor": 0, "seq": 0, "replan_reason": None, "executed": [], "done": False, "slow_busy": False}
replan_evt = threading.Event()
history, calls_log = [], []


def rel(t): return t - sim.sim_t0


def request_replan(reason):
    with lock:
        st["replan_reason"] = reason
    replan_evt.set(); sim.log_event("replan_requested", reason=reason[:120])


def ctx():
    env = sim.env
    import llm_planner as LP
    regions = list(env.regions)
    LP.DRAWER_REGIONS = [r for r in regions if env.object_sites_dict.get(r) is not None and (env.object_sites_dict[r].joints or [])]
    return list(env.objects_dict.keys()), list(env.fixtures_dict.keys()), regions


def slow_thread():
    objects, fixtures, regions = ctx()
    while sim.running:
        if not replan_evt.wait(timeout=0.2): continue
        replan_evt.clear()
        with lock: reason = st["replan_reason"]; st["slow_busy"] = True
        snap = sim.latest()
        user = scene_text(snap, regions, objects, fixtures, history, case.task_line).replace(
            "Available skills (call exactly one per turn", "Available skills (plan a sequence of these calls") + f"\n\nREPLAN REASON: {reason}"
        sim.log_event("think_start", step_idx=f"slow{st['seq']}", obs_version=snap.version, branch="slow", reason=reason[:80])
        r = slow_client.chat(slow_client.build_messages(PLAN_SYSTEM, user, images=[snap.agentview] if use_image and snap.agentview is not None else None),
                             max_tokens=4096, thinking=True)
        sim.log_event("think_end", step_idx=f"slow{st['seq']}", latency=round(r.latency, 2), completion_tokens=r.usage.get("completion_tokens"), error=r.error)
        d, err = parse_plan(r.text)
        steps = []; plan_err = None
        if d is not None:
            for i_, s_ in enumerate(d["plan"]):
                if not isinstance(s_, dict): plan_err = f"step {i_+1} is not an object"; break
                e_ = validate_action(s_, objects, regions, fixtures)
                if e_ is not None: plan_err = f"step {i_+1} {call_str(s_)}: {e_}"; break
                steps.append(s_)
            if plan_err is not None:
                d = None; err = plan_err                 # 整体拒绝：不静默丢弃非法步骤
        calls_log.append({"branch": "slow", "t_obs": rel(snap.sim_time), "latency": r.latency, "usage": r.usage, "response": r.text, "error": r.error or err, "n_steps": len(steps), "reason": reason,
                          "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
        if d is None:
            with lock: st["slow_busy"] = False
            sim.log_event("plan_rejected", error=str(r.error or err)[:120])
            time.sleep(2.0)                                     # 退避，避免对服务端形成重试风暴
            request_replan(f"previous plan output invalid: {str(r.error or err)[:200]}"); continue
        with lock:
            # 对账：计划观测之后已成功执行的动作，若与新计划开头相同则跳过
            done_after = [c for (t_end, c, ok) in st["executed"] if ok and t_end > snap.sim_time]
            k = 0
            for c in done_after:
                if k < len(steps) and call_str(steps[k]) == c: k += 1
            st["seq"] += 1
            st["plan"] = Plan(st["seq"], snap.version, snap.sim_time, len(snap.messages), steps, d.get("thought", ""), r.latency)
            st["cursor"] = k; st["slow_busy"] = False
            if not steps: st["done"] = True
        sim.log_event("plan_published", plan_id=st["seq"], obs_version=snap.version, n_steps=len(steps), skipped_already_done=k, latency=round(r.latency, 2),
                      steps=[call_str(s_) for s_ in steps][:12])


def fast_next_action(snap, objects, fixtures, regions):
    plan_txt = ""
    with lock:
        p = st["plan"]
        if p is not None:
            plan_txt = "\nCURRENT PLAN from the deliberate planner (made at sim time %.1fs, may be outdated): %s" % (rel(p.sim_time), " -> ".join(call_str(s_) for s_ in p.steps[st["cursor"]:]) or "(finished)")
    user = scene_text(snap, regions, objects, fixtures, history, case.task_line) + plan_txt
    sim.log_event("think_start", step_idx=f"fast{len(calls_log)}", obs_version=snap.version, branch="fast")
    r = fast_client.chat(fast_client.build_messages(SYSTEM, user, images=[snap.agentview] if use_image and snap.agentview is not None else None), max_tokens=256, thinking=False)
    sim.log_event("think_end", step_idx=f"fast{len(calls_log)}", latency=round(r.latency, 2))
    act, perr = parse_action(r.text)
    verr = validate_action(act, objects, regions, fixtures) if act else None
    calls_log.append({"branch": "fast", "t_obs": rel(snap.sim_time), "latency": r.latency, "usage": r.usage, "response": r.text, "error": r.error or perr or verr,
                      "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
    return (None if (act is None or verr) else act), r


def fast_check_step(snap, step):
    msgs_txt = "\n".join(f"  [{m['t']:.1f}s] {m['text']}" for m in snap.messages[-4:])
    user = (f"TASK: {case.task_line}\nObject in hand: {snap.held or 'none'}\nNEXT PLANNED STEP: {call_str(step)}\n"
            f"Recent executed: " + "; ".join(f"{h['call']}->{'OK' if h['ok'] else 'FAIL'}" for h in history[-4:]) + f"\nNEW MESSAGES:\n{msgs_txt}")
    sim.log_event("think_start", step_idx=f"chk{len(calls_log)}", obs_version=snap.version, branch="monitor")
    r = fast_client.chat(fast_client.build_messages(CHECK_SYSTEM, user), max_tokens=80, thinking=False)
    sim.log_event("think_end", step_idx=f"chk{len(calls_log)}", latency=round(r.latency, 2))
    dec = "execute"
    try:
        dd = json.loads(r.text[r.text.index("{"):r.text.rindex("}") + 1]); dec = str(dd.get("decision", "execute")).lower()
    except Exception:
        pass
    calls_log.append({"branch": "check", "t_obs": rel(snap.sim_time), "latency": r.latency, "response": r.text, "decision": dec, "step": call_str(step),
                      "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
    return dec


def run_skill(act, snap, objects, source):
    name, cargs = to_executor_call(act, objects)
    cs = call_str(act)
    cid = sim.submit_skill(name, *cargs, obs_version=snap.version, plan_id=source)
    seen = len(snap.messages); oc = None; t_wait = time.time()
    while time.time() - t_wait < 90:
        with sim._lock: oc = sim.outcomes.get(cid)
        if oc is not None or not sim.running: break
        cur = sim.latest()
        if cur is not None and len(cur.messages) > seen:
            seen = len(cur.messages)
            request_replan("new message: " + cur.messages[-1]["text"][:80])
            if monitor and cur.current_skill is not None:
                dec = fast_check_step(cur, act)
                if dec != "execute": sim.cancel(reason=f"fast check: {dec}", source="fast monitor")
        time.sleep(0.05)
    if oc is None:
        history.append({"t_sim": rel(sim.latest().sim_time), "call": cs, "ok": False, "reason": "timeout"}); return False
    ok = bool(oc["ok"])
    history.append({"t_sim": rel(oc["finished_sim"]), "call": cs, "ok": ok, "reason": oc["reason"][:100] + (f" (interrupted: {oc.get('cancel_source') or 'unknown'})" if oc.get("cancelled") else "")})
    with lock:
        st["executed"].append((oc["finished_sim"], cs, ok))
        # 去重：成功动作若等于当前计划的下一步（例如计划在该动作执行期间到达），推进游标
        p = st["plan"]
        if ok and source == "fast" and p is not None and st["cursor"] < len(p.steps) and call_str(p.steps[st["cursor"]]) == cs:
            st["cursor"] += 1; sim.log_event("plan_step_dedup", step=cs, plan_id=p.plan_id)
    return ok


def coordinator():
    while sim.latest() is None: time.sleep(0.05)
    objects, fixtures, regions = ctx()
    request_replan("episode start")
    n_skills = 0; checked = set(); fast_done_streak = 0
    while sim.running and n_skills < max_skills:
        with lock:
            p = st["plan"]; cur = st["cursor"]; done = st["done"]; busy = st["slow_busy"] or replan_evt.is_set()
        if done and not busy:
            sim.log_event("planner_done"); break
        snap = sim.latest()
        step = p.steps[cur] if (p is not None and cur < len(p.steps)) else None
        if step is not None:
            # 语义检查：计划之后出现了新消息
            if semantic_check and len(snap.messages) > p.n_messages and (p.plan_id, cur, len(snap.messages)) not in checked:
                checked.add((p.plan_id, cur, len(snap.messages)))
                dec = fast_check_step(snap, step)
                if dec == "skip":
                    with lock: st["cursor"] += 1
                    continue
                if dec == "wait_for_replan":
                    with lock: st["plan"] = None
                    if not busy: request_replan("plan invalidated by new message")
                    continue
            ok_pre, why = precondition_ok(step, snap, objects, regions)
            if not ok_pre:
                sim.log_event("precondition_failed", step=call_str(step), why=why)
                with lock: st["cursor"] += 1
                if not busy: request_replan(f"precondition failed for {call_str(step)}: {why}")
                continue
            ok = run_skill(step, snap, objects, f"plan{p.plan_id}")
            n_skills += 1
            with lock:
                if st["plan"] is p: st["cursor"] += 1
            if not ok and not (st["slow_busy"] or replan_evt.is_set()):
                request_replan(f"skill failed: {history[-1]['call']} ({history[-1]['reason'][:60]})")
                with lock:
                    if st["plan"] is p: st["plan"] = None
            continue
        # 没有可执行的计划步骤：快分支兜底或等待
        if p is not None and cur >= len(p.steps) and not busy:
            request_replan("plan exhausted"); continue
        if fast_fallback:
            act, r = fast_next_action(snap, objects, fixtures, regions)
            if act is None: time.sleep(0.2); continue
            if act.get("done"):
                fast_done_streak += 1
                if fast_done_streak >= 2:
                    sim.log_event("planner_done", by="fast branch (2 consecutive)"); break
                if not busy: request_replan("fast branch thinks the task is done; verify")
                time.sleep(0.5); continue
            fast_done_streak = 0
            run_skill(act, snap, objects, "fast"); n_skills += 1
        else:
            time.sleep(0.1)
    time.sleep(0.3)
    if sim.running: sim.stop()


th_slow = threading.Thread(target=slow_thread, daemon=True)
th_coord = threading.Thread(target=coordinator, daemon=True)
def start_both():
    th_slow.start(); th_coord.start()
starter = threading.Thread(target=lambda: (time.sleep(0.01), start_both()), daemon=True)
t0 = time.time()
sim.run(planner_thread=starter)
sim.dump(out / "timeline.json")
final = {"original": int(sim.scorer.last[0]), "repaired": int(sim.scorer.last[2]), "n_goals": int(sim.scorer.n_goals), "all_done": bool(sim.scorer.last[3])}
ends = [e for e in sim.events if e["type"] == "episode_end"]
summary = {"case": f"{tt}/{cn}", "events": ev_name, "thinking": "dual", "monitor": monitor, "fast_fallback": fast_fallback, "semantic_check": semantic_check,
           "image": use_image, "seed": seed, "final": final, "sim_time": round(float(sim.env.sim.data.time - sim.sim_t0), 2), "wall": round(time.time() - t0, 1),
           "realized_rtr": ends[0]["realized_rtr"] if ends else None, "n_calls": len(calls_log),
           "event_report": mgr.report() if mgr else {}, "history": history, "subgoal_events": [(round(t - sim.sim_t0, 2), w) for t, w in sim.scorer.rep.events]}
json.dump(summary | {"calls": calls_log}, open(out / "episode.json", "w"), indent=1, ensure_ascii=False, default=str)
if "video" in flags and frames:
    import imageio.v2 as imageio; imageio.mimsave(out / "video.mp4", frames, fps=5)
lat = {b: [c["latency"] for c in calls_log if c["branch"] == b] for b in ("slow", "fast", "check")}
print(f"[DUAL] {tt}/{cn} {tag}: final repaired {final['repaired']}/{final['n_goals']} original {final['original']} all={final['all_done']} | sim={summary['sim_time']}s "
      + " ".join(f"{b}:n={len(v)},p50={np.median(v):.1f}s" for b, v in lat.items() if v) + f" rtr={summary['realized_rtr']}")
for h in history: print(f"   [{h['t_sim']:6.1f}s] {h['call']:46s} {'OK ' if h['ok'] else 'FAIL'} {h['reason'][:80]}")
print("out:", out)
