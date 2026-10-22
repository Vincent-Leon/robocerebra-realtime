"""诊断：演示某帧区间内 eef 位置/yaw/夹爪宽度，以及某 body 前缀下的 geom 几何（把手形状）。
用法: python x_handle_diag.py task_type case t0 t1 stride [body_prefix]"""
import sys, numpy as np
import rc_env as R
import robosuite.utils.transform_utils as T
tt, cn, t0, t1, st = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
prefix = sys.argv[6] if len(sys.argv) > 6 else None
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn)
env = R.make_env(case, use_camera_obs=False); env.reset(); m = env.sim.model
print(f"[{tt}/{cn}] frames {t0}-{t1}")
for t in list(range(t0, t1, st)) + [t1]:
    obs = R.apply_state(env, case.demo_states[t]); eef = obs["robot0_eef_pos"]; q = obs["robot0_eef_quat"]
    eul = T.mat2euler(T.quat2mat(np.array(q))); g = obs["robot0_gripper_qpos"]
    print(f"  t={t:5d} eef={np.round(eef,3)} rpy={np.round(eul,2)} grip={g[0]-g[1]:.3f} act_g={case.demo_actions[t][6]:+.0f}")
if prefix:
    print(f"\n[geoms under bodies starting with '{prefix}']")
    for gid in range(m.ngeom):
        bn = m.body_id2name(m.geom_bodyid[gid]) or ""
        if bn.startswith(prefix):
            gname = m.geom_id2name(gid) or f"geom{gid}"
            print(f"  body={bn:36s} geom={gname:40s} type={int(m.geom_type[gid])} size={np.round(m.geom_size[gid],3)} pos={np.round(env.sim.data.geom_xpos[gid],3)} group={int(m.geom_group[gid])} contype={int(m.geom_contype[gid])}")
env.close()
