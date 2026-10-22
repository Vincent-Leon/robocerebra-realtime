"""复现 x_pick_robust.py 的第 i 次试验，在抓取失败时打印夹爪接触的柜体几何、物体与抽屉几何。
用法: python x_pick_diag.py <case 类型/名称> <抽屉区域> <物体> <试验编号>"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
(tt, cn), drawer, obj, i = sys.argv[1].split("/"), sys.argv[2], sys.argv[3], int(sys.argv[4])
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
rng = np.random.default_rng(1000 + i)
env = R.make_env(case, use_camera_obs=False); env.reset()
if case.init_state is not None: R.apply_state(env, case.init_state)
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.PICK_VERIFY_STEPS, ex.PICK_RETRY = 0, 0
ex.hold(15, -1.0, "settle"); ex.open_drawer(drawer)
if i > 0:
    tgt = ex.HOME + np.array([*rng.uniform(-0.08, 0.08, 2), rng.uniform(-0.04, 0.04)])
    ex.move_to(tgt, -1.0, "perturb", 0.015, 60); ex.rotate_yaw_to(float(rng.uniform(-1.3, 1.3)), -1.0, "perturb")
    ex.hold(int(rng.integers(0, 10)), -1.0, "perturb")
m = env.sim.model; d = env.sim.data
c, dd, half_d, *_ = ex.drawer_geometry(drawer)
p0 = ex.obj_pos(obj); yt = ex.grasp_yaw(obj); gp0 = ex.grasp_point(obj, yt)
print("drawer site", np.round(c, 3).tolist(), "open dir", np.round(dd, 2).tolist(), "half depth", round(half_d, 3), "site size", np.round(ex.site_size(drawer), 3).tolist())
print("bowl before", np.round(p0, 3).tolist(), "gp", np.round(gp0, 3).tolist(), "front edge of drawer site (y)", round(float(c[1] + half_d), 3))
trace = []
orig_step = ex.step
def step_hook(action, skill, event=""):
    out = orig_step(action, skill, event)
    if ex.t % 5 == 0: trace.append((ex.t, np.round(ex.eef(), 3).tolist(), np.round(ex.obj_pos(obj), 3).tolist()))
    return out
ex.step = step_hook
r = ex.pick(obj)
print("pick:", r.ok, r.reason)
for t, e, o in trace[-14:]: print("  t", t, "eef", e, "bowl", o)
for k in range(d.ncon):
    cc = d.contact[k]
    for a, b in ((cc.geom1, cc.geom2), (cc.geom2, cc.geom1)):
        na = m.body_id2name(m.geom_bodyid[a]) or ""; nb = m.body_id2name(m.geom_bodyid[b]) or ""
        if na.startswith(("gripper0", "robot0")) and not nb.startswith(("gripper0", "robot0")):
            print("  contact", m.geom_id2name(a), "<->", nb, m.geom_id2name(b) or b, "at", np.round(cc.pos, 3).tolist(),
                  "geom center", np.round(d.geom_xpos[b], 3).tolist(), "size", np.round(m.geom_size[b], 3).tolist())
env.close()
