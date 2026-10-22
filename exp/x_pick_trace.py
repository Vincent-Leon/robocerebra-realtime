"""开抽屉后以指定腕部 yaw 抓取物体，逐步打印末端、物体位置、手指开度与指垫接触，用于分析抓取失败。
用法: python x_pick_trace.py <case 类型/名称> <抽屉区域> <物体> <yaw 度> [每隔几步]"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
(tt, cn), drawer, obj, yw = sys.argv[1].split("/"), sys.argv[2], sys.argv[3], float(sys.argv[4])
every = int(sys.argv[5]) if len(sys.argv) > 5 else 5
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
if case.init_state is not None: R.apply_state(env, case.init_state)
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.PICK_VERIFY_STEPS, ex.PICK_RETRY = 0, 0
ex.hold(15, -1.0, "settle"); ex.open_drawer(drawer); ex.hold(10, -1.0, "settle")
ex.grasp_yaw = lambda o: np.radians(yw)
m = env.sim.model; d = env.sim.data; bid = env.obj_body_id[obj]
pads = [m.geom_name2id(n) for n in ("gripper0_finger1_pad_collision", "gripper0_finger2_pad_collision")]
orig = ex.step
def hook(a, s, event=""):
    out = orig(a, s, event)
    if ex.t % every == 0:
        con = []
        for k in range(d.ncon):
            c = d.contact[k]
            for x, y in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
                if m.body_id2name(m.geom_bodyid[x]).startswith("gripper0") and m.geom_bodyid[y] == bid: con.append(m.geom_id2name(x).replace("gripper0_", ""))
        print(f"t{ex.t} g={a[-1]:+.0f} eef={np.round(ex.eef(), 3).tolist()} obj={np.round(ex.obj_pos(obj), 3).tolist()} fingers={np.round(d.qpos[7:9], 4).tolist()} contacts={sorted(set(con))}")
    return out
ex.step = hook
r = ex.pick(obj); print("pick:", r.ok, r.reason)
env.close()
