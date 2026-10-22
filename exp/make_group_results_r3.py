"""第三轮群发版 PDF：实验方法细节、数据、过程与图（面向熟悉领域但没读过论文与设计的课题组成员；正式方法名，不讲项目动机）。
生成单文件 HTML 并用 Chrome 导出 16:9 PDF；样式取自 make_talk_html.py，图来自 notes/figs_r3/（plot_r3_figs.py、render_r3_frames.py）。
用法: python -I make_group_results_r3.py <具身智能项目根目录>
"""
import base64, re, subprocess, sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve(); NOTES = ROOT / "notes"; FIG = NOTES / "figs_r3"
CSS = re.search(r"<style>.*?</style>", (ROOT / "exp" / "make_talk_html.py").read_text(encoding="utf-8"), re.S).group(0)
CSS = CSS.replace("</style>", """
  /* 第三轮补充样式 */
  .layout { display: flex; gap: 6px; margin: .4em 0 .2em; }
  .seg { border-radius: 8px; padding: .55em .5em; font-size: 17px; line-height: 1.35; text-align: center; color: #fff; }
  .seg.cache { background: #008300; } .seg.vol { background: #8a8984; } .seg.adv { background: var(--orange); font-weight: 700; }
  .brace { display: flex; gap: 6px; font-size: 15px; color: var(--ink2); }
  .brace div { border-top: 2px solid currentColor; padding-top: .25em; text-align: center; }
  .quote { font-family: "SF Mono", Menlo, monospace; font-size: 16px; line-height: 1.5; color: var(--ink); }
  td.q { font-size: 17px; }
  table.dense td, table.dense th { font-size: 17px; padding: .35em .55em; line-height: 1.45; }
  .small2 { font-size: 15px; color: var(--ink2); line-height: 1.5; }
  .flow { display: flex; align-items: stretch; gap: 10px; margin: .5em 0 .9em; }
  .node { flex: 1; background: var(--soft); border: 1px solid var(--line); border-radius: 12px; padding: .55em .6em; text-align: center; font-size: 18px; font-weight: 600; }
  .node small { display: block; font-weight: 400; color: var(--ink2); font-size: 15px; margin-top: .25em; line-height: 1.4; }
  .arr { align-self: center; font-size: 26px; color: var(--ink2); }
  pre.prompt { font-family: "SF Mono", Menlo, monospace; font-size: 13.2px; line-height: 1.42; background: #f6f6f4; border: 1px solid var(--line);
    border-radius: 10px; padding: .7em .9em; white-space: pre-wrap; margin: 0; color: var(--ink); }
  pre.prompt b { color: var(--orange); } pre.prompt i { color: var(--red); font-style: normal; font-weight: 700; }
  table.narr td, table.narr th { font-size: 15.5px; padding: .28em .5em; line-height: 1.38; }
  table.narr td.t { white-space: nowrap; font-variant-numeric: tabular-nums; color: var(--ink2); }
  .fail { color: var(--red); font-weight: 600; } .okc { color: var(--green); font-weight: 600; }
  .sec { font-size: 15px; color: var(--ink2); letter-spacing: 1px; }
  table.concl td, table.concl th { font-size: 14.2px; padding: .3em .5em; line-height: 1.42; }
  table.concl td b { color: var(--ink); }
</style>""")
FILES = {"scene5": "fig_r3_scene_case5.png", "scene6": "fig_r3_scene_case6.png", "grasp": "fig_r3_frames_grasp.png", "drawer": "fig_r3_frames_drawer.png", "gt": "fig_r3_gt.png", "scorer": "fig_r3_scorer_case8.png",
         "long": "fig_r3_long.png", "case5": "fig_r3_case5.png", "slow": "fig_r3_slow_latency.png", "tl": "fig_r3_timeline_case5.png", "kv": "fig_r3_kv.png"}
IMG = {k: "data:image/png;base64," + base64.b64encode((FIG / f).read_bytes()).decode() for k, f in FILES.items()}

