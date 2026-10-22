"""汇报用图。两套标签：
  --style=talk（默认）：面向不熟悉领域的听众，通俗名称（勾选项的快脑 / 写回答的快脑 / 深度思考），输出 notes/figs_talk/
  --style=group：面向熟悉项目的课题组，正式方法名（仅快·Jev / 仅快·文本 / 仅慢 / 双分支），输出 notes/figs_group/
图：
  fig_decision_latency.png  每次决策耗时（中位数，对数轴）
  fig_kv_cache.png          共享前缀缓存前后的 Jev 决策耗时
  fig_timeline_e1.png       E1 目标更新：三种方法的时间线（以事件时刻为 0）
  fig_timeline_e3.png       E3 6 s 窗：Jev / 文本 + 阻塞监控 / 文本 + 非阻塞监控
  fig_e3_matrix_talk.png    E3 成功矩阵（第二轮）
  fig_monitor_talk.png      监控方式对照（第二批 r2b）
  fig_e1_all_talk.png       E1 响应延迟（第二轮，两个任务分面）
数据来自 runs/llm_l20_r2 与 runs/llm_l20_r2b（数值与实验记录 E4.4、E4.5 一致）。
用法: python plot_talk_figs.py [--style=talk|group]
"""
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import rc_env as R

STYLE = "group" if "--style=group" in sys.argv else "talk"
_argv = list(sys.argv); sys.argv = [sys.argv[0]]
import analyze_llm_runs as A
sys.argv = _argv

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = R.PROJECT_ROOT / "notes" / ("figs_group" if STYLE == "group" else "figs_talk"); OUT.mkdir(parents=True, exist_ok=True)
INK = {"text": "#1d1d1f", "text2": "#5f5e5a", "grid": "#e6e5e2", "surface": "#ffffff"}
C = {"think": "#2a78d6", "think_slow": "#6250d6", "monitor": "#8e7ae6", "skill": "#eb6834", "cancel": "#eda100", "fail": "#e34948",
     "event": "#e34948", "jev": "#008300", "text_m": "#2a78d6", "slow": "#eb6834"}

