"""第三轮群发报告用图（正式方法名），输出 notes/figs_r3/：
  fig_r3_frames_grasp.png   r2b 切向夹持与滑落 / r3 前沿径向夹持（render_r3_frames.py 渲染）
  fig_r3_frames_drawer.png  抽象开抽屉：内容物不随动（弹出）/ 随动 / 人类演示 / 抽象取物
  fig_r3_gt.png             标准计划（GT plan）12 个试点任务：r2b 对 r3
  fig_r3_scorer_case8.png   case8 一局的子目标计分时刻：v5 对 v6
  fig_r3_long.png           长任务子目标完成率（每点一局，计分器 v6）
  fig_r3_case5.png          case5 逐局：用时—完成率，失败技能数
  fig_r3_slow_latency.png   慢分支单次调用延迟：完整计划对建议
  fig_r3_timeline_case5.png case5 时间线：双分支·完整计划 对 双分支·建议注入（种子 1）
  fig_r3_kv.png             KV 缓存：命中 / 未命中 / cache_salt 实测；Jev 决策延迟 共享对禁缓存
数据：runs/gtplan_r2b、runs/gtplan_r3b、runs/llm_l20_r3（含 rescored.json）、runs/llm_l20_r3b。
用法: python plot_r3_figs.py
"""
import json, glob, re, collections
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import imageio.v2 as imageio
import rc_env as R

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = R.PROJECT_ROOT / "notes" / "figs_r3"; OUT.mkdir(parents=True, exist_ok=True); FR = OUT / "frames"
INK = {"text": "#1d1d1f", "text2": "#5f5e5a", "grid": "#e6e5e2", "surface": "#ffffff", "muted": "#b9b8b3"}
MC = {"fast_shared_jev": "#008300", "dual_shared_jev": "#6250d6", "dual_advice_jev": "#eb6834", "dual_advice_jev_bust": "#e87ba4", "r3b": "#2a78d6"}
MN = {"fast_shared_jev": "仅快·Jev", "dual_shared_jev": "双分支·完整计划·Jev", "dual_advice_jev": "双分支·建议注入·Jev",
      "dual_advice_jev_bust": "建议注入·Jev（禁缓存）", "r3b": "建议注入 + 完成核实（补测）"}
ORDER = ["fast_shared_jev", "dual_shared_jev", "dual_advice_jev", "dual_advice_jev_bust"]
R3 = R.RUNS_ROOT / "llm_l20_r3"; R3B = R.RUNS_ROOT / "llm_l20_r3b"


def style(ax):
    ax.set_facecolor(INK["surface"])
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"): ax.spines[sp].set_color(INK["grid"])
    ax.tick_params(colors=INK["text2"], labelsize=11)


def newfig(w, h):
    fig = plt.figure(figsize=(w, h), dpi=180); fig.patch.set_facecolor(INK["surface"]); return fig


def save(fig, name):
    fig.savefig(OUT / name, facecolor=INK["surface"]); plt.close(fig); print("saved", OUT / name)


def episodes(root):
    out = []
    for f in sorted(glob.glob(str(root / "*" / "*" / "episode.json"))):
        ep = json.load(open(f)); p = Path(f).parent
        rs = p / "rescored.json"
        if rs.exists():
            r = json.load(open(rs)); ep["final"] = {"repaired": r["repaired"], "n_goals": r["n_goals"], "all_done": r["repaired_all"]}
            ep["subgoal_events_v6"] = r["subgoal_events"]
        ep["_dir"] = p; out.append(ep)
    return out


# ---------- 1. 仿真画面拼图 ----------
def panel(files_titles, name, ncols, w, h):
    n = len(files_titles); nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(w, h), dpi=150, squeeze=False); fig.patch.set_facecolor(INK["surface"])
    for ax in axes.flat: ax.axis("off")
    for ax, (f, title, col) in zip(axes.flat, files_titles):
        ax.imshow(imageio.imread(FR / f)); ax.set_title(title, fontsize=12.5, color=col, loc="left", fontweight="bold", pad=6)
    fig.tight_layout(); save(fig, name)


