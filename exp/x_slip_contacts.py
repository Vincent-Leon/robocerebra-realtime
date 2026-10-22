"""逐步列出物体在滑脱前后的接触对象，并给出所在抽屉与柜体的几何关系。
用法: python x_slip_contacts.py <episode 目录> <起始步> <结束步> <物体>"""
import sys, json
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
ep_dir, s0, s1, obj = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
ep = json.load(open(f"{ep_dir}/episode.json")); tt, cn = ep["case"].split("/")
z = np.load(f"{ep_dir}/states.npz"); steps = list(z["steps"])
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal))
m = env.sim.model; d = env.sim.data
bid = env.obj_body_id[obj]
for s in range(s0, s1 + 1):
    env.sim.set_state_from_flattened(z["states"][steps.index(s)]); env.sim.forward()
    cs = set()
    for i in range(d.ncon):
        c = d.contact[i]; b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
        if bid in (b1, b2):
            other = b2 if b1 == bid else b1
            cs.add((m.body_id2name(other) or "?") + ":" + (m.geom_id2name(c.geom2 if b1 == bid else c.geom1) or str(c.geom2 if b1 == bid else c.geom1)))
    o = env._get_observations(force_update=True)
    print(s, "obj z", round(float(o[f"{obj}_pos"][2]), 3), "eef z", round(float(o["robot0_eef_pos"][2]), 3), sorted(cs))
r = ex.containing_drawer(obj)
print("containing drawer:", r)
if r is not None:
    c, d_open, half_d, *rest = ex.drawer_geometry(r)
    print("drawer center", np.round(c, 3).tolist(), "open dir", np.round(d_open, 3).tolist(), "half depth", round(float(half_d), 3), "rest", [np.round(x, 3).tolist() if hasattr(x, "__len__") else round(float(x), 3) for x in rest])
print("obj rbound", round(float(ex.obj_rbound(obj)), 3), "zrange", [round(float(v), 3) for v in ex.obj_zrange(obj)])
env.close()
