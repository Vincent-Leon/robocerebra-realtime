"""E0.5 演示状态回放 oracle：对全部 40 个唯一任务，逐帧回放演示状态并运行官方监控器，
记录每个子目标首次完成帧、是否落在标注区间内、最终完成数。用于识别"成功谓词与演示/标注不一致"的任务。
输出: runs/e05/oracle_replay.csv + notes/RoboCerebra_oracle回放诊断.md
"""
import csv, time, sys, collections
import numpy as np
import rc_env as R
from scoring import RepairedScorer

stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
out_dir = R.RUNS_ROOT / "e05"; out_dir.mkdir(parents=True, exist_ok=True)
rows = []
seen = set()
for task_type, d in R.case_dirs():
    key = ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type, d.name)
    if key in seen: continue
    seen.add(key)
    case = R.load_case(key[0], d)
    t0 = time.time()
    try:
        env = R.make_env(case, use_camera_obs=False); env.reset()
    except Exception as e:
        rows.append({"task_type": key[0], "case": key[1], "error": repr(e)[:200]}); print("ENV ERROR", key, e); continue
    T = case.demo_states.shape[0]
    goal_order = [(obj, k, act, stp) for obj, acts in case.goal.items() for k, (act, stp) in enumerate(zip(acts, case.goal_steps[obj]))]
    first_done = {}
    prev = {}
    n_done = 0; all_done = False
    rep = RepairedScorer(env, case.goal); rep_first = {}; rep_prev = {}
    for t in range(0, T, stride):
        R.apply_state(env, case.demo_states[t])
        _, n_done, all_done = R.check_success(env, case.goal)
        cur = dict(env._state_progress)
        for obj in cur:
            if cur[obj] > prev.get(obj, 0):
                for k in range(prev.get(obj, 0), cur[obj]):
                    first_done[(obj, k)] = t
        prev = cur
        _, rn, _ = rep.update(); rc = rep.progress
        for obj in rc:
            if rc[obj] > rep_prev.get(obj, 0):
                for k in range(rep_prev.get(obj, 0), rc[obj]): rep_first[(obj, k)] = t
        rep_prev = rc
    # 末帧再评估一次
    R.apply_state(env, case.demo_states[T - 1]); _, n_done, all_done = R.check_success(env, case.goal)
    _, rep_done, rep_all = rep.update()
    per = []
    n_mismatch = 0
    for obj, k, act, stp in goal_order:
        fr = first_done.get((obj, k))
        rng = case.step_ranges[stp] if stp < len(case.step_ranges) else None
        ok = fr is not None and rng is not None and rng[0] - 5 <= fr <= rng[1] + 60
        if not ok: n_mismatch += 1
        rfr = rep_first.get((obj, k))
        per.append(f"{act[0]}:{obj}{'->'+act[2] if len(act)>2 else ''}@{fr}{'' if ok else '!'}/R@{rfr}{'' if rfr is not None else '!'}")
    env.close()
    row = {"task_type": key[0], "case": key[1], "scene": case.scene.split("_")[0], "n_steps": case.n_steps, "n_goals": case.n_goals,
           "demo_T": T, "oracle_done": int(n_done), "oracle_all": bool(all_done), "n_unsatisfied": case.n_goals - int(n_done),
           "n_out_of_range": n_mismatch, "repaired_done": int(rep_done), "repaired_all": bool(rep_all), "detail": " | ".join(per), "sec": round(time.time() - t0, 1), "error": ""}
    rows.append(row)
    print(f"{key[0]}/{key[1]}: original {n_done}/{case.n_goals} all={all_done} | repaired {rep_done}/{case.n_goals} all={rep_all} ({row['sec']}s)", flush=True)

fields = ["task_type", "case", "scene", "n_steps", "n_goals", "demo_T", "oracle_done", "oracle_all", "n_unsatisfied", "n_out_of_range", "repaired_done", "repaired_all", "detail", "sec", "error"]
with open(out_dir / "oracle_replay.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader()
    for r in rows: w.writerow({k: r.get(k, "") for k in fields})
ok_rows = [r for r in rows if not r.get("error")]
n_all = sum(1 for r in ok_rows if r["oracle_all"])
n_all_rep = sum(1 for r in ok_rows if r["repaired_all"]); tot_rep = sum(r["repaired_done"] for r in ok_rows)
tot_goals = sum(r["n_goals"] for r in ok_rows); tot_done = sum(r["oracle_done"] for r in ok_rows)
unsat = collections.Counter()
for r in ok_rows:
    for item in r["detail"].split(" | "):
        if item.endswith("!"):
            unsat[item.split(":")[0] + ("->" + item.split("->")[1].split("@")[0] if "->" in item else "")] += 1
lines = ["# RoboCerebra 演示状态回放 oracle 诊断（E0.5）", "",
         f"方法：对每个唯一任务，把人类演示的 MuJoCo 状态逐帧（stride={stride}）写回仿真并调用官方 `_check_success(goal)`，统计每个子目标首次被判定完成的帧，与 `task_description.txt` 的标注区间比较（容差 -5/+60 帧）。这是**成功判定器在理想执行下的上界**：演示本身都无法触发的谓词，任何策略都拿不到分。", "",
         f"- 任务数：{len(ok_rows)}（环境加载失败 {len(rows)-len(ok_rows)} 个）", f"- 整任务 oracle 成功：{n_all}/{len(ok_rows)}",
         f"- 子目标 oracle 完成：{tot_done}/{tot_goals} = {100*tot_done/max(tot_goals,1):.1f}%",
         f"- **修复版计分（R1–R5，见 exp/scoring.py）**：整任务 {n_all_rep}/{len(ok_rows)}，子目标 {tot_rep}/{tot_goals} = {100*tot_rep/max(tot_goals,1):.1f}%",
         f"- 未触发子目标按谓词/目标统计（前 15）：{unsat.most_common(15)}", "",
         "| 类型 | case | 场景 | 子步 | 子目标 | 原始完成 | 原始全部 | 修复完成 | 修复全部 | 明细（谓词:物体->目标@原始首次完成帧/R@修复版首次完成帧，! 表示未触发） |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in ok_rows:
    lines.append(f"| {r['task_type']} | {r['case']} | {r['scene']} | {r['n_steps']} | {r['n_goals']} | {r['oracle_done']} | {'✅' if r['oracle_all'] else '❌'} | {r['repaired_done']} | {'✅' if r['repaired_all'] else '❌'} | {r['detail']} |")
for r in rows:
    if r.get("error"): lines.append(f"| {r['task_type']} | {r['case']} | ERROR | | | | | | {r['error']} |")
(R.PROJECT_ROOT / "notes" / "RoboCerebra_oracle回放诊断.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote", out_dir / "oracle_replay.csv")