panel([("slip_hold.png", "r2b：两指并排夹住碗沿（腕部停在 106°）", "#e34948"), ("slip_drop.png", "r2b：抬到顶后碗滑落", "#e34948"),
       ("bowl_after.png", "r3：前沿径向夹持", "#008300")], "fig_r3_frames_grasp.png", 3, 15.5, 4.4)
panel([("carry_off.png", "r2b：内容物不随动，黄油被弹出抽屉、落在杯口", "#e34948"), ("carry_on.png", "r3：内容物随抽屉平移，黄油留在抽屉内", "#008300"),
       ("demo_grasp.png", "人类演示：同一时刻黄油位置与 r3 一致", INK["text"]), ("abstract_pick.png", "r3：抽象取物，黄油在两指之间", "#008300")],
      "fig_r3_frames_drawer.png", 2, 11.5, 8.9)

# ---------- 2. 标准计划回归 ----------
def gt(tag):
    d = {}
    for f in glob.glob(str(R.RUNS_ROOT / tag / "*" / "log.txt")):
        m = re.search(r"repaired (\d+)/(\d+)", open(f).read().split("[result]")[-1])
        if m: d[Path(f).parent.name] = (int(m.group(1)), int(m.group(2)))
    return d


a, b = gt("gtplan_r2b"), gt("gtplan_r3b")
keys = sorted(b, key=lambda k: (not k.startswith("Ideal"), int(k.split("case")[-1])))
fig = newfig(11.5, 6.4); ax = fig.add_subplot(111); style(ax)
ys = np.arange(len(keys))[::-1]; hh = 0.38
for y, k in zip(ys, keys):
    (ka, na), (kb, nb) = a[k], b[k]
    bar = ax.barh(y + hh / 2, ka / na, hh, color=INK["muted"])
    if k == "Memory_Exploration_case6": bar[0].set_hatch("//"); bar[0].set_edgecolor("#ffffff")
    ax.barh(y - hh / 2, kb / nb, hh, color="#008300")
    ax.text(ka / na + 0.01, y + hh / 2, f"{ka}/{na}" + ("  伪成功：黄油被弹出抽屉后完成" if k == "Memory_Exploration_case6" else ""), va="center", fontsize=10, color=INK["text2"])
    ax.text(kb / nb + 0.01, y - hh / 2, f"{kb}/{nb}", va="center", fontsize=10.5, color=INK["text"], fontweight="bold")
lab = {k: k.replace("Memory_Exploration_", "Memory_Exploration ").replace("Ideal_", "Ideal ") + ("（厨房桌）" if k in ("Memory_Exploration_case1", "Memory_Exploration_case2") else "") for k in keys}
ax.set_yticks(ys); ax.set_yticklabels([lab[k] for k in keys], fontsize=11, color=INK["text"]); ax.tick_params(axis="y", length=0)
ax.set_xlim(0, 1.42); ax.set_xticks([0, .25, .5, .75, 1]); ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
ax.set_xlabel("标准计划逐步执行时的子目标完成率（修复版计分）", fontsize=11, color=INK["text2"])
ta, tb = sum(v[0] for v in a.values()), sum(v[0] for v in b.values()); tn = sum(v[1] for v in b.values())
ax.legend(handles=[Patch(color=INK["muted"], label=f"r2b：{ta}/{tn}（{ta / tn:.1%}）"), Patch(color="#008300", label=f"r3：{tb}/{tn}（{tb / tn:.1%}）")],
          fontsize=11.5, frameon=False, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2)
ax.grid(axis="x", color=INK["grid"]); ax.set_axisbelow(True)
fig.tight_layout(); save(fig, "fig_r3_gt.png")

