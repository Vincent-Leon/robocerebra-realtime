"""生成排行榜静态网页（单个自包含 HTML，离线可用）：notes/leaderboard/index.html。
数据：notes/figs_lb/leaderboard_llm_l20_r4lb.json 与 _episodes.json（analyze_leaderboard.py 输出），标准计划参考 runs/gtplan_r4_final。
页面里由逐局记录现算：任意时间预算下的得分、批间 SD、整任务成功率、与仅快·Jev 的逐任务配对比较（bootstrap）、分类别得分、得分随时间累积曲线。
用法: python make_leaderboard_page.py
同时输出 notes/leaderboard/embed.html：供飞书文档 html5-block 嵌入的版本（加 use-iframe / 高度模式 / 描述三个 meta，去掉页头大标题）。
"""
import json, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LB = json.load(open(ROOT / "notes/figs_lb/leaderboard_llm_l20_r4lb.json", encoding="utf-8"))
EPS = json.load(open(ROOT / "notes/figs_lb/leaderboard_llm_l20_r4lb_episodes.json", encoding="utf-8"))
OUT = ROOT / "notes/leaderboard/index.html"

# 固定顺序与颜色（已用 dataviz 校验脚本验证：浅色 / 深色模式相邻配对均通过）
MODES = [
    {"key": "fast_shared_jev", "name": "仅快·Jev", "desc": "当前所有合法动作列成选项，模型只输出 1 个 token（选项字母）"},
    {"key": "fast_shared_text", "name": "仅快·文本", "desc": "关闭思考，每步直接输出一个 JSON 动作"},
    {"key": "fast_shared_think", "name": "仅慢（每步开思考）", "desc": "每步先思考（≤ 4096 token）再输出动作"},
    {"key": "dual_shared_jev", "name": "双分支·完整计划·Jev", "desc": "快分支 Jev 持续决策；慢分支在后台开思考，输出整段计划"},
    {"key": "dual_advice_jev", "name": "双分支·建议注入·Jev", "desc": "快分支 Jev 持续决策；慢分支关思考，输出 ≤ 2 句建议注入快分支"},
]
KEYS = [m["key"] for m in MODES]
TYPES = ["Ideal", "Memory_Execution", "Memory_Exploration", "Mix", "Observation_Mismatching", "Random_Disturbance"]
TYPE_CN = ["理想", "记忆·执行", "记忆·探索", "混合", "描述错位", "随机扰动"]

tasks = sorted({e["task"] for e in EPS}, key=lambda t: (TYPES.index(t.split("/")[0]), int(t.split("case")[1])))
eps = [[KEYS.index(e["mode"]), tasks.index(e["task"]), int(e["seed"]), int(e["n"]), sorted(round(float(x), 1) for x in e["events"])] for e in EPS]
rows = {}
for r in LB["rows"]:
    rows[r["mode"]] = {k: r[k] for k in ("fast_p50", "fast_p95", "slow_p50", "time_med", "tok_med", "tok_cached_med", "gpu_med", "fail_med", "n")}
    rows[r["mode"]].update({"tok_mean": r["tok_mean"], "ends": r["ends"]})
gt = {}
for f in glob.glob(str(ROOT / "exp/runs/gtplan_r4_final/*/result.json")):
    r = json.load(open(f)); exc = int(r.get("excluded", 0))
    gt[r["task"]] = [(r["repaired_done"] - exc) / max(r["n_goals"] - exc, 1), bool(r["repaired_all"])]
DATA = {
    "modes": MODES, "rows": [rows[k] for k in KEYS], "tasks": tasks, "taskCat": [TYPES.index(t.split("/")[0]) for t in tasks],
    "cats": TYPE_CN, "seeds": sorted({e[2] for e in eps}), "eps": eps,
    "gt": [gt.get(t, [None, False]) for t in tasks], "ref": 0,
    "meta": {"date": "2026-10-22", "episodes": len(eps), "rerun": 9,
             "feishu": "https://my.feishu.cn/docx/YIoZdmnn0ofpsJxY9Vic73zjnah", "repo": "https://github.com/Vincent-Leon/robocerebra-realtime"},
}

HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RoboCerebra 实时快慢思考排行榜</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --ring: rgba(11,11,11,0.10); --wash: rgba(11,11,11,0.045);
  --m0: #008300; --m1: #2a78d6; --m2: #eda100; --m3: #6250d6; --m4: #eb6834;
  --tok0: #c3c2b7; --tok1: #86b6ef; --tok2: #1c5cab;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b; --up: #006300;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10); --wash: rgba(255,255,255,0.06);
    --m0: #008300; --m1: #3987e5; --m2: #c98500; --m3: #9085e9; --m4: #d95926;
    --tok0: #52514e; --tok1: #3987e5; --tok2: #9ec5f4; --up: #0ca30c;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10); --wash: rgba(255,255,255,0.06);
  --m0: #008300; --m1: #3987e5; --m2: #c98500; --m3: #9085e9; --m4: #d95926;
  --tok0: #52514e; --tok1: #3987e5; --tok2: #9ec5f4; --up: #0ca30c;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.6 system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif; }
