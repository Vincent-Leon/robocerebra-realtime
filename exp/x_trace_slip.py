"""沿实时 episode 保存的逐步状态，追踪物体与末端的距离、双指接触，定位滑脱时刻。
用法: python x_trace_slip.py <episode 目录> <起始步> <结束步> <物体> [间隔]"""
import sys, json
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
ep_dir, s0, s1, obj = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
every = int(sys.argv[5]) if len(sys.argv) > 5 else 5
ep = json.load(open(f"{ep_dir}/episode.json")); tt, cn = ep["case"].split("/")
z = np.load(f"{ep_dir}/states.npz"); steps = z["steps"]
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal))
for s in range(s0, s1 + 1, every):
    i = int(np.argmin(np.abs(steps - s)))
    env.sim.set_state_from_flattened(z["states"][i]); env.sim.forward()
    o = env._get_observations(force_update=True); p, e = np.array(o[f"{obj}_pos"]), np.array(o["robot0_eef_pos"])
    print(f"step {int(steps[i])}: obj={np.round(p, 3).tolist()} eef={np.round(e, 3).tolist()} d={np.linalg.norm(p - e):.3f} in_hand={bool(ex.checker._in_hand(obj))} grip={np.round(env.sim.data.qpos[7:9], 4).tolist()}")
env.close()
