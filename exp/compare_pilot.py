"""试点对比：同一批任务上，新运行（如 r5a 试点）与 r4 排行榜的逐任务比较。
r4 每个任务 × 模式有 3 批，取均值；新运行按"模式 × 开关"分组（开关 = 失败屏蔽、完成核实方式）。
"提前完成"只计宣布完成时得分低于标准计划（--gt，默认 gtplan_r4_final）的局：剩下的步骤执行器还做得到。
用法: python compare_pilot.py [--new=llm_l20_r5a_pilot] [--old=llm_l20_r4lb] [--gt=gtplan_r4_final]
"""
import sys, json, glob, collections
from pathlib import Path
import numpy as np
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
NEW, OLD = opt.get("new", "llm_l20_r5a_pilot"), opt.get("old", "llm_l20_r4lb")
GT = {}
for _f in glob.glob(str(R.RUNS_ROOT / opt.get("gt", "gtplan_r4_final") / "*" / "result.json")):
    _r = json.load(open(_f)); _x = int(_r.get("excluded", 0)); GT[_r["task"]] = (_r["repaired_done"] - _x) / max(_r["n_goals"] - _x, 1)
NAME = {"fast_shared_text": "仅快·文本", "fast_shared_jev": "仅快·Jev", "fast_shared_think": "仅慢", "dual_shared_jev": "双分支·完整计划", "dual_advice_jev": "双分支·建议注入"}


def load(root):
    out = collections.defaultdict(list)
    for f in glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "episode.json")):
        ep = json.load(open(f)); tl = json.load(open(Path(f).with_name("timeline.json")))["events"]
        fin = ep["final"]; exc = int(fin.get("excluded", 0)); hist = ep.get("history", [])
        types = {e["type"] for e in tl}
        end = next((k for k in ("all_done", "planner_done", "abort") if k in types), "max_skills" if sum(1 for h in hist if not str(h.get("call", "")).startswith("<")) >= 40 else "max_sim")
        seen, rep = set(), 0
        for h in hist:
            if h.get("ok") or str(h.get("call", "")).startswith("<"): continue
            rep += h["call"] in seen; seen.add(h["call"])
        var = ("屏蔽" if ep.get("fail_block") else "") + {"think": "+核实·开思考", "fast": "+核实"}.get(ep.get("done_verify", "off"), "")
        out[(ep["case"], ep["thinking"], var)].append({
            "score": (fin["repaired"] - exc) / max(fin["n_goals"] - exc, 1), "success": bool(fin["all_done"]), "time": ep["sim_time"],
            "failed": sum(1 for h in hist if not h.get("ok") and not str(h.get("call", "")).startswith("<")), "repeat": rep,
            "waits": sum(1 for h in hist if str(h.get("call", "")).startswith("wait")), "end": end,
            "premature": end == "planner_done" and not fin["all_done"] and (fin["repaired"] - exc) / max(fin["n_goals"] - exc, 1) < GT.get(ep["case"], 1.0) - 1e-9, "n_verify": int(ep.get("n_verify") or 0), "n_blocked": int(ep.get("n_blocked") or 0)})
    return out


new, old = load(NEW), load(OLD)
tasks = sorted({k[0] for k in new})
print(f"新运行 {NEW}：{sum(len(v) for v in new.values())} 局，{len(tasks)} 个任务；对照 {OLD}（同任务、同模式，3 批均值）\n")
groups = sorted({(k[1], k[2]) for k in new})
for mode, var in groups:
    rows = []
    for t in tasks:
        a = new.get((t, mode, var)); b = old.get((t, mode, ""))
        if not a or not b: continue
        m = lambda v, k: float(np.mean([e[k] for e in v]))
        rows.append((t, m(a, "score"), m(b, "score"), m(a, "failed"), m(b, "failed"), m(a, "repeat"), m(b, "repeat"),
                     sum(e["premature"] for e in a) / len(a), sum(e["premature"] for e in b) / len(b), m(a, "time"), m(b, "time"),
                     m(a, "n_verify"), m(a, "n_blocked"), m(a, "waits"), m(b, "waits")))
    if not rows: continue
    print(f"## {NAME.get(mode, mode)}（{var or 'r4 设置'}）  {len(rows)} 个任务")
    print(f"{'任务':30s} {'得分 新/旧':>12s} {'失败 新/旧':>12s} {'重复失败':>10s} {'提前完成':>9s} {'用时 新/旧':>12s} 核实 屏蔽 等待")
    for r in rows:
        print(f"{r[0]:30s} {r[1]:5.2f} / {r[2]:4.2f} {r[3]:5.1f} / {r[4]:4.1f} {r[5]:4.1f} / {r[6]:4.1f} {r[7]:3.0%} / {r[8]:3.0%} {r[9]:5.0f} / {r[10]:4.0f}s {r[11]:4.1f} {r[12]:4.1f} {r[13]:4.1f}/{r[14]:.1f}")
    A = np.array([r[1:] for r in rows])
    d = A[:, 0] - A[:, 1]
    print(f"{'合计（均值）':28s} {A[:, 0].mean():5.3f} / {A[:, 1].mean():5.3f}（差 {d.mean():+.3f}，更好 {int((d > 1e-9).sum())} / 相同 {int((abs(d) <= 1e-9).sum())} / 更差 {int((d < -1e-9).sum())}）"
          f"  失败 {A[:, 2].mean():.1f} / {A[:, 3].mean():.1f}  重复失败 {A[:, 4].mean():.1f} / {A[:, 5].mean():.1f}  提前完成 {A[:, 6].mean():.0%} / {A[:, 7].mean():.0%}  用时 {A[:, 8].mean():.0f} / {A[:, 9].mean():.0f} s\n")
