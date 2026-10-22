"""汇总 runs/<root>/ 下所有 LLM episode，生成：
  1) 按 (任务, 事件, 方法) 分组的统计表（k/n 成功、完成时间、响应指标），写入 markdown；
  2) 图 A：E3 成功率—时间压力曲线（事件关键子目标在截止前完成的比例 vs 时间窗）；
  3) 图 B：E1 有效响应延迟点图（事件 → 首个指向新目标的命令）。
样本量小（每组 3 次），只报告 k/n 与范围，不报置信区间。
配色：dataviz 默认类别色前三/五位（validate_palette.js 已校验；低对比色配直接标签与数据表）。
用法: python aggregate_results.py [--root=llm] [--out=../notes/figs]
"""
import sys, json, collections
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "PingFang SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
sys.argv_backup = list(sys.argv); sys.argv = [sys.argv[0]]
import analyze_llm_runs as A
sys.argv = sys.argv_backup
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root = opt.get("root", "llm"); out = Path(opt.get("out", str(R.PROJECT_ROOT / "notes" / "figs"))); out.mkdir(parents=True, exist_ok=True)
rows_all = A.extract_rows("*", root=root)
for _r in rows_all:
    if _r.get("window_s") is not None: _r["window_s"] = round(float(_r["window_s"]), 1)
rows = [r for r in rows_all if r.get("rt_ok", True)]
print(f"有效 episode {len(rows)}/{len(rows_all)}（剔除实时性违规：最大滞后 > 0.25 s 或 p95 > 50 ms）")
COL = {"nothink": "#2a78d6", "think": "#eb6834", "dual": "#1baf7a", "nothink+mon": "#eda100", "think+mon": "#e87ba4",
       "fast_shared_jev": "#008300", "dual_shared_jev": "#6250d6", "dual_shared_text": "#e34948",
       "fast_shared_jev_bust": "#1baf7a", "dual_shared_jev_bust": "#6250d6", "dual_shared_text_bust": "#e34948",
       # 第二轮（所有方法共用共享前缀运行器；无后缀 = 带事件监控）
       "fast_shared_text": "#2a78d6", "fast_shared_text_nomon": "#eda100", "fast_shared_think": "#eb6834", "fast_shared_think_nomon": "#e87ba4",
       # r2b：阻塞式监控对照
       "fast_shared_text_monsync": "#2a78d6", "fast_shared_think_monsync": "#eb6834", "dual_shared_text_monsync": "#e34948",
       # r3：慢分支建议模式（Prompt 注入）
       "dual_advice_jev": "#eb6834", "dual_advice_jev_bust": "#e87ba4"}
NAME = {"nothink": "仅快（关思考）", "think": "仅慢（开思考）", "dual": "快慢双分支", "nothink+mon": "快 + 事件监控", "think+mon": "慢 + 事件监控",
        "fast_shared_jev": "仅快·Jev 候选打分", "dual_shared_jev": "双分支·共享前缀·Jev 快分支", "dual_shared_text": "双分支·共享前缀·文本快分支",
        "fast_shared_jev_bust": "仅快·Jev（禁缓存）", "dual_shared_jev_bust": "双分支·Jev（禁缓存）", "dual_shared_text_bust": "双分支·文本（禁缓存）",
        "fast_shared_text": "仅快·文本 + 监控", "fast_shared_text_nomon": "仅快·文本", "fast_shared_think": "仅慢 + 监控", "fast_shared_think_nomon": "仅慢",
        "fast_shared_text_monsync": "仅快·文本 + 阻塞监控", "fast_shared_think_monsync": "仅慢 + 阻塞监控", "dual_shared_text_monsync": "双分支·文本 + 阻塞监控",
        "dual_advice_jev": "双分支·建议注入·Jev", "dual_advice_jev_bust": "双分支·建议注入·Jev（禁缓存）"}
INK = {"text": "#0b0b0b", "text2": "#52514e", "grid": "#e6e5e2", "surface": "#fcfcfb"}


def frac(s):
    a, b = s.split("/"); return int(a) / int(b)


