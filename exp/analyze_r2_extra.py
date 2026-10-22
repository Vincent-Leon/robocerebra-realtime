"""第二轮补充分析（runs/<root>/）：
  1) 每组（任务, 事件, 方法）：慢分支计划的发布 / 拒绝次数、计划步骤在已执行技能中的占比、无效回复、开关抽屉次数（探索）、失败技能数；
  2) 每次调用的前缀缓存命中率随提示长度（历史增长）的变化，按方法分桶；
  3) 每组每分支的调用延迟中位数与缓存命中率。
只统计满足实时性判据的 episode。用法: python analyze_r2_extra.py [--root=llm_l20_r2] [--out=../notes/figs_r2]
"""
import sys, json, glob, collections
from pathlib import Path
import numpy as np
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root = opt.get("root", "llm_l20_r2"); out = Path(opt.get("out", str(R.PROJECT_ROOT / "notes" / "figs_r2"))); out.mkdir(parents=True, exist_ok=True)


def rt_ok(ev):
    st = next((e for e in ev if e["type"] == "episode_start"), {"sim": 0.0})
    ticks = [e for e in ev if e["type"] == "tick" and e["sim"] - st["sim"] > 3.0]
    end = next((e for e in ev if e["type"] == "episode_end"), {})
    return max([t.get("lag", 0) or 0 for t in ticks] or [0]) <= 0.25 and (end.get("lag_p95") or 0) <= 0.05


G = collections.defaultdict(list); calls_by_mode = collections.defaultdict(list); n_bad = 0
for f in sorted(glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "episode.json"))):
    ep = json.load(open(f)); tl = json.load(open(Path(f).with_name("timeline.json")))["events"]
    if not rt_ok(tl): n_bad += 1; continue
    mode = ep.get("thinking"); key = (ep["case"], ep["events"], mode)
    subs = [e for e in tl if e["type"] == "cmd_submitted"]
    from_plan = sum(1 for e in subs if str(e.get("plan_id", "")).startswith("plan"))
    hist = ep.get("history", [])
    row = {
        "seed": ep["seed"], "all": bool(ep["final"]["all_done"]), "sim": ep["sim_time"],
        "n_skills": len(subs), "from_plan": from_plan,
        "plans_pub": sum(1 for e in tl if e["type"] == "plan_published"),
        "plans_rej": sum(1 for e in tl if e["type"] == "plan_rejected"),
        "invalid": sum(1 for h in hist if h.get("call") == "<invalid reply>"),
        "drawer_ops": sum(1 for h in hist if h.get("call", "").startswith(("open_drawer", "close_drawer"))),
        "failed": sum(1 for h in hist if not h.get("ok") and h.get("call") != "<invalid reply>"),
        "precond_fail": sum(1 for e in tl if e["type"] == "precondition_failed"),
        "satisfied_skip": sum(1 for e in tl if e["type"] == "plan_step_satisfied"),
    }
    G[key].append(row)
    for c in ep.get("calls", []):
        u = c.get("usage") or {}; pt = u.get("prompt_tokens"); ct = c.get("cached_tokens")
        if pt: calls_by_mode[(mode, c.get("branch"))].append((pt, ct or 0, c.get("latency")))

lines = [f"# 第二轮补充统计（{root}，剔除实时性违规 {n_bad} 个 episode）", "",
         "| 任务 | 事件 | 方法 | n | 成功 | 完成时间 s | 技能数 | 来自慢计划 | 计划发布 / 拒绝 | 前置失败 | 无效回复 | 开关抽屉 | 失败技能 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for (task, evn, mode), rs in sorted(G.items()):
    n = len(rs); k = sum(r["all"] for r in rs)
    m = lambda key: np.mean([r[key] for r in rs])
    share = sum(r["from_plan"] for r in rs) / max(sum(r["n_skills"] for r in rs), 1)
    lines.append(f"| {task} | {evn} | {mode} | {n} | {k}/{n} | {m('sim'):.1f} | {m('n_skills'):.1f} | {100*share:.0f}% | {m('plans_pub'):.1f} / {m('plans_rej'):.1f} | "
                 f"{m('precond_fail'):.1f} | {m('invalid'):.1f} | {m('drawer_ops'):.1f} | {m('failed'):.1f} |")

lines += ["", "## 调用延迟与前缀缓存（按方法与分支）", "", "| 方法 | 分支 | 调用数 | 延迟 p50 s | 延迟 p90 s | 提示 token p50 | 缓存命中 |", "|---|---|---|---|---|---|---|"]
for (mode, br), v in sorted(calls_by_mode.items()):
    pt = np.array([x[0] for x in v]); ct = np.array([x[1] for x in v]); lat = [x[2] for x in v if x[2] is not None]
    lines.append(f"| {mode} | {br} | {len(v)} | {np.median(lat):.2f} | {np.percentile(lat, 90):.2f} | {int(np.median(pt))} | {100 * ct.sum() / max(pt.sum(), 1):.0f}% |")

lines += ["", "## 缓存命中率随提示长度（历史增长）", "", "| 方法·分支 | <1500 | 1500–2500 | 2500–3500 | ≥3500 token |", "|---|---|---|---|---|"]
bins = [(0, 1500), (1500, 2500), (2500, 3500), (3500, 10 ** 9)]
for (mode, br), v in sorted(calls_by_mode.items()):
    if "bust" in str(mode): continue
    cells = []
    for lo, hi in bins:
        sel = [(p, c) for p, c, _ in v if lo <= p < hi]
        cells.append("–" if not sel else f"{100 * sum(c for _, c in sel) / sum(p for p, _ in sel):.0f}% (n={len(sel)})")
    lines.append(f"| {mode}·{br} | " + " | ".join(cells) + " |")

txt = "\n".join(lines) + "\n"
(out / f"extra_{root}.md").write_text(txt, encoding="utf-8"); print(txt)
