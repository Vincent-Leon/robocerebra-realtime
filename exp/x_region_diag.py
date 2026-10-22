"""诊断：在演示的指定帧评估物体对各区域的 in 谓词，并打印几何信息。"""
import sys, numpy as np
import rc_env as R
task_type, case_name = sys.argv[1], sys.argv[2]
frames = [int(x) for x in sys.argv[3].split(",")]
objs = sys.argv[4].split(",")
case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name)
env = R.make_env(case, use_camera_obs=False); env.reset()
regions = [r for r in env.regions]
print("monitored regions:", regions)
for t in frames:
    R.apply_state(env, case.demo_states[t])
    print(f"\n=== frame {t} ===")
    for o in objs:
        st = env.object_states_dict[o]
        g = st.get_geom_state(); pos = g["pos"]
        ins = [r for r in regions if env._eval_predicate(["in", o, r])]
        print(f"  {o}: pos={np.round(pos,3)} in={ins}")
        for r in regions:
            if "storage_box" in r or "side" in r:
                sid = env.sim.model.site_name2id(r)
                sp = env.sim.data.site_xpos[sid]; ss = env.sim.model.site_size[sid]
                d = pos - sp
                print(f"      {r:38s} site_pos={np.round(sp,3)} size={np.round(ss,3)} d(obj-site)={np.round(d,3)} inside_xyz={[bool(abs(d[i])<=ss[i]) for i in range(3)]}")
