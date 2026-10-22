"""在演示状态序列中找到物体首次被双指夹住的时刻，打印当时的抽屉开度、物体位置、末端位置与 yaw、手指开度。
用法: python x_demo_grasp_moment.py <case 类型/名称> <物体> <抽屉区域>"""
import sys
import numpy as np
import rc_env as R
import robosuite.utils.transform_utils as T
from skills import ScriptedExecutor
(tt, cn), obj, drawer = sys.argv[1].split("/"), sys.argv[2], sys.argv[3]
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=True)
env = R.make_env(case, use_camera_obs=False); env.reset()
ex = ScriptedExecutor(env, case.goal)
S = case.demo_states; print("demo states", S.shape)
m = env.sim.model; d = env.sim.data
first = None
for i in range(0, len(S), 2):
    env.sim.set_state_from_flattened(S[i]); env.sim.forward(); o = env._get_observations(force_update=True)
    if ex.checker._in_hand(obj):
        first = i; break
if first is None: print("never grasped"); sys.exit()
for i in (max(0, first - 30), max(0, first - 10), first, first + 20):
    env.sim.set_state_from_flattened(S[i]); env.sim.forward(); o = env._get_observations(force_update=True)
    eul = T.mat2euler(T.quat2mat(np.array(o["robot0_eef_quat"])))
    print(f"i={i}: frac={ex.drawer_geometry(drawer)[5]:.2f} obj={np.round(o[f'{obj}_pos'], 3).tolist()} eef={np.round(o['robot0_eef_pos'], 3).tolist()} "
          f"eef rpy(deg)={np.round(np.degrees(eul), 0).tolist()} grip={np.round(o['robot0_gripper_qpos'], 3).tolist()} in_hand={ex.checker._in_hand(obj)}")
env.close()
