"""开抽屉后列出柜体与抽屉碰撞几何的世界轴对齐包围盒（物体附近），用于判断抓取路径上的障碍。
用法: python x_cabinet_aabb.py <case 类型/名称> <抽屉区域> <物体> <装置前缀>"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
(tt, cn), drawer, obj, fx = sys.argv[1].split("/"), sys.argv[2], sys.argv[3], sys.argv[4]
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
if case.init_state is not None: R.apply_state(env, case.init_state)
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.hold(15, -1.0, "settle"); ex.open_drawer(drawer); ex.hold(30, -1.0, "settle")
m = env.sim.model; d = env.sim.data; p = ex.obj_pos(obj)
print("obj", np.round(p, 3).tolist(), "zrange", np.round(ex.obj_zrange(obj), 3).tolist(), "site xmat rows", np.round(d.site_xmat[m.site_name2id(drawer)].reshape(3, 3), 2).tolist())
for g in range(m.ngeom):
    bn = m.body_id2name(m.geom_bodyid[g]) or ""
    if not bn.startswith(fx) or m.geom_contype[g] == 0: continue
    Rm = d.geom_xmat[g].reshape(3, 3); c = d.geom_xpos[g]
    if m.geom_type[g] == 6: h = np.abs(Rm) @ m.geom_size[g]
    else: h = np.full(3, m.geom_rbound[g])
    lo, hi = c - h, c + h
    if lo[0] < p[0] + 0.15 and hi[0] > p[0] - 0.15 and lo[1] < p[1] + 0.2 and hi[1] > p[1] - 0.2 and hi[2] > 0.55 and lo[2] < 0.85:
        print(f"{bn:28s} {m.geom_id2name(g) or g!s:22s} type={int(m.geom_type[g])} x[{lo[0]:.3f},{hi[0]:.3f}] y[{lo[1]:.3f},{hi[1]:.3f}] z[{lo[2]:.3f},{hi[2]:.3f}]")
env.close()
