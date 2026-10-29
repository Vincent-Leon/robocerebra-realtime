"""Generate docs/tasks.md: the 60 public tasks with their instruction, number of scored subgoals and the scripted reference score.
Usage: python make_task_list.py [--gt=gtplan_h20_r5a]
"""
import sys, json, glob
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
GT = opt.get("gt", "gtplan_h20_r5a")
TYPES = [("Ideal", "Ideal"), ("Memory_Execution", "Memory · Execution"), ("Memory_Exploration", "Memory · Exploration"),
         ("Mix", "Mix"), ("Observation_Mismatching", "Observation Mismatch"), ("Random_Disturbance", "Random Disturbance")]
gt = {}
for f in glob.glob(str(R.RUNS_ROOT / GT / "*" / "result.json")):
    r = json.load(open(f)); x = int(r.get("excluded", 0)); gt[r["task"]] = ((r["repaired_done"] - x) / max(r["n_goals"] - x, 1), r["n_goals"] - x)
L = ["# Public tasks (v0.1)", "", "60 tasks in 6 categories. *Subgoals*: scored subgoals (excluding those completed at the start under Observation Mismatch). "
     "*Reference*: the scripted executor following the demonstration plan, no language model.", ""]
for key, name in TYPES:
    L += [f"## {name}", "", "| Task | Instruction | Subgoals | Reference |", "|---|---|---|---|"]
    for c in range(1, 11):
        t = f"{key}/case{c}"
        case = R.load_case(key, R.BENCH_ROOT / key / f"case{c}")
        s, n = gt.get(t, (None, sum(len(v) for v in case.goal.values())))
        L.append(f"| case{c} | {case.task_line.strip().replace('|', '/')} | {n} | {'—' if s is None else f'{s:.2f}'} |")
    L.append("")
out = R.PROJECT_ROOT / "docs" / "tasks.md"; out.write_text("\n".join(L) + "\n", encoding="utf-8"); print(out)
