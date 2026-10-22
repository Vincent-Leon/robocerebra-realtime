"""排行榜配图（读 analyze_leaderboard.py 的输出），输出到 notes/figs_lb/：
  fig_lb_score_latency.png  得分—单次决策延迟（对数横轴，左上最好；虚线连帕累托前沿，横虚线为执行器上限）
  fig_lb_tokens.png         每任务 token 构成：缓存输入 / 非缓存输入 / 输出（每局均值，单位 k）
  fig_lb_category.png       分类别得分热力图（模式 × 6 类，末行为标准计划上限）
  fig_lb_time.png           每任务用时与 GPU 时间（中位数）
  fig_lb_anytime.png        得分随时间的累积曲线（每局前 t 秒内完成的子目标比例，各模式均值）
用法: python plot_leaderboard.py [--root=llm_l20_r4lb] [--dir=../notes/figs_lb] [--seeds=1]（与 analyze_leaderboard.py 的 --seeds 一致；图名加同样后缀）
"""
import sys, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FixedLocator, NullFormatter, FuncFormatter
import rc_env as R

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root = opt.get("root", "llm_l20_r4lb"); OUT = Path(opt.get("dir", str(R.PROJECT_ROOT / "notes" / "figs_lb")))
INK = {"text": "#1d1d1f", "text2": "#5f5e5a", "grid": "#e6e5e2", "surface": "#ffffff", "muted": "#b9b8b3"}
MC = {"fast_shared_text": "#2a78d6", "fast_shared_jev": "#008300", "fast_shared_think": "#b8860b",
      "dual_shared_jev": "#6250d6", "dual_advice_jev": "#eb6834"}
TYPES = ["Ideal", "Memory_Execution", "Memory_Exploration", "Mix", "Observation_Mismatching", "Random_Disturbance"]
TYPE_CN = ["理想", "记忆·执行", "记忆·探索", "混合", "描述错位", "随机扰动"]
SUF = ("_s" + "".join(sorted(opt["seeds"].split(",")))) if opt.get("seeds") else ""
LB = json.load(open(OUT / f"leaderboard_{root}{SUF}.json")); rows = LB["rows"]; gt = LB["gt"]
EPS = json.load(open(OUT / f"leaderboard_{root}{SUF}_episodes.json"))
single = all(r["sd"] is None for r in rows)


def style(ax):
    ax.set_facecolor(INK["surface"])
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"): ax.spines[sp].set_color(INK["grid"])
    ax.tick_params(colors=INK["text2"], labelsize=11)


def newfig(w, h):
    fig = plt.figure(figsize=(w, h), dpi=180); fig.patch.set_facecolor(INK["surface"]); return fig


def save(fig, name):
    fig.savefig(OUT / name, facecolor=INK["surface"], bbox_inches="tight"); plt.close(fig); print("saved", OUT / name)


def note(fig):
    n = sorted({x for r in rows for x in r["seeds"]})
    fig.text(0.01, 0.005, f"{root}；{len(n)} 批（种子 {','.join(map(str, n))}），每模式 {max(r['n'] for r in rows)} 局" + ("；只有一批，无误差棒" if single else "；误差棒为各批均值的标准差"),
             fontsize=9, color=INK["text2"])


# ---------- 1. 得分—单次决策延迟 ----------
fig = newfig(9.5, 6); ax = fig.add_subplot(111); style(ax)
pts = sorted(rows, key=lambda r: r["fast_p50"]); front, best = [], -1.0
for r in pts:                                                   # 帕累托前沿：延迟更低的模式里得分都更低
    if r["score"] > best: front.append(r); best = r["score"]
for r in rows:
    c = MC.get(r["mode"], INK["muted"]); on = r in front
    ax.errorbar(r["fast_p50"], r["score"], yerr=r["sd"] or 0, fmt="o", ms=11 if on else 9, color=c, mec="white" if on else c, mew=1.5, capsize=4, zorder=3)
if len(front) > 1:
    ax.plot([r["fast_p50"] for r in front], [r["score"] for r in front], ls="--", color=INK["muted"], lw=1.2, zorder=1)
ax.set_xscale("log"); x0 = min(r["fast_p50"] for r in rows) * 0.6; ax.set_xlim(x0, max(r["fast_p50"] for r in rows) * 4)
ax.xaxis.set_major_locator(FixedLocator([0.2, 0.3, 0.5, 1, 2, 3, 5, 10, 20, 30, 50, 100])); ax.xaxis.set_minor_formatter(NullFormatter())
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
lo = min([r["score"] - (r["sd"] or 0) for r in rows] + ([gt["score"]] if gt else [])); hi = max([r["score"] + (r["sd"] or 0) for r in rows] + ([gt["score"]] if gt else []))
ax.set_ylim(lo - 0.25 * (hi - lo) - 0.01, hi + 0.08 * (hi - lo) + 0.005)
if gt:
    ax.axhline(gt["score"], color=INK["text2"], ls=":", lw=1.2)
    ax.text(x0 * 1.05, gt["score"] + 0.004, f"参考：标准计划（无语言模型，按演示步骤执行）{gt['score']:.3f}", fontsize=10, color=INK["text2"], va="bottom")
