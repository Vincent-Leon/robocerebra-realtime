// 组会 PPT（2026-10-25）：实时快慢思考基准本周进展。数据来自 notes/figs_lb/ 的排行榜统计（analyze_leaderboard.py 输出）。
// 用法: NODE_PATH=<含 pptxgenjs 的 node_modules> node make_group_deck_1025.js <pptx skill 目录>
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const SKILL = process.argv[2];
const { applyTheme } = require(path.join(SKILL, "scripts/apply_theme.js"));

const ROOT = path.resolve(__dirname, "..");
const LB = JSON.parse(fs.readFileSync(path.join(ROOT, "notes/figs_lb/leaderboard_llm_l20_r4lb.json"), "utf8"));
const EPS = JSON.parse(fs.readFileSync(path.join(ROOT, "notes/figs_lb/leaderboard_llm_l20_r4lb_episodes.json"), "utf8"));
const OUT = path.join(ROOT, "notes/组会_2026-10-25_本周进展.pptx");
const FEISHU = "https://my.feishu.cn/docx/YIoZdmnn0ofpsJxY9Vic73zjnah";
const REPO = "https://github.com/Vincent-Leon/robocerebra-realtime";

const THEME = {
  name: "RoboCerebra Realtime",
  headFontFace: "PingFang SC",
  bodyFontFace: "PingFang SC",
  colors: {
    dk1: "1D1D1F", lt1: "FFFFFF", dk2: "0F4C5C", lt2: "EEF3F4",
    accent1: "0F4C5C", accent2: "EB6834", accent3: "2A78D6", accent4: "008300", accent5: "6250D6", accent6: "B8860B",
    hlink: "2A78D6", folHlink: "6250D6",
  },
};
const MODE = {   // 与报告图一致的模式颜色
  fast_shared_text: { name: "仅快·文本", color: "2A78D6" },
  fast_shared_jev: { name: "仅快·Jev", color: "008300" },
  fast_shared_think: { name: "仅慢（每步开思考）", color: "B8860B" },
  dual_shared_jev: { name: "双分支·完整计划·Jev", color: "6250D6" },
  dual_advice_jev: { name: "双分支·建议注入·Jev", color: "EB6834" },
};
const MUTED = "6B7378", GRID = "D9DEE0";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                       // 13.33 × 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "实时快慢思考基准：本周进展";
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: THEME.colors.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.1, w: 11.7, h: 1.2, fontSize: 42, bold: true, color: C.background1, align: "left", valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.45, w: 11.7, h: 0.7, fontSize: 22, color: C.background2, align: "left", valign: "top", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "meta", type: "body", x: 0.8, y: 6.3, w: 11.7, h: 0.5, fontSize: 14, color: C.background2, align: "left", valign: "middle", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: THEME.colors.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.8, fontSize: 32, bold: true, color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "实时快慢思考基准 · 组会 2026-10-25", options: { x: 0.6, y: 7.0, w: 8, h: 0.3, fontSize: 10, color: MUTED, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: MUTED, align: "right" },
});

function text(slide, s, o) { slide.addText(s, Object.assign({ isTextBox: true, margin: 0, fontSize: 14, color: C.text1, valign: "top" }, o)); }
function card(slide, x, y, w, h, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: C.background2 }, line: { color: C.background2 }, rectRadius: 0.12, objectName: name });
}
const rowsByMode = Object.fromEntries(LB.rows.map(r => [r.mode, r]));
const pct = v => `${Math.round(v * 100)}%`;
const f3 = v => v.toFixed(3);