LABELS = {
    "talk": {
        "sec": "秒", "dec_items": ["勾选项的快脑（Jev）", "写回答的快脑", "深度思考的慢脑：每一步", "慢脑出一整份计划：短任务", "慢脑出一整份计划：长任务"],
        "dec_x": "秒（对数刻度，中位数）",
        "kv_groups": ["短任务", "长任务（历史更长）"], "kv_gain": ["快约 40%", "快约 48%"], "kv_y": "快脑每做一个决定（秒）",
        "kv_leg": ["不共享缓存：每次从头读", "共享缓存：读过的不再重读"],
        "lanes": ["动作", "思考"], "tl_leg": ["快脑在想", "慢脑在想", "监控在判断", "动作完成", "动作被取消", "动作失败"],
        "tl_x": "相对事件发生的时间（秒）：红色实线 = 事件发生", "tl_dl": "，红色虚线 = 抽屉关闭锁定", "cancel": "（被取消）", "failed": "（失败）", "cancel_short": "取消",
        "e1_rows": [("勾选项的快脑（Jev），带监控", "0.85 秒就转向，改放到桌面"), ("深度思考的慢脑，带监控", "监控取消了错误动作，但要想约 8.5 秒才转向"),
                    ("写回答的快脑，不带监控", "先把黄油放进了盒子，15 秒后才补救")],
        "e3_rows": [("勾选项的快脑（Jev）", "赶上了，还剩约 3 秒"), ("写回答的快脑 + 阻塞监控", "等监控耽误了约 1.7 秒，没赶上"),
                    ("写回答的快脑 + 后台监控", "赶上了，还剩约 0.5 秒")],
        "modes": {"fast_shared_jev": "勾选项的快脑", "dual_shared_jev": "勾选项的快脑 + 慢脑", "fast_shared_text": "写回答的快脑 + 监控",
                  "fast_shared_text_nomon": "写回答的快脑，无监控", "dual_shared_text": "写回答的快脑 + 慢脑", "fast_shared_think": "深度思考 + 监控",
                  "fast_shared_think_nomon": "深度思考，无监控"},
        "not_run": "没测", "margin": "剩 {:.1f} 秒", "e3_cols": ["6 秒后关闭", "9 秒后关闭", "12 秒后关闭"],
        "e3_x": "每格：5 次里按时放进抽屉的次数，以及平均还剩多少时间",
        "mon_rows": [("写回答的快脑", "fast_shared_text"), ("写回答的快脑 + 慢脑", "dual_shared_text"), ("深度思考", "fast_shared_think"),
                     ("勾选项的快脑", "fast_shared_jev"), ("勾选项的快脑 + 慢脑", "dual_shared_jev")],
        "mon_cols": ["监控在后台判断", "停下来等监控"], "mon_x": "抽屉 6 秒后关闭，每格：5 次里赶上的次数",
        "e1_tasks": [("Ideal/case1", "场景一：收进储物盒"), ("Ideal/case6", "场景二：放进抽屉")],
        "e1_med": "{:.1f} 秒", "e1_miss": "（{} 次没转向）", "e1_x": "主人改主意后，多久发出第一个指向新目标的动作（秒，对数刻度）",
    },
    "group": {
        "sec": "s", "dec_items": ["Jev 快分支", "文本快分支", "仅慢（开思考），每步", "慢分支完整计划，短任务", "慢分支完整计划，长任务"],
        "dec_x": "单次决策耗时（s，对数轴，中位数）",
        "kv_groups": ["短任务（case6）", "长任务（Memory_Exploration）"], "kv_gain": ["-42%", "-47%"], "kv_y": "Jev 快分支单次决策（s）",
        "kv_leg": ["禁用前缀缓存", "共享前缀缓存"],
        "lanes": ["技能", "推理"], "tl_leg": ["快分支推理", "开思考推理", "事件监控", "技能完成", "技能被取消", "技能失败"],
        "tl_x": "相对事件时刻（s）：实线 = 事件触发", "tl_dl": "，虚线 = 抽屉关闭锁定", "cancel": "（取消）", "failed": "（失败）", "cancel_short": "取消",
        "e1_rows": [("仅快·Jev + 监控", "0.85 s 发出指向新目标的放置"), ("仅慢 + 监控", "过时放置被取消，8.5 s 后转向"),
                    ("仅快·文本，无监控", "过时放置执行完，15 s 后补救")],
        "e3_rows": [("仅快·Jev", "按时完成，余量 2.9 s"), ("仅快·文本 + 阻塞监控", "监控阻塞约 1.7 s，未按时完成"),
                    ("仅快·文本 + 非阻塞监控", "按时完成，余量 0.5 s")],
        "modes": {"fast_shared_jev": "仅快·Jev", "dual_shared_jev": "双分支·Jev", "fast_shared_text": "仅快·文本 + 监控",
                  "fast_shared_text_nomon": "仅快·文本，无监控", "dual_shared_text": "双分支·文本", "fast_shared_think": "仅慢 + 监控",
                  "fast_shared_think_nomon": "仅慢，无监控"},
        "not_run": "未测", "margin": "余量 {:.1f} s", "e3_cols": ["6 s 窗", "9 s 窗", "12 s 窗"],
        "e3_x": "每格：5 次中截止前完成放入的次数，及平均余量",
        "mon_rows": [("仅快·文本", "fast_shared_text"), ("双分支·文本", "dual_shared_text"), ("仅慢", "fast_shared_think"),
                     ("仅快·Jev", "fast_shared_jev"), ("双分支·Jev", "dual_shared_jev")],
        "mon_cols": ["非阻塞监控", "阻塞监控"], "mon_x": "E3 6 s 窗，每格：5 次中按时完成的次数",
        "e1_tasks": [("Ideal/case1", "Ideal/case1：放入储物盒途中改目标"), ("Ideal/case6", "Ideal/case6：放入抽屉途中改目标")],
        "e1_med": "{:.1f} s", "e1_miss": "（{} 次未响应）", "e1_x": "目标更新 → 首个指向新目标的放置命令（s，对数轴）",
    },
}
L = LABELS[STYLE]
r2 = R.RUNS_ROOT / "llm_l20_r2"; r2b = R.RUNS_ROOT / "llm_l20_r2b"