fig.canvas.draw(); PT = fig.dpi / 72; FS = 10.5                   # 标签：延迟相近（1.5 倍以内）的点归为一簇，簇内标签排成一列放在右侧并画引线；与已放标签重叠就往下挪
textw = lambda t: max(sum(FS if ord(ch) > 0x2000 else FS * 0.56 for ch in ln) for ln in t.split("\n")) * PT
inv = ax.transData.inverted(); clusters = []
for r in sorted(rows, key=lambda r: r["fast_p50"]):
    if clusters and r["fast_p50"] <= clusters[-1][-1]["fast_p50"] * 1.5: clusters[-1].append(r)
    else: clusters.append([r])
placed = []
for cl in clusters:
    xr = max(ax.transData.transform((r["fast_p50"], r["score"]))[0] for r in cl)
    for r in sorted(cl, key=lambda r: -r["score"]):
        c = MC.get(r["mode"], INK["muted"]); lab = r["name"] + (f"\n慢分支单次 {r['slow_p50']:.1f} s" if r["slow_p50"] else "")
        x, y = ax.transData.transform((r["fast_p50"], r["score"])); w = textw(lab); h = (lab.count("\n") + 1) * FS * 1.3 * PT
        lx = xr + (24 if len(cl) > 1 else 9) * PT; top = y + 0.5 * h; moved = True
        while moved:
            moved = False
            for a0, a1, t, b_ in placed:
                if lx < a1 and lx + w > a0 and top > b_ and top - h < t: top = b_ - 3 * PT; moved = True
        placed.append((lx, lx + w, top, top - h)); tx, ty = inv.transform((lx, top))
        ax.annotate(lab, (r["fast_p50"], r["score"]), xytext=(tx, ty), textcoords="data", fontsize=FS, color=c, va="top", ha="left", zorder=4,
                    bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.85),
                    arrowprops=dict(arrowstyle="-", color=c, lw=0.7, shrinkA=2, shrinkB=6, relpos=(0, 0.5)) if len(cl) > 1 else None)
ax.set_xlabel("单次决策延迟中位数（s，对数轴；双分支为快分支）", fontsize=12, color=INK["text"])
ax.set_ylabel("得分（60 个任务子目标完成率均值）", fontsize=12, color=INK["text"])
ax.grid(True, which="both", color=INK["grid"], lw=0.6); ax.set_axisbelow(True)
ax.set_title("得分与延迟（左上最好；虚线为帕累托前沿）", fontsize=14, color=INK["text"], loc="left")
note(fig); save(fig, f"fig_lb_score_latency{SUF}.png")

# ---------- 2. token 构成 ----------
fig = newfig(9.5, 0.75 * len(rows) + 1.8); ax = fig.add_subplot(111); style(ax)
names = [r["name"] for r in rows][::-1]; y = np.arange(len(rows))
parts = [("tok_cached", "缓存输入（命中前缀缓存）", "#c9c7c0"), ("tok_in_nc", "非缓存输入", "#2a78d6"), ("tok_out", "输出", "#eb6834")]
left = np.zeros(len(rows))
for k, lab, c in parts:
    v = np.array([r["tok_mean"][k] for r in rows][::-1]) / 1000
    ax.barh(y, v, left=left, color=c, label=lab, height=0.6); left += v
for i, r in enumerate(rows[::-1]):
    nc = (r["tok_mean"]["tok_in_nc"] + r["tok_mean"]["tok_out"]) / 1000
    ax.text(left[i] + left.max() * 0.01, i, f"非缓存输入+输出 {nc:.1f} k", va="center", fontsize=10, color=INK["text2"])
ax.set_yticks(y); ax.set_yticklabels(names, fontsize=11.5); ax.set_xlim(0, left.max() * 1.3)
ax.set_xlabel("每任务 token 数（k，每局均值）", fontsize=12, color=INK["text"])
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=10, frameon=False); ax.grid(True, axis="x", color=INK["grid"], lw=0.6); ax.set_axisbelow(True)
ax.set_title("每任务 token 构成", fontsize=14, color=INK["text"], loc="left", pad=30)
note(fig); save(fig, f"fig_lb_tokens{SUF}.png")

