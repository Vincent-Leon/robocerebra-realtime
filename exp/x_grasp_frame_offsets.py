"""在物体局部坐标系中提取抓取偏移（含大物体如平底锅、盘子、碗），并给出物体包围球半径。
用法: python x_grasp_frame_offsets.py obj_substring [task_type ...]"""
import sys, numpy as np
import rc_env as R
import robosuite.utils.transform_utils as T
sub = sys.argv[1]; types = sys.argv[2:] or ["Ideal", "Memory_Exploration"]
seen = set()
for task_type, d in R.case_dirs(types):
    key = ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type, d.name)
    if key in seen: continue
    seen.add(key)
    case = R.load_case(key[0], d)
    steps = [(i, s, r) for i, (s, r) in enumerate(zip(case.steps, case.step_ranges)) if s.lower().startswith("pick") and sub in s.lower().replace(" ", "_")]
    if not steps: continue
    env = R.make_env(case, use_camera_obs=False); env.reset()
    m = env.sim.model
    objs = [o for o in env.objects_dict if sub in o]
    A, S = case.demo_actions, case.demo_states; g = np.sign(A[:, 6])
    for i, s, (a, b) in steps:
        ev = [t for t in range(max(a, 1), b) if g[t] > 0 and g[t - 1] <= 0]
        if not ev: print(f"{key[0]}/{key[1]} step{i} '{s}': no close event"); continue
        t = ev[0]
        obs = R.apply_state(env, S[t]); eef = np.array(obs["robot0_eef_pos"]); eq = np.array(obs["robot0_eef_quat"])
        for o in objs:
            p = np.array(obs[f"{o}_pos"]); q = np.array(obs[f"{o}_quat"])  # xyzw
            Rm = T.quat2mat(q); local = Rm.T @ (eef - p)
            bid = env.obj_body_id[o]
            rb = max([float(m.geom_rbound[gid]) for gid in range(m.ngeom) if m.geom_bodyid[gid] == bid] or [0])
            yaw_obj = T.mat2euler(Rm)[2]; yaw_eef = T.mat2euler(T.quat2mat(eq))[2]
            obs2 = R.apply_state(env, S[min(t + 40, S.shape[0] - 1)]); held = np.linalg.norm(np.array(obs2["robot0_eef_pos"]) - np.array(obs2[f"{o}_pos"])) < 0.25 and obs2[f"{o}_pos"][2] - p[2] > 0.03
            print(f"{key[0]}/{key[1]} step{i} t={t} {o}: world eef-obj={np.round(eef-p,3)} local={np.round(local,3)} rbound={rb:.3f} obj_yaw={yaw_obj:.2f} eef_yaw={yaw_eef:.2f} lifted_after40={held}")
    env.close()
