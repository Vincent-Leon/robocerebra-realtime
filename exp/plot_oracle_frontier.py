"""E3 可行性边界：诊断 oracle（GT 计划、固定决策延迟）在不同时间窗下是否在截止前完成放入。
实心点 = 按时完成；空心点 = 错过。虚线 = 经验边界 延迟 = 时间窗 − 放置耗时。用法: python plot_oracle_frontier.py [out.png]"""
import sys, json, glob, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "PingFang SC", "Arial Unicode MS", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
import rc_env as R
INK = {"text": "#0b0b0b", "text2": "#52514e", "grid": "#e6e5e2", "surface": "#fcfcfb"}; OK = "#2a78d6"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else R.PROJECT_ROOT / "notes" / "figs" / "E3_oracle_frontier.png"
pts = []; place_durs = []
for f in glob.glob(str(R.RUNS_ROOT / "oracle" / "Ideal_case6" / "case6_E3_w*_oracle_think*" / "episode.json")):
    m = re.search(r"case6_E3_w(\d+)_oracle_think([\d.]+)$", Path(f).parent.name)
    if not m: continue
    W, th = float(m.group(1)), float(m.group(2)); ep = json.load(open(f))
    rep = ep["event_report"].get("E3a", {}); t_fire = rep.get("t_fire")
    done = next((t for t, w in ep["subgoal_events"] if "short_cabinet_1_middle_region" in w and "'in'" in w), None)
    ok = done is not None and t_fire is not None and done <= t_fire + W
    pts.append((th, W, ok, None if done is None or t_fire is None else round(done - t_fire, 2)))
    for h in ep["history"]:
        if h["call"].startswith("place('short_cabinet") and h["ok"]: pass
pts.sort()
fig, ax = plt.subplots(figsize=(6.0, 3.4), dpi=170); fig.patch.set_facecolor(INK["surface"]); ax.set_facecolor(INK["surface"])
for th, W, ok, dt in pts:
    ax.scatter([th], [W], s=110, facecolor=OK if ok else INK["surface"], edgecolor=OK, linewidth=2, zorder=3)
    if dt is not None: ax.annotate(f"{dt:.1f}s", (th, W), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=6.5, color=INK["text2"])
xs = np.linspace(-0.5, 9, 10); ax.plot(xs, xs + 3.8, color=INK["text2"], linewidth=1.2, linestyle="--", zorder=2)
ax.text(2.7, 5.0, "虚线：时间窗 = 决策延迟 + 3.8 s（实测放置耗时）", fontsize=7, color=INK["text2"], va="center")
ax.set_xlabel("每步决策延迟（s，诊断 oracle 固定）", fontsize=8, color=INK["text2"]); ax.set_ylabel("响应时间窗（s）", fontsize=8, color=INK["text2"])
ax.set_xticks(sorted({p[0] for p in pts})); ax.set_yticks(sorted({p[1] for p in pts})); ax.set_xlim(-1, 9.5); ax.set_ylim(4.5, 14)
ax.grid(color=INK["grid"], linewidth=0.8); ax.set_axisbelow(True)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
for sp in ("left", "bottom"): ax.spines[sp].set_color(INK["grid"])
ax.tick_params(colors=INK["text2"], labelsize=8)
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker="o", linestyle="", markersize=8, markerfacecolor=OK, markeredgecolor=OK, label="截止前放入（数字=警告后到放入的秒数）"),
                   Line2D([], [], marker="o", linestyle="", markersize=8, markerfacecolor=INK["surface"], markeredgecolor=OK, label="错过截止")], fontsize=7, frameon=False, loc="upper left")
ax.set_title("E3 可行性边界（Ideal/case6，诊断 oracle）", fontsize=9, color=INK["text"], loc="left")
fig.tight_layout(); out.parent.mkdir(parents=True, exist_ok=True); fig.savefig(out, facecolor=fig.get_facecolor()); print("saved", out)
for p in pts: print("  think=%.0fs W=%.0fs ok=%s placed_after=%s" % p)