# ---------- 统计表 ----------
groups = collections.defaultdict(list)
for r in rows: groups[(r["task"], r["events"], r["mode"])].append(r)
lines = ["| 任务 | 事件 | 方法 | n | 按时整任务成功 | 子目标完成率均值 | 完成时间均值 (s) [范围] | 规划调用延迟 p50 (s) | 事件关键指标 |", "|---|---|---|---|---|---|---|---|---|"]
for (task, evn, mode), rs in sorted(groups.items()):
    n = len(rs)
    # 事件感知成功：E3 要求整任务完成且关键子目标在截止前完成（计划 §7.2"按时且无违规"）
    ok_fn = (lambda r: r["all"] and r.get("margin_s") is not None and r["margin_s"] >= 0) if "E3" in evn else (lambda r: r["all"])
    k = sum(1 for r in rs if ok_fn(r)); sub = np.mean([frac(r["score"]) for r in rs])
    t = [r["sim_s"] for r in rs]; lat = [r["lat_p50"] for r in rs if r.get("lat_p50") is not None]
    extra = ""
    if evn.startswith("case1_E1") or "E1" in evn:
        canc = sum(1 for r in rs if r.get("inflight_outcome") == "cancelled"); fin = sum(1 for r in rs if r.get("inflight_outcome") == "finished")
        resp = [r["first_new_target_cmd_s"] for r in rs if r.get("first_new_target_cmd_s") is not None]
        stale = [r.get("stale_after_event", 0) or 0 for r in rs]
        extra = f"过时放置被取消 {canc}/{n}、执行完 {fin}/{n}；响应延迟 {np.mean(resp):.1f} s [{min(resp):.1f}–{max(resp):.1f}]；事件后新增过时动作 {sum(stale)}" if resp else f"取消 {canc}/{n}"
    if "E3" in evn:
        ok = sum(1 for r in rs if r.get("margin_s") is not None and r["margin_s"] >= 0); mg = [r["margin_s"] for r in rs if r.get("margin_s") is not None]
        extra = f"截止前完成 {ok}/{n}" + (f"；余量 {np.mean(mg):.1f} s" if mg else "")
    lines.append(f"| {task} | {evn} | {NAME.get(mode, mode)} | {n} | {k}/{n} | {sub:.2f} | {np.mean(t):.1f} [{min(t):.0f}–{max(t):.0f}] | {np.mean(lat):.1f} | {extra} |")
table = "\n".join(lines)
(out / f"summary_{root}.md").write_text(table + "\n", encoding="utf-8"); print(table)

# ---------- 图 A：E3 成功率矩阵（方法 × 时间窗） ----------
MODE_ORDER = ("nothink", "think", "dual", "fast_shared_text_nomon", "fast_shared_text_monsync", "fast_shared_text", "fast_shared_think_nomon",
              "fast_shared_think_monsync", "fast_shared_think", "dual_shared_text_monsync", "dual_shared_text", "fast_shared_jev", "fast_shared_jev_bust",
              "dual_shared_jev", "dual_shared_jev_bust", "dual_advice_jev", "dual_advice_jev_bust")
e3 = [r for r in rows if "E3" in r["events"]]
if e3:
    wins = sorted({r.get("window_s") for r in e3 if r.get("window_s")})
    modes = [m for m in MODE_ORDER if any(r["mode"] == m for r in e3)]
    M = np.full((len(modes), len(wins)), np.nan); txt = [["" for _ in wins] for _ in modes]
    for i_, mode in enumerate(modes):
        for j_, w in enumerate(wins):
            rs = [r for r in e3 if r["mode"] == mode and r.get("window_s") and abs(r["window_s"] - w) < 1e-6]
            if not rs: continue
            ok = [r for r in rs if r.get("margin_s") is not None and r["margin_s"] >= 0]
            M[i_, j_] = len(ok) / len(rs)
            txt[i_][j_] = f"{len(ok)}/{len(rs)}" + (f"\n余量 {np.mean([r['margin_s'] for r in ok]):.1f} s" if ok else "")
    fig, ax = plt.subplots(figsize=(5.6, 0.42 * len(modes) + 1.2), dpi=170); fig.patch.set_facecolor(INK["surface"]); ax.set_facecolor(INK["surface"])
    cmap = matplotlib.colormaps["Blues"].copy(); cmap.set_bad(INK["surface"])
    ax.imshow(np.ma.masked_invalid(M), cmap=cmap, vmin=-0.15, vmax=1.15, aspect="auto")
    for i_ in range(len(modes)):
        for j_ in range(len(wins)):
            if np.isnan(M[i_, j_]):
                ax.text(j_, i_, "–", ha="center", va="center", fontsize=7.5, color=INK["text2"])
            else:
                ax.text(j_, i_, txt[i_][j_], ha="center", va="center", fontsize=7, color="white" if M[i_, j_] > 0.6 else INK["text"])
    ax.set_xticks(range(len(wins))); ax.set_xticklabels([f"{w:g} s" for w in wins], fontsize=8, color=INK["text"])
    ax.set_yticks(range(len(modes))); ax.set_yticklabels([NAME.get(m, m) for m in modes], fontsize=8, color=INK["text"])
    ax.set_xlabel("响应时间窗（警告发出到抽屉自动关闭）", fontsize=8, color=INK["text2"])
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("E3 限时关闭（Ideal/case6）：截止前完成放入的比例", fontsize=9, color=INK["text"], loc="left")
    fig.tight_layout(); fig.savefig(out / f"E3_success_vs_window_{root}.png", facecolor=fig.get_facecolor()); print("saved", out / f"E3_success_vs_window_{root}.png")