# ---------- 3. case8 计分：v5 对 v6 ----------
OBJ = {"white_bowl_1": "碗", "cookies_1": "饼干", "chocolate_pudding_1": "布丁"}
REG = {"wooden_cabinet_1_top_region": "上层抽屉", "wooden_cabinet_1_middle_region": "中层抽屉", "wooden_cabinet_1_bottom_region": "下层抽屉",
       "coffee_table_table_region": "桌面", "wooden_cabinet_1_top_side": "柜顶", "white_bowl_1": "碗"}
VB = {"open": "开", "close": "关", "pick": "拿起", "pour": "倒入", "in": "放到"}
ep8 = R3 / "Memory_Exploration_case8" / "noevent_fastshared_jev_s1"
e8 = json.load(open(ep8 / "episode.json")); rs8 = json.load(open(ep8 / "rescored.json"))
c8 = R.load_case("Memory_Exploration", R.BENCH_ROOT / "Memory_Exploration" / "case8", load_demo=False)
rows = []
for obj, acts in c8.goal.items():
    for st in acts:
        tgt = st[2] if len(st) > 2 else (st[1] if st[0] in ("open", "close") else "")
        rows.append((obj, st, f"{OBJ.get(obj, obj)}：{VB.get(st[0], st[0])}{REG.get(tgt, '')}"))


def credit_times(events):
    pool = collections.defaultdict(list)
    for t, w in events: pool[w].append(t)
    out = []
    for obj, st, _ in rows:
        key = f"{obj}:{st}"; out.append(pool[key].pop(0) if pool[key] else None)
    return out


t5 = credit_times(e8["subgoal_events"]); t6 = credit_times(rs8["subgoal_events"])
fig = newfig(8.6, 6.6); gs = fig.add_gridspec(2, 1, height_ratios=[1.25, 6.0], hspace=0.08)
axa = fig.add_subplot(gs[0]); ax = fig.add_subplot(gs[1], sharex=axa); style(axa); style(ax)
ev8 = json.load(open(ep8 / "timeline.json"))["events"]; t08 = ev8[0]["sim"]; st8 = {}; drawer = []
for e in ev8:
    if e["type"] == "skill_started": st8[e["cid"]] = e
    elif e["type"] in ("skill_finished", "skill_cancelled") and e["cid"] in st8:
        s0 = st8.pop(e["cid"]); nm = s0.get("skill") or ""
        if nm.startswith(("open_drawer", "close_drawer")) and e.get("ok"):
            drawer.append((s0["sim"] - t08, e["sim"] - t08, nm))
for i, (a0, b0, nm) in enumerate(drawer):
    v = "开" if nm.startswith("open") else "关"; r_ = REG.get(nm.split("'")[1], "") if "'" in nm else ""
    axa.barh(0.45, b0 - a0, left=a0, height=0.5, color="#6250d6", edgecolor="white", linewidth=1.2)
    axa.text((a0 + b0) / 2, 1.05 if i % 2 == 0 else 1.55, f"{v}{r_.replace('抽屉', '')}", ha="center", fontsize=10.5, color="#6250d6")
axa.set_ylim(0, 2.0); axa.set_yticks([]); axa.spines["left"].set_visible(False); axa.tick_params(axis="x", labelbottom=False)
axa.set_title("智能体的抽屉操作（case8，仅快·Jev，种子 1；73 s 完成任务）", loc="left", fontsize=12, color=INK["text"])
ys = np.arange(len(rows))[::-1]
for y, (obj, st, lab_), a5, a6 in zip(ys, rows, t5, t6):
    if a6 is not None: ax.scatter(a6, y, s=90, color="#008300", zorder=3)
    if a5 is not None: ax.scatter(a5, y, s=190, facecolor="none", edgecolor=INK["text"], linewidth=1.6, zorder=4)
    if a5 is None: ax.text(81, y, "v5 未计", va="center", fontsize=10, color="#e34948")