.wrap { max-width: 1320px; margin: 0 auto; padding: 32px 24px 64px; }
header { display: flex; gap: 24px; align-items: flex-start; justify-content: space-between; }
header > div { flex: 1 1 auto; }
h1 { font-size: 30px; line-height: 1.25; margin: 0 0 6px; font-weight: 650; letter-spacing: 0.01em; }
.sub { color: var(--ink2); margin: 0; }
.links { margin-top: 8px; font-size: 14px; color: var(--ink2); }
a { color: var(--m1); text-decoration: none; } a:hover { text-decoration: underline; }
.btn { white-space: nowrap; flex: none; font: inherit; font-size: 13px; color: var(--ink2); background: var(--surface); border: 1px solid var(--ring); border-radius: 8px; padding: 5px 12px; cursor: pointer; }
.btn:hover { background: var(--wash); }
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 24px 0 8px; }
.tile { background: var(--surface); border: 1px solid var(--ring); border-radius: 12px; padding: 16px 18px; }
.tile .label { color: var(--ink2); font-size: 13px; }
.tile .value { font-size: 30px; font-weight: 650; line-height: 1.2; margin-top: 2px; }
.tile .note { color: var(--muted); font-size: 12px; margin-top: 2px; }
.filters { position: sticky; top: 0; z-index: 5; background: var(--page); display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 14px 0; margin-top: 12px; border-bottom: 1px solid var(--grid); }
.filters .flabel { font-weight: 600; font-size: 14px; }
.seg { display: inline-flex; border: 1px solid var(--ring); border-radius: 10px; overflow: hidden; background: var(--surface); }
.seg button { font: inherit; font-size: 14px; border: 0; background: transparent; color: var(--ink2); padding: 6px 14px; cursor: pointer; }
.seg button + button { border-left: 1px solid var(--ring); }
.seg button:hover { background: var(--wash); }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--surface); font-weight: 600; }
.verdict { color: var(--ink2); font-size: 14px; flex: 1 1 380px; }
.verdict b { color: var(--ink); }
.card { background: var(--surface); border: 1px solid var(--ring); border-radius: 14px; padding: 20px 22px; margin-top: 20px; }
.card h2 { font-size: 18px; margin: 0; font-weight: 650; }
.card .how { color: var(--ink2); font-size: 13.5px; margin: 4px 0 12px; }
.card-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.grid2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; }
.grid2 > .card { margin-top: 20px; }
h3.section { font-size: 15px; color: var(--ink2); font-weight: 600; margin: 36px 0 0; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 8px 7px; border-bottom: 1px solid var(--grid); vertical-align: middle; }
th { color: var(--ink2); font-weight: 600; font-size: 13px; white-space: nowrap; }
th.sortable { cursor: pointer; user-select: none; } th.sortable:hover { color: var(--ink); }
th .arrow { font-size: 11px; margin-left: 3px; color: var(--muted); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.ref td { color: var(--ink2); font-style: italic; }
tr:hover td { background: var(--wash); }
.rank { font-weight: 650; font-size: 16px; font-variant-numeric: tabular-nums; }
.mode { display: flex; align-items: center; gap: 9px; }
#lb td:nth-child(2) { min-width: 210px; }
#lb td:nth-child(4) { min-width: 140px; }
.dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.mname { font-weight: 600; }
.mdesc, .sub { color: var(--muted); font-size: 12px; line-height: 1.4; }
.scorecell { display: flex; align-items: center; gap: 8px; min-width: 180px; }
.bar { position: relative; flex: 1; height: 10px; background: var(--wash); border-radius: 0 4px 4px 0; min-width: 64px; }
.bar > i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 0 4px 4px 0; }
.bar > em { position: absolute; top: -4px; bottom: -4px; width: 1px; background: var(--ink2); }
.scoreval { font-variant-numeric: tabular-nums; font-weight: 650; white-space: nowrap; }
.sd { color: var(--muted); font-weight: 400; font-size: 12.5px; }
.sig { white-space: nowrap; font-variant-numeric: tabular-nums; line-height: 1.5; }
.sig .ci { display: block; }
.sig .tag { display: inline-block; font-size: 12px; padding: 1px 7px; border-radius: 999px; margin-left: 6px; border: 1px solid var(--ring); color: var(--ink2); }
.sig .tag.yes { color: var(--ink); font-weight: 600; border-color: var(--ink2); }
.ci { color: var(--muted); font-size: 12.5px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--ink2); margin: 2px 0 8px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.key-line { width: 16px; height: 2px; border-radius: 1px; display: inline-block; }
.key-rect { width: 11px; height: 11px; border-radius: 2px; display: inline-block; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { fill: var(--ink2); font-size: 12px; font-family: inherit; }
svg .axis-label { fill: var(--muted); font-size: 12px; }
svg .lbl { fill: var(--ink); font-size: 12.5px; }
svg .halo { paint-order: stroke; stroke: var(--surface); stroke-width: 4px; stroke-linejoin: round; }
.tablebox { display: none; margin-top: 10px; overflow-x: auto; } .tablebox.on { display: block; }
#tip { position: fixed; pointer-events: none; z-index: 20; background: var(--surface); color: var(--ink); border: 1px solid var(--ring); border-radius: 10px; padding: 9px 12px; font-size: 13px; box-shadow: 0 6px 24px rgba(0,0,0,0.12); display: none; min-width: 150px; }
#tip .t { color: var(--ink2); font-size: 12px; margin-bottom: 4px; }
#tip .r { display: flex; align-items: center; gap: 8px; line-height: 1.7; }
#tip .r b { font-variant-numeric: tabular-nums; min-width: 44px; }
#tip .r span { color: var(--ink2); }
.notes { color: var(--ink2); font-size: 14px; }
.notes li { margin: 4px 0; }
footer { color: var(--muted); font-size: 12.5px; margin-top: 28px; }
@media (max-width: 860px) { .grid2 { grid-template-columns: 1fr; } .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  #lb .mdesc { display: none; } #lb td:nth-child(2) { min-width: 150px; } .scorecell { min-width: 150px; } .bar { min-width: 44px; } }
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>RoboCerebra 实时快慢思考排行榜</h1>
    <p class="sub">同一模型 Qwen3.8-27B（FP8，vLLM，前缀缓存）· 5 种推理模式 · RoboCerebra 全部 60 个任务 · 3 批（随机种子）共 900 局 · 实时运行：仿真时间 = 墙钟时间，模型思考时场景不停</p>
    <div class="links" id="links"></div>
  </div>
  <button class="btn" id="themeBtn" type="button">外观：自动</button>
</header>

<section class="kpis" id="kpis" aria-label="概况"></section>

<div class="filters" role="group" aria-label="时间预算">
  <span class="flabel">时间预算</span>
  <div class="seg" id="budgetSeg"></div>
  <div class="verdict" id="verdict" aria-live="polite"></div>
</div>

<section class="card">
  <div class="card-head"><div><h2>排行榜</h2>
  <p class="how">按所选时间预算下的得分排名：每局只统计开局后预算时间内完成的子目标。点击表头可改变排序。"与仅快·Jev 的差"是同一任务上两种模式得分之差的均值，区间为按任务重抽样 10000 次的 95% 区间，区间不含 0 才算显著。双分支模式之所以和它比，是因为它们用的就是同一个快分支。</p></div></div>
  <div style="overflow-x:auto"><table id="lb"></table></div>
</section>

<div class="grid2">
  <section class="card">
    <div class="card-head"><div><h2>得分与单次决策延迟</h2><p class="how">横轴为单次决策延迟中位数（对数轴；双分支取快分支），纵轴为所选预算下的得分，越靠左上越好。误差棒为 3 批之间的标准差，细线连接帕累托前沿（没有别的模式比它更快且得分更高）。</p></div>
    <button class="btn" data-table="scatterTable" type="button">数据表</button></div>
    <div id="scatter"></div><div class="tablebox" id="scatterTable"></div>
  </section>
  <section class="card">
    <div class="card-head"><div><h2>得分随时间累积</h2><p class="how">开局后各时刻已完成的子目标比例（每种模式 180 局的均值）。曲线越靠左上，得分来得越早；竖线标出所选时间预算。鼠标移到图上可读各模式的数值。</p></div>
    <button class="btn" data-table="curveTable" type="button">数据表</button></div>
    <div class="legend" id="curveLegend"></div>
    <div id="curves"></div><div class="tablebox" id="curveTable"></div>
  </section>
</div>

<section class="card">
  <div class="card-head"><div><h2>分类别得分</h2><p class="how">6 类任务各 10 个，每格是该模式在该类任务上的平均得分（3 批共 30 局），得分越高，格子颜色越醒目（浅色外观下越深，深色外观下越亮）。末行"参考：标准计划"为不用语言模型、按演示步骤执行的结果，只有全程数据。</p></div>
  <button class="btn" data-table="heatTable" type="button">数据表</button></div>
  <div id="heat"></div><div class="tablebox" id="heatTable"></div>
</section>

<h3 class="section">成本与行为（以下不随时间预算变化，均按全程统计）</h3>
<div class="grid2">
  <section class="card">
    <div class="card-head"><div><h2>每任务 token 构成</h2><p class="how">每局 token 的均值：缓存输入（命中前缀缓存，可复用）、非缓存输入、输出。条末数字为非缓存输入 + 输出，即 VISTA 排行榜的 token 口径。</p></div>
    <button class="btn" data-table="tokTable" type="button">数据表</button></div>
    <div class="legend" id="tokLegend"></div>
    <div id="tok"></div><div class="tablebox" id="tokTable"></div>
  </section>
  <section class="card">
    <div class="card-head"><div><h2>每局怎么结束</h2><p class="how">每种模式 180 局的结束原因。"宣布完成（未做完）"指模型认为任务已完成而停止，但仍有子目标没完成。</p></div>
    <button class="btn" data-table="endTable" type="button">数据表</button></div>
    <div class="legend" id="endLegend"></div>
    <div id="ends"></div><div class="tablebox" id="endTable"></div>
  </section>
</div>

<section class="card">
  <h2>说明</h2>
  <ul class="notes">
    <li><b>得分</b>：每个任务的子目标完成率（修复版计分），60 个任务取平均；没做完的任务按完成的部分计分。描述错位类开局已完成的子目标不计入。</li>
    <li><b>± 批间 SD</b>：3 批（随机种子）各自 60 个任务均值之间的标准差。</li>
    <li><b>整任务成功</b>：在所选预算内完成了全部子目标的局数占比。</li>
    <li><b>单次决策</b>：模型做一次决定的延迟中位数；双分支取快分支，慢分支在后台运行。<b>每任务用时</b>：一局的时长（中位数），全部完成、模型宣布完成、40 次技能用尽或 300 s 到时，最先发生者结束一局。</li>
    <li><b>每任务 token</b>：非缓存输入 + 输出（中位数）。<b>GPU 时间</b>：一局内模型调用延迟之和（中位数）；模型是自部署的，用它代替 VISTA 的美元成本。</li>
    <li><b>参考：标准计划</b>：同一执行器按人类演示的子步顺序调用技能、不用语言模型，可看作执行器能力的近似上限；它失败不重试，所以个别任务上模型能超过它。</li>
    <li>每局最多 300 s、40 次技能。实时性判据：开局 3 s 后最大滞后 ≤ 0.25 s、p95 ≤ 50 ms；不满足的 <span id="rerun"></span> 局已在同一代码版本上重跑。</li>
  </ul>
</section>
<footer id="foot"></footer>
</div>
<div id="tip" role="tooltip"></div>

<script>
const DATA = __DATA__;
const MODES = DATA.modes, M = MODES.length, T = DATA.tasks.length, REF = DATA.ref;
const BUDGETS = [30, 60, 120, 180, Infinity];
const blabel = b => b === Infinity ? "全程（300 秒）" : b + " 秒";
const bshort = b => b === Infinity ? "全程" : b + " 秒";
const mcol = i => `var(--m${i})`;
const state = { B: Infinity, sortKey: "score", sortDir: -1 };
const SVGNS = "http://www.w3.org/2000/svg";

function el(tag, attrs, ...kids) {
  const svg = ["svg", "g", "line", "rect", "circle", "path", "text", "polyline", "title"].includes(tag);
  const e = svg ? document.createElementNS(SVGNS, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined) continue;
    if (k === "style" && typeof v === "object") Object.assign(e.style, v);
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c !== null && c !== undefined && c !== false) e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return e;
}
const f3 = v => v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(3);
const sgn = v => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(3);
const pct = v => Math.round(v * 100) + "%";

// ---------- 计算 ----------
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const NB = 10000; const RS = (() => { const r = mulberry32(20261022); const out = new Uint8Array(NB * T); for (let i = 0; i < out.length; i++) out[i] = Math.floor(r() * T); return out; })();
function cnt(ev, B) { if (B === Infinity) return ev.length; let c = 0; for (const x of ev) { if (x <= B) c++; else break; } return c; }
const cache = new Map();
function compute(B) {
  if (cache.has(B)) return cache.get(B);
  const acc = MODES.map(() => ({ sum: 0, n: 0, succ: 0, seed: {}, task: new Float64Array(T), taskN: new Float64Array(T), cat: new Float64Array(6), catN: new Float64Array(6) }));
  for (const [m, t, s, n, ev] of DATA.eps) {
    const c = cnt(ev, B), sc = c / Math.max(n, 1), a = acc[m];
    a.sum += sc; a.n++; if (c >= n) a.succ++;
    (a.seed[s] = a.seed[s] || [0, 0]); a.seed[s][0] += sc; a.seed[s][1]++;
    a.task[t] += sc; a.taskN[t]++; const k = DATA.taskCat[t]; a.cat[k] += sc; a.catN[k]++;
  }
  const out = acc.map(a => {
    const bm = Object.values(a.seed).map(([x, y]) => x / y), mu = bm.reduce((p, q) => p + q, 0) / bm.length;
    const sd = bm.length > 1 ? Math.sqrt(bm.reduce((p, q) => p + (q - mu) ** 2, 0) / (bm.length - 1)) : null;
    return { score: a.sum / a.n, sd, succ: a.succ / a.n, task: Array.from(a.task, (v, i) => v / a.taskN[i]), cat: Array.from(a.cat, (v, i) => v / a.catN[i]) };
  });
  out.forEach((o, m) => {
    if (m === REF) { o.pair = null; return; }
    const d = o.task.map((v, i) => v - out[REF].task[i]); const means = new Float64Array(NB);
    for (let b = 0; b < NB; b++) { let s = 0; for (let j = 0; j < T; j++) s += d[RS[b * T + j]]; means[b] = s / T; }
    means.sort();
    o.pair = { diff: d.reduce((p, q) => p + q, 0) / T, lo: means[Math.floor(0.025 * (NB - 1))], hi: means[Math.ceil(0.975 * (NB - 1))],
               win: d.filter(x => x > 1e-9).length, tie: d.filter(x => Math.abs(x) <= 1e-9).length, loss: d.filter(x => x < -1e-9).length };
    o.pair.sig = o.pair.lo > 0 ? 1 : (o.pair.hi < 0 ? -1 : 0);
  });
  const ranked = out.map((o, i) => i).sort((a, b) => out[b].score - out[a].score); ranked.forEach((m, r) => out[m].rank = r + 1);
  cache.set(B, out); return out;
}
const GT = (() => { const v = DATA.gt.filter(g => g[0] !== null); const cat = Array(6).fill(0), n = Array(6).fill(0);
  DATA.gt.forEach((g, t) => { if (g[0] !== null) { cat[DATA.taskCat[t]] += g[0]; n[DATA.taskCat[t]]++; } });
  return { score: v.reduce((p, g) => p + g[0], 0) / v.length, succ: v.filter(g => g[1]).length / v.length, cat: cat.map((x, i) => x / n[i]) }; })();
const CURVE = (() => { const TMAX = 300, out = MODES.map(() => new Float64Array(TMAX + 1)), cntm = new Array(M).fill(0);
  for (const [m, , , n, ev] of DATA.eps) { cntm[m]++; for (const x of ev) { const k = Math.max(0, Math.ceil(x)); if (k <= TMAX) out[m][k] += 1 / Math.max(n, 1); } }
  return out.map((h, m) => { let s = 0; return Array.from(h, v => (s += v) / cntm[m]); }); })();

// ---------- 提示框 ----------
const tip = document.getElementById("tip");
function showTip(ev, title, rows) {
  tip.replaceChildren(el("div", { class: "t", text: title }), ...rows.map(([color, val, lab, shape]) =>
    el("div", { class: "r" }, color ? el("span", { class: shape === "rect" ? "key-rect" : "key-line", style: { background: color } }) : null, el("b", { text: val }), el("span", { text: lab }))));
  tip.style.display = "block";
  const r = tip.getBoundingClientRect(); let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - 14; if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - 14;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
function hideTip() { tip.style.display = "none"; }
function focusTip(node, title, rows) {
  node.setAttribute("tabindex", "0");
  node.addEventListener("pointermove", e => showTip(e, title(), rows()));
  node.addEventListener("pointerleave", hideTip);
  node.addEventListener("focus", () => { const b = node.getBoundingClientRect(); showTip({ clientX: b.right, clientY: b.top }, title(), rows()); });
  node.addEventListener("blur", hideTip);
}

// ---------- 页头 ----------
function header() {
  const m = DATA.meta;
  document.getElementById("links").replaceChildren("统计日期 " + m.date + " · ", el("a", { href: m.feishu, target: "_blank", rel: "noopener", text: "飞书合并文档" }), " · ", el("a", { href: m.repo, target: "_blank", rel: "noopener", text: "GitHub 仓库（私有）" }));
  document.getElementById("rerun").textContent = m.rerun;
  const tiles = [["任务", "60", "6 类 × 10，含随机扰动与描述错位"], ["推理模式", "5", "同一模型、同一服务实例"], ["实时运行", m.episodes.toLocaleString(), "全部通过实时性检查"], ["参考线（标准计划）", GT.score.toFixed(3), "执行器能力的近似上限"]];
  document.getElementById("kpis").replaceChildren(...tiles.map(([l, v, n]) => el("div", { class: "tile" }, el("div", { class: "label", text: l }), el("div", { class: "value", text: v }), el("div", { class: "note", text: n }))));
  document.getElementById("foot").textContent = "数据：exp/runs/llm_l20_r4lb（每局 episode.json / timeline.json）；统计脚本 exp/analyze_leaderboard.py；本页由 exp/make_leaderboard_page.py 生成，所有数字在页面内由逐局记录现算。";
}
function budgetSeg() {
  const seg = document.getElementById("budgetSeg");
  seg.replaceChildren(...BUDGETS.map(b => el("button", { type: "button", "aria-pressed": String(b === state.B), text: bshort(b), onclick: () => { state.B = b; history.replaceState(null, "", b === Infinity ? location.pathname : "#" + b); renderAll(); } })));
}
function verdict() {
  const R = compute(state.B), up = [], dn = [], ns = [];
  R.forEach((o, m) => { if (m === REF) return; (o.pair.sig > 0 ? up : o.pair.sig < 0 ? dn : ns).push(MODES[m].name); });
  const v = document.getElementById("verdict"); v.replaceChildren(el("b", { text: blabel(state.B) + "：" }));
  if (up.length) v.append("显著高于仅快·Jev 的有 ", el("b", { text: up.join("、") }), "；");
  if (dn.length) v.append("显著低于仅快·Jev 的有 ", el("b", { text: dn.join("、") }), "；");
  if (ns.length) v.append(ns.join("、") + (ns.length === M - 1 ? " 与仅快·Jev 的差异都不显著。" : " 与仅快·Jev 差异不显著。"));
}

// ---------- 排行榜 ----------
const COLS = [
  { key: "rank", label: "排名", num: true, get: (o) => o.rank },
  { key: "mode", label: "模式", get: (o, m) => m },
  { key: "score", label: "得分（± 批间 SD）", get: o => o.score },
  { key: "pair", label: "与仅快·Jev 的差（95% 区间）", get: o => o.pair ? o.pair.diff : 0 },
  { key: "succ", label: "整任务成功", num: true, get: o => o.succ },
  { key: "lat", label: "单次决策", num: true, get: (o, m) => DATA.rows[m].fast_p50 },
  { key: "time", label: "每任务用时", num: true, get: (o, m) => DATA.rows[m].time_med },
  { key: "tok", label: "每任务 token", num: true, get: (o, m) => DATA.rows[m].tok_med },
  { key: "gpu", label: "GPU 时间", num: true, get: (o, m) => DATA.rows[m].gpu_med },
];
function leaderboard() {
  const R = compute(state.B), tbl = document.getElementById("lb");
  const order = R.map((o, m) => m);
  const col = COLS.find(c => c.key === state.sortKey);
  order.sort((a, b) => { const va = col.get(R[a], a), vb = col.get(R[b], b); return (va > vb ? 1 : va < vb ? -1 : 0) * state.sortDir || R[b].score - R[a].score; });
  const head = el("tr", {}, ...COLS.map(c => el("th", { class: (c.num ? "num " : "") + (c.key === "mode" ? "" : "sortable"), scope: "col",
    onclick: c.key === "mode" ? null : () => { if (state.sortKey === c.key) state.sortDir *= -1; else { state.sortKey = c.key; state.sortDir = ["rank", "lat", "time", "tok", "gpu"].includes(c.key) ? 1 : -1; } leaderboard(); } },
    c.label, state.sortKey === c.key ? el("span", { class: "arrow", text: state.sortDir > 0 ? "▲" : "▼" }) : null)));
  const showRef = state.B === Infinity;
  const body = order.map(m => {
    const o = R[m], r = DATA.rows[m];
    const bar = el("div", { class: "bar" }, el("i", { style: { width: (o.score * 100).toFixed(1) + "%", background: mcol(m) } }), showRef ? el("em", { style: { left: (GT.score * 100).toFixed(1) + "%" }, title: "参考线 " + GT.score.toFixed(3) }) : null);
    const p = o.pair;
    const sig = p ? el("div", { class: "sig" }, el("span", { text: sgn(p.diff) }),
      el("span", { class: "tag" + (p.sig ? " yes" : ""), text: p.sig > 0 ? "▲ 显著更高" : p.sig < 0 ? "▼ 显著更低" : "○ 不显著" }),
      el("span", { class: "ci", text: `[${sgn(p.lo)}, ${sgn(p.hi)}]` })) : el("span", { class: "ci", text: "基线" });
    const tr = el("tr", {},
      el("td", { class: "num rank", text: o.rank }),
      el("td", {}, el("div", { class: "mode" }, el("span", { class: "dot", style: { background: mcol(m) } }), el("div", {}, el("div", { class: "mname", text: MODES[m].name }), el("div", { class: "mdesc", text: MODES[m].desc })))),
      el("td", {}, el("div", { class: "scorecell" }, bar, el("span", { class: "scoreval" }, f3(o.score), " ", el("span", { class: "sd", text: o.sd !== null ? "± " + o.sd.toFixed(3) : "" })))),
      el("td", {}, sig),
      el("td", { class: "num", text: pct(o.succ) }),
      el("td", { class: "num", text: r.fast_p50.toFixed(2) + " s" + (r.slow_p50 ? "" : "") }),
      el("td", { class: "num", text: Math.round(r.time_med) + " s" }),
      el("td", { class: "num", text: (r.tok_med / 1000).toFixed(1) + " k" }),
      el("td", { class: "num", text: Math.round(r.gpu_med) + " s" }));
    if (r.slow_p50) tr.children[5].append(el("div", { class: "sub", text: "慢分支 " + r.slow_p50.toFixed(1) + " s" }));
    return tr;
  });
  const ref = el("tr", { class: "ref" }, el("td", { class: "num", text: "–" }),
    el("td", {}, el("div", { class: "mode" }, el("span", { class: "dot", style: { background: "var(--muted)" } }), el("div", {}, el("div", { class: "mname", text: "参考：标准计划" }), el("div", { class: "mdesc", text: "不用语言模型，按演示步骤执行" })))),
    el("td", {}, showRef ? el("div", { class: "scorecell" }, el("div", { class: "bar" }, el("i", { style: { width: (GT.score * 100).toFixed(1) + "%", background: "var(--muted)" } })), el("span", { class: "scoreval", text: GT.score.toFixed(3) })) : el("span", { class: "ci", text: "只有全程数据" })),
    el("td", {}, ""), el("td", { class: "num", text: showRef ? pct(GT.succ) : "—" }), el("td", { class: "num", text: "–" }), el("td", { class: "num", text: "–" }), el("td", { class: "num", text: "–" }), el("td", { class: "num", text: "–" }));
  tbl.replaceChildren(el("thead", {}, head), el("tbody", {}, ...body, ref));
}

// ---------- 坐标轴工具 ----------
function linear(d0, d1, r0, r1) { return v => r0 + (v - d0) / (d1 - d0) * (r1 - r0); }
function logs(d0, d1, r0, r1) { const a = Math.log(d0), b = Math.log(d1); return v => r0 + (Math.log(v) - a) / (b - a) * (r1 - r0); }

// ---------- 散点 ----------
function scatter() {
  const R = compute(state.B), W = 560, H = 380, L = 56, Rm = 24, Tp = 16, Bt = 48;
  const xs = DATA.rows.map(r => r.fast_p50), ys = R.map(o => o.score);
  const yLo = Math.max(0, Math.floor((Math.min(...ys.map((y, i) => y - (R[i].sd || 0)), state.B === Infinity ? GT.score : 1) - 0.05) * 20) / 20);
  const yHi = Math.min(1, Math.ceil((Math.max(...ys.map((y, i) => y + (R[i].sd || 0)), state.B === Infinity ? GT.score : 0) + 0.04) * 20) / 20);
  const X = logs(0.3, 30, L, W - Rm), Y = linear(yLo, yHi, H - Bt, Tp);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "得分与单次决策延迟散点图" });
  const yt = []; for (let v = yLo; v <= yHi + 1e-9; v += (yHi - yLo) > 0.3 ? 0.1 : 0.05) yt.push(+v.toFixed(2));
  yt.forEach(v => { svg.append(el("line", { x1: L, x2: W - Rm, y1: Y(v), y2: Y(v), style: { stroke: "var(--grid)" } }), el("text", { x: L - 8, y: Y(v) + 4, "text-anchor": "end", class: "axis-label", text: v.toFixed(2) })); });
  [0.3, 0.5, 1, 2, 5, 10, 20].forEach(v => { svg.append(el("line", { x1: X(v), x2: X(v), y1: Tp, y2: H - Bt, style: { stroke: "var(--grid)" } }), el("text", { x: X(v), y: H - Bt + 18, "text-anchor": "middle", class: "axis-label", text: v + " s" })); });
  svg.append(el("line", { x1: L, x2: W - Rm, y1: H - Bt, y2: H - Bt, style: { stroke: "var(--axis)" } }));
  svg.append(el("text", { x: (L + W - Rm) / 2, y: H - 8, "text-anchor": "middle", class: "axis-label", text: "单次决策延迟中位数（对数轴）" }));
  svg.append(el("text", { x: 14, y: (Tp + H - Bt) / 2, transform: `rotate(-90 14 ${(Tp + H - Bt) / 2})`, "text-anchor": "middle", class: "axis-label", text: "得分（" + bshort(state.B) + "）" }));
  if (state.B === Infinity) { const y = Y(GT.score); svg.append(el("line", { x1: L, x2: W - Rm, y1: y, y2: y, style: { stroke: "var(--ink2)", strokeWidth: 1 } }), el("text", { x: L + 6, y: y - 6, class: "axis-label", text: "参考：标准计划 " + GT.score.toFixed(3) })); }
  const ord = R.map((o, m) => m).sort((a, b) => xs[a] - xs[b]); let best = -1; const front = [];
  ord.forEach(m => { if (ys[m] > best) { front.push(m); best = ys[m]; } });
  if (front.length > 1) svg.append(el("polyline", { points: front.map(m => `${X(xs[m])},${Y(ys[m])}`).join(" "), style: { fill: "none", stroke: "var(--ink2)", strokeWidth: 1 } }));
  // 标签：延迟相近（1.5 倍以内）的点归为一簇，簇内标签在右侧排成一列，用引线连到点；单点标签直接放在点右侧
  const byX = R.map((o, m) => m).sort((a, b) => xs[a] - xs[b]); const clusters = [];
  byX.forEach(m => { const c = clusters[clusters.length - 1]; if (c && xs[m] <= xs[c[c.length - 1]] * 1.5) c.push(m); else clusters.push([m]); });
  const labels = [];
  clusters.forEach(c => {
    const colX = Math.max(...c.map(m => X(xs[m]))) + (c.length > 1 ? 44 : 12);
    c.slice().sort((a, b) => ys[b] - ys[a]).forEach((m, k, arr) => {
      let ly = Y(ys[m]) + 4;
      if (c.length > 1) { const top = Math.min(...arr.map(q => Y(ys[q]))) - (arr.length - 1) * 9; ly = top + k * 19 + 4; }
      labels.push({ m, x: colX, y: ly, lead: c.length > 1 });
    });
  });
  R.forEach((o, m) => {
    const x = X(xs[m]), y = Y(ys[m]), sd = o.sd || 0;
    svg.append(el("line", { x1: x, x2: x, y1: Y(ys[m] - sd), y2: Y(ys[m] + sd), style: { stroke: mcol(m), strokeWidth: 2, strokeLinecap: "round" } }));
  });
  labels.forEach(L2 => { if (L2.lead) svg.append(el("line", { x1: X(xs[L2.m]) + 7, y1: Y(ys[L2.m]), x2: L2.x - 4, y2: L2.y - 4, style: { stroke: "var(--axis)", strokeWidth: 1 } })); });
  R.forEach((o, m) => {
    const x = X(xs[m]), y = Y(ys[m]);
    const g = el("g", { "aria-label": MODES[m].name }); g.append(el("circle", { cx: x, cy: y, r: 14, style: { fill: "transparent" } }), el("circle", { cx: x, cy: y, r: 6, style: { fill: mcol(m), stroke: "var(--surface)", strokeWidth: 2 } }));
    focusTip(g, () => MODES[m].name, () => [[mcol(m), f3(R[m].score), "得分（" + bshort(state.B) + "）", "line"], [null, (R[m].sd !== null ? "± " + R[m].sd.toFixed(3) : "—"), "批间 SD"], [null, xs[m].toFixed(2) + " s", "单次决策延迟中位数"]]);
    svg.append(g);
  });
  labels.forEach(L2 => svg.append(el("text", { x: L2.x, y: L2.y, class: "lbl halo", text: MODES[L2.m].name })));
  document.getElementById("scatter").replaceChildren(svg);
  tableView("scatterTable", ["模式", "单次决策延迟中位数", "得分（" + bshort(state.B) + "）", "批间 SD", "帕累托前沿"],
    R.map((o, m) => [MODES[m].name, xs[m].toFixed(2) + " s", f3(o.score), o.sd !== null ? o.sd.toFixed(3) : "—", front.includes(m) ? "是" : "否"]));
}