// ---------- 1. 封面 ----------
pres.addSection({ title: "开场" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "开场" });
s.addText("实时快慢思考基准：本周进展", { placeholder: "title" });
s.addText("RoboCerebra 60 任务排行榜 · 与路线 A 的合并", { placeholder: "body" });
s.addText("Vincent　|　2026-10-25 组会", { placeholder: "meta" });
[["60", "个任务"], ["5", "种推理模式"], ["900", "局实时运行"]].forEach(([n, l], i) => {
  text(s, [{ text: n, options: { fontSize: 40, bold: true, color: C.background1, breakLine: true } }, { text: l, options: { fontSize: 14, color: C.background2 } }],
       { x: 0.8 + i * 2.6, y: 4.55, w: 2.4, h: 1.2, objectName: `cover-stat-${i}` });
});
s.addNotes("本周主要做了两件事：一是按师兄的要求，在 RoboCerebra 全部 60 个任务上做了实时排行榜；二是和 Noah 的路线 A 合并成一份文档和一个代码仓库。先过一下上次组会行动项的完成情况。");

// ---------- 2. 行动项 ----------
pres.addSection({ title: "进展" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "进展" });
s.addText("上次组会行动项：均已完成，外部基线待定", { placeholder: "title" });
const H = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
const done = { text: "完成", options: { bold: true, color: C.accent4 } }, pend = { text: "待定", options: { bold: true, color: C.accent2 } };
const items = [
  ["执行器修正", done, "12 个试点任务的标准计划 95/129 → 116/129；60 任务版本冻结，参考线 0.832"],
  ["Prompt 注入（建议注入）", done, "慢分支关思考、一次 2–3 s；60 任务上整任务成功最多、用时最短"],
  ["计分器 v6", done, "探索步骤不计顺序；演示回放：官方计分 248/405，修复版 400/405"],
  ["不可达评分目标", done, "10/60 个任务的评分站点未在场景中声明，已补进区域列表"],
  ["KV 缓存调研", done, "vLLM 按 784 token 一块缓存；禁缓存对照改用请求级 cache_salt"],
  ["外部模型基线", pend, "需要 API 密钥与预算"],
  ["60 任务排行榜（新增）", done, "5 种模式 × 60 个任务 × 3 批 = 900 局"],
  ["与路线 A 合并（新增）", done, "飞书合并文档 + GitHub 私有仓库"],
];
s.addTable([[H("行动项"), H("状态"), H("结果")], ...items.map(([a, b, c]) => [{ text: a, options: { bold: true } }, b, c])], {
  x: 0.6, y: 1.35, w: 12.1, colW: [3.1, 1.1, 7.9], fontSize: 14, color: C.text1, rowH: 0.56, valign: "middle",
  border: { type: "solid", pt: 0.75, color: GRID }, autoPage: false, objectName: "action-items",
});
s.addNotes("上次组会定的行动项：执行器修正、Prompt 注入、计分器修正、KV 缓存调研都已完成。外部模型基线需要 API 密钥和预算，等组里定。另外新增了 60 任务排行榜和与路线 A 的合并。");

// ---------- 3. 排行榜设置 ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "进展" });
s.addText("排行榜设置：同一模型，5 种推理模式", { placeholder: "title" });
[["60", "个任务（6 类 × 10）"], ["5", "种推理模式"], ["3", "批（随机种子）"], ["900", "局，全部通过实时性检查"]].forEach(([n, l], i) => {
  const x = 0.6 + (i % 2) * 2.25, y = 1.45 + Math.floor(i / 2) * 2.15;
  card(s, x, y, 2.05, 1.9, `setup-stat-${i}`);
  text(s, [{ text: n, options: { fontSize: 40, bold: true, color: C.accent1, breakLine: true } }, { text: l, options: { fontSize: 14, color: C.text1 } }],
       { x: x + 0.2, y: y + 0.25, w: 1.7, h: 1.5 });
});
const modes = [
  ["仅快·文本", "关闭思考，每步直接输出 JSON 动作"],
  ["仅快·Jev", "合法动作列成选项，只输出 1 个 token 选字母"],
  ["仅慢（每步开思考）", "每步先思考（≤ 4096 token）再输出动作"],
  ["双分支·完整计划·Jev", "快分支持续决策；慢分支后台思考，给整段计划"],
  ["双分支·建议注入·Jev", "慢分支关思考，给 ≤ 2 句建议注入快分支"],
];
s.addTable([[H("模式"), H("做法")], ...modes.map(([m, d]) => [{ text: m, options: { bold: true } }, d])], {
  x: 5.3, y: 1.45, w: 7.4, colW: [2.75, 4.65], fontSize: 14, color: C.text1, rowH: 0.62, valign: "middle",
  border: { type: "solid", pt: 0.75, color: GRID }, autoPage: false, objectName: "modes",
});
text(s, "模型 Qwen3.8-27B（FP8，L20 单卡，vLLM，开前缀缓存）。仿真时间与墙钟 1:1，模型思考时场景不停；每局上限 300 s、40 次技能。随机扰动、描述错位按官方评测代码实现。",
     { x: 5.3, y: 5.45, w: 7.4, h: 0.9, fontSize: 13, color: MUTED });