ax.set_yticks(ys); ax.set_yticklabels([r[2] for r in rows], fontsize=10.5, color=INK["text"]); ax.tick_params(axis="y", length=0)
ax.set_xlim(0, 88); ax.set_xlabel("时间（s）", fontsize=11, color=INK["text2"]); ax.grid(axis="x", color=INK["grid"]); ax.set_axisbelow(True)
n5 = sum(x is not None for x in t5); n6 = sum(x is not None for x in t6)
ax.legend(handles=[Line2D([], [], marker="o", color="#008300", linestyle="", markersize=9, label=f"v6 计分时刻（{n6}/15）"),
                   Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor=INK["text"], linestyle="", markersize=12, label=f"v5 计分时刻（{n5}/15）")],
          fontsize=11, frameon=False, loc="lower right")
fig.subplots_adjust(left=0.2, right=0.98, top=0.93, bottom=0.08); save(fig, "fig_r3_scorer_case8.png")

# ---------- 4. 长任务完成率 ----------
eps = episodes(R3)
long_tasks = [("Memory_Exploration/case10", 11), ("Memory_Exploration/case6", 12), ("Memory_Exploration/case8", 15), ("Memory_Exploration/case5", 14)]
fig, axes = plt.subplots(1, 4, figsize=(15.5, 5.0), dpi=180, sharey=True); fig.patch.set_facecolor(INK["surface"])
for ax, (task, ng) in zip(axes, long_tasks):
    style(ax)
    for i, m in enumerate(ORDER):
        rs = [e for e in eps if e["case"] == task and e["thinking"] == m]
        v = [e["final"]["repaired"] / e["final"]["n_goals"] for e in rs]; k = sum(bool(e["final"]["all_done"]) for e in rs)
        ax.bar(i, np.mean(v), 0.62, color=MC[m], alpha=0.28)
        ax.scatter(i + np.linspace(-0.16, 0.16, len(v)), v, s=36, color=MC[m], edgecolor="white", linewidth=0.8, zorder=3)
        ax.text(i, 1.06, f"{k}/{len(rs)}", ha="center", fontsize=11.5, color=INK["text"], fontweight="bold")
        ax.text(i, np.mean(v) - 0.07 if np.mean(v) > 0.2 else np.mean(v) + 0.03, f"{np.mean(v):.2f}", ha="center", fontsize=10, color=INK["text2"])
    ax.set_title(f"{task.split('/')[1]}（{ng} 个子目标）", fontsize=12.5, color=INK["text"], loc="left", fontweight="bold")
    ax.set_xticks(range(4)); ax.set_xticklabels(["仅快", "完整计划", "建议注入", "建议注入\n禁缓存"], fontsize=10.5, color=INK["text"])
    ax.set_ylim(0, 1.15); ax.grid(axis="y", color=INK["grid"]); ax.set_axisbelow(True); ax.tick_params(axis="x", length=0)
axes[0].set_ylabel("子目标完成率（每点一局，柱为均值）", fontsize=11, color=INK["text2"])
fig.text(0.01, 0.005, "柱顶数字：5 局中整任务成功的局数。快分支均为 Jev；计分器 v6。", fontsize=10.5, color=INK["text2"])
fig.tight_layout(rect=(0, 0.04, 1, 1)); save(fig, "fig_r3_long.png")

# ---------- 5. case5 逐局 ----------
c5 = [e for e in eps if e["case"] == "Memory_Exploration/case5"]
c5b = [e for e in episodes(R3B) if e["case"] == "Memory_Exploration/case5"]
for e in c5b: e["thinking"] = "r3b"
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 5.2), dpi=180, gridspec_kw={"width_ratios": [1.35, 1]}); fig.patch.set_facecolor(INK["surface"])
style(ax1); style(ax2)
nfail = lambda e: sum(1 for h in e["history"] if not h["ok"] and h["call"] != "<invalid reply>")
for m in ORDER + ["r3b"]:
    rs = [e for e in c5 + c5b if e["thinking"] == m]
    xs = [e["sim_time"] for e in rs]; ys_ = [e["final"]["repaired"] / e["final"]["n_goals"] for e in rs]
    kw = dict(s=70, color=MC[m], edgecolor="white", linewidth=0.8, zorder=3) if m != "r3b" else dict(s=70, facecolor="none", edgecolor=MC[m], linewidth=1.8, zorder=3)
    ax1.scatter(xs, ys_, label=MN[m], **kw)
