"""倒伏物体抓取测试：把物体绕水平轴转倒（绕世界 x 或 y 轴 90°）放在原处，静置后抓取并抬起，检查是否在手中。
用法: python x_tipped_pick_test.py <case 类型/名称> <物体> [绕轴 x|y ...]"""
import sys
import numpy as np
import rc_env as R
import robosuite.utils.transform_utils as T
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
(tt, cn), obj = sys.argv[1].split("/"), sys.argv[2]
for ax in (sys.argv[3:] or ["x", "y"]):
    case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
    env = R.make_env(case, use_camera_obs=False); env.reset()
    if case.init_state is not None: R.apply_state(env, case.init_state)
    ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.hold(15, -1.0, "settle")
    m = env.sim.model; d = env.sim.data; jn = env.objects_dict[obj].joints[-1]; a0 = m.get_joint_qpos_addr(jn)[0]
    q = d.qpos[a0 + 3:a0 + 7].copy()                                         # MuJoCo 四元数 (w, x, y, z)
    rot = {"x": np.array([np.cos(np.pi / 4), np.sin(np.pi / 4), 0, 0]), "y": np.array([np.cos(np.pi / 4), 0, np.sin(np.pi / 4), 0])}[ax]
    w1, x1, y1, z1 = rot; w2, x2, y2, z2 = q
    d.qpos[a0 + 3:a0 + 7] = [w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2]
    d.qpos[a0 + 2] += 0.05; env.sim.forward(); ex.hold(40, -1.0, "settle")
    tilt = np.degrees(np.arccos(np.clip(ex.obj_rotmat(obj)[2, 2], -1, 1)))
    r = ex.pick(obj); held = r.ok and bool(ex.checker._in_hand(obj))
    if r.ok: ex.hold(40, 1.0, "hold"); held = bool(ex.checker._in_hand(obj))
    print(f"tipped about {ax}: tilt={tilt:.0f}deg tipped={ex.is_tipped(obj)} pick ok={r.ok} ({r.reason[:70]}) held after 2s={held}", flush=True)
    env.close()