s.addNotes("参考 VISTA 排行榜的格式：同一个 Qwen3.8-27B，5 种推理模式，60 个任务，3 个种子，共 900 局。全部实时运行，模型思考时机械臂和场景继续运行。运行中有 9 局因电脑卡顿不合格，已重跑。");

// ---------- 4. 结果一：全程得分 ----------
pres.addSection({ title: "结果" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "结果" });
s.addText("结果一：给满 300 秒，前四名分不开", { placeholder: "title" });
const order = ["fast_shared_text", "dual_advice_jev", "fast_shared_jev", "dual_shared_jev", "fast_shared_think"];
const lbRows = order.map((m, i) => {
  const r = rowsByMode[m];
  return [String(i + 1), { text: MODE[m].name, options: { bold: true, color: MODE[m].color } }, `${f3(r.score)} ± ${f3(r.sd)}`, pct(r.succ),
          `${r.fast_p50.toFixed(2)} s`, `${Math.round(r.time_med)} s`];
});
lbRows.push(["–", { text: "参考：标准计划（无语言模型）", options: { italic: true } }, f3(LB.gt.score), pct(LB.gt.succ), "–", "–"]);
s.addTable([[H("#"), H("模式"), H("得分（± 批间 SD）"), H("整任务成功"), H("单次决策"), H("每任务用时")], ...lbRows], {
  x: 0.6, y: 1.45, w: 8.6, colW: [0.45, 3.05, 1.95, 1.15, 1.0, 1.0], fontSize: 14, color: C.text1, rowH: 0.6, valign: "middle",
  border: { type: "solid", pt: 0.75, color: GRID }, autoPage: false, objectName: "leaderboard",
});
card(s, 9.6, 1.45, 3.1, 2.0, "callout-range");
const top4 = order.slice(0, 4).map(m => rowsByMode[m].score);
text(s, [{ text: `${f3(Math.min(...top4))}–${f3(Math.max(...top4))}`, options: { fontSize: 30, bold: true, color: C.accent1, breakLine: true } }, { text: "前四名全程得分", options: { fontSize: 14 } }], { x: 9.85, y: 1.7, w: 2.7, h: 1.5 });
card(s, 9.6, 3.7, 3.1, 2.4, "callout-paired");
text(s, [{ text: "不显著", options: { fontSize: 30, bold: true, color: C.accent1, breakLine: true } },
         { text: "各模式与仅快·Jev 的逐任务得分差，95% 区间都包含 0", options: { fontSize: 14 } }], { x: 9.85, y: 3.95, w: 2.7, h: 2.0 });
text(s, "得分 = 子目标完成率（修复版计分），60 个任务取平均。参考线是近似上限：它失败不重试，模型在 7–11 个任务上超过了它。",
     { x: 0.6, y: 5.85, w: 8.6, h: 0.7, fontSize: 12, color: MUTED });
s.addNotes("给满 300 秒时，前四名得分在 0.707 到 0.724 之间，批间标准差 0.004 到 0.028。逐任务配对比较，和仅快·Jev 的差都不显著。约一半任务各模式得分完全一样，全程得分主要受执行器能力限制。仅慢 0.674，也不显著。参考线 0.832 是不用语言模型、按演示步骤执行的结果。");