// ---------- 曲线 ----------
function curves() {
  const W = 560, H = 380, L = 48, Rm = 16, Tp = 16, Bt = 48, X = linear(0, 300, L, W - Rm), Y = linear(0, 0.9, H - Bt, Tp);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "得分随时间累积曲线" });
  [0, 0.2, 0.4, 0.6, 0.8].forEach(v => svg.append(el("line", { x1: L, x2: W - Rm, y1: Y(v), y2: Y(v), style: { stroke: "var(--grid)" } }), el("text", { x: L - 8, y: Y(v) + 4, "text-anchor": "end", class: "axis-label", text: v.toFixed(1) })));
  [0, 60, 120, 180, 240, 300].forEach(v => svg.append(el("text", { x: X(v), y: H - Bt + 18, "text-anchor": "middle", class: "axis-label", text: v + " s" })));
  svg.append(el("line", { x1: L, x2: W - Rm, y1: Y(0), y2: Y(0), style: { stroke: "var(--axis)" } }));
  svg.append(el("text", { x: (L + W - Rm) / 2, y: H - 8, "text-anchor": "middle", class: "axis-label", text: "开局后的时间" }));
  const bx = X(state.B === Infinity ? 300 : state.B);
  svg.append(el("line", { x1: bx, x2: bx, y1: Tp, y2: H - Bt, style: { stroke: "var(--ink2)", strokeWidth: 1 } }), el("text", { x: Math.min(bx + 6, W - Rm - 60), y: Tp + 12, class: "axis-label", text: "预算 " + bshort(state.B) }));
  CURVE.forEach((c, m) => svg.append(el("polyline", { points: c.map((v, t) => `${X(t).toFixed(1)},${Y(v).toFixed(1)}`).join(" "), style: { fill: "none", stroke: mcol(m), strokeWidth: 2, strokeLinejoin: "round", strokeLinecap: "round" } })));
  const cross = el("line", { y1: Tp, y2: H - Bt, style: { stroke: "var(--axis)", strokeWidth: 1, display: "none" } }); svg.append(cross);
  const dots = MODES.map((_, m) => { const d = el("circle", { r: 4.5, style: { fill: mcol(m), stroke: "var(--surface)", strokeWidth: 2, display: "none" } }); svg.append(d); return d; });
  const hit = el("rect", { x: L, y: Tp, width: W - Rm - L, height: H - Bt - Tp, style: { fill: "transparent" }, tabindex: "0" }); svg.append(hit);
  const at = (e) => { const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; const p = pt.matrixTransform(svg.getScreenCTM().inverse()); return Math.max(0, Math.min(300, Math.round((p.x - L) / (W - Rm - L) * 300))); };
  const show = (e, t) => { cross.setAttribute("x1", X(t)); cross.setAttribute("x2", X(t)); cross.style.display = ""; dots.forEach((d, m) => { d.setAttribute("cx", X(t)); d.setAttribute("cy", Y(CURVE[m][t])); d.style.display = ""; });
    const order = MODES.map((_, m) => m).sort((a, b) => CURVE[b][t] - CURVE[a][t]);
    showTip(e, "开局后 " + t + " 秒", order.map(m => [mcol(m), CURVE[m][t].toFixed(3), MODES[m].name, "line"])); };
  hit.addEventListener("pointermove", e => show(e, at(e)));
  hit.addEventListener("pointerleave", () => { cross.style.display = "none"; dots.forEach(d => d.style.display = "none"); hideTip(); });
  hit.addEventListener("focus", () => { const b = hit.getBoundingClientRect(); show({ clientX: b.right - 20, clientY: b.top + 20 }, state.B === Infinity ? 300 : state.B); });
  hit.addEventListener("blur", () => { cross.style.display = "none"; dots.forEach(d => d.style.display = "none"); hideTip(); });
  document.getElementById("curves").replaceChildren(svg);
  document.getElementById("curveLegend").replaceChildren(...MODES.map((md, m) => el("span", {}, el("span", { class: "key-line", style: { background: mcol(m) } }), md.name)));
  const ts = [0, 30, 60, 90, 120, 150, 180, 240, 300];
  tableView("curveTable", ["时间", ...MODES.map(md => md.name)], ts.map(t => [t + " s", ...MODES.map((_, m) => CURVE[m][t].toFixed(3))]));
}