ax1.set_xlabel("episode 用时（s，上限 300）", fontsize=11, color=INK["text2"]); ax1.set_ylabel("子目标完成率", fontsize=11, color=INK["text2"])
ax1.set_xlim(0, 310); ax1.set_ylim(0.45, 1.0); ax1.grid(color=INK["grid"]); ax1.set_axisbelow(True)
ax1.legend(fontsize=10, frameon=False, loc="lower right"); ax1.set_title("Memory_Exploration case5：每点一局", fontsize=12.5, color=INK["text"], loc="left", fontweight="bold")
for i, m in enumerate(ORDER + ["r3b"]):
    rs = [e for e in c5 + c5b if e["thinking"] == m]; v = [nfail(e) for e in rs]
    ax2.barh(i, np.mean(v), 0.6, color=MC[m], alpha=0.3); ax2.scatter(v, [i] * len(v), s=36, color=MC[m], zorder=3)
    ax2.text(max(v) + 1.0, i, f"均值 {np.mean(v):.1f}", va="center", fontsize=10.5, color=INK["text"])
ax2.set_yticks(range(5)); ax2.set_yticklabels([MN[m] for m in ORDER + ["r3b"]], fontsize=10.5, color=INK["text"]); ax2.invert_yaxis()
ax2.set_xlabel("每局失败技能数", fontsize=11, color=INK["text2"]); ax2.grid(axis="x", color=INK["grid"]); ax2.set_axisbelow(True); ax2.tick_params(axis="y", length=0)
ax2.set_xlim(0, 36)
fig.tight_layout(); save(fig, "fig_r3_case5.png")

# ---------- 6. 慢分支延迟 ----------
grp = [("dual_shared_jev", "Ideal/case6", "完整计划 · 事件任务"), ("dual_shared_jev", "Memory", "完整计划 · 长任务"),
       ("dual_advice_jev", "Ideal/case6", "建议注入 · 事件任务"), ("dual_advice_jev", "Memory", "建议注入 · 长任务"),
       ("dual_advice_jev_bust", "Memory", "建议注入（禁缓存）· 长任务")]
fig = newfig(11.5, 4.6); ax = fig.add_subplot(111); style(ax)
for i, (m, tsk, lab_) in enumerate(grp):
    lat = [c["latency"] for e in eps if e["thinking"] == m and e["case"].startswith(tsk) for c in e["calls"] if c.get("branch") == "slow" and c.get("latency")]
    y = len(grp) - 1 - i; col = MC[m]
    ax.scatter(lat, y + np.random.default_rng(i).uniform(-0.18, 0.18, len(lat)), s=18, color=col, alpha=0.75, edgecolor="none", zorder=3)
    med = float(np.median(lat)); ax.plot([med, med], [y - 0.3, y + 0.3], color=INK["text"], linewidth=2.2, zorder=4)
    ax.text(260, y, f"中位数 {med:.1f} s，n = {len(lat)}", va="center", fontsize=11, color=INK["text"])
ax.set_yticks(range(len(grp))); ax.set_yticklabels([g[2] for g in grp][::-1], fontsize=11.5, color=INK["text"]); ax.tick_params(axis="y", length=0)
ax.set_xscale("log"); ax.set_xlim(1, 1500); ax.set_xticks([1, 3, 10, 30, 100]); ax.set_xticklabels(["1", "3", "10", "30", "100"])
ax.set_xlabel("慢分支单次调用延迟（s，对数轴；只统计 episode 结束前返回的调用）", fontsize=11, color=INK["text2"])
ax.grid(axis="x", color=INK["grid"]); ax.set_axisbelow(True)
fig.tight_layout(); save(fig, "fig_r3_slow_latency.png")