// ---------- 5. 结果二：时间预算 ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "结果" });
s.addText("结果二：时间一收紧，决策速度决定得分", { placeholder: "title" });
const TS = Array.from({ length: 31 }, (_, i) => i * 10);
const series = order.map(m => {
  const v = EPS.filter(e => e.mode === m);
  const vals = TS.map(t => v.reduce((a, e) => a + e.events.filter(x => x <= t).length / Math.max(e.n, 1), 0) / v.length);
  return { name: MODE[m].name, labels: TS.map(String), values: vals.map(x => Math.round(x * 1000) / 1000) };
});
s.addChart(pres.charts.LINE, series, {
  x: 0.6, y: 1.35, w: 8.4, h: 5.35, chartColors: order.map(m => MODE[m].color), lineSize: 2.5, lineDataSymbol: "none",
  showTitle: true, title: "已完成子目标比例（180 局均值）随时间变化", titleFontSize: 14, titleColor: THEME.colors.dk1, titleFontFace: "+mn-lt",
  showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt",
  catAxisTitle: "开局后的时间（s）", showCatAxisTitle: true, catAxisTitleFontSize: 12, catAxisLabelFrequency: 3,
  catAxisLabelFontSize: 12, catAxisLabelColor: MUTED, catAxisLabelFontFace: "+mn-lt", catAxisTitleColor: MUTED,
  valAxisMinVal: 0, valAxisMaxVal: 0.8, valAxisMajorUnit: 0.2, valAxisLabelFormatCode: "0.0", valAxisLabelFontSize: 12, valAxisLabelColor: MUTED, valAxisLabelFontFace: "+mn-lt",
  valGridLine: { color: GRID, size: 0.75 }, catGridLine: { style: "none" }, objectName: "anytime-chart",
});
const b60 = m => rowsByMode[m].budget["60"];
const j3 = ["fast_shared_jev", "dual_shared_jev", "dual_advice_jev"].map(b60);
const d60 = m => Math.abs(LB.pairs.find(p => p.mode === m && p.budget === 60).diff).toFixed(3);
card(s, 9.4, 1.35, 3.3, 5.35, "budget-callout");
text(s, [
  { text: "60 秒时", options: { fontSize: 18, bold: true, color: C.accent1, breakLine: true } },
  { text: `${Math.min(...j3).toFixed(3)}–${Math.max(...j3).toFixed(3)}`, options: { fontSize: 30, bold: true, color: C.accent4, breakLine: true } },
  { text: "三种 Jev 快分支模式", options: { fontSize: 14, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: b60("fast_shared_text").toFixed(3), options: { fontSize: 30, bold: true, color: MODE.fast_shared_text.color, breakLine: true } },
  { text: `仅快·文本：比仅快·Jev 低 ${d60("fast_shared_text")}，显著`, options: { fontSize: 14, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: b60("fast_shared_think").toFixed(3), options: { fontSize: 30, bold: true, color: MODE.fast_shared_think.color, breakLine: true } },
  { text: `仅慢：比仅快·Jev 低 ${d60("fast_shared_think")}，显著`, options: { fontSize: 14 } },
], { x: 9.65, y: 1.6, w: 2.85, h: 4.9 });
s.addNotes("横轴是开局后的时间，纵轴是已完成的子目标比例。三种用 Jev 做快分支的模式，60 秒时约 0.61；仅快·文本 0.563，显著落后，到 120 秒左右才追平；每步开思考只有 0.316，到 300 秒曲线还在往上走。所以排行榜建议同时报告全程得分和 60 秒得分。");

// ---------- 6. 结果三：行为差异 ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "结果" });
s.addText("结果三：四种模式各有短板", { placeholder: "title" });
const cards = [
  ["dual_shared_jev", "完整计划：计划来得太晚", ["慢分支 56 s 一次，首个计划中位数 40 s 才到", "此时快分支已完成约 0.55 的子目标", "只有 4.1% 的技能来自计划"]],
  ["dual_advice_jev", "建议注入：更完整、更快，但会提前收工", ["整任务成功 76/180（仅快·Jev 66/180）", "每任务 97 s（仅快·Jev 135 s），失败技能约减半", "31 局没做完就宣布完成"]],
  ["fast_shared_jev", "仅快·Jev：最快，但反复试错", ["单次决策 0.51 s", "失败技能中位数 16 次", "67/180 局用完 40 次技能机会"]],
  ["fast_shared_think", "仅慢：时间不够用", ["单次决策 12.5 s，p95 55 s", "每局中位数只做 8 次决策", "122/180 局到 300 s 仍未完成"]],
];
cards.forEach(([m, head, lines], i) => {
  const x = 0.6 + (i % 2) * 6.15, y = 1.4 + Math.floor(i / 2) * 2.75;
  card(s, x, y, 5.95, 2.5, `mode-card-${i}`);
  text(s, head, { x: x + 0.3, y: y + 0.25, w: 5.4, h: 0.5, fontSize: 19, bold: true, color: MODE[m].color });
  s.addText(lines.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < lines.length - 1 } })),
            { x: x + 0.3, y: y + 0.85, w: 5.4, h: 1.5, fontSize: 15, color: C.text1, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
});
s.addNotes("四种模式的短板各不相同。完整计划的慢分支一次要 56 秒，计划到的时候快分支已经做完一半多，所以和仅快·Jev 几乎一样。建议注入整任务成功最多、用时最短、失败最少，但有 31 局没做完就说做完了，这是下一步要解决的。仅快·Jev 最快但容易反复试同一个失败动作。仅慢则是时间不够。");