// ---------- 热力图 ----------
function heatColor(v) {
  const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  const ramp = dark ? ["#104281", "#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef", "#9ec5f4"]
                    : ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281"];
  const t = Math.max(0, Math.min(1, (v - 0.4) / (0.9 - 0.4))); const hex = ramp[Math.round(t * (ramp.length - 1))];
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = n >> 8 & 255, b = n & 255;
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return { fill: hex, ink: lum > 0.55 ? "#0b0b0b" : "#ffffff" };
}
function heat() {
  const R = compute(state.B), showRef = state.B === Infinity, rowsN = M + (showRef ? 1 : 0);
  const W = 1100, L = 200, cw = (W - L) / 6, ch = 40, Tp = 34, H = Tp + rowsN * ch + 8;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "分类别得分热力图" });
  DATA.cats.forEach((c, j) => svg.append(el("text", { x: L + cw * j + cw / 2, y: 20, "text-anchor": "middle", class: "lbl", text: c })));
  const rowsDef = R.map((o, m) => ({ name: MODES[m].name, color: mcol(m), vals: o.cat }));
  if (showRef) rowsDef.push({ name: "参考：标准计划", color: "var(--muted)", vals: GT.cat });
  rowsDef.forEach((row, i) => {
    const y = Tp + i * ch;
    svg.append(el("circle", { cx: 12, cy: y + ch / 2, r: 5, style: { fill: row.color } }), el("text", { x: 24, y: y + ch / 2 + 4.5, class: "lbl", text: row.name }));
    row.vals.forEach((v, j) => {
      const c = heatColor(v), x = L + cw * j;
      const g = el("g", {}, el("rect", { x: x + 1, y: y + 1, width: cw - 2, height: ch - 2, rx: 3, style: { fill: c.fill } }), el("text", { x: x + cw / 2, y: y + ch / 2 + 4.5, "text-anchor": "middle", style: { fill: c.ink, fontSize: "13px", fontVariantNumeric: "tabular-nums" }, text: v.toFixed(2) }));
      focusTip(g, () => row.name + " · " + DATA.cats[j], () => [[c.fill, v.toFixed(3), "平均得分（" + (i < M ? bshort(state.B) : "全程") + "）", "rect"], [null, i < M ? "30 局" : "10 个任务", "统计量"]]);
      svg.append(g);
    });
  });
  document.getElementById("heat").replaceChildren(svg);
  tableView("heatTable", ["模式", ...DATA.cats], rowsDef.map(r => [r.name, ...r.vals.map(v => v.toFixed(3))]));
}

