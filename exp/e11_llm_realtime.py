"""E1.1 真实 LLM 规划器 × 实时异步环境（顺序决策基线）。
每轮：取最新快照 → 构造提示（结构化状态 + 可选图像）→ 调用模型（思考开/关）→ 解析 JSON → 提交技能 → 等待结果。
世界在模型思考期间持续推进；所有时间戳进入 timeline.json，提示与回复进入 llm_log.json。
用法: python e11_llm_realtime.py Ideal/case6 [--thinking=on|off] [--image=on|off] [--rtr=1.0] [--max_calls=25] [--max_sim=240] [--video] [--tag=NAME]
"""
import sys, time, threading, json
import numpy as np
import rc_env as R
from realtime_env import RealtimeSim
from llm_client import LLMClient
from llm_planner import SYSTEM, scene_text, parse_action, validate_action, to_executor_call

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
flags = {a[2:] for a in sys.argv[1:] if a.startswith("--") and "=" not in a}
tt, cn = (args[0] if args else "Ideal/case6").split("/")
thinking = opt.get("thinking", "on") == "on"; use_image = opt.get("image", "on") == "on"
rtr = float(opt.get("rtr", 1.0)); max_calls = int(opt.get("max_calls", 25)); max_sim = float(opt.get("max_sim", 240))
tag = opt.get("tag", f"llm_{'think' if thinking else 'nothink'}_{'img' if use_image else 'noimg'}")
out = R.RUNS_ROOT / "e11" / f"{tt}_{cn}_{tag}"; out.mkdir(parents=True, exist_ok=True)
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
sim = RealtimeSim(case, rtr=rtr, camera=True, max_sim_time=max_sim)
client = LLMClient()
llm_log = []; history = []
frames = []
def grab(s):
    snap = s.latest()
    if "video" in flags and snap is not None and snap.agentview is not None and snap.step % 4 == 0: frames.append(snap.agentview)
sim.on_tick = grab


def planner():
    while sim.latest() is None: time.sleep(0.05)
    env = sim.env
    objects = list(env.objects_dict.keys()); fixtures = list(env.fixtures_dict.keys()); regions = list(env.regions)
    n_calls = 0; consecutive_invalid = 0
    while sim.running and n_calls < max_calls:
        snap = sim.latest()
        user = scene_text(snap, regions, objects, fixtures, history, case.task_line)
        msgs = client.build_messages(SYSTEM, user, images=[snap.agentview] if use_image and snap.agentview is not None else None)
        sim.log_event("think_start", step_idx=n_calls, obs_version=snap.version, sim_time_obs=snap.sim_time, thinking=thinking)
        r = client.chat(msgs, max_tokens=1536 if thinking else 256, thinking=thinking)
        n_calls += 1
        sim.log_event("think_end", step_idx=n_calls - 1, latency=round(r.latency, 3), ttft=None if r.ttft is None else round(r.ttft, 3),
                      completion_tokens=r.usage.get("completion_tokens"), prompt_tokens=r.usage.get("prompt_tokens"), error=r.error)
        act, perr = parse_action(r.text)
        verr = validate_action(act, objects, regions, fixtures) if act else None
        entry = {"call": n_calls, "sim_time_obs": snap.sim_time, "obs_version": snap.version, "latency": r.latency, "ttft": r.ttft,
                 "usage": r.usage, "response": r.text, "error": r.error, "parse_error": perr, "validation_error": verr, "action": act,
                 "prompt_chars": len(user)}
        llm_log.append(entry)
        if r.error or act is None or verr:
            consecutive_invalid += 1
            reason = r.error or perr or verr
            history.append({"t_sim": snap.sim_time, "call": f"<invalid reply: {str(reason)[:80]}>", "ok": False, "reason": "respond with valid JSON and exact identifiers"})
            sim.log_event("invalid_action", reason=str(reason)[:120])
            if consecutive_invalid >= 3:
                sim.log_event("abort", reason="3 consecutive invalid replies"); break
            continue
        consecutive_invalid = 0
        if act.get("done"):
            sim.log_event("planner_done", thought=act.get("thought", "")[:200]); break
        name, cargs = to_executor_call(act, objects)
        cid = sim.submit_skill(name, *cargs, obs_version=snap.version, plan_id=f"c{n_calls}")
        oc = sim.wait_outcome(cid, timeout=90)
        if oc is None:
            history.append({"t_sim": snap.sim_time, "call": f"{act['skill']}({', '.join(map(str, act['args']))})", "ok": False, "reason": "timeout"}); continue
        history.append({"t_sim": oc["finished_sim"], "call": f"{act['skill']}({', '.join(map(str, act['args']))})", "ok": bool(oc["ok"]), "reason": oc["reason"][:100]})
        if not sim.running: break
    time.sleep(0.3)
    if sim.running: sim.stop()


th = threading.Thread(target=planner, daemon=True)
t0 = time.time()
sim.run(planner_thread=th)
sim.dump(out / "timeline.json")
json.dump({"case": f"{tt}/{cn}", "thinking": thinking, "image": use_image, "rtr": rtr, "calls": llm_log, "history": history,
           "final": {"original": sim.scorer.last[0], "repaired": sim.scorer.last[2], "n_goals": case.n_goals, "all_done": bool(sim.scorer.last[3])}},
          open(out / "llm_log.json", "w"), indent=1, ensure_ascii=False, default=str)
if "video" in flags and frames:
    import imageio.v2 as imageio; imageio.mimsave(out / "video.mp4", frames, fps=5)
ends = [e for e in sim.events if e["type"] == "episode_end"]
lat = [c["latency"] for c in llm_log]; toks = [c["usage"].get("completion_tokens") or 0 for c in llm_log]
print(f"[E1.1] {tt}/{cn} thinking={thinking} image={use_image}: wall={time.time()-t0:.0f}s sim={sim.env.sim.data.time - sim.sim_t0:.1f}s "
      f"calls={len(llm_log)} latency mean/p50/max={np.mean(lat):.1f}/{np.median(lat):.1f}/{np.max(lat):.1f}s completion_tokens mean={np.mean(toks):.0f} "
      f"realized_rtr={ends[0]['realized_rtr']:.3f} | original {sim.scorer.last[0]}/{case.n_goals} repaired {sim.scorer.last[2]}/{case.n_goals} all_done={sim.scorer.last[3]}")
for h in history:
    print(f"   [{h['t_sim']:6.1f}s] {h['call']:48s} {'OK ' if h['ok'] else 'FAIL'} {h['reason'][:70]}")
print("outputs:", out)
