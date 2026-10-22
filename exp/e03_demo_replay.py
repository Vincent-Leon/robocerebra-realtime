"""E0.3 演示回放诊断：验证官方成功监控器与标注边界是否一致，并测试动作开环回放在本机的保真度。

(a) 状态回放：逐帧 set_state(demo_states[t]) 并调用 _check_success，记录每个子目标首次完成的帧，与 task_description 的 [start,end] 对比。
(b) 动作回放：从 demo_states[0] 出发，逐步 env.step(demo_actions[t])，记录子目标完成帧与最终状态偏差（跨平台数值差异诊断）。

用法: python e03_demo_replay.py [task_type] [case_name] [--video] [--stride N]
"""
import sys, json, time
import numpy as np
import imageio.v2 as imageio
import rc_env as R

args = [a for a in sys.argv[1:] if not a.startswith("--")]
task_type = args[0] if len(args) > 0 else "Ideal"
case_name = args[1] if len(args) > 1 else "case1"
want_video = "--video" in sys.argv
stride = 1
for a in sys.argv:
    if a.startswith("--stride="): stride = int(a.split("=")[1])

out_dir = R.RUNS_ROOT / "e03" / f"{task_type}_{case_name}"; out_dir.mkdir(parents=True, exist_ok=True)
fh = open(out_dir / "log.txt", "w")
case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name)
R.log(f"[case] {task_type}/{case_name}: {case.task_line}", fh)
T = case.demo_states.shape[0]
goal_order = [(obj, k, act, stp) for obj, acts in case.goal.items() for k, (act, stp) in enumerate(zip(acts, case.goal_steps[obj]))]
R.log(f"[goal] {len(goal_order)} subgoals; annotated step ranges={case.step_ranges}", fh)

env = R.make_env(case, use_camera_obs=want_video)
env.reset()

def snapshot_progress(env):
    return dict(getattr(env, "_state_progress", {}))

# ---------- (a) 状态回放 ----------
R.apply_state(env, case.demo_states[0])
env._reset_success_buffers() if hasattr(env, "_reset_success_buffers") else None
first_done_state = {}
prev = snapshot_progress(env)
t0 = time.perf_counter()
for t in range(0, T, stride):
    R.apply_state(env, case.demo_states[t])
    comp, n_done, all_done = R.check_success(env, case.goal)
    cur = snapshot_progress(env)
    for obj in cur:
        if cur[obj] > prev.get(obj, 0):
            for k in range(prev.get(obj, 0), cur[obj]):
                first_done_state[(obj, k)] = t
    prev = cur
R.log(f"[state-replay] {T} frames in {time.perf_counter()-t0:.1f}s; final done={n_done}/{case.n_goals} all={all_done}", fh)
for obj, k, act, stp in goal_order:
    fr = first_done_state.get((obj, k))
    rng = case.step_ranges[stp] if stp < len(case.step_ranges) else None
    inside = (rng is not None and fr is not None and rng[0] <= fr <= rng[1] + 2)
    R.log(f"   {obj} [{k}] {act} (task_step {stp}) first_done_frame={fr} annotated={rng} {'OK' if inside else 'MISMATCH'}", fh)

# ---------- (b) 动作回放 ----------
env.reset()
R.apply_state(env, case.demo_states[0])
env._reset_success_buffers() if hasattr(env, "_reset_success_buffers") else None
first_done_action = {}
prev = snapshot_progress(env)
frames = []
drift = []
t0 = time.perf_counter()
for t in range(T):
    a = np.clip(case.demo_actions[t], -1, 1).tolist()
    obs, _, _, _ = env.step(a)
    comp, n_done_a, all_done_a = R.check_success(env, case.goal)
    cur = snapshot_progress(env)
    for obj in cur:
        if cur[obj] > prev.get(obj, 0):
            for k in range(prev.get(obj, 0), cur[obj]):
                first_done_action[(obj, k)] = t
    prev = cur
    if t % 50 == 0 or t == T - 1:
        s_now = env.sim.get_state().flatten()
        s_ref = case.demo_states[min(t + 1, T - 1)]
        drift.append((t, float(np.abs(s_now[1:] - s_ref[1:]).max())))  # 跳过 time 维
    if want_video and t % 2 == 0:
        frames.append(R.to_image(obs["agentview_image"]))
R.log(f"[action-replay] {T} steps in {time.perf_counter()-t0:.1f}s ({T/(time.perf_counter()-t0):.1f} steps/s); final done={n_done_a}/{case.n_goals} all={all_done_a}", fh)
for obj, k, act, stp in goal_order:
    R.log(f"   {obj} [{k}] {act} first_done_frame(action)={first_done_action.get((obj,k))} vs state-replay={first_done_state.get((obj,k))}", fh)
R.log("[action-replay] state drift |sim - demo| (max abs, every 50 steps): " + ", ".join(f"t{t}:{d:.3f}" for t, d in drift), fh)
if want_video and frames:
    imageio.mimsave(out_dir / "action_replay.mp4", frames, fps=10)
    R.log(f"[video] {out_dir/'action_replay.mp4'} ({len(frames)} frames)", fh)
json.dump({"state_replay_done": n_done, "action_replay_done": int(n_done_a), "n_goals": case.n_goals,
           "first_done_state": {f"{o}|{k}": v for (o, k), v in first_done_state.items()},
           "first_done_action": {f"{o}|{k}": v for (o, k), v in first_done_action.items()},
           "drift": drift}, open(out_dir / "result.json", "w"), indent=2)
env.close()
R.log(f"[done] {out_dir}", fh)