// ---------- 7. 与路线 A 合并 ----------
pres.addSection({ title: "合并与下一步" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "合并与下一步" });
s.addText("与路线 A 合并：两条路线互补", { placeholder: "title" });
const routes = [
  ["路线 A：学习策略直接控制（Noah）", ["公开 VLA 策略（OpenVLA-OFT、SmolVLA）直接输出机械臂动作", "Ideal 10 个任务：完整任务 0/10，子目标最多 2/76", "原生 LIBERO 9/9；RoboCerebra 上独立抓取 4 组全部失败"]],
  ["路线 B：语言模型实时调度（Vincent）", ["语言模型选技能与参数，真值技能执行器执行", "60 个任务 × 5 种模式 × 3 批，实时排行榜", "回答：执行可靠时，快慢调度的收益与代价"]],
];
routes.forEach(([head, lines], i) => {
  const x = 0.6 + i * 6.15;
  card(s, x, 1.4, 5.95, 2.85, `route-card-${i}`);
  text(s, head, { x: x + 0.3, y: 1.62, w: 5.4, h: 0.5, fontSize: 19, bold: true, color: C.accent1 });
  s.addText(lines.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < lines.length - 1 } })),
            { x: x + 0.3, y: 2.25, w: 5.4, h: 1.85, fontSize: 15, color: C.text1, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
});
s.addTable([
  [H("演示状态回放（Ideal 10 个任务）"), H("路线 A"), H("路线 B")],
  ["官方计分", { text: "55/76", options: { bold: true } }, { text: "55/76（逐任务相同）", options: { bold: true } }],
  ["修复版计分（v6）", "–", { text: "75/76", options: { bold: true, color: C.accent4 } }],
], { x: 0.6, y: 4.5, w: 7.6, colW: [3.4, 1.6, 2.6], fontSize: 14, color: C.text1, rowH: 0.5, valign: "middle",
     border: { type: "solid", pt: 0.75, color: GRID }, autoPage: false, objectName: "replay-table" });