// ---------- 堆叠条（token、结束原因） ----------
function stacked(targetId, legendId, tableId, parts, valueOf, endLabel, unit) {
  const W = 560, L = 150, Rm = 92, bh = 22, gap = 22, Tp = 6, H = Tp + M * (bh + gap);
  const totals = MODES.map((_, m) => parts.reduce((s, p) => s + valueOf(m, p.key), 0)), maxT = Math.max(...totals);
  const X = linear(0, maxT, L, W - Rm);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  MODES.forEach((md, m) => {
    const y = Tp + m * (bh + gap); let x0 = L;
    svg.append(el("circle", { cx: 8, cy: y + bh / 2, r: 5, style: { fill: mcol(m) } }), el("text", { x: 20, y: y + bh / 2 + 4.5, class: "lbl", text: md.name.length > 9 ? md.name.replace("（每步开思考）", "") : md.name }));
    parts.forEach((p, k) => {
      const v = valueOf(m, p.key), w = X(v) - L; if (w <= 0) return;
      const isLast = parts.slice(k + 1).every(q => valueOf(m, q.key) <= 0);
      const rect = el("rect", { x: x0, y, width: Math.max(0, w - 2), height: bh, rx: isLast ? 4 : 0, style: { fill: p.color } });
      const g = el("g", {}, rect); focusTip(g, () => md.name, () => [[p.color, p.fmt(v), p.label, "rect"]]); svg.append(g);
      if (isLast && w > 6) svg.append(el("rect", { x: x0, y, width: Math.max(0, Math.min(4, w - 2)), height: bh, style: { fill: p.color } }));
      x0 += w;
    });
    svg.append(el("text", { x: x0 + 6, y: y + bh / 2 + 4.5, class: "lbl", text: endLabel(m) }));
  });
  document.getElementById(targetId).replaceChildren(svg);
  document.getElementById(legendId).replaceChildren(...parts.map(p => el("span", {}, el("span", { class: "key-rect", style: { background: p.color } }), p.label)));
  tableView(tableId, ["模式", ...parts.map(p => p.label + (unit ? "（" + unit + "）" : ""))], MODES.map((md, m) => [md.name, ...parts.map(p => p.fmt(valueOf(m, p.key)))]));
}
function tokens() {
  const k = v => (v / 1000).toFixed(1) + " k";
  stacked("tok", "tokLegend", "tokTable", [
    { key: "tok_cached", label: "缓存输入", color: "var(--tok0)", fmt: k },
    { key: "tok_in_nc", label: "非缓存输入", color: "var(--tok1)", fmt: k },
    { key: "tok_out", label: "输出", color: "var(--tok2)", fmt: k }],
    (m, key) => DATA.rows[m].tok_mean[key], m => "非缓存 " + ((DATA.rows[m].tok_mean.tok_in_nc + DATA.rows[m].tok_mean.tok_out) / 1000).toFixed(1) + " k", "每局均值");
}
function ends() {
  const c = v => String(Math.round(v));
  stacked("ends", "endLegend", "endTable", [
    { key: "all_done", label: "✓ 全部完成", color: "var(--good)", fmt: c },
    { key: "planner_done", label: "! 宣布完成（未做完）", color: "var(--serious)", fmt: c },
    { key: "max_skills", label: "↻ 40 次技能用尽", color: "var(--warning)", fmt: c },
    { key: "max_sim", label: "⏱ 300 s 到时", color: "var(--critical)", fmt: c }],
    (m, key) => DATA.rows[m].ends[key] || 0, m => DATA.rows[m].ends.all_done + "/" + DATA.rows[m].n + " 完成", "局");
}

