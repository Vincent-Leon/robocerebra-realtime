"""开抽屉后打印物体的局部包围盒半尺寸、yaw、所在抽屉、抽屉开启方向与内腔范围，并试抓几种腕部 yaw。
用法: python x_obj_extent.py <case 类型/名称> <抽屉区域> <物体> [yaw 度 ...]"""
import sys
import numpy as np
import rc_env as R
import robosuite.utils.transform_utils as T
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
(tt, cn), drawer, obj = sys.argv[1].split("/"), sys.argv[2], sys.argv[3]
yaws = [float(a) for a in sys.argv[4:]]
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
def setup():
    env = R.make_env(case, use_camera_obs=False); env.reset()
    if case.init_state is not None: R.apply_state(env, case.init_state)
    ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.PICK_VERIFY_STEPS, ex.PICK_RETRY = 0, 0
    ex.hold(15, -1.0, "settle"); ex.open_drawer(drawer); ex.hold(10, -1.0, "settle")
    return env, ex
env, ex = setup(); m = env.sim.model; d = env.sim.data; bid = env.obj_body_id[obj]
Rb = d.body_xmat[bid].reshape(3, 3); pb = d.body_xpos[bid]
pts = []
for g in range(m.ngeom):
    if m.geom_bodyid[g] != bid or m.geom_contype[g] == 0: continue
    Rg = d.geom_xmat[g].reshape(3, 3); c = d.geom_xpos[g]
    if m.geom_type[g] == 6:
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1): pts.append(c + Rg @ (m.geom_size[g] * np.array([sx, sy, sz])))
    else:
        pts.append(c + m.geom_rbound[g]); pts.append(c - m.geom_rbound[g])
loc = (np.array(pts) - pb) @ Rb                                  # 物体局部坐标
print("obj", obj, "pos", np.round(pb, 3).tolist(), "local half-extent", np.round((loc.max(0) - loc.min(0)) / 2, 3).tolist(),
      "local x-axis yaw(deg)", round(float(np.degrees(np.arctan2(Rb[1, 0], Rb[0, 0]))), 1), "geom types", sorted({int(m.geom_type[g]) for g in range(m.ngeom) if m.geom_bodyid[g] == bid}))
r = ex.containing_drawer(obj); print("containing drawer", r)
if r:
    c, dd, half, *_ = ex.drawer_geometry(r); print("drawer site", np.round(c, 3).tolist(), "open dir", np.round(dd, 2).tolist(), "half depth", round(half, 3))
    yt = ex.grasp_yaw(obj); print("grasp_yaw (deg)", None if yt is None else round(float(np.degrees(yt)), 1))
env.close()
for yw in yaws:
    env, ex = setup()
    ex.grasp_yaw = (lambda o, _y=np.radians(yw): _y)
    rr = ex.pick(obj)
    print(f"yaw {yw:.0f}: ok={rr.ok} ({rr.reason[:70]}) eef_yaw={np.degrees(ex.eef_yaw()):.0f}")
    env.close()