def style(ax):
    ax.set_facecolor(INK["surface"])
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"): ax.spines[sp].set_color(INK["grid"])
    ax.tick_params(colors=INK["text2"], labelsize=11)


# ---------- 1. 单次决策耗时 ----------
# 仅快·Jev / 仅快·文本 / 仅慢每步 / 慢分支完整计划（短、长任务）
vals = [0.40, 2.6, 8.8, 20.0, 78.0]; cols = [C["jev"], C["text_m"], C["slow"], C["think_slow"], C["think_slow"]]
fig, ax = plt.subplots(figsize=(9.6, 4.2), dpi=180); fig.patch.set_facecolor(INK["surface"]); style(ax)
ys = list(range(len(vals)))[::-1]
for y, name, v, col in zip(ys, L["dec_items"], vals, cols):
    ax.barh(y, v, color=col, height=0.58)
    ax.text(v * 1.08, y, f"{v:g} {L['sec']}", va="center", fontsize=12, color=INK["text"], fontweight="bold")
ax.set_yticks(ys); ax.set_yticklabels(L["dec_items"], fontsize=12, color=INK["text"])
ax.set_xscale("log"); ax.set_xlim(0.2, 300); ax.set_xticks([0.3, 1, 3, 10, 30, 100]); ax.set_xticklabels(["0.3", "1", "3", "10", "30", "100"])
ax.set_xlabel(L["dec_x"], fontsize=11, color=INK["text2"]); ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color=INK["grid"]); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig(OUT / "fig_decision_latency.png", facecolor=INK["surface"]); plt.close(fig)

# ---------- 2. 共享前缀缓存 ----------
fig, ax = plt.subplots(figsize=(8.4, 4.2), dpi=180); fig.patch.set_facecolor(INK["surface"]); style(ax)
w = 0.34
for i, (g, a, b, gain) in enumerate(zip(L["kv_groups"], (0.69, 0.99), (0.40, 0.52), L["kv_gain"])):   # 同场景中位数：case6 无事件 + E3 6 s；长任务 Memory_Exploration
    ax.bar(i - w / 2, a, w, color="#b9b8b3"); ax.bar(i + w / 2, b, w, color=C["jev"])
    ax.text(i - w / 2, a + 0.02, f"{a:.2f} {L['sec']}", ha="center", fontsize=12, color=INK["text"])
    ax.text(i + w / 2, b + 0.02, f"{b:.2f} {L['sec']}", ha="center", fontsize=12, color=INK["text"], fontweight="bold")
    ax.annotate(gain, xy=(i + w / 2, b + 0.12), ha="center", fontsize=13, color=C["jev"], fontweight="bold")
ax.set_xticks(range(2)); ax.set_xticklabels(L["kv_groups"], fontsize=12, color=INK["text"])
ax.set_ylabel(L["kv_y"], fontsize=11, color=INK["text2"]); ax.set_ylim(0, 1.25)
ax.legend(handles=[Patch(color="#b9b8b3", label=L["kv_leg"][0]), Patch(color=C["jev"], label=L["kv_leg"][1])], fontsize=11, frameon=False, loc="upper left")
ax.grid(axis="y", color=INK["grid"]); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig(OUT / "fig_kv_cache.png", facecolor=INK["surface"]); plt.close(fig)