# ---------- 7. case5 时间线 ----------
VERB = {"pick": "拿", "place": "放到", "place_on_object": "放入", "pour": "倒入", "open_drawer": "开", "close_drawer": "关", "turnon": "开", "wait": "等待"}
SHORT = {"butter_1": "黄油", "chefmate_8_frypan_1": "锅", "wine_bottle_1": "酒", "white_yellow_mug_1": "杯", "flat_stove_1": "灶",
         "wooden_cabinet_1_top_region": "上层", "wooden_cabinet_1_middle_region": "中层", "wooden_cabinet_1_bottom_region": "下层",
         "coffee_table_table_region": "桌面", "flat_stove_1_cook_region": "灶面"}


def tl_load(d):
    ev = json.load(open(d / "timeline.json"))["events"]; t0 = ev[0]["sim"]; end = next(e["sim"] for e in ev if e["type"] == "episode_end") - t0
    thinks, op = [], {}
    for e in ev:
        if e["type"] == "think_start": op[str(e.get("step_idx"))] = e
        elif e["type"] == "think_end" and str(e.get("step_idx")) in op:
            s = op.pop(str(e["step_idx"])); thinks.append((s["sim"] - t0, e["sim"] - t0, s.get("branch", "fast"), True))
    for k, s in op.items(): thinks.append((s["sim"] - t0, end, s.get("branch", "fast"), False))          # 结束时仍未返回
    skills, st = [], {}
    for e in ev:
        if e["type"] == "skill_started": st[e["cid"]] = e
        elif e["type"] in ("skill_finished", "skill_cancelled") and e["cid"] in st:
            s = st.pop(e["cid"]); nm = s.get("skill") or ""; verb = nm.split("(")[0]; arg = nm.split("'")[1] if "'" in nm else ""
            skills.append((s["sim"] - t0, e["sim"] - t0, VERB.get(verb, verb) + SHORT.get(arg, ""), bool(e.get("ok"))))
    pubs = [(e["sim"] - t0, e["type"]) for e in ev if e["type"] in ("advice_published", "plan_published", "plan_rejected")]
    return thinks, skills, pubs, end


rows_tl = [("双分支·完整计划·Jev（种子 1）", R3 / "Memory_Exploration_case5" / "noevent_dualshared_jev_s1"),
           ("双分支·建议注入·Jev（种子 1）", R3 / "Memory_Exploration_case5" / "noevent_dualadvice_jev_s1")]
fig, axes = plt.subplots(2, 1, figsize=(15.5, 5.4), dpi=180, sharex=True); fig.patch.set_facecolor(INK["surface"])
for ax, (title, d) in zip(axes, rows_tl):
    style(ax); thinks, skills, pubs, end = tl_load(d)
    for a0, b0, br, done in thinks:
        if br == "slow":
            ax.barh(2, max(b0 - a0, 0.5), left=a0, height=0.5, color="#6250d6" if "shared" in d.name else "#eb6834",
                    hatch=None if done else "//", edgecolor="white" if done else "#ffffff", alpha=1.0 if done else 0.55)
            if not done and "shared" in d.name: ax.text(a0 + 1, 2, "完整计划生成中，直到 episode 结束仍未返回", va="center", fontsize=10.5, color="white", fontweight="bold")
            if not done and "advice" in d.name: ax.text(a0 - 0.8, 2, "\"完成\"核实请求，episode 结束时未返回 →", ha="right", va="center", fontsize=10, color="#eb6834")
        else:
            ax.barh(1, max(b0 - a0, 0.25), left=a0, height=0.5, color="#008300")
    for a0, b0, nm, ok in skills:
        ax.barh(0, b0 - a0, left=a0, height=0.5, color="#eb6834" if False else ("#b9b8b3" if ok else "#e34948"), edgecolor="white", linewidth=0.8)
        if b0 - a0 > 2.4: ax.text((a0 + b0) / 2, 0, nm, ha="center", va="center", fontsize=9.5, color="white" if not ok else INK["text"])
    ax.axvline(end, color=INK["text"], linestyle=":", linewidth=1.5)
    ax.set_yticks([0, 1, 2]); ax.set_yticklabels(["技能", "快分支决策", "慢分支"], fontsize=10.5, color=INK["text2"]); ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.5, 2.5); ax.set_title(title, loc="left", fontsize=12, color=INK["text"], fontweight="bold", pad=4)
    ax.grid(axis="x", color=INK["grid"]); ax.set_axisbelow(True)