# ---------- 3. 分类别热力图 ----------
labels = [r["name"] for r in rows] + (["标准计划（参考）"] if gt else [])
M = np.array([[r["cat"].get(t, np.nan) for t in TYPES] for r in rows] + ([[gt["cat"][t] for t in TYPES]] if gt else []))
fig = newfig(10, 0.6 * len(labels) + 1.8); ax = fig.add_subplot(111)
im = ax.imshow(M, cmap="YlGn", vmin=0, vmax=1, aspect="auto")
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        if not np.isnan(M[i, j]): ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=11, color="white" if M[i, j] > 0.7 else INK["text"])
ax.set_xticks(range(len(TYPES))); ax.set_xticklabels(TYPE_CN, fontsize=11.5); ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=11.5)
if gt: ax.axhline(len(rows) - 0.5, color="white", lw=3)
for sp in ax.spines.values(): sp.set_visible(False)
ax.tick_params(length=0, colors=INK["text"]); cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02); cb.outline.set_visible(False)
ax.set_title("分类别得分（子目标完成率）", fontsize=14, color=INK["text"], loc="left")
note(fig); save(fig, f"fig_lb_category{SUF}.png")

# ---------- 4. 用时 ----------
fig = newfig(9.5, 0.75 * len(rows) + 1.8); ax = fig.add_subplot(111); style(ax)
t = np.array([r["time_med"] for r in rows][::-1]); g = np.array([r["gpu_med"] for r in rows][::-1])
ax.barh(y + 0.17, t, height=0.32, color=[MC.get(r["mode"], INK["muted"]) for r in rows][::-1], label="每任务用时（仿真时间 = 墙钟时间）")
ax.barh(y - 0.17, g, height=0.32, color="#c9c7c0", label="每任务 GPU 时间（模型调用延迟之和）")
for i in range(len(rows)):
    ax.text(t[i] + 3, i + 0.17, f"{t[i]:.0f} s", va="center", fontsize=10, color=INK["text2"]); ax.text(g[i] + 3, i - 0.17, f"{g[i]:.0f} s", va="center", fontsize=10, color=INK["text2"])
ax.set_yticks(y); ax.set_yticklabels(names, fontsize=11.5); ax.set_xlim(0, max(t.max(), g.max()) * 1.18)
ax.set_xlabel("秒（每局数值的中位数；每局上限 300 s）", fontsize=12, color=INK["text"])
ax.legend(handles=[Patch(color=INK["text2"], label="每任务用时（实时执行，仿真时间 = 墙钟时间；颜色同模式）"), Patch(color="#c9c7c0", label="每任务 GPU 时间（模型调用延迟之和）")],
          loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=10, frameon=False); ax.grid(True, axis="x", color=INK["grid"], lw=0.6); ax.set_axisbelow(True)
ax.set_title("每任务用时与 GPU 时间", fontsize=14, color=INK["text"], loc="left", pad=30)
note(fig); save(fig, f"fig_lb_time{SUF}.png")

# ---------- 5. 得分随时间累积 ----------
fig = newfig(9.5, 6); ax = fig.add_subplot(111); style(ax)
T = np.arange(0, 301, 1.0)
for r in rows:
    v = [e for e in EPS if e["mode"] == r["mode"]]
    ev = [np.sort(np.array(e["events"])) for e in v]; n = np.array([max(e["n"], 1) for e in v], dtype=float)
    curve = np.mean([np.searchsorted(x, T, side="right") / k for x, k in zip(ev, n)], axis=0)
    ax.plot(T, curve, color=MC.get(r["mode"], INK["muted"]), lw=2.2, label=f"{r['name']}（最终 {r['score']:.3f}）")
if gt:
    ax.axhline(gt["score"], color=INK["text2"], ls=":", lw=1.2)
    ax.text(4, gt["score"] + 0.008, f"参考：标准计划 {gt['score']:.3f}（最终值）", fontsize=10, color=INK["text2"], va="bottom")
for B in (60, 120):
    ax.axvline(B, color=INK["grid"], lw=1.0, zorder=0)
ax.set_xlim(0, 300); ax.set_ylim(0, max(0.9, (gt or {"score": 0})["score"] + 0.05))
ax.set_xlabel("每局开始后的时间（s，实时）", fontsize=12, color=INK["text"]); ax.set_ylabel("已完成子目标比例（各局均值）", fontsize=12, color=INK["text"])
ax.legend(loc="lower right", fontsize=10.5, frameon=False); ax.grid(True, color=INK["grid"], lw=0.6); ax.set_axisbelow(True)
ax.set_title("得分随时间累积（曲线越靠左上，得分来得越快）", fontsize=14, color=INK["text"], loc="left")
note(fig); save(fig, f"fig_lb_anytime{SUF}.png")
