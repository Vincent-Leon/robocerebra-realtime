"""E0.4 脚本化执行器 × Original 协议（GT 计划顺序执行）在纯抓放任务上的试运行。
用法: python e04_scripted_pickplace.py [task_type] [case] [--video]
"""
import sys, json, time
import numpy as np
import imageio.v2 as imageio
import rc_env as R
from skills import ScriptedExecutor

args = [a for a in sys.argv[1:] if not a.startswith("--")]
task_type = args[0] if args else "Ideal"; case_name = args[1] if len(args) > 1 else "case1"
want_video = "--video" in sys.argv
out_dir = R.RUNS_ROOT / "e04" / f"{task_type}_{case_name}"; out_dir.mkdir(parents=True, exist_ok=True)
fh = open(out_dir / "log.txt", "w")
case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name, load_demo=False)
R.log(f"[case] {task_type}/{case_name}: {case.task_line}", fh)
env = R.make_env(case, use_camera_obs=want_video); env.reset()
if case.init_state is not None: R.apply_state(env, case.init_state)
frames = []
def on_step(ex):
    if want_video and ex.t % 3 == 0:
        frames.append(R.to_image(ex.obs["agentview_image"]))
ex = ScriptedExecutor(env, case.goal, on_step=on_step)
# 等待物体稳定（与官方 num_steps_wait=15 一致）
ex.hold(15, -1.0, "settle")
R.log(f"[monitor] after settle: done={ex.n_done}/{case.n_goals}", fh)

# GT 计划：按 goal.json 的 task_step 顺序把子目标转为技能调用
plan = []
for obj, acts in case.goal.items():
    for k, (act, stp) in enumerate(zip(acts, case.goal_steps[obj])):
        plan.append((stp, obj, act))
plan.sort(key=lambda x: x[0])
R.log("[plan] " + " ; ".join(f"step{stp}:{act}" for stp, obj, act in plan), fh)

results = []
t_wall0 = time.time()
for stp, obj, act in plan:
    verb = act[0]
    if verb == "pick":
        res = ex.pick(obj)
    elif verb in ("in", "on"):
        res = ex.place(act[2])
    else:
        R.log(f"[skip] step{stp} {act}: 技能未实现", fh); continue
    results.append(res)
    R.log(f"[skill] step{stp} {res.name}: ok={res.ok} ({res.reason}) steps={res.steps} sim_t={env.sim.data.time:.1f}s done={res.n_done_before}->{res.n_done_after}", fh)
    if not res.ok and verb == "pick":
        R.log("[plan] pick 失败，跳过对应 place", fh)
        # 简单恢复：张开夹爪抬起
        ex.hold(5, -1.0, "recover"); ex.gripper = -1.0; ex.move_z(ex.safe_z(), -1.0, "recover")

_, n_done, all_done = R.check_success(env, case.goal)
R.log(f"[result] all_done={all_done} done={n_done}/{case.n_goals} total_steps={ex.t} sim_time={env.sim.data.time:.1f}s wall={time.time()-t_wall0:.1f}s", fh)
json.dump({"all_done": bool(all_done), "n_done": int(n_done), "n_goals": case.n_goals, "total_steps": ex.t,
           "skills": [{k: (bool(v) if isinstance(v, (bool, np.bool_)) else v) for k, v in r.__dict__.items()} for r in results],
           "steps": [s.__dict__ for s in ex.log]}, open(out_dir / "result.json", "w"), indent=1)
if want_video and frames:
    imageio.mimsave(out_dir / "rollout.mp4", frames, fps=10); R.log(f"[video] {out_dir/'rollout.mp4'}", fh)
env.close()