BODY = r"""
<!-- 1 封面 -->
<section class="slide cover"><div class="wrap">
  <span class="tag">实验结果 · 2026-10-21</span>
  <h1 style="font-size: clamp(36px, 4.6vw, 70px);">实时快慢思考基准：第三轮实验结果</h1>
  <p class="sub">执行器 r3 · 计分器 v6 · Prompt 注入（建议模式）· vLLM 前缀缓存<br>第三轮 110 局 + 补测 5 局，全部通过实时性检查</p>
  <p class="one">核心结论：执行器修正后，标准计划完成率由 73.6% 升至 89.9%。修正了两个评测问题：官方子目标链对探索顺序要求过严（v6）；10/60 个任务各有一个评分目标对规划器不可达。建议注入把慢分支单次调用从 47–98 s 降到约 2.5 s，在唯一能区分方法的 case5 上完成率最高、用时最短、失败最少。多数试点任务已达上限，需要更难的任务。</p>
</div></section>

<!-- 2 结论速览 -->
<section class="slide"><div class="wrap">
  <span class="tag">结论速览</span>
  <h2 style="margin-bottom:.25em;">实验文档与组会问题：当前结论</h2>
  <p class="small2" style="margin:0 0 .5em;">"RQ"为实验计划文档中的研究问题，"组会"为 10-20 组会纪要中的讨论问题，"实验记录"为 Phase0 实验记录中的待解问题；"详见"为本文页码。</p>
  <table class="dense concl">
    <tr><th style="width:19%">问题（来源）</th><th style="width:21%">结论</th><th>简要说明</th><th style="width:7%">详见</th></tr>
    <tr><td>慢分支返回太慢、干预失效（组会）；同一模型并行快慢分支是否有效（RQ2）</td><td><b>完整计划无效；改为建议注入后有改善，证据有限</b></td><td>完整计划在长任务上中位 47–98 s，来自计划的动作只占 0–5%。建议注入（关思考、≤ 2 句）每次约 2.5 s；在唯一能区分方法的 case5 上，完成率 0.87（仅快 0.79），用时 102 s 对 183 s，失败技能 2.6 次对 10 次。其余任务各方法均满分；每组 5 个种子。</td><td class="num">22–25</td></tr>
    <tr><td>Prompt 注入的实际作用（组会）</td><td><b>建议到得快，但主要影响触发后的第二个决策；关思考的完成核实不可靠</b></td><td>快分支在技能结束后约 0.5 s 就决策，建议需要 2–3 s。补测中关思考的慢分支 3 次都误判"平底锅已在灶上"，加核实后完成率不升反降（0.79）。</td><td class="num">19, 21, 27</td></tr>
    <tr><td>快、慢推理的失败模式是否不同（RQ1）</td><td><b>部分支持</b></td><td>每步开思考约 9 s，E3 6 s 窗 0/5，会错过事件窗口（第二轮）；快分支在长任务上的典型失败是循环（反复开关抽屉、反复抓放）和过早判完成。执行器修正后多数长任务两类方法都能完成，长程依赖方面的证据还不足。</td><td class="num">21, 24</td></tr>
    <tr><td>共享上下文是否有收益（RQ3）；vLLM 缓存底层实现（组会）</td><td><b>支持；缓存机制已查清</b></td><td>共享前缀使快分支单次决策从 0.74–1.25 s 降到 0.51–0.59 s；case5 上禁缓存组完成率也更低（0.73）。命中按 784 token 整块计，这是 vLLM 为 GDN 混合架构自动设定的块大小；当前提示布局能正确复用前缀。</td><td class="num">24, 28</td></tr>
    <tr><td>快慢分支共享上下文的管理（组会）</td><td><b>现方案可用，暂不需改动</b></td><td>两个分支共用"系统提示 + 静态块 + 只追加的历史"作为前缀，易变内容与建议放在其后；vLLM 自动在请求间共享 KV 块，但不支持钉住前缀。若要更细的复用粒度，可改用 bf16 递归态把块缩到 400 token，需先验证精度。</td><td class="num">19, 28</td></tr>
    <tr><td>旧计划的有效性检查是否必要（RQ4）</td><td><b>必要</b></td><td>第一轮缺少检查时，双分支执行了过时步骤（如黄油未放就关抽屉）而失败；加入检查后能拦住过时计划，但长任务上的计划到达时多已不适用而被拒绝。</td><td class="num">25</td></tr>
    <tr><td>评测代码 Bug（组会）</td><td><b>原两处已修复；本轮又发现并修正两处</b></td><td>阻塞式监控、"盒顶误判为盒内"已在第二轮修复。本轮：官方子目标链要求复现演示的翻抽屉顺序（计分器 v6）；60 个任务中 10 个各有一个评分目标对规划器不可达。演示回放仍为 37/40。</td><td class="num">16–18</td></tr>
    <tr><td>长任务成败由执行器决定（实验记录）</td><td><b>已解决；但多数试点任务变得太简单</b></td><td>执行器 r3 后，标准计划完成率 73.6% → 89.9%。LLM 方法在 case10、case6、case8 上基本都能完成，多数试点任务对所有方法都已满分，需要更难的任务来区分方法。</td><td class="num">12–15, 22</td></tr>
    <tr><td>尚未开展（RQ5、RQ6、组会）</td><td><b>主动创造思考时间、同预算对照、外部模型基线、更多数据集、训练集加噪声</b></td><td>RQ5、RQ6 待设计实验。外部模型的无缓存基线需要 API 密钥与预算；OpenAI 会自动缓存 1,024 token 以上的提示，需主动禁用；推理模型不提供逐 token 概率，用不了 Jev。更多数据集建议先在 RoboCerebra 内选更难的任务。"训练集加噪声"含义待确认（目前不训练模型）。</td><td class="num">29</td></tr>
  </table>
</div></section>

<!-- 2 目录 -->
<section class="slide"><div class="wrap">
  <span class="tag gray">目录</span>
  <h2>本文内容</h2>
  <table class="dense">
    <tr><th style="width:24%">部分</th><th style="width:12%">页码</th><th>内容</th></tr>
    <tr><td>结论速览</td><td class="num">2</td><td>实验计划文档中的研究问题与组会讨论问题的当前结论</td></tr>
    <tr><td>一、实验方法</td><td class="num">4–11</td><td>一局实验如何运行；模型实际收到的输入；技能与执行器；任务与事件的原文和子目标；四种方法如何运行；指标与计分</td></tr>
    <tr><td>二、执行器修正（r3）</td><td class="num">12–15</td><td>问题、原因与修正；仿真画面；标准计划回归</td></tr>
    <tr><td>三、计分与任务定义</td><td class="num">16–18</td><td>计分器 v6（探索顺序）；评分目标对规划器不可达</td></tr>
    <tr><td>四、Prompt 注入实验</td><td class="num">19–27</td><td>建议模式；建议示例；一局实况；结果；慢分支延迟；时间线；触发与采纳；补测</td></tr>
    <tr><td>五、KV 缓存</td><td class="num">28</td><td>vLLM 前缀缓存的机制与实测</td></tr>
    <tr><td>六、结论</td><td class="num">29–30</td><td>结论与下一步；数据与代码位置</td></tr>
  </table>
  <p class="small">规模：第三轮 110 局（4 种方法 × 6 个任务或事件场景 × 5 个种子，事件场景不含禁缓存组），补测 5 局。所有分数为计分器 v6 离线重算结果。</p>
</div></section>

<!-- 3 平台与运行方式 -->
<section class="slide"><div class="wrap">
  <span class="sec">一、实验方法</span><br><span class="tag gray">平台</span>
  <h2>实验平台与一局的运行方式</h2>
  <div class="flow">
    <div class="node">观测<small>相机图像 + 文本状态<br>（物体坐标、手中物体、抽屉开度、消息）</small></div><div class="arr">→</div>
    <div class="node">语言模型决策<small>快分支每步约 0.5 s<br>慢分支按需调用</small></div><div class="arr">→</div>
    <div class="node">技能调用<small>每次一个，如<br>pick(butter_1)</small></div><div class="arr">→</div>
    <div class="node">脚本化执行器<small>完成一个技能约 3–10 s<br>可被中途取消</small></div><div class="arr">→</div>
    <div class="node">仿真实时推进<small>20 Hz，不等待模型<br>返回成功 / 失败及原因</small></div>
  </div>
  <ul>
    <li>平台：RoboCerebra 基准（NeurIPS 2025 Datasets &amp; Benchmarks），构建在 LIBERO / robosuite（MuJoCo 物理）之上；Franka Panda 机械臂，家居桌面场景。6 类任务各 10 个，共 60 个。</li>
    <li>语言模型不输出关节动作，只决定下一个技能；技能由脚本化执行器完成，执行器读取仿真中物体的真实位姿规划运动。</li>
    <li>实时：仿真按墙钟时间推进（实时比 1.0）。模型思考时机器人与环境不暂停；技能执行期间模型可以并行思考，必要时取消当前技能。</li>
    <li>一局结束：全部子目标完成；或规划器连续两次判断"已完成"；或达到上限（长任务 300 s / 40 次技能，事件任务 240 s / 30 次）。</li>
    <li>模型：Qwen3.8-27B（FP8），一张 L20 GPU，vLLM 0.27.1，开启前缀缓存；所有方法、所有分支共用这一个模型实例。仿真若落后墙钟（最大滞后 &gt; 0.25 s 或 p95 &gt; 50 ms），该局作废重跑。</li>
  </ul>
</div></section>

<!-- 4 模型输入输出 -->
<section class="slide"><div class="wrap cols" style="grid-template-columns: 1.25fr .75fr; align-items: start; gap: 34px;">
  <pre class="prompt">TASK: Find the butter from the wooden cabinet, melt it in a Chefmate
      frypan, and serve wine in a white-and-yellow mug.
OBJECT IDS: butter_1, chefmate_8_frypan_1, macaroni_and_cheese_1,
            white_yellow_mug_1, wine_bottle_1
FIXTURE IDS: flat_stove_1, wooden_cabinet_1
REGION IDS with centers (x, y, z in metres; fixed in the scene):
  wooden_cabinet_1_top_side: +0.15, +0.56, +0.66
  wooden_cabinet_1_top_region / _middle_region / _bottom_region: …
  coffee_table_table_region: +0.00, +0.00, +0.42      <i>← 没有灶台区域</i>
HISTORY (append-only, oldest first):
  [11.0s] open_drawer(wooden_cabinet_1_bottom_region) -> OK
  [11.7s] pick(butter_1) -> FAILED: blocked from above: open drawer
          wooden_cabinet_1_middle_region, ..._top_region; close it first
  …
  [57.3s] place(chefmate_8_frypan_1) -> OK: ok
CURRENT STATE at sim time 69.8 s:
  object in hand: none; gripper open
  chefmate_8_frypan_1: -0.13, +0.55, +0.42
  wine_bottle_1: -0.00, -0.08, +0.42      …
  drawer open fraction: ..._top_region=0.01, ..._middle_region=0.02,
                        ..._bottom_region=1.01
<b>ADVICE from the deliberate planner (given at sim time 57.3s; asked
because: possible loop …): The butter is already in the frypan, so stop
repeating pick/place on it. Next, turn on flat_stove_1 to melt the
butter, then pick wine_bottle_1 to pour into white_yellow_mug_1.</b>
CANDIDATE NEXT ACTIONS (all currently valid calls):
  A) pick(butter_1)  B) pick(chefmate_8_frypan_1)  …  E) pick(wine_bottle_1)
  F)–H) open / close drawers  I) turnon(flat_stove_1)  J) wait(20)  K) DONE
MODE: CHOOSE. Answer with its single letter only.    → 模型输出：E</pre>
  <div>
    <span class="tag gray">模型输入</span>
    <h2 style="font-size:32px;">模型实际收到的提示（节选）</h2>
    <p class="small2" style="margin:0 0 .5em;">case5，双分支·建议注入·Jev，种子 1，第 69.8 s 快分支决策；由运行记录原样重建，省略处以"…"标出。</p>
    <ul style="font-size:17px;">
      <li style="font-size:17px;">系统提示（约 1,100 token，所有调用相同）：角色、家务规则（倒完放回桌面、最后空手）、技能说明、各模式输出格式。</li>
      <li style="font-size:17px;">静态块在开局生成；历史只追加，记录每个技能的结果与失败原因。</li>
      <li style="font-size:17px;">另附 256×256 相机图像。关闭抽屉里的物体不列出，需要自己打开查看。</li>
      <li style="font-size:17px;">Jev 快分支只输出一个字母（此处 E → pick(wine_bottle_1)）；橙色为建议注入方法特有的一行。</li>
      <li style="font-size:17px;">一次快分支调用约 1,500–3,500 token。</li>
    </ul>
  </div>
</div></section>

<!-- 5 技能与执行器 -->
<section class="slide"><div class="wrap">
  <span class="sec">一、实验方法</span><br><span class="tag gray">技能</span>
  <h2>技能与执行器</h2>
  <table class="dense">
    <tr><th>技能</th><th>作用</th><th>实现</th><th>中位耗时</th><th>常见失败反馈（r3）</th></tr>
    <tr><td>pick(物体)</td><td>抓起物体</td><td>桌面：物理抓取；抽屉 / 储物盒内：抽象</td><td class="num">4.7 s</td><td>接近时停滞、上层抽屉拉开挡住（blocked from above）、抬升失败</td></tr>
    <tr><td>place(区域或容器)</td><td>放到区域内或容器上</td><td>物理（储物盒内为抽象）</td><td class="num">3.7 s</td><td>搬运途中停滞、目标抽屉未打开</td></tr>
    <tr><td>pour(容器)</td><td>把手中物体倒进容器</td><td>物理（倾斜手腕）</td><td class="num">5.5 s</td><td>倾倒不完整</td></tr>
    <tr><td>open_drawer / close_drawer</td><td>开 / 关抽屉</td><td>抽象：手臂移到抽屉前，抽屉关节连同内容物平移</td><td class="num">3.1 / 3.3 s</td><td>接近失败（少见）</td></tr>
    <tr><td>turnon(灶台)</td><td>打开灶台</td><td>物理（转旋钮）</td><td class="num">9.8 s</td><td>接近失败、旋钮未转到位（失败率 61%）</td></tr>
    <tr><td>wait(n)</td><td>等待 n 个控制步</td><td>–</td><td class="num">1 s</td><td>–</td></tr>
  </table>
  <ul style="margin-top:.5em;">
    <li>技能失败时返回文字原因，写入历史供规划器参考；同一时刻只能拿一个物体，开关抽屉与开灶须空手。</li>
    <li>抽象技能：抽屉、储物盒等狭窄空间的操作，用运动学动画代替接触物理，避免执行器问题掩盖规划差异。</li>
    <li>标准计划（GT plan）：不用语言模型，按官方子目标顺序直接调用技能，用来衡量执行器本身能做到的上限。</li>
  </ul>
</div></section>

<!-- 6 事件任务 -->
<section class="slide"><div class="wrap">
  <span class="sec">一、实验方法</span><br><span class="tag gray">任务</span>
  <h2>事件任务：Ideal/case6 + 两种动态事件</h2>
  <figure><img src="{{scene6}}" alt="case6 场景" style="max-height:470px"></figure>
  <table class="dense" style="margin-top:.4em;">
    <tr><td style="width:13%"><b>任务原文</b></td><td>Place the butter into the short cabinet and pour the tomato sauce into the plate.　6 个子目标：开中层抽屉 → 拿黄油 → 黄油放进抽屉；拿番茄酱 → 倒进盘子 → 放回桌面</td></tr>
    <tr><td><b>E1 改目标</b></td><td>机器人开始把黄油放进抽屉时，出现消息 "Change of plan: put the butter on the plate instead of in the short cabinet."，黄油的目标改为盘子；正在执行的放置已过时，需要取消或补救</td></tr>
    <tr><td><b>E3 限时关闭</b></td><td>前两个子目标（开抽屉、拿起黄油）完成时，出现消息 "Warning: the short cabinet middle drawer will close automatically in 6 seconds and then stay locked."；6 s 后抽屉自动关闭并锁死，黄油须在此之前放入</td></tr>
  </table>
</div></section>

<!-- 7 长任务一览 -->
<section class="slide"><div class="wrap">
  <span class="sec">一、实验方法</span><br><span class="tag gray">任务</span>
  <h2>长任务：Memory_Exploration（需要翻找抽屉）</h2>
  <table class="dense">
    <tr><th style="width:9%">任务</th><th>任务原文</th><th style="width:8%">子目标</th><th style="width:30%">要点</th></tr>
    <tr><td>case10</td><td>Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet.</td><td class="num">11</td><td>碗在木柜上层抽屉；倒入两样食品后放到柜顶</td></tr>
    <tr><td>case8</td><td>（与 case10 相同）</td><td class="num">15</td><td>碗在下层抽屉；官方子目标含翻找路径：开上 → 关上 → 开中 → 关中 → 开下</td></tr>
    <tr><td>case6</td><td>Find the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice.</td><td class="num">12</td><td>黄油在白柜中层抽屉；翻找路径：开上 → 关上 → 开中</td></tr>
    <tr><td>case5</td><td>Find the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug.</td><td class="num">14</td><td>黄油在下层抽屉；还要把平底锅放上灶台并开灶、倒酒（见下页）</td></tr>
  </table>
  <ul style="margin-top:.5em;">
    <li>关闭抽屉里的物体不出现在物体列表中，智能体需要自己决定打开哪个抽屉查看。</li>
    <li>上层抽屉拉开时会挡住下层抽屉的取物（执行器返回 blocked from above），需要先关上。</li>
    <li>"倒入"对盒装食品可用"放进容器"完成；倒完的物体按家务规则放回桌面。</li>
  </ul>
</div></section>

<!-- 8 case5 场景 -->
<section class="slide"><div class="wrap">
  <span class="sec">一、实验方法</span><br><span class="tag gray">任务</span>
  <h2>case5 的场景与 14 个子目标</h2>
  <figure><img src="{{scene5}}" alt="case5 场景" style="max-height:480px"></figure>
  <table class="dense" style="margin-top:.4em;">
    <tr><td style="width:14%">黄油（8 个）</td><td>开上层 → 关上层 → 开中层 → 关中层 → 开下层（翻找路径）→ 拿起黄油 → 倒进平底锅 → 放回桌面</td></tr>
    <tr><td>平底锅（2 个）</td><td>拿起平底锅 → 放到灶台区域（flat_stove_1_cook_region）　<span class="bad">r3 中对规划器不可达，见第 18 页</span></td></tr>
    <tr><td>灶台（1 个）· 酒（3 个）</td><td>开灶；拿起酒瓶 → 倒进白黄杯 → 放回桌面</td></tr>
  </table>
</div></section>

<!-- 9 方法 -->
<section class="slide"><div class="wrap">
  <span class="sec">一、实验方法</span><br><span class="tag gray">方法</span>
  <h2>四种方法如何运行</h2>
  <table class="dense">
    <tr><th style="width:17%">方法</th><th style="width:22%">快分支（每步决策）</th><th style="width:22%">慢分支</th><th style="width:17%">慢分支何时调用</th><th>慢分支结果如何使用</th></tr>
    <tr><td><b>仅快·Jev</b></td><td>每个技能结束后立即决定下一步，约 0.5 s</td><td>无</td><td>–</td><td>–</td></tr>
    <tr><td><b>双分支·完整计划·Jev</b></td><td>同上；没有可用计划时由它决策</td><td>同一模型，开思考（≤ 4096 token），输出剩余全部步骤的 JSON 计划</td><td>开局、技能失败、新消息、计划用完</td><td>计划到达后按当前状态对齐、逐步校验；通过则按计划逐步执行，否则拒绝并重新规划</td></tr>
    <tr><td><b>双分支·建议注入·Jev</b></td><td>每一步都由快分支决策</td><td>同一模型，关思考，输出 ≤ 2 句建议（≤ 120 token），约 2.5 s</td><td>开局、技能失败、检测到循环、新消息</td><td>注入快分支提示，由快分支自行决定是否采纳</td></tr>
    <tr><td><b>建议注入·Jev（禁缓存）</b></td><td colspan="4">与上一行相同，但每次请求都不复用前缀缓存，用来分离共享 KV 的作用</td></tr>
  </table>
  <ul style="margin-top:.5em;">
    <li>Jev 式候选打分：把当前所有合法技能调用列成字母选项，模型只生成 1 个 token，读取各字母的概率并取最大者，无需生成长文本。</li>
    <li>事件监控（所有方法）：技能执行期间出现新消息时，快分支判断是否取消当前技能，监控不阻塞下一步决策。</li>
    <li>各方法共用同一模型实例与同一提示布局，只在慢分支的用法上不同。</li>
  </ul>
</div></section>

<!-- 10 指标与计分 -->
<section class="slide"><div class="wrap">
  <span class="sec">一、实验方法</span><br><span class="tag gray">指标</span>
  <h2>指标与计分</h2>
  <table class="dense">
    <tr><th style="width:22%">指标</th><th>定义</th></tr>
    <tr><td>子目标完成率</td><td>官方子目标表中判定完成的比例（如 case5 共 14 个）</td></tr>
    <tr><td>整任务成功</td><td>全部子目标完成；E3 另要求黄油在抽屉关闭前放入</td></tr>
    <tr><td>E3 截止余量</td><td>抽屉关闭时刻 − 黄油放入时刻</td></tr>
    <tr><td>用时、失败技能数</td><td>一局的仿真时长（等于墙钟时长）；返回失败的技能调用次数</td></tr>
    <tr><td>慢分支延迟</td><td>请求发出到结果返回的时间；只统计 episode 结束前返回的调用</td></tr>
    <tr><td>建议采纳</td><td>建议到达后，快分支下一个动作的参数 id 出现在建议原文中</td></tr>
  </table>
  <ul style="margin-top:.5em;">
    <li>官方判定器存在谓词问题：人类演示逐帧回放，只有 6/40 个任务判为完成。我们用修复版计分（演示回放 37/40）。规则例：放置须离手并保持 5 帧；储物盒内须低于顶板；盒装食品的"倒入"可用"放进容器"完成。本轮升级到 v6（第 16–17 页）。</li>
    <li>每局逐步保存仿真状态，计分在状态上离线重算，规则改动不需要重跑实验；官方原始计分并列保存。</li>
  </ul>
</div></section>

<!-- 11 执行器：问题与修正 -->
<section class="slide"><div class="wrap">
  <span class="sec">二、执行器修正</span><br><span class="tag red">执行器 r3</span>
  <h2>执行器修正：问题、原因与修正</h2>
  <table class="dense">
    <tr><th style="width:22%">问题</th><th style="width:42%">原因</th><th>修正</th></tr>
    <tr><td>抽屉内取碗：报告成功后滑落（r2b case10 的主要失败）</td><td>前沿抓取的目标腕部偏航 ±180° 超出第 7 关节限位（±166°），腕部停在约 106°，两指沿碗沿切向夹持</td><td>目标偏航按 180° 对称折叠到可达范围；抓取后保持 6 步并确认双指接触，滑落时自动重抓一次</td></tr>
    <tr><td>抽象开抽屉后内容物位置异常</td><td>只推动抽屉关节、速度清零，内容物不随动，被后板推挤、穿插甚至弹出；开抽屉时夹爪停在把手高度，被拉出的抽屉扫过夹爪</td><td>内容物随抽屉平移；开关抽屉时夹爪停在安全高度</td></tr>
    <tr><td>抽屉内竖直下抓受阻</td><td>侧板、柜顶板与上层抽屉把手限制下抓空间；人类演示靠 2–3° 腕部倾斜完成，脚本复现只有 −5° 一档可行</td><td>抽屉内取物改为抽象技能：夹爪悬停，物体由动画移入两指之间，闭合并确认持握；抽屉未开或被上层抽屉阻挡时仍返回失败</td></tr>
    <tr><td>厨房桌场景整体失败（60 个任务中的 5 个）</td><td>机器人底座高 0.50 m，执行器的高度常数按咖啡桌场景标定</td><td>所有绝对高度随底座高度平移</td></tr>
    <tr><td>物体被碰倒后无法再抓</td><td>抓取偏移按直立物体计算，指向瓶颈原先所在的高度</td><td>竖直抓取偏移改在物体局部坐标系计算，倒伏时闭合方向垂直于物体轴线</td></tr>
  </table>
  <p class="small">定位方法：从失败局逐步保存的仿真状态离线还原现场，再用随机起始姿态的批量抓取测试验证修正（每组 10 次）。</p>
</div></section>

<!-- 12 执行器：抓取画面 -->
<section class="slide"><div class="wrap">
  <span class="sec">二、执行器修正</span><br><span class="tag red">执行器 r3</span>
  <h2>抽屉内取碗：滑落的复现与修正</h2>
  <figure><img src="{{grasp}}" alt="抓取滑落与修正"><figcaption>前两幅由 r2b 失败局（Memory_Exploration case10，仅快·文本，种子 1）的逐步状态还原，分别为第 305 步与第 314 步：两指并排卡在碗沿同一侧（切向夹持），抬到顶、手臂减速时碗滑落。第三幅为修正后从同一视角看到的前沿径向夹持。</figcaption></figure>
  <div class="take"><p>随机起始姿态各 10 次、抬起后保持 3 s 的比例：原实现 2/10，偏航折叠后 6/10，再加上内容物随动等修正后 10/10。最终版本改为抽象取物，碗与黄油各 10/10。</p></div>
</div></section>

<!-- 13 执行器：抽屉内容物 -->
<section class="slide"><div class="wrap cols fig-left">
  <figure><img src="{{drawer}}" alt="抽屉内容物"></figure>
  <div>
    <span class="sec">二、执行器修正</span><br><span class="tag red">执行器 r3</span>
    <h2>抽象开抽屉：内容物随动</h2>
    <ul>
      <li>r2b：抽象开抽屉时，黄油被后板弹出约 55 cm，落在桌面的杯口。r2b 中 case6 标准计划的 12/12 就是在这一状态下完成的，属伪成功。</li>
      <li>r3：内容物随抽屉平移。人类演示抓取黄油时，黄油位于 (−0.011, 0.403)；r3 开抽屉后为 (−0.005, 0.405)，二者一致。</li>
      <li>抽屉内物体改为抽象取物：随机起始姿态下碗与黄油各 10/10。</li>
    </ul>
  </div>
</div></section>

<!-- 14 标准计划回归 -->
<section class="slide"><div class="wrap">
  <span class="sec">二、执行器修正</span><br><span class="tag red">执行器 r3</span>
  <h2>标准计划回归：12 个试点任务</h2>
  <figure><img src="{{gt}}" alt="标准计划回归" style="max-height:530px"></figure>
  <div class="take"><p>不用语言模型、按官方子目标顺序逐步执行时，子目标完成率从 95/129（73.6%）升到 116/129（89.9%），没有任务退步。剩余缺口集中在两个厨房桌任务：case1 7/12，case2 5/10（其中一个物体距底座 0.86 m，超出可达范围）。</p></div>
</div></section>

<!-- 15 计分器：问题 -->
<section class="slide"><div class="wrap cols" style="grid-template-columns: 1.18fr .82fr;">
  <figure><img src="{{scorer}}" alt="case8 计分对比" style="max-height:700px"></figure>
  <div>
    <span class="sec">三、计分与任务定义</span><br><span class="tag gray">计分器 v6</span>
    <h2>官方子目标链要求复现演示的翻找顺序</h2>
    <ul>
      <li>每个物体的子目标是一条严格有序的链。碗的链前 5 步就是演示者翻找抽屉的路径：开上层→关上层→开中层→关中层→开下层。</li>
      <li>智能体采用另一种合理顺序：三个抽屉都打开，取碗被上层挡住后，再关上中层与上层。</li>
      <li>链在"关上层"之后等待"开中层"而停滞，其后完成的 7 个子目标全部不计。任务实际已完成，v5 只计 8/15。</li>
    </ul>
  </div>
</div></section>

<!-- 16 计分器：修正与影响 -->
<section class="slide"><div class="wrap cols" style="grid-template-columns: 1.05fr .95fr; align-items: start;">
  <div>
    <span class="sec">三、计分与任务定义</span><br><span class="tag gray">计分器 v6</span>
    <h2>修正、验证与影响</h2>
    <ul>
      <li><b>R11</b>：链首连续的开/关步骤不计顺序、各自独立计分（关闭须发生在打开之后）；其余步骤保持有序，且不必等探索步骤全部完成。链中间的开/关（如先开微波炉门再放入）仍按顺序。</li>
      <li>适用范围：60 个任务中有 42 条物体链以开/关步骤开头。</li>
      <li>验证：人类演示回放与 v5 完全一致（37/40 任务，400/405 子目标）。</li>
      <li>影响：r3 共 110 局，39 局变化（case5 全部 20 局各 +6 个子目标；case8 有 19 局由 8/15 变为 15/15）。r2b 共 145 局，27 局变化，全部在 case5。</li>
    </ul>
  </div>
  <div>
    <table class="dense">
      <tr><th>r2b case5 子目标完成率</th><th>v5</th><th>v6</th></tr>
      <tr><td>仅快·Jev</td><td class="num">0.24</td><td class="num">0.34</td></tr>
      <tr><td>双分支·Jev</td><td class="num">0.24</td><td class="num">0.39</td></tr>
      <tr><td>仅快·Jev（禁缓存）</td><td class="num">0.23</td><td class="num">0.34</td></tr>
      <tr><td>双分支·Jev（禁缓存）</td><td class="num">0.27</td><td class="num">0.39</td></tr>
      <tr><td>仅快·文本</td><td class="num">0.67</td><td class="num">0.69</td></tr>
      <tr><td>双分支·文本</td><td class="num">0.39</td><td class="num">0.49</td></tr>
      <tr><td>仅慢</td><td class="num">0.17</td><td class="num">0.37</td></tr>
    </table>
    <div class="hint"><p>r2b 中 case10、case6 与事件任务的得分均不变，第二轮的结论不变；上一版报告中 case5 的完成率按此表更正。</p></div>
  </div>
</div></section>

<!-- 17 评分目标不可达 -->
<section class="slide"><div class="wrap">
  <span class="sec">三、计分与任务定义</span><br><span class="tag red">任务定义</span>
  <h2>部分评分目标对规划器不可达</h2>
  <ul>
    <li><b>现象</b>：r2b、r3 中 case5 各方法整任务均为 0/5，漏项都包含"平底锅放到灶台"。</li>
    <li><b>原因</b>：该子目标的目标 <code>flat_stove_1_cook_region</code> 是灶台模型自带的站点，任务场景定义（BDDL）没有声明它。提供给模型的区域列表、Jev 候选动作和动作校验都取自 BDDL 声明的区域，因此任何规划器都发不出"放到灶台"的动作（第 5 页的提示中，区域列表里没有灶台）。</li>
    <li><b>证据</b>：补测中慢分支两次建议"把平底锅放到灶上（flat_stove_1）"，但快分支的候选里没有这个目标，只能把锅放到桌面（搬运中途停滞）或柜顶（失败）。</li>
    <li><b>范围</b>：扫描全部 60 个任务，10 个任务各有 1 个子目标受影响：7 个是灶台 cook_region，3 个是木托盘 contain_region。这些任务整任务成功的上限为 0。已跑 LLM 实验的任务中只有 case5 受影响；各方法上限相同（13/14），方法间的比较仍然有效。</li>
    <li><b>修正</b>：区域列表补上物体自带的功能性站点（cook_region、contain_region、center_region），下一轮起生效。</li>
  </ul>
</div></section>

<!-- 18 建议注入：方法 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>建议模式：提示布局与触发</h2>
  <p style="margin:.1em 0 .3em;">快、慢两个分支共用同一提示布局；建议注入在历史之后，不改变可复用的共享前缀：</p>
  <div class="layout">
    <div class="seg cache" style="flex:2.2">系统提示<br>角色、规则、技能、各模式输出格式</div>
    <div class="seg cache" style="flex:1.6">静态块<br>任务、物体与区域</div>
    <div class="seg cache" style="flex:1.6">历史<br>只追加</div>
    <div class="seg vol" style="flex:.9">图像</div>
    <div class="seg vol" style="flex:1.2">当前状态</div>
    <div class="seg adv" style="flex:1.5">慢分支建议<br>ADVICE …</div>
    <div class="seg vol" style="flex:1.6">模式指令<br>候选动作</div>
  </div>
  <div class="brace"><div style="flex:5.4">共享前缀：按 784 token 整块复用</div><div style="flex:5.2">每次调用变化</div></div>
  <ul style="margin-top:.6em;">
    <li>慢分支关闭思维链，以 ADVISE 模式输出不超过两句的建议（JSON，上限 120 token），内容为下一个子目标与应避免的动作。</li>
    <li>触发：开局、技能失败、检测到循环（同一调用连续 3 次，或两个调用交替出现）、新消息。慢分支忙时，请求排队，完成后按最新原因再给一次。</li>
    <li>快分支在技能结束后立即决策（约 0.5 s），而建议需要 2–3 s，所以触发后的第一个决策通常在建议到达之前做出，建议影响的是其后的决策。</li>
  </ul>
</div></section>

<!-- 19 建议示例 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>建议示例（第三轮原文）</h2>
  <table class="dense">
    <tr><th style="width:15%">触发</th><th style="width:15%">场景</th><th>建议原文</th><th style="width:8%">延迟</th></tr>
    <tr><td>开局</td><td>case5，种子 1</td><td class="q quote">Open the wooden cabinet drawers (start with top) to locate the butter. Keep the gripper empty and avoid moving the frypan or mug until the butter is found.</td><td class="num">2.1 s</td></tr>
    <tr><td>技能失败：上层抽屉挡住取物</td><td>case5，种子 1</td><td class="q quote">Close the open wooden_cabinet_1 drawers (top and middle) so the butter is no longer blocked from above, then pick butter_1. Avoid picking while any drawer above the butter remains open.</td><td class="num">2.9 s</td></tr>
    <tr><td>检测到循环：反复抓放黄油</td><td>case5，种子 1</td><td class="q quote">The butter is already in the frypan, so stop repeating pick/place on it. Next, turn on flat_stove_1 to melt the butter, then pick wine_bottle_1 to pour into white_yellow_mug_1.</td><td class="num">2.7 s</td></tr>
    <tr><td>新消息：E1 改目标</td><td>Ideal/case6，种子 1</td><td class="q quote">Place the butter onto plate_1, then close the middle drawer. After that, pick tomato_sauce_1 and pour it into plate_1, returning the sauce container to the table when done.</td><td class="num">3.2 s</td></tr>
  </table>
</div></section>

<!-- 20 一局实况 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>一局实况：case5，双分支·建议注入·Jev，种子 1</h2>
  <table class="dense narr">
    <tr><th style="width:9%">时刻</th><th style="width:36%">慢分支（建议，关思考）</th><th>快分支决策 → 技能结果</th></tr>
    <tr><td class="t">0.0 s</td><td>开局建议（2.1 s 后到达）：先依次打开抽屉找黄油，找到前不动平底锅和杯子</td><td>依次打开上、中、下层抽屉 <span class="okc">成功</span>（4.7 / 7.8 / 11.0 s），黄油出现在下层抽屉</td></tr>
    <tr><td class="t">11.7 s</td><td>失败触发（2.9 s）：先关上上层和中层抽屉，再拿黄油</td><td>pick(butter_1) <span class="fail">失败</span>：blocked from above，上层抽屉拉开挡住</td></tr>
    <tr><td class="t">19–32 s</td><td></td><td>关中层、关上层 <span class="okc">成功</span>；pick(butter_1) <span class="okc">成功</span>（31.7 s，抽象取物）</td></tr>
    <tr><td class="t">36.4 s</td><td>失败触发（2.7 s）：重新拿起黄油放进平底锅</td><td>place(平底锅) <span class="fail">失败</span>：黄油没有落进锅里</td></tr>
    <tr><td class="t">47–57 s</td><td></td><td>再拿黄油、放进平底锅 <span class="okc">成功</span>（57.3 s）</td></tr>
    <tr><td class="t">57.3 s</td><td>检测到"拿黄油 / 放进锅"交替出现 → 循环触发（2.7 s）：黄油已在锅里，停止重复；下一步开灶，再取酒倒进杯子</td><td>快分支在建议到达前（57.95 s）已自行选择 turnon <span class="okc">成功</span>（69.6 s）</td></tr>
    <tr><td class="t">70–90 s</td><td></td><td>按建议拿酒瓶 → 倒进白黄杯 → 放回桌面 <span class="okc">成功</span>（77.0 / 82.2 / 90.1 s）</td></tr>
    <tr><td class="t">94.7 s</td><td></td><td>关下层抽屉 <span class="okc">成功</span>；随后连续两次选"完成"，96.8 s 结束</td></tr>
  </table>
  <div class="hint"><p>结果 12/14：缺"拿起平底锅"与"平底锅放到灶台"，后者对规划器不可达（第 18 页）。全局 15 个技能、2 次失败、4 次建议；完整计划方法同一种子的计划直到 74 s 结束都没有返回（第 26 页）。</p></div>
</div></section>

<!-- 21 结果总览 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>结果总览</h2>
  <table class="dense">
    <tr><th>方法</th><th>E1 改目标</th><th>E3 6 s 窗</th><th>case10</th><th>case6</th><th>case8</th><th>case5：成功 / 完成率 / 用时</th><th>慢分支单次延迟</th></tr>
    <tr><td>仅快·Jev</td><td class="num">5/5</td><td class="num">5/5（余量 1.8 s）</td><td class="num">5/5</td><td class="num">5/5</td><td class="num">5/5</td><td class="num">0/5 · 0.79 · 183 s</td><td class="num">–</td></tr>
    <tr><td>双分支·完整计划·Jev</td><td class="num">5/5</td><td class="num">5/5（1.8 s）</td><td class="num">5/5</td><td class="num">5/5</td><td class="num">4/5</td><td class="num">0/5 · 0.81 · 183 s</td><td class="num">18.8 s / 65.1 s</td></tr>
    <tr><td><b>双分支·建议注入·Jev</b></td><td class="num">5/5</td><td class="num">5/5（1.7 s）</td><td class="num">5/5</td><td class="num">5/5</td><td class="num">5/5</td><td class="num ok">0/5 · 0.87 · 102 s</td><td class="num ok">2.5 s / 2.6 s</td></tr>
    <tr><td>建议注入·Jev（禁缓存）</td><td class="num">未测</td><td class="num">未测</td><td class="num">5/5</td><td class="num">5/5</td><td class="num">5/5</td><td class="num">0/5 · 0.73 · 205 s</td><td class="num">– / 3.7 s</td></tr>
  </table>
  <p class="small">每格为 5 局中整任务成功的局数；E3 要求截止前完成放入，括号内为平均余量。case5 一列另给出子目标完成率均值与平均用时；case5 有一个子目标不可达，完成率上限为 13/14 = 0.93。慢分支延迟为中位数，斜线前为事件任务、后为长任务，只统计 episode 结束前返回的调用。计分器 v6。</p>
  <div class="take"><p>事件任务与 case10、case6 上各方法均为满分，区分不了方法；case8 只有完整计划掉了一局；case5 是唯一能区分方法的任务。</p></div>
</div></section>

<!-- 22 长任务 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>长任务：子目标完成率</h2>
  <figure><img src="{{long}}" alt="长任务完成率"><figcaption>读图：每个小图是一个任务，每列是一种方法；每个点是一局（5 个种子），浅色柱为均值，柱顶数字为整任务成功的局数。</figcaption></figure>
  <div class="take"><p>case8 中完整计划有一局停在 7/15，每局平均失败技能 8.0 次（其余方法 1.0–2.0 次）。case5 上建议注入的均值最高（0.87），禁缓存时降到 0.73。</p></div>
</div></section>

<!-- 23 case5 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>case5 逐局：建议注入更快、失败更少</h2>
  <figure><img src="{{case5}}" alt="case5 逐局"><figcaption>读图：左图每点一局，横轴为用时（上限 300 s），纵轴为子目标完成率；空心点为补测（第 27 页）。右图为每局失败技能数，柱为均值。</figcaption></figure>
  <ul>
    <li>case5 共 14 个子目标，"平底锅放到灶台"对所有方法不可达，可达上限为 13/14。建议注入只漏了平底锅的两个子目标；其余方法还会漏开灶，或漏取酒、倒酒。</li>
    <li>建议注入平均用时 102 s，其余 183–205 s；每局失败技能 2.6 次，其余 10.0–18.2 次。每组 5 个种子，差异方向一致，但样本量小。</li>
  </ul>
</div></section>

<!-- 24 慢分支延迟 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>慢分支延迟：完整计划对建议</h2>
  <figure><img src="{{slow}}" alt="慢分支延迟"><figcaption>读图：每点是一次慢分支调用，竖线为中位数，横轴为对数刻度。</figcaption></figure>
  <div class="take"><p>完整计划在长任务上的中位数：case10 47.4 s、case6 54.2 s、case8 65.1 s、case5 98.5 s；不少计划直到 episode 结束都未返回（图中未计入）。长任务中来自慢计划的技能只占 0–5%（E3 中为 22%）。建议每次约 2.5 s，每局 1–4 次；禁缓存时 3.7 s，且因失败更多、触发更多，case5 增至每局 17 次。</p></div>
</div></section>

<!-- 25 时间线 -->
<section class="slide"><div class="wrap">
  <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
  <h2>时间线对比：case5，种子 1</h2>
  <figure><img src="{{tl}}" alt="case5 时间线"><figcaption>读图：每行三条泳道，自上而下为慢分支调用、快分支决策、正在执行的技能（灰 = 成功，红 = 失败）；虚线为 episode 结束。</figcaption></figure>
  <div class="hint"><p>完整计划在开局发出后，直到 74 s episode 结束都未返回，所有动作由快分支独立完成。建议注入在开局、两次技能失败后和检测到循环时各给出一次建议，每次 2–3 s。快分支在每次触发后立即做的第一个决策都早于建议到达；建议主要影响之后的决策（如 70 s 起按建议取酒、倒酒）。末尾的"完成"核实请求在 episode 结束时尚未返回。</p></div>
</div></section>

<!-- 26 触发与采纳、补测 -->
<section class="slide"><div class="wrap cols" style="grid-template-columns: 1fr 1fr; align-items: start;">
  <div>
    <span class="sec">四、Prompt 注入实验</span><br><span class="tag orange">Prompt 注入</span>
    <h2>建议的触发与采纳</h2>
    <table class="dense">
      <tr><th>触发</th><th>次数</th><th>延迟 p50 / p90</th><th>输出 token</th><th>采纳</th></tr>
      <tr><td>开局</td><td class="num">30</td><td class="num">2.2 / 2.7 s</td><td class="num">42</td><td class="num">10/30</td></tr>
      <tr><td>技能失败</td><td class="num">38</td><td class="num">2.6 / 3.8 s</td><td class="num">48</td><td class="num">21/38</td></tr>
      <tr><td>检测到循环</td><td class="num">2</td><td class="num">2.9 / 3.0 s</td><td class="num">54</td><td class="num">2/2</td></tr>
      <tr><td>新消息</td><td class="num">10</td><td class="num">2.7 / 3.2 s</td><td class="num">44</td><td class="num">1/10</td></tr>
    </table>
    <p class="small2">双分支·建议注入·Jev，共 30 局。采纳：建议到达后，快分支下一个动作的参数 id 出现在建议原文中。新消息到达后，快分支通常在建议到达之前已作出反应。</p>
  </div>
  <div>
    <span class="tag purple">补测</span>
    <h2>完成须经核实</h2>
    <p>快分支首次判断"完成"后，先等慢分支核实（最多 8 s）再决定。case5 共 5 局，子目标完成率 0.79（不核实时为 0.87），没有改善。</p>
    <ul>
      <li>3 局的核实建议在 2.1–2.9 s 内到达，但都是误判：<span class="quote">"The task is complete: butter is in the frypan on the stove …"</span>。实际上平底锅在桌上的柜子旁，灶台在桌子另一侧；模型得到的信息里没有灶台的位置，无从核对。</li>
      <li>另外 2 局：一局黄油掉到够不着的位置后被连抓 14 次；另一局慢分支建议"把平底锅放到灶上"，但快分支没有这个候选（第 18 页），把锅放到桌面、柜顶都失败了。</li>
    </ul>
  </div>
</div></section>

<!-- 27 KV 缓存 -->
<section class="slide"><div class="wrap">
  <span class="sec">五、KV 缓存</span><br><span class="tag green">KV 缓存</span>
  <h2>vLLM 前缀缓存：机制与实测</h2>
  <figure><img src="{{kv}}" alt="KV 缓存"></figure>
  <ul>
    <li>命中粒度 784 token 是 vLLM 0.27.1 为 GDN 混合架构自动设定的注意力块大小：align 模式下注意力页不小于单层 GDN 状态页，启动日志可证。命中量为共享前缀长度向下取整到 784 的倍数。</li>
    <li>当前布局正确：图像、状态与注入的建议都在历史之后，不影响前缀复用。禁缓存对照今后改用请求级 cache_salt：输入 token 不变、命中归零，也不影响其他请求的缓存（r2、r3 用的是系统提示随机串）。</li>
  </ul>
</div></section>

<!-- 28 结论与下一步 -->
<section class="slide"><div class="wrap cols" style="align-items: start;">
  <div>
    <span class="sec">六、结论</span><br><span class="tag">结论</span>
    <h2>结论</h2>
    <ol>
      <li>执行器 r3 消除了 r2b 长任务中的主要执行失败，标准计划完成率从 73.6% 升到 89.9%。</li>
      <li>修正两个评测问题：计分器 v6 去掉了对探索顺序的过严要求（演示回放不受影响，r2b 结论不变）；10/60 个任务的评分目标对规划器不可达，已补上区域列表。</li>
      <li>建议注入把慢分支单次调用从 47–98 s 降到约 2.5 s。在 case5 上完成率最高（0.87）、用时最短（102 s）、失败最少（2.6 次）；完整计划在长任务上几乎不被采用。</li>
      <li>多数试点任务已达上限，现有任务区分不了方法。</li>
    </ol>
  </div>
  <div>
    <span class="tag gray">下一步</span>
    <h2>下一步</h2>
    <ol>
      <li>补上区域列表后重跑 case5；引入更难的任务：更多 Memory、Mix 类任务，长任务上叠加事件。</li>
      <li>完成判定的可靠核实：核实时开启思考，或在状态描述中加入区域关系。</li>
      <li>执行器：够不着的物体给出明确的失败原因；平底锅等大件物体的搬运与放置。</li>
      <li>外部模型（OpenAI API 等）的无缓存基线；增加种子数。</li>
    </ol>
    <p class="small">局限：每组 5 个种子；单一模型；抽屉与储物盒交互为抽象技能。</p>
  </div>
</div></section>

<!-- 29 附录 -->
<section class="slide"><div class="wrap">
  <span class="sec">六、结论</span><br><span class="tag gray">附录</span>
  <h2>数据与代码</h2>
  <table class="dense">
    <tr><th style="width:30%">内容</th><th>位置（项目根目录下）</th></tr>
    <tr><td>第三轮 110 局 / 补测 5 局</td><td><code>exp/runs/llm_l20_r3/</code>、<code>exp/runs/llm_l20_r3b/</code>（每局含 episode.json、timeline.json、逐步状态 states.npz、v6 重算结果 rescored.json）</td></tr>
    <tr><td>冻结代码</td><td><code>exp_r3snap/</code>（第三轮）、<code>exp_r3bsnap/</code>（补测）</td></tr>
    <tr><td>标准计划回归</td><td><code>exp/runs/gtplan_r2b/</code>、<code>exp/runs/gtplan_r3b/</code></td></tr>
    <tr><td>演示回放（计分器验证）</td><td><code>exp/runs/e05/oracle_replay.csv</code>（v6），<code>oracle_replay_v5.csv</code>（v5）</td></tr>
    <tr><td>不可达目标扫描</td><td><code>exp/x_scan_goal_targets.py</code></td></tr>
    <tr><td>统计表与图</td><td><code>notes/figs_r3/</code>（<code>exp/analyze_r3.py</code>、<code>exp/plot_r3_figs.py</code>、<code>exp/render_r3_frames.py</code>、<code>exp/render_scene_overview.py</code>）</td></tr>
    <tr><td>实验记录</td><td><code>notes/Phase0_实验记录_2026-10-16.md</code> 第 E5 节；缓存调研 <code>notes/vLLM前缀缓存调研_2026-10-21.md</code></td></tr>
  </table>
</div></section>
"""

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>实时快慢思考基准：第三轮实验结果 · 2026-10-21</title>
{CSS}
</head>
<body>
{BODY}
<div id="bar"></div>
<div id="nav"><span id="count"></span><button id="prev">‹ 上一页</button><button id="next">下一页 ›</button></div>
<script>
  const slides = Array.from(document.querySelectorAll('.slide')); const bar = document.getElementById('bar'), count = document.getElementById('count'); let cur = 0;
  function show(n) {{ cur = Math.max(0, Math.min(slides.length - 1, n)); slides.forEach((s, k) => s.classList.toggle('active', k === cur));
    count.textContent = (cur + 1) + ' / ' + slides.length; bar.style.width = ((cur + 1) / slides.length * 100) + '%'; }}
  document.addEventListener('keydown', e => {{ if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(e.key)) {{ e.preventDefault(); show(cur + 1); }}
    else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) {{ e.preventDefault(); show(cur - 1); }} }});
  document.getElementById('prev').onclick = () => show(cur - 1); document.getElementById('next').onclick = () => show(cur + 1); show(0);
</script>
</body></html>"""

for k, v in IMG.items():
    HTML = HTML.replace("{{" + k + "}}", v)
assert "{{" not in HTML, "unfilled placeholder"
html_out = NOTES / "实验结果_2026-10-21_群发版.html"; html_out.write_text(HTML, encoding="utf-8")
pdf_out = NOTES / "实时快慢思考基准_第三轮实验结果_2026-10-21.pdf"
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=8000", f"--print-to-pdf={pdf_out}", html_out.as_uri()], check=True, capture_output=True)
print("written", html_out, f"{len(HTML) / 1e6:.2f} MB, slides:", HTML.count('<section class="slide'))
print("written", pdf_out, f"{pdf_out.stat().st_size / 1e6:.2f} MB")
