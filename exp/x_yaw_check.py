"""对照目标 yaw、实际 eef yaw 与两指垫连线的世界方向。用法: python x_yaw_check.py <episode 目录> <物体> <起始步> <抓取步>"""
import sys, json
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
ep_dir, obj, s_start, s_grasp = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
ep = json.load(open(f"{ep_dir}/episode.json")); tt, cn = ep["case"].split("/")
z = np.load(f"{ep_dir}/states.npz"); steps = list(z["steps"])
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal))
m = env.sim.model; d = env.sim.data
g1, g2 = m.geom_name2id("gripper0_finger1_pad_collision"), m.geom_name2id("gripper0_finger2_pad_collision")
def show(s):
    env.sim.set_state_from_flattened(z["states"][steps.index(s)]); env.sim.forward(); env._get_observations(force_update=True)
    cl = d.geom_xpos[g2] - d.geom_xpos[g1]
    R_ = ex.eef_rotmat()
    print(f"step {s}: eef_yaw={np.degrees(ex.eef_yaw()):.0f}deg closing(world)={np.degrees(np.arctan2(cl[1], cl[0])):.0f}deg "
          f"eef x-axis={np.degrees(np.arctan2(R_[1,0], R_[0,0])):.0f}deg eef y-axis={np.degrees(np.arctan2(R_[1,1], R_[0,1])):.0f}deg q7={d.qpos[6]:.2f}")
show(s_start)
yt = ex.grasp_yaw(obj); r = ex.containing_drawer(obj)
print("drawer", r, "open dir", np.round(ex.drawer_geometry(r)[1], 3).tolist() if r else None, "target yaw", None if yt is None else round(float(np.degrees(yt)), 1),
      "grasp point - obj", np.round(ex.grasp_point(obj, 0.0 if yt is None else yt) - ex.obj_pos(obj), 3).tolist())
show(s_grasp)
env.close()
