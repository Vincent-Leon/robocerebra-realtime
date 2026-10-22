"""排行榜统计（参考 VISTA 的列）：runs/<root>/<类型>_<case>/<tag>/episode.json（优先用 rescored.json）。
每种模式：
  - 得分：60 个任务"有效子目标完成率"的均值，有效 = (完成 − 预先完成) / (总数 − 预先完成)，失败按实际完成计；
    多批（种子）时给"± SD"，为各批 60 任务均值之间的标准差；
  - 整任务成功率、6 类分类得分；
  - 单次决策延迟：快分支调用（仅慢模式即每步开思考的调用）中位数与 p95；双分支另列慢分支单次延迟中位数；
  - 每任务用时：episode 时长中位数（全部完成、模型宣布完成、技能次数用尽或 300 s 上限，最先到者为止）；
  - 每任务 token：非缓存输入 + 输出（与 VISTA 同口径），另给缓存输入；每任务 GPU 时间：所有模型调用延迟之和（中位数）；
  - 失败技能数（中位数）、结束原因分布；
  - 不同时间预算下的得分：每局前 B 秒内完成的子目标比例（同主表口径）；最后一列"全程"即主表得分（含 300 s 到时后正在执行的技能完成的子目标）。
参考行：标准计划（GT plan，无语言模型）在同一任务集上的完成率，即执行器上限。
输出：<out>/leaderboard_<root>.md、leaderboard_<root>.json（每模式一行）、leaderboard_<root>_episodes.json（每局一条，供 plot_leaderboard.py）。
用法: python analyze_leaderboard.py [--root=llm_l20_r4lb] [--gt=gtplan_r4_final] [--out=../notes/figs_lb] [--seeds=1,2]
  --seeds：只统计这些种子（批次），输出文件名加后缀，如 leaderboard_llm_l20_r4lb_s1.md
"""
import sys, json, glob, collections
from pathlib import Path
import numpy as np
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root = opt.get("root", "llm_l20_r4lb"); gt_tag = opt.get("gt", "gtplan_r4_final")
out = Path(opt.get("out", str(R.PROJECT_ROOT / "notes" / "figs_lb"))); out.mkdir(parents=True, exist_ok=True)
SEEDS = {int(x) for x in opt["seeds"].split(",")} if opt.get("seeds") else None
stem = f"leaderboard_{root}" + (f"_s{''.join(map(str, sorted(SEEDS)))}" if SEEDS else "")
NAME = {"fast_shared_text": "仅快·文本", "fast_shared_jev": "仅快·Jev", "fast_shared_think": "仅慢（每步开思考）",
        "dual_shared_jev": "双分支·完整计划·Jev", "dual_advice_jev": "双分支·建议注入·Jev"}
TYPES = ["Ideal", "Memory_Execution", "Memory_Exploration", "Mix", "Observation_Mismatching", "Random_Disturbance"]
ENDS = ["all_done", "planner_done", "abort", "max_skills", "max_sim"]
END_NAME = {"all_done": "全部完成", "planner_done": "宣布完成", "abort": "连续无效回复", "max_skills": "技能次数用尽", "max_sim": "时间上限"}
MAX_SKILLS = 40
BUDGETS = (30, 60, 120, 180, None)                            # None = 全程


def rt_ok(tl):
    st = next((e for e in tl if e["type"] == "episode_start"), {"sim": 0.0})
    ticks = [e for e in tl if e["type"] == "tick" and e["sim"] - st["sim"] > 3.0]
    end = next((e for e in tl if e["type"] == "episode_end"), {})
    return max([t.get("lag", 0) or 0 for t in ticks] or [0]) <= 0.25 and (end.get("lag_p95") or 0) <= 0.05


def end_reason(tl, hist):
    types = {e["type"] for e in tl}
    for k in ("all_done", "planner_done", "abort"):
        if k in types: return k
    return "max_skills" if len(hist) >= MAX_SKILLS else "max_sim"