# ---------- 图 B：E1 有效响应延迟（按任务分面，对数横轴） ----------
e1_all = [r for r in rows if "E1_midplace" in r["events"]]
if e1_all:
    tasks = sorted({r["task"] for r in e1_all})
    order = [m for m in MODE_ORDER if any(r["mode"] == m for r in e1_all)]
    fig, axes = plt.subplots(1, len(tasks), figsize=(4.2 * len(tasks) + 1.6, 0.42 * len(order) + 1.2), dpi=170, sharey=True, squeeze=False)
    fig.patch.set_facecolor(INK["surface"])
    for ax, task in zip(axes[0], tasks):
        ax.set_facecolor(INK["surface"])
        for i_, mode in enumerate(order):
            rs = [r for r in e1_all if r["mode"] == mode and r["task"] == task]
            vals = [r["first_new_target_cmd_s"] for r in rs if r.get("first_new_target_cmd_s") is not None]
            if not vals: continue
            jitter = np.linspace(-0.13, 0.13, len(vals)) if len(vals) > 1 else [0]
            ax.scatter(vals, [i_ + j for j in jitter], s=34, color=COL.get(mode, "#888888"), edgecolor=INK["surface"], linewidth=1.0, zorder=3)
            med = float(np.median(vals))
            ax.plot([med] * 2, [i_ - 0.3, i_ + 0.3], color=INK["text"], linewidth=1.8, zorder=4)
            miss = len(rs) - len(vals)
            ax.annotate(f"{med:.1f} s" + (f"（{miss} 次未响应）" if miss else ""), (max(vals), i_), textcoords="offset points", xytext=(7, 0), va="center", fontsize=6.8, color=INK["text2"])
        ax.set_xscale("log"); ax.set_xlim(0.5, 200)
        ax.set_xticks([0.5, 1, 2, 5, 10, 20, 50, 100]); ax.set_xticklabels(["0.5", "1", "2", "5", "10", "20", "50", "100"])
        ax.grid(axis="x", color=INK["grid"], linewidth=0.8); ax.set_axisbelow(True)
        for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(INK["grid"]); ax.tick_params(axis="x", colors=INK["text2"], labelsize=7.5); ax.tick_params(axis="y", length=0)
        ax.set_title(task, fontsize=8.5, color=INK["text"], loc="left")
        ax.set_xlabel("目标更新 → 首个指向新目标的放置命令（s，对数轴）", fontsize=7.5, color=INK["text2"])
    axes[0][0].set_yticks(range(len(order))); axes[0][0].set_yticklabels([NAME.get(m, m) for m in order], fontsize=8, color=INK["text"])
    axes[0][0].set_ylim(len(order) - 0.5, -0.5)
    fig.suptitle("E1 放置途中改目标：有效响应延迟（点 = 单次，竖线 = 中位数）", fontsize=9, color=INK["text"], x=0.01, ha="left")
    fig.tight_layout(); fig.savefig(out / f"E1_response_latency_{root}.png", facecolor=fig.get_facecolor()); print("saved", out / f"E1_response_latency_{root}.png")
