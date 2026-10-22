"""第三轮分析（runs/<root>/，默认 llm_l20_r3）：建议注入（--slow=advice）与完整计划、仅快的对照。
  1) 每组（任务, 事件, 方法）：整任务成功（E3 要求截止前完成）、子目标完成率、用时、技能数 / 失败数、
     慢分支调用数与延迟、计划发布 / 拒绝与来自慢计划的技能占比、建议次数、快分支决策延迟与缓存命中；
  2) 建议：触发原因分布、建议延迟与长度、"下一步与建议一致"的比例（下一个快分支动作的首个参数 id 出现在建议文本中）；
  3) 实时性违规的 episode 列表（需重跑）。
用法: python analyze_r3.py [--root=llm_l20_r3] [--out=../notes/figs_r3]
"""
import sys, json, glob, collections
from pathlib import Path
import numpy as np
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root = opt.get("root", "llm_l20_r3"); out = Path(opt.get("out", str(R.PROJECT_ROOT / "notes" / "figs_r3"))); out.mkdir(parents=True, exist_ok=True)
NAME = {"fast_shared_jev": "仅快·Jev", "dual_shared_jev": "双分支·完整计划·Jev", "dual_advice_jev": "双分支·建议注入·Jev",
        "dual_advice_jev_bust": "双分支·建议注入·Jev（禁缓存）", "fast_shared_jev_bust": "仅快·Jev（禁缓存）", "dual_shared_jev_bust": "双分支·完整计划·Jev（禁缓存）"}
ORDER = ["fast_shared_jev", "fast_shared_jev_bust", "dual_shared_jev", "dual_shared_jev_bust", "dual_advice_jev", "dual_advice_jev_bust"]


def rt_check(ev):
    st = next((e for e in ev if e["type"] == "episode_start"), {"sim": 0.0})
    ticks = [e for e in ev if e["type"] == "tick" and e["sim"] - st["sim"] > 3.0]
    end = next((e for e in ev if e["type"] == "episode_end"), {})
    mx = max([t.get("lag", 0) or 0 for t in ticks] or [0]); p95 = end.get("lag_p95") or 0
    return (mx <= 0.25 and p95 <= 0.05), mx, p95


def trigger_kind(reason):
    r = (reason or "").lower()
    for k, key in (("episode start", "开局"), ("skill failed", "技能失败"), ("possible loop", "循环"), ("new message", "新消息"),
                   ("thinks the task is done", "快分支认为完成"), ("periodic", "定期"), ("precondition", "前置失败"), ("plan", "计划相关")):
        if k in r: return key
    return "其他"


def e3_margin(ep, tl, t0):
    fired = [e for e in tl if e["type"] == "event_fired"]
    if not fired: return None
    fe = fired[0]; rep = (ep.get("event_report") or {}).get(fe["eid"], {})
    try: deadline = float(rep["deadline"]) - t0
    except Exception: return None
    region = fe["params"]["region"]
    done_t = next((t for t, what in ep.get("subgoal_events", []) if region in str(what) and "'in'" in str(what)), None)
    return None if done_t is None else round(deadline - done_t, 2)


G = collections.defaultdict(list); advice_rows = collections.defaultdict(list); bad = []; versions = collections.Counter()
for f in sorted(glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "episode.json"))):
    ep = json.load(open(f)); tl = json.load(open(Path(f).with_name("timeline.json")))["events"]
    rs_path = Path(f).with_name("rescored.json")
    if rs_path.exists():                                   # 优先使用离线重算（当前计分器版本）的结果
        rs = json.load(open(rs_path))
        ep["final"] = {"original": rs["original"], "repaired": rs["repaired"], "n_goals": rs["n_goals"], "all_done": rs["repaired_all"]}
        ep["subgoal_events"] = rs["subgoal_events"]; versions[rs.get("scorer_version", "?")] += 1
    else:
        versions["运行时（v5）"] += 1
    ok_rt, mx, p95 = rt_check(tl)
    if not ok_rt:
        bad.append((Path(f).parent.parent.name, Path(f).parent.name, round(mx, 2), round(p95, 3))); continue
    t0 = next((e["sim"] for e in tl if e["type"] == "episode_start"), 0.0)
    mode = ep.get("thinking"); key = (ep["case"], ep["events"], mode)
    subs = [e for e in tl if e["type"] == "cmd_submitted"]
    hist = ep.get("history", [])
    calls = ep.get("calls", [])
    slow = [c for c in calls if c.get("branch") == "slow"]
    fast = [c for c in calls if c.get("branch") == "fast"]
    n_goals = ep["final"]["n_goals"]; done = ep["final"]["repaired"]
    allok = bool(ep["final"]["all_done"])
    margin = e3_margin(ep, tl, t0) if "E3" in ep["events"] else None
    if "E3" in ep["events"]: allok = allok and margin is not None and margin >= 0
    pt = sum((c.get("usage") or {}).get("prompt_tokens") or 0 for c in fast); ct = sum(c.get("cached_tokens") or 0 for c in fast)
    G[key].append({
        "seed": ep["seed"], "all": allok, "frac": done / n_goals, "sim": ep["sim_time"], "n_skills": len(subs),
        "failed": sum(1 for h in hist if not h.get("ok") and h.get("call") != "<invalid reply>"),
        "from_plan": sum(1 for e in subs if str(e.get("plan_id", "")).startswith("plan")),
        "plans_pub": sum(1 for e in tl if e["type"] == "plan_published"), "plans_rej": sum(1 for e in tl if e["type"] == "plan_rejected"),
        "advice_pub": sum(1 for e in tl if e["type"] == "advice_published"),
        "slow_n": len(slow), "slow_lat": [c["latency"] for c in slow if c.get("latency") is not None],
        "fast_lat": [c["latency"] for c in fast if c.get("latency") is not None], "fast_pt": pt, "fast_ct": ct,
        "margin": margin, "done_by": next((e.get("by") for e in tl if e["type"] == "planner_done"), None),
    })
    # 建议：触发、延迟、与下一步动作的一致性
    pubs = [e for e in tl if e["type"] == "advice_published"]
    adv_calls = [c for c in calls if c.get("mode") == "ADVISE"]
    for c in adv_calls:
        row = {"kind": trigger_kind(c.get("reason")), "lat": c.get("latency"), "tok": (c.get("usage") or {}).get("completion_tokens"),
               "err": bool(c.get("error")), "consistent": None}
        if not c.get("error") and c.get("advice"):
            # 对应的发布事件：t_obs 之后第一个 advice_published
            pe = next((e for e in pubs if e["sim"] - t0 >= c["t_obs"] - 1e-6), None)
            if pe is not None:
                nxt = next((e for e in subs if e["sim"] >= pe["sim"]), None)
                if nxt is not None:
                    sk = str(nxt.get("skill", ""))
                    arg = sk[sk.find("(") + 1:sk.rfind(")")].strip("',\" ") if "(" in sk else ""
                    row["consistent"] = bool(arg) and arg in c["advice"]
        advice_rows[(ep["case"], ep["events"], mode)].append(row)

