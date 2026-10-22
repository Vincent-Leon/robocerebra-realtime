"""打印物体与夹爪指垫的碰撞几何、摩擦、condim，以及物体质量。用法: python x_bowl_geoms.py <case 类型/名称> <物体>"""
import sys
import numpy as np
import rc_env as R
tt, cn = sys.argv[1].split("/"); obj = sys.argv[2]
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
m = env.sim.model; bid = env.obj_body_id[obj]
print("mass", round(float(m.body_mass[bid]), 3), "subtree", round(float(m.body_subtreemass[bid]), 3), "body pos", np.round(env.sim.data.body_xpos[bid], 3).tolist())
for g in range(m.ngeom):
    nm = m.geom_id2name(g) or ""
    if m.geom_bodyid[g] == bid or "pad" in nm or "finger" in nm:
        if m.geom_contype[g] == 0 and m.geom_conaffinity[g] == 0: continue
        print(f"{nm or g:40s} body={m.body_id2name(m.geom_bodyid[g])} type={int(m.geom_type[g])} size={np.round(m.geom_size[g], 4).tolist()} "
              f"rbound={m.geom_rbound[g]:.3f} fric={np.round(m.geom_friction[g], 4).tolist()} condim={int(m.geom_condim[g])} "
              f"xpos_rel={np.round(env.sim.data.geom_xpos[g] - env.sim.data.body_xpos[bid], 3).tolist() if m.geom_bodyid[g] == bid else ''}")
print("opt: cone", int(m.opt.cone), "impratio", float(m.opt.impratio), "noslip", int(m.opt.noslip_iterations), "timestep", float(m.opt.timestep))
act = [m.actuator_id2name(i) for i in range(m.nu)]
for i, a in enumerate(act):
    if "gripper" in (a or ""): print("actuator", a, "ctrlrange", np.round(m.actuator_ctrlrange[i], 3).tolist(), "forcerange", np.round(m.actuator_forcerange[i], 3).tolist(), "gain", np.round(m.actuator_gainprm[i][:3], 3).tolist())
env.close()