text(s, [
  { text: "两边的回放流程一致，差别只来自计分器。", options: { bold: true, breakLine: true } },
  { text: "飞书合并文档", options: { hyperlink: { url: FEISHU }, color: C.accent3, breakLine: true } },
  { text: "GitHub 私有仓库 Vincent-Leon/robocerebra-realtime", options: { hyperlink: { url: REPO }, color: C.accent3 } },
], { x: 8.6, y: 4.55, w: 4.1, h: 1.6, fontSize: 14, paraSpaceAfter: 6 });
s.addNotes("Noah 用公开的 VLA 策略直接输出动作，回答学习策略能不能执行；我用语言模型调度真值技能，回答实时调度的收益。两边独立做的演示状态回放，在官方计分下逐任务一致，都是 55/76，说明差别只来自计分器。合并文档在飞书，代码在 GitHub 私有仓库，老师和师兄都已邀请。");

// ---------- 8. 下一步 ----------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "合并与下一步" });
s.addText("下一步，以及需要组里决定的事", { placeholder: "title" });
card(s, 0.6, 1.4, 6.5, 5.3, "next-steps");
text(s, "下一步", { x: 0.9, y: 1.62, w: 6, h: 0.5, fontSize: 19, bold: true, color: C.accent1 });
const next = [
  ["共同", "统一计分口径（建正反例测试集），核对场景与版本"],
  ["路线 B", "完成判定先核实；让完整计划更早到达；排行榜加 60 秒得分一栏"],
  ["路线 A", "独立技能达到每技能 9/10 的门槛"],
  ["对接", "达标的学习技能接入实时框架，用同一套排行榜评测"],
];
s.addText(next.map(([who, what], j) => ({ text: `${who}：${what}`, options: { bullet: { type: "number" }, breakLine: j < next.length - 1 } })),
          { x: 0.9, y: 2.25, w: 5.95, h: 4.2, fontSize: 15, color: C.text1, paraSpaceAfter: 10, valign: "top", margin: 0, isTextBox: true });
card(s, 7.3, 1.4, 5.4, 5.3, "decisions");
text(s, "需要组里决定", { x: 7.6, y: 1.62, w: 4.9, h: 0.5, fontSize: 19, bold: true, color: C.accent2 });
const asks = [`排行榜主指标是否改成"全程 + 60 秒"两栏`, "外部模型基线：用哪个模型、预算多少", `上次纪要中"训练集加噪声以丰富缓存命中"的具体含义`, "是否补微波炉技能（补的话排行榜需重跑，约 15 小时）"];
s.addText(asks.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < asks.length - 1 } })),
          { x: 7.6, y: 2.25, w: 4.85, h: 4.2, fontSize: 15, color: C.text1, paraSpaceAfter: 10, valign: "top", margin: 0, isTextBox: true });
s.addNotes("下一步：两人一起统一计分口径、核对场景版本；我这边解决提前宣布完成和计划来得太晚，排行榜固定加 60 秒得分；Noah 的技能达到门槛后接进实时框架。需要组里定四件事：排行榜主指标、外部模型基线的预算、上次说的训练集加噪声具体指什么、要不要补微波炉技能。");

// ---------- 9. 备份：分类别 ----------
pres.addSection({ title: "备份" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "备份" });
s.addText("备份：分类别得分", { placeholder: "title" });
s.addImage({ path: path.join(ROOT, "notes/figs_lb/fig_lb_category.png"), x: 1.4, y: 1.3, w: 9.5, h: 5.0, sizing: { type: "contain", w: 9.5, h: 5.0 }, altText: "分类别得分热力图：5 种模式 × 6 类任务，末行为标准计划参考", objectName: "category-heatmap" });
text(s, "差距最大的两类：记忆·执行 0.48–0.67（参考 0.85），随机扰动 0.65–0.70（参考 0.86）；记忆·探索接近参考。",
     { x: 1.4, y: 6.35, w: 10.5, h: 0.5, fontSize: 13, color: MUTED });
s.addNotes("如果被问到哪类任务最难：记忆·执行和随机扰动离参考线最远，记忆·探索基本接近参考线。");

pres.writeFile({ fileName: OUT }).then(async () => { await applyTheme(OUT, THEME); console.log("saved", OUT); });
