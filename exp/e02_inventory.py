"""E0.2 任务清单：解析全部 60 个 case，输出 markdown 与 csv（不启动仿真）。"""
import csv, json, collections
from pathlib import Path
import rc_env as R

out_dir = R.RUNS_ROOT / "e02"; out_dir.mkdir(parents=True, exist_ok=True)
rows = []
verb_counter = collections.Counter()
for task_type, d in R.case_dirs():
    c = R.load_case(task_type, d, load_demo=True)
    T = 0 if c.demo_actions is None else c.demo_actions.shape[0]
    durs = [b - a for (a, b) in c.step_ranges if a is not None]
    verbs = [a[0] for acts in c.goal.values() for a in acts]
    verb_counter.update(verbs)
    objs = sorted(c.goal.keys())
    rows.append({
        "task_type": task_type, "case": c.name, "scene": c.scene, "task": c.task_line,
        "n_steps": c.n_steps, "n_goals": c.n_goals, "demo_T": T,
        "demo_sim_seconds": round(T / 20.0, 1),
        "step_dur_min": min(durs) if durs else "", "step_dur_max": max(durs) if durs else "",
        "step_dur_mean": round(sum(durs) / len(durs), 1) if durs else "",
        "goal_verbs": " ".join(verbs), "goal_objects": " ".join(objs), "distractor": c.distractor or "",
        "has_init": c.init_state is not None, "bddl": c.bddl_path.name,
        "steps": " || ".join(c.steps),
    })

with open(out_dir / "inventory.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# 注意：Ideal / Observation_Mismatching / Random_Disturbance 三类共用 Ideal 目录的任务文件（官方代码如此）
uniq = {(r["task_type"] if r["task_type"] not in R.USE_IDEAL_FILES else "Ideal", r["case"]) for r in rows}
lines = ["# RoboCerebra 基准任务清单（自动生成，E0.2）", "",
         f"- 任务目录总数：{len(rows)}（6 类 × 10 case）；其中 Ideal / Observation_Mismatching / Random_Disturbance 共用 Ideal 的 10 个任务文件，故不同任务文件实际为 {len(uniq)} 个。",
         f"- 场景分布：{dict(collections.Counter(r['scene'] for r in rows))}",
         f"- goal.json 谓词分布（全部 60 个目录）：{dict(verb_counter)}",
         f"- 每个任务子步数：min={min(r['n_steps'] for r in rows)} max={max(r['n_steps'] for r in rows)} mean={sum(r['n_steps'] for r in rows)/len(rows):.1f}",
         f"- 人类演示长度（控制步，20 Hz）：min={min(r['demo_T'] for r in rows)} max={max(r['demo_T'] for r in rows)} mean={sum(r['demo_T'] for r in rows)/len(rows):.0f}；官方评测每子步固定 150 步。",
         "", "| 类型 | case | 场景 | 任务 | 子步数 | 目标数 | 演示步数 | 子步时长 min/mean/max | 谓词 | 干扰物 |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    lines.append(f"| {r['task_type']} | {r['case']} | {r['scene'].split('_')[0]} | {r['task']} | {r['n_steps']} | {r['n_goals']} | {r['demo_T']} | {r['step_dur_min']}/{r['step_dur_mean']}/{r['step_dur_max']} | {r['goal_verbs']} | {r['distractor']} |")
lines += ["", "## 各任务的子步描述", ""]
seen = set()
for r in rows:
    key = ("Ideal" if r["task_type"] in R.USE_IDEAL_FILES else r["task_type"], r["case"])
    if key in seen: continue
    seen.add(key)
    lines.append(f"### {key[0]}/{key[1]} — {r['task']}")
    for i, s in enumerate(r["steps"].split(" || ")):
        lines.append(f"{i+1}. {s}")
    lines.append("")
(R.PROJECT_ROOT / "notes" / "RoboCerebra_任务清单.md").write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {len(rows)} rows -> {out_dir/'inventory.csv'} and notes/RoboCerebra_任务清单.md")
print("verbs:", dict(verb_counter))