eps = collections.defaultdict(list); bad = []; dyn = collections.defaultdict(lambda: [0, 0])
for f in sorted(glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "episode.json"))):
    p = Path(f); ep = json.load(open(f))
    if SEEDS and int(ep["seed"]) not in SEEDS: continue
    tl = json.load(open(p.with_name("timeline.json")))["events"]
    if not rt_ok(tl): bad.append(f"{p.parent.parent.name}/{p.parent.name}"); continue
    fin = ep["final"]; exc = int(fin.get("excluded", 0))
    if p.with_name("rescored.json").exists():
        rs = json.load(open(p.with_name("rescored.json"))); fin = {"repaired": rs["repaired"], "n_goals": rs["n_goals"], "all_done": rs["repaired_all"]}; exc = int(rs.get("excluded", exc))
    n = fin["n_goals"] - exc; d = fin["repaired"] - exc
    calls = ep.get("calls", []); hist = ep.get("history", [])
    fast = [c["latency"] for c in calls if c.get("branch") == "fast" and c.get("latency")]
    slow = [c["latency"] for c in calls if c.get("branch") == "slow" and c.get("latency")]
    pt = sum((c.get("usage") or {}).get("prompt_tokens") or 0 for c in calls); ct = sum(c.get("cached_tokens") or 0 for c in calls)
    ot = sum((c.get("usage") or {}).get("completion_tokens") or 0 for c in calls)
    log = ep.get("rc_dynamics") or []
    nd = sum(1 for e in log if e.get("type") == "rc_disturbance"); ns = sum(1 for e in log if e.get("type") == "rc_disturbance_skipped")
    dyn[ep["case"]][0] += nd; dyn[ep["case"]][1] += ns
    eps[ep["thinking"]].append({"mode": ep["thinking"], "task": ep["case"], "type": ep["case"].split("/")[0], "seed": ep["seed"], "score": d / max(n, 1),
                                "done": d, "n": n, "success": bool(fin["all_done"]), "time": ep["sim_time"], "fast": fast, "slow": slow,
                                "tok_nc": pt - ct + ot, "tok_cached": ct, "tok_in_nc": pt - ct, "tok_out": ot, "gpu": sum(c.get("latency") or 0 for c in calls),
                                "n_skills": len(hist), "failed": sum(1 for h in hist if not h.get("ok") and h.get("call") != "<invalid reply>"),
                                "invalid": sum(1 for h in hist if h.get("call") == "<invalid reply>"), "end": end_reason(tl, hist), "dist": nd, "dist_skipped": ns,
                                "events": [float(t) for t, _ in ep.get("subgoal_events", [])]})       # 子目标完成时刻（不含描述错位预完成的），用于时间预算得分

gt = {}
for f in glob.glob(str(R.RUNS_ROOT / gt_tag / "*" / "result.json")):
    r = json.load(open(f)); exc = int(r.get("excluded", 0)); gt[r["task"]] = ((r["repaired_done"] - exc) / max(r["n_goals"] - exc, 1), bool(r["repaired_all"]))

