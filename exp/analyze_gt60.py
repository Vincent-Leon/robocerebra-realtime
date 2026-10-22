"""汇总全部 60 个任务的标准计划筛查（runs/<tag>/<类型>_<case>/result.json）：每个任务的执行器上限（扣除描述错位预先完成的子目标后）、
失败技能及原因归类，按类别汇总。用法: python analyze_gt60.py [--tag=gtplan_r4_all60]"""
import sys, json, glob, re, collections
from pathlib import Path
import rc_env as R
tag = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tag=")), "gtplan_r4_all60")
rows = []; reasons = collections.Counter(); by_type = collections.defaultdict(list)
for f in sorted(glob.glob(str(R.RUNS_ROOT / tag / "*" / "result.json"))):
    r = json.load(open(f)); tt, cn = r["task"].split("/")
    ex = int(r.get("excluded", 0)); n = r["n_goals"] - ex; d = r["repaired_done"] - ex
    fails = [s for s in r["skills"] if not s.get("ok")]
    for s in fails:
        why = re.sub(r"err=\[.*?\]", "", str(s.get("reason", ""))); why = re.sub(r"\(.*", "", why).strip()[:50]
        reasons[f"{str(s.get('name', '')).split('(')[0]}: {why}"] += 1
    rows.append((tt, cn, d, n, r["repaired_all"], [f"{s.get('name')}: {str(s.get('reason'))[:70]}" for s in fails]))
    by_type[tt].append((d, n, r["repaired_all"]))
print(f"| 类别 | 任务数 | 子目标完成 | 完成率 | 整任务成功 |\n|---|---|---|---|---|")
tot_d = tot_n = tot_s = 0
for tt, v in by_type.items():
    d = sum(x[0] for x in v); n = sum(x[1] for x in v); k = sum(x[2] for x in v); tot_d += d; tot_n += n; tot_s += k
    print(f"| {tt} | {len(v)} | {d}/{n} | {d / max(n, 1):.1%} | {k}/{len(v)} |")
print(f"| 合计 | {len(rows)} | {tot_d}/{tot_n} | {tot_d / max(tot_n, 1):.1%} | {tot_s}/{len(rows)} |\n")
print("未满分的任务：")
for tt, cn, d, n, ok, fails in rows:
    if d < n: print(f"  {tt}/{cn}: {d}/{n}  " + " | ".join(fails[:3]))
print("\n失败原因（按次数）："); [print(f"  {v:3d}  {k}") for k, v in reasons.most_common(15)]
