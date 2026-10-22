"""E0.7 从演示提取可动固定装置的操作参数：开/关抽屉与微波炉门、旋钮。
对每个 Open/Close/Turn on 子步：找到步内第一次夹爪闭合事件，记录 eef 相对目标区域站点中心的偏移、
抽屉关节的世界开启方向与行程、以及闭合期间 eef 的位移。输出 runs/e07/articulation_events.csv。"""
import sys, csv, re
import numpy as np
import rc_env as R

out_dir = R.RUNS_ROOT / "e07"; out_dir.mkdir(parents=True, exist_ok=True)
rows = []
seen = set()
for task_type, d in R.case_dirs():
    key = ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type, d.name)
    if key in seen: continue
    seen.add(key)
    case = R.load_case(key[0], d)
    steps = [(i, s, r) for i, (s, r) in enumerate(zip(case.steps, case.step_ranges)) if re.match(r"(open|close|turn on|turnon)", s.lower())]
    if not steps: continue
    env = R.make_env(case, use_camera_obs=False); env.reset()
    m = env.sim.model
    A, S = case.demo_actions, case.demo_states
    g = np.sign(A[:, 6])
    for i, s, (a, b) in steps:
        # 对应 goal 中该 task_step 的目标
        tgt = None
        for obj, acts in case.goal.items():
            for act, stp in zip(acts, case.goal_steps[obj]):
                if stp == i and act[0] in ("open", "close", "turnon"):
                    tgt = (act[0], act[1] if len(act) == 2 else act[1], obj)
        if tgt is None: continue
        verb, target, gobj = tgt
        # 目标站点/物体与关节
        if target in m.site_names:
            site_pos0 = env.sim.data.site_xpos[m.site_name2id(target)].copy()
            joints = env.object_sites_dict[target].joints if target in env.object_sites_dict else []
            parent = env.object_sites_dict[target].parent_name if target in env.object_sites_dict else None
        else:
            site_pos0 = env.sim.data.body_xpos[env.obj_body_id[target]].copy() if target in env.obj_body_id else None
            joints = list(env.get_object(target).joints or []); parent = target
        # 闭合事件
        close_events = [t for t in range(max(a, 1), b) if g[t] > 0 and g[t - 1] <= 0]
        open_events = [t for t in range(max(a, 1), b) if g[t] < 0 and g[t - 1] >= 0]
        t_close = close_events[0] if close_events else None
        t_rel = next((t for t in open_events if t_close is not None and t > t_close), b - 1)
        R.apply_state(env, S[a]); site_pos_a = env.sim.data.site_xpos[m.site_name2id(target)].copy() if target in m.site_names else site_pos0
        info = {"task": f"{key[0]}/{key[1]}", "step": i, "desc": s, "verb": verb, "target": target, "parent": parent,
                "joints": " ".join(joints), "t_close": t_close, "t_release": t_rel, "frames": b - a}
        if t_close is not None:
            obs_c = R.apply_state(env, S[t_close]); eef_c = np.array(obs_c["robot0_eef_pos"]); grip_c = obs_c["robot0_gripper_qpos"]
            obs_r = R.apply_state(env, S[min(t_rel, S.shape[0]-1)]); eef_r = np.array(obs_r["robot0_eef_pos"])
            info.update({"eef_close_minus_site": np.round(eef_c - site_pos_a, 3).tolist(), "grip_width_close": round(float(grip_c[0]-grip_c[1]), 3),
                         "eef_disp_close_to_release": np.round(eef_r - eef_c, 3).tolist()})
        for j in joints:
            jid = m.joint_name2id(j); addr = m.get_joint_qpos_addr(j)
            traj = S[a:b, 1 + addr]
            # 世界开启方向：关节所在 body 的旋转 × 局部轴
            bid = m.jnt_bodyid[jid]; Rm = env.sim.data.body_xmat[bid].reshape(3, 3); axis_w = Rm @ m.jnt_axis[jid]
            info_j = dict(info); info_j.update({"joint": j, "jnt_type": int(m.jnt_type[jid]), "axis_world": np.round(axis_w, 2).tolist(),
                                                "range": np.round(m.jnt_range[jid], 3).tolist(), "q_start": round(float(traj[0]), 3), "q_end": round(float(traj[-1]), 3),
                                                "q_min": round(float(traj.min()), 3), "q_max": round(float(traj.max()), 3)})
            rows.append(info_j)
        if not joints:
            rows.append(info)
        print(f"{key[0]}/{key[1]} step{i} {verb} {target}: t_close={t_close} {info.get('eef_close_minus_site')} grip={info.get('grip_width_close')} disp={info.get('eef_disp_close_to_release')} joints={joints}", flush=True)
    env.close()
keys = sorted({k for r in rows for k in r})
with open(out_dir / "articulation_events.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader()
    for r in rows: w.writerow({k: r.get(k, "") for k in keys})
print("wrote", out_dir / "articulation_events.csv", len(rows), "rows")