rows = []
for m, v in eps.items():
    seeds = sorted({e["seed"] for e in v}); ntask = {s: len({e["task"] for e in v if e["seed"] == s}) for s in seeds}
    full = [s for s in seeds if ntask[s] >= 0.95 * max(ntask.values())]      # SD 只用任务基本齐全的批次，跑到一半的批次不计
    batch = [float(np.mean([e["score"] for e in v if e["seed"] == s])) for s in full]
    f_ = np.array([x for e in v for x in e["fast"]]) if any(e["fast"] for e in v) else np.array([np.nan])
    s_ = [x for e in v for x in e["slow"]]
    rows.append({"mode": m, "name": NAME.get(m, m), "n": len(v), "tasks": len({e["task"] for e in v}), "seeds": seeds, "full_seeds": full, "ntask": ntask, "batch": batch,
                 "score": float(np.mean([e["score"] for e in v])), "sd": float(np.std(batch, ddof=1)) if len(batch) > 1 else None,
                 "succ": float(np.mean([e["success"] for e in v])),
                 "cat": {t: float(np.mean([e["score"] for e in v if e["type"] == t])) for t in TYPES if any(e["type"] == t for e in v)},
                 "fast_p50": float(np.nanmedian(f_)), "fast_p95": float(np.nanpercentile(f_, 95)), "slow_p50": float(np.median(s_)) if s_ else None,
                 "time_med": float(np.median([e["time"] for e in v])), "tok_med": float(np.median([e["tok_nc"] for e in v])),
                 "tok_cached_med": float(np.median([e["tok_cached"] for e in v])), "gpu_med": float(np.median([e["gpu"] for e in v])),
                 "tok_mean": {k: float(np.mean([e[k] for e in v])) for k in ("tok_cached", "tok_in_nc", "tok_out")},
                 "fail_med": float(np.median([e["failed"] for e in v])), "invalid_mean": float(np.mean([e["invalid"] for e in v])),
                 "ends": {k: sum(1 for e in v if e["end"] == k) for k in ENDS},
                 "budget": {str(B): float(np.mean([sum(B is None or t <= B for t in e["events"]) / max(e["n"], 1) for e in v])) for B in BUDGETS}})
rows.sort(key=lambda r: -r["score"])
gt_row = None
if gt:
    gt_row = {"score": float(np.mean([g[0] for g in gt.values()])), "succ": float(np.mean([g[1] for g in gt.values()])), "n": len(gt),
              "cat": {t: float(np.mean([g[0] for k, g in gt.items() if k.startswith(t + "/")])) for t in TYPES}}