# ---------- 3/4. 时间线对比 ----------
OBJ = {"butter_1": "黄油", "tomato_sauce_1": "番茄酱", "plate_1": "盘子", "cream_cheese_1": "奶酪", "popcorn_1": "爆米花",
       "coffee_table_table_region": "桌面", "short_cabinet_1_middle_region": "抽屉", "white_storage_box_1_bottom_side": "盒子",
       "white_storage_box_1_left_side": "盒子", "white_storage_box_1_right_side": "盒子", "white_storage_box_1_top_side": "盒子"}
VERB = {"pick": "拿", "place": "放到", "place_on_object": "放到", "pour": "倒进", "open_drawer": "开", "close_drawer": "关"}


def load(path):
    d = json.load(open(path)); ev = d["events"]
    fire = next(e for e in ev if e["type"] == "event_fired"); tf = fire["sim"]
    dl = next((e["sim"] - tf for e in ev if e["type"] == "event_deadline"), None)
    thinks, op = [], {}
    for e in ev:
        if e["type"] == "think_start": op[str(e.get("step_idx"))] = e
        elif e["type"] == "think_end" and str(e.get("step_idx")) in op:
            s = op.pop(str(e["step_idx"])); thinks.append((s["sim"] - tf, e["sim"] - tf, s.get("branch", "fast")))
    skills, st = [], {}
    for e in ev:
        if e["type"] == "skill_started": st[e["cid"]] = e
        elif e["type"] in ("skill_finished", "skill_cancelled") and e["cid"] in st:
            s = st.pop(e["cid"]); nm = s.get("skill") or ""
            verb = nm.split("(")[0]; arg = nm.split("'")[1] if "'" in nm else ""
            skills.append((s["sim"] - tf, e["sim"] - tf, f"{VERB.get(verb, verb)}{OBJ.get(arg, arg)}", e["type"] == "skill_cancelled", bool(e.get("ok"))))
    return thinks, skills, dl


