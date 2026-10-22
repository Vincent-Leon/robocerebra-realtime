"""episode 时间线图（计划文档 §10）：规划器思考（按分支：slow/fast/monitor）、技能执行、子目标完成、事件触发/截止、取消。
横轴为相对 episode 开始的仿真时间（s）。配色为 dataviz 默认类别色（已用 validate_palette.js 校验，低对比色配直接标签）。
用法: python plot_timeline.py <timeline.json> [out.png] [--title=...]
"""
import sys, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "PingFang SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

args = [a for a in sys.argv[1:] if not a.startswith("--")]
src = Path(args[0]); out = Path(args[1]) if len(args) > 1 else src.with_suffix(".png")
title = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--title=")), None)
d = json.load(open(src)); ev = d["events"]
t0 = next((e["sim"] for e in ev if e["type"] == "episode_start"), 0.0)
rel = lambda e: e["sim"] - t0
C = {"slow": "#2a78d6", "fast": "#1baf7a", "monitor": "#6250d6", "skill": "#eb6834", "skill_cancelled": "#eda100", "skill_failed": "#e34948",
     "subgoal": "#008300", "event": "#e87ba4", "text": "#0b0b0b", "text2": "#52514e", "grid": "#e6e5e2", "surface": "#fcfcfb"}
thinks = []; open_t = {}
for e in ev:
    if e["type"] == "think_start": open_t[str(e.get("step_idx"))] = e
    elif e["type"] == "think_end" and str(e.get("step_idx")) in open_t:
        s0 = open_t.pop(str(e["step_idx"])); thinks.append((rel(s0), rel(e), s0.get("branch") or ("slow" if s0.get("thinking") else "fast")))
skills = []; started = {}
for e in ev:
    if e["type"] == "skill_started": started[e["cid"]] = e
    elif e["type"] in ("skill_finished", "skill_cancelled") and e["cid"] in started:
        s0 = started.pop(e["cid"]); skills.append((rel(s0), rel(e), e["skill"], e["type"] == "skill_cancelled", e.get("ok")))
subgoals = [rel(e) for e in ev if e["type"] == "subgoal_done"]
fired = [(rel(e), e.get("eid", ""), e.get("message") or e.get("event_type", "")) for e in ev if e["type"] == "event_fired"]
deadlines = [(rel(e), e.get("eid", "")) for e in ev if e["type"] == "event_deadline"]
cancels = [rel(e) for e in ev if e["type"] == "cancel_requested"]
t_end = max(rel(e) for e in ev)
fig, ax = plt.subplots(figsize=(14, 4.2), dpi=160)
fig.patch.set_facecolor(C["surface"]); ax.set_facecolor(C["surface"])
for a, b, br in thinks:
    y = 3 if br == "monitor" else 2
    ax.barh(y, max(b - a, 0.15), left=a, height=0.42, color=C.get(br, C["slow"]), edgecolor=C["surface"], linewidth=1)
for i, (a, b, name, cancelled, ok) in enumerate(skills):
    col = C["skill_cancelled"] if cancelled else (C["skill"] if ok else C["skill_failed"])
    ax.barh(1, b - a, left=a, height=0.42, color=col, edgecolor=C["surface"], linewidth=1)
    try:
        obj = name.split("'")[1].replace("white_storage_box_1_", "box ").replace("_table_region", "").replace("_1", "").replace("_", " ")
    except Exception:
        obj = ""
    label = f"{name.split('(')[0]} {obj}" + ("（取消）" if cancelled else ("" if ok else "（失败）"))
    ax.text((a + b) / 2, 1.33 if i % 2 == 0 else 0.67, label, ha="center", va="center", fontsize=6.5, color=C["text"])
for t in subgoals:
    ax.plot([t], [0], marker="o", markersize=7, color=C["subgoal"], markeredgecolor=C["surface"], markeredgewidth=1.2)
for t, eid, msg in fired:
    ax.axvline(t, color=C["event"], linewidth=1.6)
    ax.text(t + 0.4, 3.55, f"{eid}: {msg[:60]}", fontsize=6.8, color=C["text"], va="center")
for t, eid in deadlines:
    ax.axvline(t, color=C["event"], linewidth=1.4, linestyle="--")
    ax.text(t + 0.4, 3.25, f"{eid} 截止", fontsize=6.8, color=C["text2"], va="center")
for t in cancels:
    ax.axvline(t, color=C["skill_cancelled"], linewidth=1.0, linestyle=":")
lanes = {"事件": 3.4, "快速监控（关思考）": 3, "规划器思考": 2, "技能执行": 1, "子目标完成": 0}
ax.set_yticks(list(lanes.values())); ax.set_yticklabels(list(lanes.keys()), fontsize=8, color=C["text"])
ax.set_xlim(0, t_end + 1); ax.set_ylim(-0.6, 3.85)
rtr = next((e["realized_rtr"] for e in ev if e["type"] == "episode_end"), float("nan"))
ax.set_xlabel(f"episode 仿真时间 (s)  —  实际 RTR = {rtr:.3f}，环境在思考期间持续推进", fontsize=8, color=C["text2"])
ax.grid(axis="x", color=C["grid"], linewidth=0.8); ax.set_axisbelow(True)
for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
ax.spines["bottom"].set_color(C["grid"]); ax.tick_params(axis="x", colors=C["text2"], labelsize=8); ax.tick_params(axis="y", length=0)
legend = [Patch(color=C["slow"], label="慢分支思考（开思考）"), Patch(color=C["fast"], label="快分支思考（关思考）"), Patch(color=C["monitor"], label="快速监控"),
          Patch(color=C["skill"], label="技能完成"), Patch(color=C["skill_failed"], label="技能失败"), Patch(color=C["skill_cancelled"], label="技能被取消"),
          Line2D([], [], marker="o", color=C["subgoal"], linestyle="", markersize=6, label="子目标完成（修复版）"), Line2D([], [], color=C["event"], label="事件触发 / 截止(虚线)")]
ax.legend(handles=legend, loc="upper center", fontsize=7, frameon=False, ncol=8, bbox_to_anchor=(0.5, -0.2))
fin = d["final"]
ax.set_title(title or f"{d['case']} — 最终 修复版 {fin['repaired']}/{fin['n_goals']} · 原始 {fin['original']}", fontsize=9.5, color=C["text"], loc="left", pad=8)
fig.tight_layout(); fig.savefig(out, facecolor=fig.get_facecolor()); print("saved", out)
