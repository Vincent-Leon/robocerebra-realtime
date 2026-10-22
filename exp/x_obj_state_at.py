"""读取实时 episode 保存的逐步状态，打印某步物体的位置、竖直轴倾角（物体局部 z 与世界 z 夹角）和与末端的距离。
用法: python x_obj_state_at.py <episode 目录> <物体> <步|-1 表示最后一步> [...]"""
import sys, json
import numpy as np
import rc_env as R
ep_dir, obj = sys.argv[1], sys.argv[2]; qs = [int(a) for a in sys.argv[3:]]
ep = json.load(open(f"{ep_dir}/episode.json")); tt, cn = ep["case"].split("/")
z = np.load(f"{ep_dir}/states.npz"); steps = list(z["steps"])
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset(); m = env.sim.model; d = env.sim.data; bid = env.obj_body_id[obj]
for s in qs:
    i = len(steps) - 1 if s < 0 else steps.index(s)
    env.sim.set_state_from_flattened(z["states"][i]); env.sim.forward(); o = env._get_observations(force_update=True)
    Rb = d.body_xmat[bid].reshape(3, 3); tilt = np.degrees(np.arccos(np.clip(Rb[2, 2], -1, 1)))
    print(f"step {steps[i]}: {obj} pos={np.round(o[f'{obj}_pos'], 3).tolist()} tilt={tilt:.0f}deg eef={np.round(o['robot0_eef_pos'], 3).tolist()} dist={np.linalg.norm(o[f'{obj}_pos'] - o['robot0_eef_pos']):.3f}")
env.close()
