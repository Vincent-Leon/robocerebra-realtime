"""检查抽象开抽屉时抽屉内物体是否随抽屉平移：打印开抽屉前后物体位置与抽屉后板位置。
用法: python x_drawer_carry_check.py <case 类型/名称> <抽屉区域> <物体> <carry 0|1>"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
(tt, cn), drawer, obj, carry = sys.argv[1].split("/"), sys.argv[2], sys.argv[3], int(sys.argv[4])
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
if case.init_state is not None: R.apply_state(env, case.init_state)
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.DRAWER_CARRY = bool(carry)
ex.hold(15, -1.0, "settle")
m = env.sim.model; d = env.sim.data; g13 = m.geom_name2id("wooden_cabinet_1_g13")
def show(tag):
    print(f"{tag}: obj={np.round(ex.obj_pos(obj), 3).tolist()} back wall y={d.geom_xpos[g13][1]:.3f} in={env._eval_predicate(['in', obj, drawer])} frac={ex.drawer_geometry(drawer)[5]:.2f}")
show("before"); print("contents", ex.drawer_contents(drawer), "obj joint", env.objects_dict[obj].joints)
orig = ex.step
def hook(a, s, event=""):
    out = orig(a, s, event)
    if event == "abstract_drawer" and ex.t % 8 == 0: show(f"  t{ex.t}")
    return out
ex.step = hook
r = ex.open_drawer(drawer); show(f"after open ({r.reason})")
for k in range(4): ex.hold(25, -1.0, "wait"); show(f"after +{25 * (k + 1)} steps")
env.close()
