"""E0.6 从人类演示提取技能参数：每类物体的抓取偏移（闭合瞬间 eef - 物体中心）、松手时 eef 相对落点区域的高度、
以及倾倒段的手腕旋转幅度。用于给脚本化执行器提供按物体类别的参数，而不是手工猜。
用法: python e06_demo_grasp_offsets.py [task_type ...]
"""
import sys, csv, collections
import numpy as np
import rc_env as R

types = sys.argv[1:] or ["Ideal"]
out_dir = R.RUNS_ROOT / "e06"; out_dir.mkdir(parents=True, exist_ok=True)
rows = []
for task_type, d in R.case_dirs(types):
    case = R.load_case(task_type, d)
    env = R.make_env(case, use_camera_obs=False); env.reset()
    A, S = case.demo_actions, case.demo_states
    T = A.shape[0]
    g = np.sign(A[:, 6])
    objs = list(env.objects_dict.keys())
    def obs_at(t):
        return R.apply_state(env, S[t])
    def nearest_obj(obs, eef):
        best, bd = None, 1e9
        for o in objs:
            p = obs.get(f"{o}_pos")
            if p is None: continue
            dd = np.linalg.norm(np.array(p) - eef)
            if dd < bd: best, bd = o, dd
        return best, bd
    for t in range(1, T):
        if g[t] > 0 and g[t - 1] <= 0:        # 闭合事件
            obs = obs_at(t); eef = np.array(obs["robot0_eef_pos"])
            o, dist = nearest_obj(obs, eef)
            p = np.array(obs[f"{o}_pos"]); q = np.array(obs[f"{o}_quat"])
            # 20 帧后是否仍在手中（抓取成功）
            obs2 = obs_at(min(t + 40, T - 1)); eef2 = np.array(obs2["robot0_eef_pos"]); p2 = np.array(obs2[f"{o}_pos"])
            rows.append({"task": f"{task_type}/{d.name}", "event": "grasp", "t": t, "object": o, "obj_type": o.rsplit("_", 1)[0],
                         "dx": round(float(eef[0]-p[0]), 3), "dy": round(float(eef[1]-p[1]), 3), "dz": round(float(eef[2]-p[2]), 3),
                         "dist": round(float(dist), 3), "held_after40": bool(np.linalg.norm(eef2 - p2) < 0.08),
                         "eef_z": round(float(eef[2]), 3), "obj_z": round(float(p[2]), 3), "region": ""})
        if g[t] < 0 and g[t - 1] >= 0:        # 松手事件
            obs = obs_at(t); eef = np.array(obs["robot0_eef_pos"])
            o, dist = nearest_obj(obs, eef)
            obs2 = obs_at(min(t + 60, T - 1))
            regs = [r for r in env.regions if env._eval_predicate(["in", o, r])]
            reg = regs[0] if regs else "None"
            reg_z = ""
            if reg != "None" and reg in env.sim.model.site_names:
                reg_z = round(float(eef[2] - env.sim.data.site_xpos[env.sim.model.site_name2id(reg)][2]), 3)
            rows.append({"task": f"{task_type}/{d.name}", "event": "release", "t": t, "object": o, "obj_type": o.rsplit("_", 1)[0],
                         "dx": "", "dy": "", "dz": "", "dist": round(float(dist), 3), "held_after40": "",
                         "eef_z": round(float(eef[2]), 3), "obj_z": round(float(obs[f"{o}_pos"][2]), 3), "region": f"{reg} (eef-site dz={reg_z})"})
    # 倾倒：手腕旋转动作段
    rot = np.abs(np.clip(A[:, 3:6], -1, 1)).sum(axis=1)
    seg = []
    for i, (s, r) in enumerate(zip(case.steps, case.step_ranges)):
        if s.lower().startswith("pour") and r[0] is not None:
            a, b = r
            n_rot = int((rot[a:b] > 0.1).sum())
            rows.append({"task": f"{task_type}/{d.name}", "event": "pour_segment", "t": a, "object": "", "obj_type": "", "dx": "", "dy": "", "dz": "",
                         "dist": "", "held_after40": "", "eef_z": "", "obj_z": "", "region": f"'{s}' frames={b-a} rot_steps={n_rot} rot_dims_used={np.round(np.abs(np.clip(A[a:b,3:6],-1,1)).sum(axis=0),1).tolist()}"})
    env.close()
    print(f"{task_type}/{d.name}: {sum(1 for r in rows if r['task']==f'{task_type}/{d.name}')} events", flush=True)

with open(out_dir / "events.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("\n=== 按物体类别的抓取偏移（eef - 物体中心，米；仅统计 40 帧后仍在手中的抓取） ===")
by = collections.defaultdict(list)
for r in rows:
    if r["event"] == "grasp" and r["held_after40"]:
        by[r["obj_type"]].append((r["dx"], r["dy"], r["dz"]))
for k, v in sorted(by.items()):
    v = np.array(v, dtype=float)
    print(f"  {k:24s} n={len(v):2d} mean dx,dy,dz = {np.round(v.mean(0),3).tolist()}  std = {np.round(v.std(0),3).tolist()}")
print("\n=== 松手事件：落点区域与 eef 相对区域面高度 ===")
for r in rows:
    if r["event"] == "release": print(f"  {r['task']:16s} t={r['t']:5d} {r['object']:22s} {r['region']}")
print("\n=== 倾倒段 ===")
for r in rows:
    if r["event"] == "pour_segment": print(f"  {r['task']:16s} {r['region']}")
