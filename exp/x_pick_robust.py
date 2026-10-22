"""抽屉内物体抓取的稳健性测试：开抽屉 → 随机扰动起始姿态 → 抓取（关闭确认与重抓）→ 保持 3 s，统计仍在手中的比例。
用法: python x_pick_robust.py <case 类型/名称> <抽屉区域> <物体> <次数> <fold 0|1> [verify 0|1] [抽屉边沿抓取闭合步数] [属性=0|1 ...]"""
import sys, time
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
(tt, cn), drawer, obj, N, fold = sys.argv[1].split("/"), sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
verify = int(sys.argv[6]) if len(sys.argv) > 6 else 0
rim = int(sys.argv[7]) if len(sys.argv) > 7 else None
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
kept = 0
for i in range(N):
    rng = np.random.default_rng(1000 + i); t0 = time.time()
    env = R.make_env(case, use_camera_obs=False); env.reset()
    if case.init_state is not None: R.apply_state(env, case.init_state)
    ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal))
    ex.YAW_FOLD = bool(fold)
    if rim is not None: ex.RIM_GAP_STEPS = rim
    for k, v in [a.split("=") for a in sys.argv[8:]]: setattr(ex, k, type(getattr(ex, k))(int(v)))   # 其余开关，如 DRAWER_CARRY=0
    if not verify: ex.PICK_VERIFY_STEPS, ex.PICK_RETRY = 0, 0
    ex.hold(15, -1.0, "settle")
    r0 = ex.open_drawer(drawer)
    if i > 0:                                                    # 第 0 次不扰动（与 GT 计划相同的起点）
        tgt = ex.HOME + np.array([*rng.uniform(-0.08, 0.08, 2), rng.uniform(-0.04, 0.04)])
        ex.move_z(0.71, -1.0, "perturb"); ex.move_xy(tgt[0], tgt[1], -1.0, "perturb", 0.015, 80)      # 与技能相同：先抬高、再平移、最后下降
        ex.move_z(tgt[2], -1.0, "perturb"); ex.rotate_yaw_to(float(rng.uniform(-1.3, 1.3)), -1.0, "perturb")
        ex.hold(int(rng.integers(0, 10)), -1.0, "perturb")
    yaw0 = ex.eef_yaw()
    r = ex.pick(obj)
    yaw_g = ex.eef_yaw()
    still = False
    if r.ok:
        ex.hold(60, 1.0, "hold")
        still = bool(ex.checker._in_hand(obj)) or np.linalg.norm(ex.obj_pos(obj) - ex.eef()) < 0.08
    kept += int(still)
    print(f"trial {i}: drawer_ok={r0.ok} yaw0={np.degrees(yaw0):.0f} yaw_after={np.degrees(yaw_g):.0f} pick ok={r.ok} ({r.reason[:70]}) kept_3s={still} steps={r.steps} wall={time.time() - t0:.0f}s", flush=True)
    env.close()
print(f"SUMMARY fold={fold} verify={verify} rim={ex.RIM_GAP_STEPS}: kept {kept}/{N}")
