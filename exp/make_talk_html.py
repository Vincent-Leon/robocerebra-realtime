"""生成组会汇报用的单文件 HTML 幻灯片（图片以 base64 内嵌，可直接发送）。
用法: python -I make_talk_html.py <具身智能项目根目录>
翻页：← → / 空格 / PageUp PageDown / Home End；S 键切换"滚动阅读"模式；打印时每页一张。
"""
import base64, io, re, sys
from pathlib import Path
from PIL import Image

ROOT = Path(sys.argv[1]).resolve()
NOTES = ROOT / "notes"


def b64_png(p):
    return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()


def b64_jpg_resized(p, width=1100):
    im = Image.open(p).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=84)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


IMG = {
    "scene6": b64_jpg_resized(ROOT / "data/RoboCerebra_Bench/Ideal/case6/case6.png"),
    "scene1": b64_jpg_resized(ROOT / "data/RoboCerebra_Bench/Ideal/case1/case1.png"),
    "decision": b64_png(NOTES / "figs_talk/fig_decision_latency.png"),
    "kv": b64_png(NOTES / "figs_talk/fig_kv_cache.png"),
    "tl_e1": b64_png(NOTES / "figs_talk/fig_timeline_e1.png"),
    "tl_e3": b64_png(NOTES / "figs_talk/fig_timeline_e3.png"),
    "e1_all": b64_png(NOTES / "figs_r2/E1_response_latency_llm_l20_r2.png"),
    "e1_talk": b64_png(NOTES / "figs_talk/fig_e1_all_talk.png"),
    "e3_talk": b64_png(NOTES / "figs_talk/fig_e3_matrix_talk.png"),
    "monitor_talk": b64_png(NOTES / "figs_talk/fig_monitor_talk.png"),
    "e3_matrix": b64_png(NOTES / "figs_r2/E3_success_vs_window_llm_l20_r2.png"),
    "monitor": b64_png(NOTES / "figs_r2b/E3_success_vs_window_llm_l20_r2b.png"),
}

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>机器人边想边做：实时快慢思考基准 · 进度汇报 2026-10-18</title>
<style>
  :root {
    --ink: #1d1d1f; --ink2: #5f5e5a; --line: #e6e5e2; --bg: #ffffff; --soft: #f6f6f4;
    --blue: #2a78d6; --green: #008300; --orange: #eb6834; --purple: #6250d6; --red: #e34948; --yellow: #eda100;
    --h1: clamp(30px, 3.4vw, 50px); --h2: clamp(24px, 2.5vw, 38px); --body: clamp(16px, 1.45vw, 22px); --small: clamp(13px, 1.1vw, 17px);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; background: var(--bg); color: var(--ink);
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif; }
  .slide { position: absolute; inset: 0; display: none; padding: 4vh 5vw 11vh; overflow: auto; }
  .slide.active { display: flex; }
  .wrap { margin: auto; width: 100%; max-width: 1240px; }
  h1 { font-size: var(--h1); margin: 0 0 .4em; line-height: 1.25; letter-spacing: .5px; }
  h2 { font-size: var(--h2); margin: 0 0 .55em; line-height: 1.3; }
  p, li, td, th { font-size: var(--body); line-height: 1.65; }
  .small, figcaption { font-size: var(--small); color: var(--ink2); line-height: 1.6; }
  .tag { display: inline-block; font-size: var(--small); font-weight: 600; color: #fff; background: var(--blue);
    border-radius: 999px; padding: .15em .9em; margin-bottom: .8em; letter-spacing: 1px; }
  .tag.green { background: var(--green); } .tag.orange { background: var(--orange); } .tag.purple { background: var(--purple); }
  .tag.red { background: var(--red); } .tag.gray { background: #8a8984; }
  .lead { font-size: calc(var(--body) * 1.12); color: var(--ink); }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 3.2vw; align-items: center; }
  .cols.wide-left { grid-template-columns: 1.15fr .85fr; }
  .cols.fig-left { grid-template-columns: 1.22fr .78fr; }
  figure img { cursor: zoom-in; }
  #lightbox { position: fixed; inset: 0; background: rgba(255,255,255,.97); display: none; align-items: center; justify-content: center; z-index: 20; cursor: zoom-out; }
  #lightbox img { max-width: 96vw; max-height: 94vh; object-fit: contain; }
  .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.6vw; align-items: start; }
  .grid3 figure img { max-height: 36vh; }
  .cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.4vw; }
  .card { border: 1px solid var(--line); border-radius: 14px; padding: 1.1em 1.3em; background: var(--soft); }
  .card h3 { margin: 0 0 .35em; font-size: calc(var(--body) * 1.08); }
  .card p { margin: .2em 0; font-size: calc(var(--body) * .9); }
  .card .rel { color: var(--blue); font-weight: 600; }
  figure { margin: 0; }
  figure img { display: block; width: 100%; max-height: 54vh; object-fit: contain; border-radius: 10px; }
  figure.photo img { border: 1px solid var(--line); }
  figcaption { margin-top: .6em; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border-bottom: 1px solid var(--line); padding: .45em .7em; text-align: left; vertical-align: top; }
  th { color: var(--ink2); font-weight: 600; font-size: var(--small); }
  .num { font-variant-numeric: tabular-nums; }
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2vw; margin: 1.2em 0; }
  .stat { border-radius: 14px; padding: 1em 1.2em; background: var(--soft); border: 1px solid var(--line); }
  .stat b { display: block; font-size: clamp(34px, 4.6vw, 64px); line-height: 1.1; color: var(--purple); }
  .stat span { font-size: var(--small); color: var(--ink2); }
  .hint { border-left: 4px solid var(--blue); background: #f2f7fd; padding: .7em 1em; border-radius: 0 10px 10px 0; margin-top: 1em; }
  .hint p { margin: .15em 0; font-size: calc(var(--body) * .92); }
  .take { border-left: 4px solid var(--green); background: #f1f8f1; padding: .7em 1em; border-radius: 0 10px 10px 0; margin-top: 1em; }
  .take p { margin: .15em 0; }
  .warn { border-left: 4px solid var(--orange); background: #fdf4ee; padding: .7em 1em; border-radius: 0 10px 10px 0; margin-top: 1em; }
  ol, ul { margin: .3em 0; padding-left: 1.3em; } li { margin: .25em 0; }
  .cover { text-align: left; }
  .cover h1 { font-size: clamp(40px, 5.6vw, 84px); margin-bottom: .2em; }
  .cover .sub { font-size: calc(var(--body) * 1.35); color: var(--ink2); margin: 0 0 1.6em; }
  .cover .one { font-size: calc(var(--body) * 1.2); border-left: 5px solid var(--blue); padding-left: 1em; max-width: 900px; }
  .script p { font-size: calc(var(--body) * .84); margin: .5em 0; line-height: 1.6; }
  .qa dt { font-weight: 700; margin-top: .7em; font-size: var(--body); }
  .qa dd { margin: .2em 0 0; font-size: calc(var(--body) * .92); color: var(--ink); line-height: 1.6; }
  .ok { color: var(--green); font-weight: 700; } .bad { color: var(--red); font-weight: 700; }
  /* 底部导航 */
  #nav { position: fixed; left: 0; right: 0; bottom: 0; height: 6vh; min-height: 40px; display: flex; align-items: center;
    justify-content: flex-end; gap: 12px; padding: 0 2vw; background: linear-gradient(transparent, rgba(255,255,255,.95) 40%); }
  #bar { position: fixed; left: 0; bottom: 0; height: 4px; background: var(--blue); transition: width .2s; }
  #nav button { border: 1px solid var(--line); background: #fff; color: var(--ink); border-radius: 8px; padding: 6px 14px; font-size: 15px; cursor: pointer; }
  #nav button:hover { border-color: var(--blue); color: var(--blue); }
  #count { font-size: 14px; color: var(--ink2); min-width: 64px; text-align: right; }
  #help { position: fixed; left: 2vw; bottom: 1.6vh; font-size: 13px; color: #8a8984; }
  /* 滚动阅读模式与打印 */
  body.scroll .slide { position: relative; display: flex; min-height: 100vh; border-bottom: 1px solid var(--line); }
  body.scroll #nav, body.scroll #help, body.scroll #bar { display: none; }
  @page { size: 1600px 900px; margin: 0; }
  @media print {
    html, body { width: 1600px; height: auto; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .slide { position: relative; display: flex !important; width: 1600px; height: 900px; overflow: hidden; padding: 40px 80px 48px;
      page-break-after: always; break-after: page; inset: auto; }
    .slide:last-of-type { page-break-after: auto; break-after: auto; }
    #nav, #help, #bar, #lightbox { display: none !important; }
    figure img { cursor: default; max-height: 470px; }
    /* 打印时按 1600×900 屏幕的取值固定字号与间距（打印时 vw/vh 以默认纸张计算，不可靠） */
    :root { --h1: 50px; --h2: 38px; --body: 22px; --small: 17px; }
    .cover h1 { font-size: 84px; }
    .stat b { font-size: 64px; }
    .cols { gap: 50px; } .cards { gap: 22px; } .stats { gap: 32px; } .grid3 { gap: 26px; }
    .grid3 figure img { max-height: 320px; }
  }
  @media screen and (max-width: 900px) { .cols, .cols.wide-left, .cols.fig-left, .cards, .stats, .grid3 { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<!-- 1 封面 -->
<section class="slide cover"><div class="wrap">
  <span class="tag">进度汇报 · 2026-10-18</span>
  <h1>机器人边想边做</h1>
  <p class="sub">实时快慢思考基准与同模型快慢并行方法</p>
  <p class="one">大模型想问题需要时间，现实世界却不会停下来等它。<br>我们研究：机器人怎样才能既想得对，又来得及。</p>
</div></section>

<!-- 2 研究什么 -->
<section class="slide"><div class="wrap cols wide-left">
  <div>
    <span class="tag">背景</span>
    <h2>我们在研究什么</h2>
    <p class="lead">现在很多机器人用大模型当"大脑"。</p>
    <ul>
      <li>大模型看着桌面，决定下一步做什么：<b>"拿起黄油""打开抽屉""把黄油放进抽屉"</b>。</li>
      <li>底层程序再驱动机械臂去完成这个动作。</li>
      <li>大模型想得越仔细越准确，但也越慢。</li>
    </ul>
    <div class="hint"><p>我们用的大脑：实验室自己部署的通义千问模型 Qwen3.8-27B，约 270 亿参数，跑在实验室的 L20 显卡上。</p></div>
  </div>
  <figure class="photo"><img src="{{scene6}}" alt="实验场景：机械臂、柜子、盘子和桌上的物品"><figcaption>实验场景之一：机械臂要把黄油放进柜子抽屉，再把番茄酱倒进盘子。来自 RoboCerebra 数据集。</figcaption></figure>
</div></section>

<!-- 3 问题出在哪 -->
<section class="slide"><div class="wrap">
  <span class="tag">背景</span>
  <h2>问题出在哪里：想需要时间，世界不等人</h2>
  <div class="cols">
    <div>
      <table>
        <tr><th>大模型的思考方式</th><th>做一个决定要多久</th></tr>
        <tr><td>不深想，直接回答</td><td class="num">约 3 秒</td></tr>
        <tr><td>开启深度思考</td><td class="num">约 9 秒，有时二十多秒</td></tr>
      </table>
      <div class="hint"><p>人也有两种思考：快思考靠直觉、反应快；慢思考仔细推敲、费时间。心理学里叫"系统 1"和"系统 2"。我们想让机器人也会在两者之间取舍。</p></div>
    </div>
    <div>
      <p class="lead">可现实世界不会暂停：</p>
      <ul>
        <li>机器人正要把黄油放进抽屉，主人突然说<b>"别放抽屉了，放盘子上"</b>。</li>
        <li>系统提醒<b>"抽屉 6 秒后自动关上并锁住"</b>。</li>
      </ul>
      <p>机器人如果还在慢慢想，就会错过时机，或者把已经过时的动作做完。</p>
    </div>
  </div>
</div></section>

<!-- 4 相关研究 -->
<section class="slide"><div class="wrap">
  <span class="tag">背景</span>
  <h2>相关研究在做什么</h2>
  <div class="cards">
    <div class="card"><h3>RoboCerebra · NeurIPS 2025</h3>
      <p>机器人多步家务的"考试题库"，在模拟器里完成，比如"把食品盒收进储物盒"，共 40 个任务。</p>
      <p class="rel">我们直接用它的任务。但它考试时，模型思考期间世界相当于暂停，失败了还能重置。</p></div>
    <div class="card"><h3>RealtimeGym · 2025</h3>
      <p>在电子游戏里研究"边想边做"：只会快反应的在复杂局面下出错，只会慢规划的在时间紧时出错。</p>
      <p class="rel">思路最接近，我们把这个问题带到机器人上。</p></div>
    <div class="card"><h3>RoboDyna · NeurIPS 2026 研讨会</h3>
      <p>机器人动态任务考试，比较"推理时世界冻结"和"推理时世界继续"两种考法。</p>
      <p class="rel">同样关心时间，但考的是端到端控制模型，没有快慢思考的设计。</p></div>
    <div class="card"><h3>Visual Jev · 2026</h3>
      <p>做选择题时，不让模型写一段回答，直接读出每个选项的概率，选最大的。</p>
      <p class="rel">我们借用它做"快脑"：让模型勾选项，而不是写作文。</p></div>
  </div>
</div></section>

<!-- 5 两件事 -->
<section class="slide"><div class="wrap cols wide-left">
  <div>
    <span class="tag">我们的工作</span>
    <h2>这篇论文要做的两件事</h2>
    <p class="lead"><b>① 出一套新"考试"</b></p>
    <ul>
      <li>用 RoboCerebra 的任务，但让世界按真实时间运行：模型思考的这几秒里，场景照常变化。</li>
      <li>加入突发事件。<b>中途改主意</b>：机器人正在放东西，主人换了目的地。<b>限时</b>：抽屉几秒后关闭并锁住。</li>
      <li>考三样：能不能完成、对突发事件反应多快、花了多少时间和算力。</li>
    </ul>
    <p class="lead"><b>② 提出一种方法</b></p>
    <ul>
      <li>同一个大模型同时开"快脑"和"慢脑"：快脑随时应对眼前情况，慢脑在后台想完整计划。</li>
      <li>两者共享已经读过的内容，不必各自从头读一遍，省掉重复计算。</li>
    </ul>
  </div>
  <figure class="photo"><img src="{{scene1}}" alt="实验场景：桌上的食品盒与白色储物盒"><figcaption>另一个实验场景：把食品盒收进左边的白色储物盒。"中途改主意"就在这里测：主人突然说"黄油别放盒子了，放桌上"。</figcaption></figure>
</div></section>

<!-- 6 名词 -->
<section class="slide"><div class="wrap">
  <span class="tag gray">名词速查</span>
  <h2>后面会用到的几个词</h2>
  <table>
    <tr><th style="width:22%">名词</th><th>一句话解释</th></tr>
    <tr><td>快脑</td><td>大模型不深想，直接给出下一步动作</td></tr>
    <tr><td>慢脑</td><td>大模型开启深度思考，想好一整套计划</td></tr>
    <tr><td>勾选项的快脑（Jev）</td><td>把当前能做的动作列成 A、B、C、D，模型只勾一个，约 0.4 秒出结果</td></tr>
    <tr><td>监控</td><td>机器人做动作时如果来了新消息，快速判断要不要立刻停下</td></tr>
    <tr><td>共享缓存</td><td>模型把读过的内容记在内存里，下次不重读，相当于书签</td></tr>
    <tr><td>执行器</td><td>把"拿起黄油"变成具体机械臂动作的程序；所有方法用同一个，只比较"大脑"</td></tr>
    <tr><td>计分器</td><td>自动判断任务有没有完成的程序</td></tr>
    <tr><td>种子</td><td>同一个实验换不同随机数重复跑，看结果稳不稳；我们每组跑 5 次</td></tr>
  </table>
</div></section>

<!-- 7 进度 -->
<section class="slide"><div class="wrap">
  <span class="tag">进度</span>
  <h2>做到哪一步了</h2>
  <div class="cols">
    <table>
      <tr><th>阶段（按计划书）</th><th>状态</th></tr>
      <tr><td>0　复现原考试</td><td class="ok">完成</td></tr>
      <tr><td>1　改成实时运行</td><td class="ok">完成</td></tr>
      <tr><td>2　加入突发事件</td><td class="ok">完成</td></tr>
      <tr><td>3　同一模型的快慢方法</td><td>主要实验完成，正在改进</td></tr>
      <tr><td>4　扩大规模、跨基准</td><td>未开始</td></tr>
    </table>
    <div>
      <div class="stats" style="grid-template-columns: 1fr 1fr;">
        <div class="stat"><b class="num">345</b><span>局正式实验：第二轮 200 局，第二批 145 局</span></div>
        <div class="stat"><b class="num">100%</b><span>都通过实时性检查；卡顿的局作废重跑</span></div>
      </div>
      <p class="small">每一局都检查模拟器有没有卡顿：最大滞后不超过 0.25 秒，否则作废重跑。计划书列出的"第一轮最小交付"六项都已具备。</p>
    </div>
  </div>
</div></section>

<!-- 8 发现1 决策耗时 -->
<section class="slide"><div class="wrap">
  <span class="tag green">发现 1</span>
  <h2>世界不等人时，反应速度决定成败</h2>
  <figure><img src="{{decision}}" alt="每做一个决定要多久的条形图"><figcaption>每做一个决定要多久。横轴是对数刻度，每一格差 10 倍左右。</figcaption></figure>
  <div class="take"><p>勾选项的快脑每次只要 0.4 秒，比写回答快约 6 倍，比深度思考快 20 倍以上。</p></div>
</div></section>

<!-- 9 E1 时间线 -->
<section class="slide"><div class="wrap">
  <span class="tag green">发现 1 · 例子一</span>
  <h2>主人中途改主意："黄油别放盒子了，放桌上"</h2>
  <figure><img src="{{tl_e1}}" alt="三种方法在主人改主意前后的时间线"><figcaption>同一个任务、同一个随机种子下三种方法的录像回放。</figcaption></figure>
  <div class="hint"><p>怎么看：红线是主人改主意的时刻；上面一条是"在想"，下面一条是"在做"；黄色是被取消的动作。</p><p>勾选项的快脑 0.85 秒就转向；深度思考的慢脑要 8.5 秒；不带监控的快脑先把黄油放进了盒子，15 秒后才补救。</p></div>
</div></section>

<!-- 10 E1 全部 -->
<section class="slide"><div class="wrap">
  <span class="tag green">发现 1 · 详细结果</span>
  <h2>所有方法、两个任务：改主意后多久转向</h2>
  <figure><img src="{{e1_talk}}" alt="各方法在两个场景中改主意后的转向时间"><figcaption>每个点是一次实验，每种方法每个场景 5 次；竖线是中位数。越靠左越快，横轴是对数刻度。</figcaption></figure>
  <div class="hint"><p>两个场景的结论一致：勾选项约 1 秒；写回答的快脑或深度思考，带监控时约 5 到 9 秒；不带监控要 13 到 51 秒。</p></div>
</div></section>

<!-- 11 E3 矩阵 -->
<section class="slide"><div class="wrap cols fig-left">
  <figure><img src="{{e3_talk}}" alt="各方法在不同时限下按时完成的次数矩阵"><figcaption>深蓝 = 5 次全部赶上，浅色 = 没赶上，灰色 = 没测。</figcaption></figure>
  <div>
    <span class="tag green">发现 1 · 例子二</span>
    <h2>限时关抽屉，能赶上吗</h2>
    <ul>
      <li><b>6 秒</b>：勾选项的快脑每次都赶上，还剩约 3 秒；深度思考一次都没赶上。</li>
      <li><b>9 秒</b>：除深度思考外都来得及。</li>
      <li><b>12 秒</b>：几乎都来得及。</li>
    </ul>
    <div class="warn"><p>奇怪的一格："写回答的快脑 + 监控"在 6 秒时 0 次赶上，不带监控反而 5 次赶上。原因见发现 3。</p></div>
  </div>
</div></section>

<!-- 12 发现2 缓存 -->
<section class="slide"><div class="wrap cols wide-left">
  <figure><img src="{{kv}}" alt="共享缓存前后的决策耗时柱状图"><figcaption>勾选项的快脑每做一个决定的耗时，中位数。</figcaption></figure>
  <div>
    <span class="tag green">发现 2</span>
    <h2>记住读过的内容，能明显提速</h2>
    <p>模型每次决定前都要读一遍任务、历史和当前画面。大部分内容和上一次一样。</p>
    <p>共享缓存就是把读过的部分记下来，下次不重读，相当于夹了书签。</p>
    <div class="take"><p>每次决策快约 40%。任务越长、历史越多，省得越多：长任务里快约 48%。</p></div>
  </div>
</div></section>

<!-- 13 发现3 时间线 -->
<section class="slide"><div class="wrap">
  <span class="tag orange">发现 3</span>
  <h2>要有监控，但监控不能挡路</h2>
  <figure><img src="{{tl_e3}}" alt="抽屉 6 秒后关闭时三种方法的时间线"><figcaption>"抽屉 6 秒后关闭"这一刻前后的时间线。红色实线 = 警告发出，红色虚线 = 抽屉关闭锁定。</figcaption></figure>
  <div class="hint"><p>中间一行：警告恰好在"拿黄油"快做完时到达，监控判断得没错，但机器人停下来等它，白白耽误了约 1.7 秒，放黄油时抽屉已经关了。</p><p>下面一行：监控改在后台判断，机器人不用等它，赶上了。</p></div>
</div></section>

<!-- 14 发现3 对照 -->
<section class="slide"><div class="wrap cols fig-left">
  <figure><img src="{{monitor_talk}}" alt="后台监控与停下来等监控的对照"><figcaption>"抽屉 6 秒后关闭"，每种做法试 5 次。深度思考本身每步要 9 秒左右，怎么监控都来不及。</figcaption></figure>
  <div>
    <span class="tag orange">发现 3 · 对照实验</span>
    <h2>只改监控的工作方式</h2>
    <table>
      <tr><th>方法</th><th>后台监控</th><th>停下来等监控</th></tr>
      <tr><td>写回答的快脑</td><td class="ok">5/5</td><td class="bad">0/5</td></tr>
      <tr><td>写回答的快脑 + 慢脑</td><td class="ok">5/5</td><td class="bad">0/5</td></tr>
    </table>
    <div class="take"><p>同时也确认了监控是必要的：没有监控时，过时的动作 20 次全被做完了。所以监控要有，但必须在后台。</p></div>
  </div>
</div></section>

<!-- 15 发现4 慢脑 -->
<section class="slide"><div class="wrap">
  <span class="tag purple">发现 4</span>
  <h2>快脑加慢脑同时跑：慢脑来不及</h2>
  <div class="stats">
    <div class="stat"><b class="num">20 秒</b><span>短任务里，慢脑想好一整份计划</span></div>
    <div class="stat"><b class="num">78 秒</b><span>长任务里，慢脑想好一整份计划</span></div>
    <div class="stat"><b class="num">0–12%</b><span>长任务里，机器人的动作来自慢脑计划的比例</span></div>
  </div>
  <p>计划交过来的时候，快脑要么已经把活干完了，要么情况已经变了，计划用不上。</p>
  <div class="take"><p>下一步重点：让慢脑先交出前几步、限制它的思考时间，并在快脑反复失败、兜圈子的时候再请它出手。</p></div>
</div></section>

<!-- 16 发现5 长任务 -->
<section class="slide"><div class="wrap">
  <span class="tag red">发现 5</span>
  <h2>长任务目前卡在机械臂抓取，还不能比较思考方式</h2>
  <p class="small">三个"先去柜子里找东西，再做一串步骤"的长任务，每格是 5 次里完成整个任务的次数和平均完成比例。</p>
  <table>
    <tr><th>方法</th><th>任务 A：找碗、倒食物</th><th>任务 B：找黄油、倒酱料</th><th>任务 C：找黄油、加热、倒酒</th></tr>
    <tr><td>勾选项的快脑</td><td class="num">5/5，100%</td><td class="num">0/5，60%</td><td class="num">0/5，24%</td></tr>
    <tr><td>写回答的快脑</td><td class="num">1/5，27%</td><td class="num">0/5，55%</td><td class="num">0/5，67%</td></tr>
    <tr><td>勾选项的快脑 + 慢脑</td><td class="num">5/5，100%</td><td class="num">0/5，75%</td><td class="num">0/5，24%</td></tr>
    <tr><td>写回答的快脑 + 慢脑</td><td class="num">3/5，64%</td><td class="num">1/5，70%</td><td class="num">0/5，39%</td></tr>
    <tr><td>深度思考的慢脑</td><td class="num">1/5，29%</td><td class="num">0/5，32%</td><td class="num">0/5，17%</td></tr>
  </table>
  <div class="warn"><p>失败大多发生在从抽屉里拿碗、拿黄油：碗刚抬起来就从夹子里滑掉了，程序却报告"拿到了"，大脑被误导，反复去抓一只卡歪的碗。任务 C 里的平底锅放得太远，够不着。</p><p>所以长任务上谁好谁坏暂不下结论，要先把抓取修稳。也能看到只靠快脑容易兜圈子，比如一局里反复开关抽屉 30 多次，这正是慢脑该帮忙的地方。</p></div>
</div></section>

<!-- 17 原考试的问题 -->
<section class="slide"><div class="wrap">
  <span class="tag gray">严谨性</span>
  <h2>我们还发现并修好了原考试的几处问题</h2>
  <div class="cols">
    <table>
      <tr><th>问题</th><th>后果</th></tr>
      <tr><td>计分器把"放在盒子顶上"判成"放进了盒子里"</td><td>原来部分任务的成绩不可信</td></tr>
      <tr><td>模拟器每次启动把盒子、柜子随机挪动 1–2 厘米</td><td>同样的实验结果不一样，方法之间不能公平比较</td></tr>
      <tr><td>机器人做完动作时，大模型看到的还是动作前的状态</td><td>快脑重复做已经做过的动作</td></tr>
    </table>
    <div>
      <div class="stats" style="grid-template-columns: 1fr 1fr;">
        <div class="stat"><b class="num" style="color:var(--green)">37 / 40</b><span>我们的计分器认可的人类示范任务数</span></div>
        <div class="stat"><b class="num" style="color:var(--red)">6 / 40</b><span>官方计分认可的数目</span></div>
      </div>
      <p class="small">40 个任务的人类示范其实都完成了任务，用它来检验计分器是否可信。</p>
      <div class="hint"><p>原考试允许"失败后重置到正确状态"，分数会虚高：同样 9 个任务，允许重置时算完成 75 个小步骤，其中 22 个是靠重置补上的；不允许时只有 51 个。</p></div>
    </div>
  </div>
</div></section>

<!-- 18 局限与下一步 -->
<section class="slide"><div class="wrap cols">
  <div>
    <span class="tag gray">局限</span>
    <h2>还不够的地方</h2>
    <ul>
      <li>突发事件只在 2 个任务上测过，每组 5 次，样本还不大。</li>
      <li>机械臂动作是写好的程序，开关抽屉、放进储物盒等少数动作做了简化。</li>
      <li>只测了一个大模型，还没在相同算力预算下和其他做法对比。</li>
    </ul>
  </div>
  <div>
    <span class="tag">下一步</span>
    <h2>接下来做什么</h2>
    <ol>
      <li>先把长任务里的抓取修稳：确认真的拿住了再报告成功，滑掉就自动重抓。</li>
      <li>让慢脑及时有用：先交出前几步，限时思考，快脑兜圈子时出手。</li>
      <li>在更多任务、更多突发事件上验证。</li>
      <li>更多模型、相同算力预算下对比，然后扩大规模。</li>
    </ol>
  </div>
</div></section>

<!-- 19 总结 -->
<section class="slide"><div class="wrap">
  <span class="tag">总结</span>
  <h2>四句话</h2>
  <ol>
    <li><b>实时考试已搭好并验证：</b>世界不等人，突发事件可复现，计分可信。</li>
    <li><b>反应速度决定成败：</b>勾选项的快脑 0.4 秒一个决定，是唯一在所有突发情况下都成功的方法。</li>
    <li><b>两条工程经验：</b>共享缓存省 40% 到 48% 的时间；监控必须放在后台，不能让机器人停下来等。</li>
    <li><b>下一阶段的重点：</b>快慢并行还没带来好处，因为慢脑太慢；长任务要先修好抓取。</li>
  </ol>
</div></section>

<!-- 20 讲稿 -->
<section class="slide presenter-only"><div class="wrap script">
  <span class="tag gray">附录</span>
  <h2>3 分钟讲稿</h2>
  <p>我们研究的问题是：机器人用大模型当大脑时，大模型想问题需要几秒甚至几十秒，但现实世界不会停下来等它。比如机器人正要把东西放进抽屉，主人突然改了主意；或者抽屉马上要自动关上。现有的机器人考试，比如 NeurIPS 2025 的 RoboCerebra，在模型思考时相当于把世界暂停了，测不出"想得慢"带来的问题。</p>
  <p>我们做了两件事。第一，把 RoboCerebra 的任务改造成实时考试：模拟器按真实时间运行，并加入"中途改主意"和"限时关闭"这类突发事件。第二，研究同一个大模型怎样在快思考和慢思考之间配合，以及让不同的思考共享已读内容来节省计算。</p>
  <p>目前考试已经搭好并验证，正式实验跑了 345 局。主要发现有四点。第一，世界不等人时，反应速度决定成败：我们把快速决策做成"勾选项"而不是"写回答"，每次只要 0.4 秒，主人改主意时 1 秒内就能转向，抽屉 6 秒后关闭也能每次赶上，深度思考的方法一次都没赶上。第二，共享已读内容让每次决策快 40% 到 48%。第三，监控新消息是必要的，没有它机器人会先把错的动作做完；但监控不能让机器人停下来等它，改成后台监控后，6 秒的紧急情况从 5 次全失败变成 5 次全成功。第四，快慢两个脑子同时跑，按现在的做法还没有带来好处，因为慢脑出一份完整计划要 20 秒到 80 秒，来不及用上；我们也试了三个需要先找东西的长任务，发现目前主要卡在机械臂抓取不稳上。</p>
  <p>另外，我们在原考试里发现并修正了几处问题，比如把"放在盒子顶上"误判成"放进盒子里"；修正后的计分器在人类示范上认可了 40 个任务中的 37 个，官方计分只认可 6 个。下一步是先修好抓取，再让慢思考及时发挥作用，并在更多任务和模型上验证。</p>
</div></section>

<!-- 21 问答 -->
<section class="slide presenter-only"><div class="wrap">
  <span class="tag gray">附录</span>
  <h2>可能被问到的问题</h2>
  <dl class="qa">
    <dt>为什么不在真机器人上做？</dt>
    <dd>先在模拟器里把考试规则和方法做扎实。模拟器能精确控制时间、可以重复，方便公平比较；计划书里真机验证是最后一步的可选项。</dd>
    <dt>和 RoboCerebra 原来的考法有什么本质区别？</dt>
    <dd>原考法里模型思考时世界不动，失败了还能重置；我们让世界按真实时间运行，并加入突发事件，所以能测出"想得慢"导致的失败。</dd>
    <dt>"勾选项"是我们的方法吗？</dt>
    <dd>不是，它来自 2026 年的 Visual Jev 论文，我们借用了"做选择题而不写作文"的思路。我们的贡献是这套实时考试、评测规则，以及快慢配合和共享缓存的实验分析。</dd>
    <dt>既然勾选项又快又好，还要慢脑做什么？</dt>
    <dd>现在的突发事件任务比较短，快脑够用。在需要多步推理、要先去找东西的长任务上，快脑容易兜圈子，比如一局里反复开关抽屉 30 多次，慢脑应该在这里发挥作用，这正是下一步要验证的。</dd>
    <dt>每组只跑 5 次够吗？</dt>
    <dd>作为初期结果足够看出方向，比如 5 次全成功和 5 次全失败的差别很明显。正式实验会扩大任务数和重复次数，并做统计检验。</dd>
  </dl>
</div></section>

<!-- 22 附录：原始分析图 -->
<section class="slide presenter-only"><div class="wrap">
  <span class="tag gray">附录</span>
  <h2>原始分析图</h2>
  <p class="small">前面几页的汇报版图片由同一份数据重画，字号更大、名称更通俗。下面是分析报告中的原图，方法名对照："仅快·Jev 候选打分"= 勾选项的快脑；"仅快·文本"= 写回答的快脑；"仅慢"= 深度思考；"双分支"= 快脑加慢脑；"禁缓存"= 不共享缓存的对照。</p>
  <div class="grid3">
    <figure><img src="{{e1_all}}" alt="原始图：改主意后的响应延迟"><figcaption>改主意后的响应延迟，第二轮 200 局中的 70 局</figcaption></figure>
    <figure><img src="{{e3_matrix}}" alt="原始图：限时关闭的成功矩阵"><figcaption>限时关闭的成功矩阵，含不共享缓存的对照</figcaption></figure>
    <figure><img src="{{monitor}}" alt="原始图：监控方式对照"><figcaption>监控方式对照，第二批实验</figcaption></figure>
  </div>
</div></section>

<div id="bar"></div>
<div id="help">← → 翻页　点击图片放大　S 滚动阅读　P 打印</div>
<div id="lightbox"><img alt="放大的图片"></div>
<div id="nav"><span id="count"></span><button id="prev" aria-label="上一页">‹ 上一页</button><button id="next" aria-label="下一页">下一页 ›</button></div>

<script>
  const slides = Array.from(document.querySelectorAll('.slide'));
  const bar = document.getElementById('bar'), count = document.getElementById('count');
  let cur = 0;
  function show(n) {
    cur = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach((s, k) => s.classList.toggle('active', k === cur));
    count.textContent = (cur + 1) + ' / ' + slides.length;
    bar.style.width = ((cur + 1) / slides.length * 100) + '%';
    history.replaceState(null, '', '#' + (cur + 1));
  }
  document.addEventListener('keydown', e => {
    if (document.getElementById('lightbox').style.display === 'flex') return;
    if (document.body.classList.contains('scroll') && e.key !== 's' && e.key !== 'S') return;
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'].includes(e.key)) { e.preventDefault(); show(cur + 1); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'].includes(e.key)) { e.preventDefault(); show(cur - 1); }
    else if (e.key === 'Home') show(0);
    else if (e.key === 'End') show(slides.length - 1);
    else if (e.key === 's' || e.key === 'S') { document.body.classList.toggle('scroll'); if (!document.body.classList.contains('scroll')) show(cur); }
    else if (e.key === 'p' || e.key === 'P') window.print();
  });
  const lb = document.getElementById('lightbox');
  document.querySelectorAll('figure img').forEach(img => img.addEventListener('click', () => { lb.querySelector('img').src = img.src; lb.style.display = 'flex'; }));
  lb.addEventListener('click', () => { lb.style.display = 'none'; });
  document.addEventListener('keydown', e => { if (lb.style.display === 'flex' && e.key === 'Escape') { lb.style.display = 'none'; e.stopImmediatePropagation(); } }, true);
  document.getElementById('prev').onclick = () => show(cur - 1);
  document.getElementById('next').onclick = () => show(cur + 1);
  show((parseInt(location.hash.slice(1)) || 1) - 1);
</script>
</body>
</html>
"""

out = HTML        # 群发版（只讲实验结果）由 make_group_results.py 单独生成
for k, v in IMG.items():
    out = out.replace("{{" + k + "}}", v)
assert "{{" not in out, "unfilled placeholder"
dst = NOTES / "进度汇报_2026-10-18.html"
dst.write_text(out, encoding="utf-8")
print("written", dst, f"{len(out) / 1e6:.2f} MB", "slides:", out.count('<section class="slide'))