axes[-1].set_xlabel("时间（s）；虚线 = episode 结束（快分支连续两次判断完成）", fontsize=11, color=INK["text2"]); axes[-1].set_xlim(0, 100)
fig.legend(handles=[Patch(color="#6250d6", label="慢分支：完整计划（开思考）"), Patch(color="#eb6834", label="慢分支：建议（关思考）"),
                    Patch(color="#008300", label="快分支决策（Jev）"), Patch(color="#b9b8b3", label="技能成功"), Patch(color="#e34948", label="技能失败")],
           loc="lower center", ncol=5, fontsize=10.5, frameon=False, bbox_to_anchor=(0.5, -0.01))
fig.tight_layout(rect=(0, 0.07, 1, 1)); save(fig, "fig_r3_timeline_case5.png")

# ---------- 8. KV 缓存 ----------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.0, 4.6), dpi=180, gridspec_kw={"width_ratios": [1, 1.25]}); fig.patch.set_facecolor(INK["surface"])
style(ax1); style(ax2)
vals = [("首次请求（未命中）", 1.61, INK["muted"]), ("重复请求（命中 3,136 token）", 0.26, "#008300"), ("重复请求 + 随机 cache_salt", 1.52, "#e87ba4")]
for i, (lab_, v, col) in enumerate(vals):
    ax1.barh(2 - i, v, 0.55, color=col); ax1.text(v + 0.03, 2 - i, f"{v:.2f} s", va="center", fontsize=12, color=INK["text"], fontweight="bold")
ax1.set_yticks([2, 1, 0]); ax1.set_yticklabels([v[0] for v in vals], fontsize=11, color=INK["text"]); ax1.tick_params(axis="y", length=0)
ax1.set_xlim(0, 2.0); ax1.set_xlabel("同一 3,551 token 提示的请求延迟（s）", fontsize=11, color=INK["text2"])
ax1.set_title("实测：命中按 784 token 整块计，3,136 = 4 × 784", fontsize=12, color=INK["text"], loc="left", fontweight="bold")
ax1.grid(axis="x", color=INK["grid"]); ax1.set_axisbelow(True)
w = 0.36
for i, (task, _) in enumerate(long_tasks):
    p50 = []
    for m in ("dual_advice_jev", "dual_advice_jev_bust"):
        lat = [c["latency"] for e in eps if e["thinking"] == m and e["case"] == task for c in e["calls"] if c.get("branch") == "fast" and c.get("latency")]
        p50.append(float(np.median(lat)))
    ax2.bar(i - w / 2, p50[0], w, color="#eb6834"); ax2.bar(i + w / 2, p50[1], w, color="#e87ba4")
    ax2.text(i - w / 2, p50[0] + 0.02, f"{p50[0]:.2f}", ha="center", fontsize=10.5, color=INK["text"])
    ax2.text(i + w / 2, p50[1] + 0.02, f"{p50[1]:.2f}", ha="center", fontsize=10.5, color=INK["text"])