L = [f"# 排行榜（{root}" + (f"，种子 {','.join(map(str, sorted(SEEDS)))}" if SEEDS else "") + f"；实时性违规剔除 {len(bad)} 局）", "",
     "| # | 模式 | 得分 | 整任务成功 | 单次决策 p50 / p95 | 慢分支单次 | 每任务用时 | 每任务 token（非缓存输入+输出） | 缓存输入 | 每任务 GPU 时间 | 失败技能 | 局数 |",
     "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    sc = f"{r['score']:.3f}" + (f" ± {r['sd']:.3f}" if r["sd"] is not None else "†")
    L.append(f"| {i} | {r['name']} | {sc} | {r['succ']:.0%} | {r['fast_p50']:.2f} / {r['fast_p95']:.2f} s | "
             + (f"{r['slow_p50']:.1f} s" if r["slow_p50"] is not None else "–") + f" | {r['time_med']:.0f} s | {r['tok_med'] / 1000:.1f} k | {r['tok_cached_med'] / 1000:.1f} k | {r['gpu_med']:.0f} s | {r['fail_med']:.0f} | {r['n']} |")
if gt_row:
    L.append(f"| – | 参考：标准计划（无语言模型，按演示步骤执行） | {gt_row['score']:.3f} | {gt_row['succ']:.0%} | – | – | – | – | – | – | – | {gt_row['n']} |")
L += ["", "± 为各批（种子）60 任务均值之间的标准差，只用任务齐全的批次；† 只有一批，没有标准差。每任务用时、token、GPU 时间、失败技能均为每局数值的中位数。"]
part = sorted({(s, n) for r in rows for s, n in r["ntask"].items() if s not in r["full_seeds"]})
if part: L.append("未计入标准差的不完整批次：" + "；".join(f"种子 {s}（{n} 个任务）" for s, n in part))
L += ["", "## 分类别得分", "", "| 模式 | " + " | ".join(TYPES) + " |", "|---" * (len(TYPES) + 1) + "|"]
for r in rows:
    L.append(f"| {r['name']} | " + " | ".join(f"{r['cat'].get(t, float('nan')):.3f}" for t in TYPES) + " |")
if gt_row:
    L.append("| 标准计划 | " + " | ".join(f"{gt_row['cat'][t]:.3f}" for t in TYPES) + " |")
L += ["", "## 不同时间预算下的得分", "", "每局前 B 秒内完成的子目标比例（与主表同口径），各模式取均值；\"全程\"即主表得分。", "",
      "| 模式 | " + " | ".join(f"{B} s" if B else "全程" for B in BUDGETS) + " |", "|---" * (len(BUDGETS) + 1) + "|"]
L += [f"| {r['name']} | " + " | ".join(f"{r['budget'][str(B)]:.3f}" for B in BUDGETS) + " |" for r in rows]
L += ["", "## 结束原因（局数）", "", "| 模式 | " + " | ".join(END_NAME[k] for k in ENDS) + " | 无效回复（均值） |", "|---" * (len(ENDS) + 2) + "|"]
for r in rows:
    L.append(f"| {r['name']} | " + " | ".join(str(r["ends"][k]) for k in ENDS) + f" | {r['invalid_mean']:.1f} |")
REF = "fast_shared_jev"                                       # 配对比较的基线：双分支模式所用的同一个快分支单独运行
PAIR_B = 60                                                   # 另给 60 s 时间预算下的配对比较，反映得分来得快慢
pairs = []
if REF in eps:
    rng = np.random.default_rng(0)
    sc_at = lambda e, B: e["score"] if B is None else sum(t <= B for t in e["events"]) / max(e["n"], 1)
    task_mean = lambda v, B: {t: float(np.mean([sc_at(e, B) for e in v if e["task"] == t])) for t in {e["task"] for e in v}}   # 多批时先按任务平均
    for B in (None, PAIR_B):
        ref = task_mean(eps[REF], B)
        for r in rows:
            if r["mode"] == REF: continue
            mine = task_mean(eps[r["mode"]], B); common = sorted(set(mine) & set(ref))
            if not common: continue
            dlt = np.array([mine[t] - ref[t] for t in common])
            boot = dlt[rng.integers(0, len(dlt), size=(10000, len(dlt)))].mean(axis=1)
            pairs.append({"mode": r["mode"], "name": r["name"], "budget": B, "n": len(common), "diff": float(dlt.mean()), "lo": float(np.percentile(boot, 2.5)),
                          "hi": float(np.percentile(boot, 97.5)), "win": int((dlt > 1e-9).sum()), "tie": int((np.abs(dlt) <= 1e-9).sum()), "loss": int((dlt < -1e-9).sum())})
    L += ["", f"## 与{NAME[REF]}的逐任务配对比较", "",
          f"同一任务上两种模式得分之差的均值（多批时先按任务平均）；95% 区间为按任务重抽样（bootstrap，10000 次），区间包含 0 即差异不显著。"
          f"左半为主表得分（300 s），右半为 {PAIR_B} s 时间预算下的得分。", "",
          f"| 模式 | 得分差（300 s） | 95% 区间 | 更好 / 相同 / 更差 | 得分差（{PAIR_B} s） | 95% 区间 | 更好 / 相同 / 更差 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        a = [q for q in pairs if q["mode"] == r["mode"]]
        if len(a) == 2:
            L.append(f"| {r['name']} | " + " | ".join(f"{q['diff']:+.3f} | [{q['lo']:+.3f}, {q['hi']:+.3f}] | {q['win']} / {q['tie']} / {q['loss']}" for q in a) + " |")
if dyn:
    L += ["", "## 随机扰动执行情况（各模式合计）", "", "| 任务 | 已执行 | 跳过（无合适物体或目标位置） |", "|---|---|---|"]
    L += [f"| {k} | {a} | {s} |" for k, (a, s) in sorted(dyn.items()) if a or s]
L += ["", "## 实时性违规（需重跑）", ""] + ([f"- {b}" for b in bad] or ["- 无"])
txt = "\n".join(L) + "\n"; (out / f"{stem}.md").write_text(txt, encoding="utf-8"); print(txt)
json.dump({"rows": rows, "gt": gt_row, "bad": bad, "pairs": pairs}, open(out / f"{stem}.json", "w"), ensure_ascii=False, indent=1)
json.dump([e for v in eps.values() for e in v], open(out / f"{stem}_episodes.json", "w"), ensure_ascii=False)
