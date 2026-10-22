"""E1.0 实时异步环境演示：伪规划器带人工"思考"延迟，验证
(1) 思考期间仿真按 wall-clock 继续推进（RTR≈1）；(2) 技能可被中途取消；(3) 全链路时间戳可用于时间线图。
用法: python e10_realtime_demo.py [task_type/case] [--rtr=1.0] [--think=3.0] [--video]
"""
import sys, time, threading, json
import numpy as np
import rc_env as R
from realtime_env import RealtimeSim

args = [a for a in sys.argv[1:] if not a.startswith("--")]
tt, cn = (args[0] if args else "Ideal/case1").split("/")
rtr = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--rtr=")), 1.0))
think = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--think=")), 3.0))
want_video = "--video" in sys.argv
out = R.RUNS_ROOT / "e10" / f"{tt}_{cn}_rtr{rtr}_think{think}"; out.mkdir(parents=True, exist_ok=True)
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
sim = RealtimeSim(case, rtr=rtr, camera=want_video, max_sim_time=120.0)
frames = []
if want_video:
    def grab(s):
        snap = s.latest()
        if snap is not None and snap.agentview is not None and snap.step % 4 == 0: frames.append(snap.agentview)
    sim.on_tick = grab

plan = sorted([(stp, obj, act) for obj, acts in case.goal.items() for act, stp in zip(acts, case.goal_steps[obj])], key=lambda x: x[0])


def planner():
    """伪规划器：每步决策前"思考" think 秒（世界继续走）；在第 2 个技能执行中途发起一次取消再重发，演示中断语义。"""
    while sim.latest() is None: time.sleep(0.05)
    cancelled_once = False
    for i, (stp, obj, act) in enumerate(plan):
        snap = sim.latest()
        sim.log_event("think_start", step_idx=stp, obs_version=snap.version, sim_time_obs=snap.sim_time)
        time.sleep(think)                                   # 模拟慢推理（LLM 调用）
        sim.log_event("think_end", step_idx=stp)
        verb = act[0]; tgt = act[2] if len(act) > 2 else None
        if verb == "pick":
            cid = sim.submit_skill("pick", obj, obs_version=snap.version, plan_id=f"p{stp}")
        elif verb in ("in", "on"):
            cid = sim.submit_skill("place", tgt, obs_version=snap.version, plan_id=f"p{stp}")
        else:
            continue
        if i == 1 and not cancelled_once:                   # 第 2 个技能：执行 1.5 s 后取消，再"重新思考"并重发
            time.sleep(1.5); sim.cancel(reason="demo: plan invalidated mid-skill"); cancelled_once = True
            oc = sim.wait_outcome(cid, timeout=30)
            sim.log_event("think_start", step_idx=stp, obs_version=sim.latest().version, note="replan after cancel")
            time.sleep(think); sim.log_event("think_end", step_idx=stp)
            cid = sim.submit_skill("place", tgt, obs_version=sim.latest().version, plan_id=f"p{stp}b")
        oc = sim.wait_outcome(cid, timeout=60)
        if oc is None: break
    time.sleep(0.5); sim.stop()


th = threading.Thread(target=planner, daemon=True)
t_wall0 = time.time()
sim.run(planner_thread=th)
sim.dump(out / "timeline.json")
ev = sim.events
final = sim.scorer.last
print(f"[E1.0] {tt}/{cn} rtr={rtr} think={think}s: wall={time.time()-t_wall0:.1f}s sim={sim.env.sim.data.time - sim.sim_t0:.1f}s "
      f"realized_rtr={[e for e in ev if e['type']=='episode_end'][0]['realized_rtr']:.3f} "
      f"lag_p50/p95={[e for e in ev if e['type']=='episode_end'][0]['lag_p50']*1e3:.1f}/{[e for e in ev if e['type']=='episode_end'][0]['lag_p95']*1e3:.1f} ms "
      f"| original {final[0]}/{case.n_goals} repaired {final[2]}/{case.n_goals}")
for e in ev:
    if e["type"] in ("think_start", "think_end", "cmd_submitted", "skill_started", "skill_finished", "skill_cancelled", "cancel_requested", "cancel_applied", "subgoal_done", "episode_end"):
        extra = {k: v for k, v in e.items() if k not in ("type", "wall", "sim", "step")}
        print(f"   sim={e['sim']:6.2f}s step={e['step']:4d} {e['type']:16s} {json.dumps(extra, ensure_ascii=False, default=str)[:120]}")
if want_video and frames:
    import imageio.v2 as imageio; imageio.mimsave(out / "video.mp4", frames, fps=5)
print("timeline:", out / "timeline.json")
