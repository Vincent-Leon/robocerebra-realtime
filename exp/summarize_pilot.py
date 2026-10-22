"""汇总 runs/<tag>/summary.json 为 pilot 子集的版本对照表（修复版子目标完成数 / 总数，✅=整任务通过）。
用法: python summarize_pilot.py tag1 tag2 ... [--md out.md]"""
import sys, json
from pathlib import Path
import rc_env as R
tags = [a for a in sys.argv[1:] if not a.startswith("--")]
md_out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--md=")), None)
tasks = ["Ideal/case1", "Ideal/case3", "Ideal/case5", "Ideal/case6", "Ideal/case8", "Memory_Exploration/case3", "Memory_Exploration/case5", "Memory_Exploration/case10", "Memory_Execution/case5"]
table = {t: {} for t in tasks}
for tag in tags:
    for f in (R.RUNS_ROOT).glob(f"{tag}*/summary.json"):
        for s in json.load(open(f)):
            if "error" in s or s["task"] not in table: continue
            table[s["task"]][tag] = s
cols = sorted({tag for t in table.values() for tag in t})
def cell(s):
    if not s: return "–"
    return f"{s['repaired_done']}/{s['n_goals']}{' ✅' if s['repaired_all'] else ''} (原 {s['original_done']})"
lines = ["| 任务 | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
tot = {c: [0, 0, 0] for c in cols}
for t in tasks:
    lines.append(f"| {t} | " + " | ".join(cell(table[t].get(c)) for c in cols) + " |")
    for c in cols:
        s = table[t].get(c)
        if s: tot[c][0] += s["repaired_done"]; tot[c][1] += s["n_goals"]; tot[c][2] += int(s["repaired_all"])
lines.append("| **合计（修复版子目标 / 整任务通过）** | " + " | ".join(f"**{tot[c][0]}/{tot[c][1]} · {tot[c][2]} 任务**" if tot[c][1] else "–" for c in cols) + " |")
out = "\n".join(lines); print(out)
if md_out: Path(md_out).write_text(out + "\n", encoding="utf-8"); print("wrote", md_out)
