"""E0.1 冒烟测试 + 仿真吞吐基准。

- 创建一个 RoboCerebra 任务环境（macOS 离屏渲染验证）
- 应用官方 init 状态，保存 agentview / eye-in-hand 图像
- 测量 env.step 的 wall-clock 吞吐（有/无相机渲染），判断 1:1 实时（20 Hz）是否可行

用法: python e01_smoke_and_speed.py [task_type] [case_name] [n_steps]
"""
import sys, time, json
from pathlib import Path
import numpy as np
import imageio.v2 as imageio

import rc_env as R

task_type = sys.argv[1] if len(sys.argv) > 1 else "Ideal"
case_name = sys.argv[2] if len(sys.argv) > 2 else "case1"
n_steps = int(sys.argv[3]) if len(sys.argv) > 3 else 200

out_dir = R.RUNS_ROOT / "e01" / f"{task_type}_{case_name}"
out_dir.mkdir(parents=True, exist_ok=True)
fh = open(out_dir / "log.txt", "w")

case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name)
R.log(f"[case] {case.task_type}/{case.name} scene={case.scene} problem={case.problem_name}", fh)
R.log(f"[task] {case.task_line}", fh)
for i, (s, r) in enumerate(zip(case.steps, case.step_ranges)):
    R.log(f"   step{i}: {s}  demo_frames={r}", fh)
R.log(f"[goal] {json.dumps(case.goal)}", fh)
R.log(f"[demo] actions={None if case.demo_actions is None else case.demo_actions.shape} states={None if case.demo_states is None else case.demo_states.shape}", fh)
R.log(f"[init] init_state={None if case.init_state is None else getattr(case.init_state, 'shape', type(case.init_state))}", fh)

t0 = time.perf_counter()
env = R.make_env(case)
R.log(f"[env] created in {time.perf_counter()-t0:.1f}s; state_dim={env.sim.get_state().flatten().shape}", fh)

t0 = time.perf_counter()
obs = env.reset()
R.log(f"[env] reset in {time.perf_counter()-t0:.2f}s; obs keys={sorted(obs.keys())}", fh)
for k, v in obs.items():
    if hasattr(v, "shape"):
        R.log(f"      {k}: {v.shape} {v.dtype}", fh)

if case.init_state is not None:
    obs = R.apply_state(env, case.init_state)
    R.log("[env] applied official init state", fh)
imageio.imwrite(out_dir / "agentview_init.png", R.to_image(obs["agentview_image"]))
imageio.imwrite(out_dir / "eye_in_hand_init.png", R.to_image(obs["robot0_eye_in_hand_image"]))
if case.demo_states is not None:
    R.apply_state(env, case.demo_states[0])
    obs2 = env._get_observations()
    imageio.imwrite(out_dir / "agentview_demo_frame0.png", R.to_image(obs2["agentview_image"]))
    R.log(f"[diag] |init_state - demo_state0| max abs diff = {np.abs(case.init_state - case.demo_states[0]).max() if case.init_state is not None else float('nan'):.4f}", fh)
    R.apply_state(env, case.init_state if case.init_state is not None else case.demo_states[0])

comp, n_done, all_done = R.check_success(env, case.goal)
R.log(f"[monitor] initial completion={comp} done={n_done}/{case.n_goals} all={all_done}", fh)

# 吞吐：零动作（保持姿态，夹爪张开 -1）
zero = [0, 0, 0, 0, 0, 0, -1]
ts = []
for i in range(n_steps):
    t0 = time.perf_counter()
    obs, r, d, info = env.step(zero)
    ts.append(time.perf_counter() - t0)
ts = np.array(ts)
R.log(f"[speed] with 2 cams @256: mean={ts.mean()*1e3:.1f} ms  p50={np.percentile(ts,50)*1e3:.1f}  p95={np.percentile(ts,95)*1e3:.1f}  -> {1/ts.mean():.1f} steps/s (need >= 20 for RTR=1; sim dt per control step = {1/env.control_freq:.3f}s)", fh)

# 吞吐：只物理不渲染（单独测 _check_success 的开销）
ts2, ts3 = [], []
for i in range(n_steps):
    t0 = time.perf_counter()
    env.sim.data.ctrl[:] = env.sim.data.ctrl[:]
    for _ in range(int(env.model_timestep / env.sim.model.opt.timestep) if hasattr(env, "model_timestep") else 1):
        pass
    t1 = time.perf_counter()
    R.check_success(env, case.goal)
    ts3.append(time.perf_counter() - t1)
ts3 = np.array(ts3)
R.log(f"[speed] _check_success alone: mean={ts3.mean()*1e3:.2f} ms", fh)

env2 = R.make_env(case, use_camera_obs=False)
env2.reset()
if case.init_state is not None:
    R.apply_state(env2, case.init_state)
for i in range(n_steps):
    t0 = time.perf_counter()
    env2.step(zero)
    ts2.append(time.perf_counter() - t0)
ts2 = np.array(ts2)
R.log(f"[speed] physics only (no cameras): mean={ts2.mean()*1e3:.1f} ms -> {1/ts2.mean():.1f} steps/s", fh)

env.close(); env2.close()
json.dump({"step_ms_with_cams": float(ts.mean()*1e3), "step_ms_p95_with_cams": float(np.percentile(ts,95)*1e3),
           "step_ms_physics_only": float(ts2.mean()*1e3), "check_success_ms": float(ts3.mean()*1e3),
           "control_freq": env.control_freq}, open(out_dir / "speed.json", "w"), indent=2)
R.log(f"[done] outputs in {out_dir}", fh)
