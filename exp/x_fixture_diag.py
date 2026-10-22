"""诊断固定装置：关节名/范围、站点、演示中关节行程、把手几何（用于 open/close/turnon 技能与谓词修复）。
用法: python x_fixture_diag.py task_type case"""
import sys, numpy as np
import rc_env as R
task_type, case_name = sys.argv[1], sys.argv[2]
case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name)
env = R.make_env(case, use_camera_obs=False); env.reset()
m = env.sim.model
print(f"[{task_type}/{case_name}] {case.task_line}")
print("steps:", [s for s in case.steps])
nq = m.nq
for fname, fobj in env.fixtures_dict.items():
    joints = list(getattr(fobj, "joints", []) or [])
    print(f"\n== fixture {fname} ({type(fobj).__name__}) joints={joints}")
    art = fobj.object_properties.get("articulation", {})
    print("   articulation ranges:", {k: v for k, v in art.items() if "range" in k})
    for j in joints:
        jid = m.joint_name2id(j); addr = m.get_joint_qpos_addr(j)
        rng = m.jnt_range[jid]; axis = m.jnt_axis[jid]; jtype = m.jnt_type[jid]
        traj = case.demo_states[:, 1 + addr]   # state = [time, qpos..., qvel...]
        print(f"   joint {j}: type={jtype} axis={np.round(axis,2)} range={np.round(rng,3)} demo qpos min/max={traj.min():.3f}/{traj.max():.3f} start={traj[0]:.3f} end={traj[-1]:.3f}")
    sites = [n for n in m.site_names if n.startswith(fname)]
    for sname in sites:
        sid = m.site_name2id(sname)
        print(f"   site {sname}: pos={np.round(env.sim.data.site_xpos[sid],3)} size={np.round(m.site_size[sid],3)}")
    bodies = [m.body_id2name(i) for i in range(m.nbody) if m.body_id2name(i) and m.body_id2name(i).startswith(fname)]
    print("   bodies:", bodies[:12])
    geoms = [m.geom_id2name(i) for i in range(m.ngeom) if m.geom_id2name(i) and m.geom_id2name(i).startswith(fname) and ("handle" in m.geom_id2name(i) or "knob" in m.geom_id2name(i))]
    for g in geoms[:8]:
        gid = m.geom_id2name and m.geom_name2id(g)
        print(f"   handle/knob geom {g}: pos={np.round(env.sim.data.geom_xpos[gid],3)} size={np.round(m.geom_size[gid],3)} type={m.geom_type[gid]}")
# 演示中每个子步的 eef 与把手距离最小值（判断人类是否抓把手）
env.close()