def timeline(rows, fname, xlim, with_deadline=False):
    fig, axes = plt.subplots(len(rows), 1, figsize=(11.5, 1.55 * len(rows) + 0.9), dpi=180, sharex=True)
    fig.patch.set_facecolor(INK["surface"])
    for ax, row in zip(axes, rows):
        (label, verdict), path = row[0], row[1]; deep = len(row) > 2 and row[2]          # deep：该方法的决策本身开思考（仅慢）
        thinks, skills, dl = load(path); style(ax)
        for a, b, br in thinks:
            if b < xlim[0] or a > xlim[1]: continue
            ax.barh(1, max(b - a, 0.12), left=a, height=0.5, color=C["monitor"] if br == "monitor" else (C["think_slow"] if (br == "slow" or deep) else C["think"]))
        for a, b, name, canc, ok in skills:
            if b < xlim[0] or a > xlim[1]: continue
            col = C["cancel"] if canc else (C["skill"] if ok else C["fail"])
            ax.barh(0, b - a, left=a, height=0.5, color=col, edgecolor="white", linewidth=1.2)
            mid = (max(a, xlim[0]) + min(b, xlim[1])) / 2; width = min(b, xlim[1]) - max(a, xlim[0])
            full = name + (L["cancel"] if canc else ("" if ok else L["failed"]))
            lab = full if width > 0.32 * len(full) * (xlim[1] - xlim[0]) / 15 else (L["cancel_short"] if canc else (name if width > 1.4 else ""))
            if lab and width > 0.8:
                ax.text(mid, 0, lab, ha="center", va="center", fontsize=10, color="white", fontweight="bold")
        ax.axvline(0, color=C["event"], linewidth=2)
        if dl is not None: ax.axvline(dl, color=C["event"], linewidth=2, linestyle="--")
        ax.set_yticks([0, 1]); ax.set_yticklabels(L["lanes"], fontsize=10, color=INK["text2"]); ax.tick_params(axis="y", length=0)
        ax.set_ylim(-0.5, 1.5); ax.set_xlim(*xlim)
        ax.set_title(f"{label}    {verdict}", loc="left", fontsize=12.5, color=INK["text"], fontweight="bold", pad=4)
        ax.grid(axis="x", color=INK["grid"]); ax.set_axisbelow(True)
    axes[-1].set_xlabel(L["tl_x"] + (L["tl_dl"] if with_deadline else ""), fontsize=11, color=INK["text2"])
    handles = [Patch(color=c, label=t) for c, t in zip((C["think"], C["think_slow"], C["monitor"], C["skill"], C["cancel"], C["fail"]), L["tl_leg"])]
    fig.legend(handles=handles, loc="lower center", ncol=6, fontsize=10.5, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(OUT / fname, facecolor=INK["surface"]); plt.close(fig)


timeline([(L["e1_rows"][0], r2 / "Ideal_case1/case1_E1_midplace_fastshared_jev_s1/timeline.json"),
          (L["e1_rows"][1], r2 / "Ideal_case1/case1_E1_midplace_fastshared_think_s1/timeline.json", True),
          (L["e1_rows"][2], r2 / "Ideal_case1/case1_E1_midplace_fastshared_text_nomon_s1/timeline.json")], "fig_timeline_e1.png", (-6, 22))
timeline([(L["e3_rows"][0], r2 / "Ideal_case6/case6_E3_w6_fastshared_jev_s1/timeline.json"),
          (L["e3_rows"][1], r2b / "Ideal_case6/case6_E3_w6_fastshared_text_monsync_s1/timeline.json"),
          (L["e3_rows"][2], r2b / "Ideal_case6/case6_E3_w6_fastshared_text_s1/timeline.json")], "fig_timeline_e3.png", (-6, 9), with_deadline=True)


# ---------- 5/6/7. 成功矩阵、监控对照、E1 响应延迟 ----------
def ok_rows(root, pat):
    return [r for r in A.extract_rows(pat, root=root) if r.get("rt_ok", True)]


def matrix(cells, rows, cols, fname, col_label):
    M = np.full((len(rows), len(cols)), np.nan)
    for (i, j), (k, n, extra) in cells.items(): M[i, j] = k / n
    fig, ax = plt.subplots(figsize=(2.3 * len(cols) + 3.6, 0.62 * len(rows) + 1.3), dpi=180); fig.patch.set_facecolor(INK["surface"])
    cmap = matplotlib.colormaps["Blues"].copy(); cmap.set_bad("#f6f6f4")
    ax.imshow(np.ma.masked_invalid(M), cmap=cmap, vmin=-0.15, vmax=1.15, aspect="auto")
    for i in range(len(rows)):
        for j in range(len(cols)):
            if (i, j) not in cells:
                ax.text(j, i, L["not_run"], ha="center", va="center", fontsize=11, color="#a5a49f"); continue
            k, n, extra = cells[(i, j)]
            ax.text(j, i, f"{k}/{n}" + (f"\n{extra}" if extra else ""), ha="center", va="center", fontsize=13 if not extra else 12,
                    color="white" if M[i, j] > 0.6 else INK["text"], fontweight="bold")
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, fontsize=12.5, color=INK["text"])
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=12.5, color=INK["text"])
    ax.xaxis.set_ticks_position("top"); ax.tick_params(length=0)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_xticks(np.arange(-.5, len(cols), 1), minor=True); ax.set_yticks(np.arange(-.5, len(rows), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=3); ax.tick_params(which="minor", length=0)
    ax.set_xlabel(col_label, fontsize=11, color=INK["text2"])
    fig.tight_layout(); fig.savefig(OUT / fname, facecolor=INK["surface"]); plt.close(fig)


e3 = [r for r in ok_rows("llm_l20_r2", "Ideal_case6") if "E3" in r["events"]]
order = ["fast_shared_jev", "dual_shared_jev", "fast_shared_text_nomon", "fast_shared_text", "dual_shared_text", "fast_shared_think", "fast_shared_think_nomon"]
cells = {}
for i, m in enumerate(order):
    for j, w_ in enumerate([6.0, 9.0, 12.0]):
        rs = [r for r in e3 if r["mode"] == m and r.get("window_s") and abs(r["window_s"] - w_) < 0.2]
        if not rs: continue
        ok = [r for r in rs if r.get("margin_s") is not None and r["margin_s"] >= 0]
        cells[(i, j)] = (len(ok), len(rs), L["margin"].format(np.mean([r["margin_s"] for r in ok])) if ok else "")
matrix(cells, [L["modes"][m] for m in order], L["e3_cols"], "fig_e3_matrix_talk.png", L["e3_x"])

e3b = [r for r in ok_rows("llm_l20_r2b", "Ideal_case6") if "E3_w6" in r["events"]]
cells = {}
for i, (_, m) in enumerate(L["mon_rows"]):
    for j, suf in enumerate(("", "_monsync")):
        rs = [r for r in e3b if r["mode"] == m + suf]
        if rs:
            cells[(i, j)] = (sum(1 for r in rs if r.get("margin_s") is not None and r["margin_s"] >= 0), len(rs), "")
matrix(cells, [p[0] for p in L["mon_rows"]], L["mon_cols"], "fig_monitor_talk.png", L["mon_x"])

e1 = [r for r in ok_rows("llm_l20_r2", "*") if "E1_midplace" in r["events"]]
order = ["fast_shared_jev", "dual_shared_jev", "fast_shared_text", "dual_shared_text", "fast_shared_think", "fast_shared_text_nomon", "fast_shared_think_nomon"]
colors = {"fast_shared_jev": C["jev"], "dual_shared_jev": "#1baf7a", "fast_shared_text": C["text_m"], "dual_shared_text": "#e34948",
          "fast_shared_think": C["slow"], "fast_shared_text_nomon": "#eda100", "fast_shared_think_nomon": "#e87ba4"}
fig, axes = plt.subplots(1, 2, figsize=(13.5, 0.62 * len(order) + 1.6), dpi=180, sharey=True); fig.patch.set_facecolor(INK["surface"])
for ax, (task, tname) in zip(axes, L["e1_tasks"]):
    style(ax)
    for i, m in enumerate(order):
        rs = [r for r in e1 if r["mode"] == m and r["task"] == task]
        vs = [r["first_new_target_cmd_s"] for r in rs if r.get("first_new_target_cmd_s") is not None]
        if not vs: continue
        jit = np.linspace(-0.14, 0.14, len(vs)) if len(vs) > 1 else [0]
        ax.scatter(vs, [i + j for j in jit], s=55, color=colors[m], edgecolor="white", linewidth=1.0, zorder=3)
        med = float(np.median(vs)); ax.plot([med, med], [i - 0.32, i + 0.32], color=INK["text"], linewidth=2.2, zorder=4)
        ax.text(max(vs) * 1.15, i, L["e1_med"].format(med) + (L["e1_miss"].format(len(rs) - len(vs)) if len(rs) > len(vs) else ""), va="center", fontsize=11.5, color=INK["text"])
    ax.set_xscale("log"); ax.set_xlim(0.5, 250); ax.set_xticks([0.5, 1, 2, 5, 10, 20, 50]); ax.set_xticklabels(["0.5", "1", "2", "5", "10", "20", "50"])
    ax.grid(axis="x", color=INK["grid"]); ax.set_axisbelow(True); ax.tick_params(axis="y", length=0)
    ax.set_title(tname, fontsize=13, color=INK["text"], loc="left", fontweight="bold")
    ax.set_xlabel(L["e1_x"], fontsize=11, color=INK["text2"])
axes[0].set_yticks(range(len(order))); axes[0].set_yticklabels([L["modes"][m] for m in order], fontsize=12.5, color=INK["text"]); axes[0].set_ylim(len(order) - 0.5, -0.5)
fig.tight_layout(); fig.savefig(OUT / "fig_e1_all_talk.png", facecolor=INK["surface"]); plt.close(fig)
print("saved", STYLE, "figures to", OUT)
