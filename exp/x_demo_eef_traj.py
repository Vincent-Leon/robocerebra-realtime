"""探索：从演示 states 经前向运动学恢复末端位姿/夹爪/物体位姿轨迹，评估演示重定向执行器的可行性。
用法: python x_demo_eef_traj.py task_type case step_idx [stride]
"""
import sys, numpy as np
import rc_env as R
task_type, case_name, step_idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
stride = int(sys.argv[4]) if len(sys.argv) > 4 else 20
case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name)
env = R.make_env(case, use_camera_obs=False); env.reset()
a, b = case.step_ranges[step_idx]
obj = case.step_objects[step_idx] if step_idx < len(case.step_objects) else ""
obj_key = next((k for k in case.goal if obj and k.startswith(obj.replace(" ", "_"))), None)
print("[debug] step_objects =", case.step_objects)
print(f"[step {step_idx}] {case.steps[step_idx]}  frames {a}-{b}  main object={obj_key}")
print(f"{'t':>5} {'eef_pos(x,y,z)':>26} {'grip_qpos':>10} {'act_xyz':>20} {'act_rot':>20} {'act_g':>6} {'obj_pos':>26} {'obj-eef dist':>12}")
for t in list(range(a, b, stride)) + [b - 1]:
    obs = R.apply_state(env, case.demo_states[t])
    eef = obs["robot0_eef_pos"]; g = obs["robot0_gripper_qpos"]
    act = case.demo_actions[t]
    op = obs.get(f"{obj_key}_pos", np.full(3, np.nan)) if obj_key else np.full(3, np.nan)
    print(f"{t:5d} {np.array2string(eef, precision=3, floatmode='fixed'):>26} {g[0]-g[1]:10.3f} {np.array2string(np.clip(act[:3],-1,1), precision=2, floatmode='fixed'):>20} {np.array2string(np.clip(act[3:6],-1,1), precision=2, floatmode='fixed'):>20} {act[6]:6.0f} {np.array2string(op, precision=3, floatmode='fixed'):>26} {np.linalg.norm(op-eef):12.3f}")
# 场景中的区域/把手/关节信息
names = [n for n in env.sim.model.site_names if any(k in n for k in ("region", "side", "handle"))]
print("\n[sites with region/side/handle]", len(names)); print(" ", sorted(names)[:60])
jn = [n for n in env.sim.model.joint_names if not n.startswith("robot0")]
print("[non-robot joints]", jn)
print("[fixtures]", list(env.fixtures_dict.keys()), "[objects]", list(env.objects_dict.keys()))