lines = [f"# 第三轮统计（{root}；有效 {sum(len(v) for v in G.values())} 局，实时性违规 {len(bad)} 局已剔除；计分器版本："
         + "，".join(f"{k} ×{v}" for k, v in versions.items()) + "）", "",
         "| 任务 | 事件 | 方法 | n | 整任务成功 | 子目标完成率 | 用时 s | 技能数 | 失败技能 | 慢分支调用（p50 延迟） | 计划发布/拒绝（来自计划的技能） | 建议次数 | 快分支 p50 s | 快分支缓存命中 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for (task, evn, mode), rs in sorted(G.items(), key=lambda kv: (kv[0][0], kv[0][1], ORDER.index(kv[0][2]) if kv[0][2] in ORDER else 99)):
    n = len(rs); k = sum(r["all"] for r in rs); m = lambda key: np.mean([r[key] for r in rs])
    sl = [x for r in rs for x in r["slow_lat"]]; fl = [x for r in rs for x in r["fast_lat"]]
    share = sum(r["from_plan"] for r in rs) / max(sum(r["n_skills"] for r in rs), 1)
    pt = sum(r["fast_pt"] for r in rs); ct = sum(r["fast_ct"] for r in rs)
    mg = [r["margin"] for r in rs if r["margin"] is not None]
    succ = f"{k}/{n}" + (f"（余量 {np.mean(mg):.1f} s）" if "E3" in evn and mg else "")
    plan_col = f"{m('plans_pub'):.1f}/{m('plans_rej'):.1f}（{100 * share:.0f}%）" if mode.startswith("dual_shared") else "–"
    adv_col = f"{m('advice_pub'):.1f}" if mode.startswith("dual_advice") else "–"
    slow_col = f"{m('slow_n'):.1f}（{np.median(sl):.1f}）" if sl else ("0" if mode.startswith("dual") else "–")
    lines.append(f"| {task} | {evn} | {NAME.get(mode, mode)} | {n} | {succ} | {m('frac'):.2f} | {m('sim'):.1f} | {m('n_skills'):.1f} | {m('failed'):.1f} | "
                 f"{slow_col} | {plan_col} | {adv_col} | {np.median(fl) if fl else float('nan'):.2f} | {100 * ct / max(pt, 1):.0f}% |")

lines += ["", "## 建议注入：触发原因、延迟与采纳", "", "| 方法 | 触发原因 | 次数 | 延迟 p50 s | 延迟 p90 s | 输出 token p50 | 下一步与建议一致 |", "|---|---|---|---|---|---|---|"]
by_mode_kind = collections.defaultdict(list)
for (task, evn, mode), v in advice_rows.items():
    for r in v: by_mode_kind[(mode, r["kind"])].append(r)
for (mode, kind), v in sorted(by_mode_kind.items()):
    lat = [r["lat"] for r in v if r["lat"] is not None]; tok = [r["tok"] for r in v if r["tok"]]
    cons = [r["consistent"] for r in v if r["consistent"] is not None]
    lines.append(f"| {NAME.get(mode, mode)} | {kind} | {len(v)} | {np.median(lat):.2f} | {np.percentile(lat, 90):.2f} | {int(np.median(tok)) if tok else '–'} | "
                 + (f"{sum(cons)}/{len(cons)}" if cons else "–") + " |")

lines += ["", "## 结束方式（planner_done 的来源；空 = 到达时间或技能上限）", ""]
for (task, evn, mode), rs in sorted(G.items()):
    c = collections.Counter(str(r["done_by"]) for r in rs)
    lines.append(f"- {task} {evn} {NAME.get(mode, mode)}：" + "，".join(f"{k} ×{v}" for k, v in c.items()))

lines += ["", "## 实时性违规（需重跑）", ""] + ([f"- {a}/{b}：最大滞后 {c} s，p95 {d} s" for a, b, c, d in bad] or ["- 无"])
txt = "\n".join(lines) + "\n"
(out / f"r3_{root}.md").write_text(txt, encoding="utf-8"); print(txt)