ax2.set_xticks(range(4)); ax2.set_xticklabels([t.split("/")[1] for t, _ in long_tasks], fontsize=11, color=INK["text"]); ax2.tick_params(axis="x", length=0)
ax2.set_ylabel("Jev 快分支单次决策中位数（s）", fontsize=11, color=INK["text2"]); ax2.set_ylim(0, 1.45)
ax2.legend(handles=[Patch(color="#eb6834", label="双分支·建议注入·Jev（共享前缀）"), Patch(color="#e87ba4", label="同上，禁缓存")], fontsize=10.5, frameon=False, loc="upper left")
ax2.set_title("长任务：共享前缀对快分支决策延迟的影响", fontsize=12, color=INK["text"], loc="left", fontweight="bold")
ax2.grid(axis="y", color=INK["grid"]); ax2.set_axisbelow(True)
fig.tight_layout(); save(fig, "fig_r3_kv.png")


# ---------- 9. 场景总览（标注） ----------
def scene(name, labels, out, title_right):
    img = imageio.imread(FR / f"{name}_wide.png"); av = imageio.imread(FR / f"{name}_agentview.png")
    fig = plt.figure(figsize=(15.5, 6.6), dpi=150); fig.patch.set_facecolor(INK["surface"])
    ax = fig.add_axes([0.0, 0.0, 0.72, 1.0]); ax.imshow(img); ax.axis("off")
    for text, (px, py), (tx, ty), col in labels:
        ax.annotate(text, xy=(px, py), xytext=(tx, ty), fontsize=16, color=col, fontweight="bold", ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col, lw=1.2, alpha=0.93),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=1.6, shrinkA=2, shrinkB=3))
    ax2 = fig.add_axes([0.745, 0.2, 0.245, 0.62]); ax2.imshow(av); ax2.axis("off")
    ax2.set_title(title_right, fontsize=14, color=INK["text"], loc="left", pad=6)
    save(fig, out)


P5 = json.load(open(FR / "case5_scene_wide_pts.json"))
scene("case5_scene", [
    ("机械臂（Franka Panda）", P5["robot0_base"], (300, 90), INK["text"]),
    ("灶台 flat_stove_1\n平底锅最终要放在这里", P5["flat_stove_1_cook_region"], (200, 560), "#e34948"),
    ("白黄杯 white_yellow_mug_1", P5["white_yellow_mug_1"], (430, 250), "#2a78d6"),
    ("酒瓶 wine_bottle_1", P5["wine_bottle_1"], (560, 560), "#2a78d6"),
    ("干扰物：通心粉盒", P5["macaroni_and_cheese_1"], (860, 235), INK["text2"]),
    ("平底锅 chefmate_8_frypan_1（柜后）", P5["chefmate_8_frypan_1"], (1010, 300), "#eb6834"),
    ("木柜 wooden_cabinet_1：上 / 中 / 下三层抽屉\n黄油 butter_1 在下层抽屉内（关闭时不可见）", P5["butter_1"], (930, 680), "#6250d6"),
], "fig_r3_scene_case5.png", "模型实际收到的图像\n（256×256，此处放大）")
P6 = json.load(open(FR / "case6_scene_wide_pts.json"))
scene("case6_scene", [
    ("机械臂（Franka Panda）", P6["robot0_base"], (300, 90), INK["text"]),
    ("矮柜 short_cabinet_1\n黄油要放进中层抽屉", (300, 385), (230, 600), "#6250d6"),
    ("黄油 butter_1", P6["butter_1"], (500, 560), "#eb6834"),
    ("番茄酱 tomato_sauce_1", P6["tomato_sauce_1"], (850, 250), "#2a78d6"),
    ("盘子 plate_1（番茄酱倒入处；\nE1 中改为黄油的新目标）", P6["plate_1"], (900, 600), "#2a78d6"),
    ("干扰物：巧克力布丁", P6["chocolate_pudding_1"], (560, 230), INK["text2"]),
], "fig_r3_scene_case6.png", "模型实际收到的图像\n（256×256，此处放大）")