// ---------- 数据表视图 ----------
function tableView(id, head, rows) {
  document.getElementById(id).replaceChildren(el("table", {}, el("thead", {}, el("tr", {}, ...head.map((h, i) => el("th", { class: i ? "num" : "", text: h })))),
    el("tbody", {}, ...rows.map(r => el("tr", {}, ...r.map((v, i) => el("td", { class: i ? "num" : "", text: v })))))));
}
document.querySelectorAll("[data-table]").forEach(b => b.addEventListener("click", () => { const t = document.getElementById(b.dataset.table); t.classList.toggle("on"); b.textContent = t.classList.contains("on") ? "收起数据表" : "数据表"; }));

// ---------- 外观 ----------
const THEMES = [["", "外观：自动"], ["light", "外观：浅色"], ["dark", "外观：深色"]]; let ti = 0;
document.getElementById("themeBtn").addEventListener("click", () => { ti = (ti + 1) % 3; const [v, l] = THEMES[ti]; if (v) document.documentElement.dataset.theme = v; else delete document.documentElement.dataset.theme; document.getElementById("themeBtn").textContent = l; heat(); });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", heat);

function renderAll() { budgetSeg(); verdict(); leaderboard(); scatter(); curves(); heat(); }
const h0 = parseInt(location.hash.slice(1), 10); if (BUDGETS.includes(h0)) state.B = h0;
header(); renderAll(); tokens(); ends();
</script>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
payload = json.dumps(DATA, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
page = HTML.replace("__DATA__", payload)
OUT.write_text(page, encoding="utf-8")
print("saved", OUT, f"{OUT.stat().st_size / 1024:.0f} KB")
# 飞书 html5-block 嵌入版：声明 iframe 与自适应高度；文档本身已有标题，去掉页头大标题与外观按钮
META = ('<meta name="use-iframe" content="true">\n<meta name="html-box-height-mode" content="auto">\n'
        '<meta name="description" content="RoboCerebra 实时快慢思考排行榜：5 种推理模式在 60 个任务上的得分、延迟、token 与时间预算得分，可按时间预算切换排名">\n')
embed = page.replace('<meta name="viewport" content="width=device-width, initial-scale=1">', '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + META, 1)
embed = embed.replace('<h1>RoboCerebra 实时快慢思考排行榜</h1>', '', 1).replace('<button class="btn" id="themeBtn" type="button">外观：自动</button>', '<button class="btn" id="themeBtn" type="button" hidden>外观：自动</button>', 1)
embed = embed.replace(".wrap { max-width: 1320px; margin: 0 auto; padding: 32px 24px 64px; }", ".wrap { width: 100%; max-width: 100%; margin: 0; padding: 8px 4px 24px; }", 1)
EMB = OUT.with_name("embed.html"); EMB.write_text(embed, encoding="utf-8")
print("saved", EMB, f"{EMB.stat().st_size / 1024:.0f} KB")
