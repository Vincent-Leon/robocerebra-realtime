"""群发版：只讲实验结果（面向熟悉项目的课题组，正式方法名），生成单文件 HTML 并用 Chrome 导出 16:9 PDF。
样式取自 make_talk_html.py，图片来自 notes/figs_group/（plot_talk_figs.py --style=group）。
用法: python -I make_group_results.py <具身智能项目根目录>
"""
import base64, re, subprocess, sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve(); NOTES = ROOT / "notes"; FIG = NOTES / "figs_group"
CSS = re.search(r"<style>.*?</style>", (ROOT / "exp" / "make_talk_html.py").read_text(encoding="utf-8"), re.S).group(0)
IMG = {k: "data:image/png;base64," + base64.b64encode((FIG / f).read_bytes()).decode() for k, f in {
    "decision": "fig_decision_latency.png", "kv": "fig_kv_cache.png", "tl_e1": "fig_timeline_e1.png", "tl_e3": "fig_timeline_e3.png",
    "e1": "fig_e1_all_talk.png", "e3": "fig_e3_matrix_talk.png", "mon": "fig_monitor_talk.png"}.items()}

BODY = r"""
<!-- 1 封面 -->
<section class="slide cover"><div class="wrap">
  <span class="tag">实验结果 · 2026-10-18</span>
  <h1 style="font-size: clamp(36px, 4.6vw, 70px);">实时快慢思考基准：第二轮实验结果</h1>
  <p class="sub">第二轮 200 局 + 第二批 145 局，共 345 局，全部通过实时性检查</p>
  <p class="one">核心结论：动态事件下决策延迟决定成败。Jev 快分支单次决策 0.4 s，是唯一在全部事件场景都成功的方法；事件监控必须非阻塞；慢分支的完整计划来得太晚，双分支尚无收益。</p>
</div></section>

<!-- 2 实验设置 -->
<section class="slide"><div class="wrap">
  <span class="tag gray">实验设置</span>
  <h2>实验设置</h2>
  <table>
    <tr><th style="width:16%">项目</th><th>设置</th></tr>
    <tr><td>环境</td><td>RoboCerebra / LIBERO，实时运行（RTR = 1）；每局检查滞后：最大 ≤ 0.25 s 且 p95 ≤ 50 ms，违规局作废重跑；场景几何用固定种子</td></tr>
    <tr><td>模型</td><td>Qwen3.8-27B，L20 单卡 vLLM，FP8，开启前缀缓存；所有方法共用同一提示布局与运行器</td></tr>
    <tr><td>执行器与计分</td><td>脚本化技能，抽屉与储物盒为抽象技能；修复版计分 v5</td></tr>
    <tr><td>事件</td><td>E1 放置途中改目标（Ideal/case1、case6）；E3 抽屉限时关闭，6 / 9 / 12 s 窗（case6）；无事件对照（case6）</td></tr>
    <tr><td>长任务</td><td>Memory_Exploration case10 / case6 / case5，目标物体在柜内抽屉、关闭时不可见；上限 300 s、40 次技能</td></tr>
    <tr><td>方法</td><td>仅快·文本、仅慢（开思考）、仅快·Jev、双分支（文本或 Jev 快分支）；事件监控有 / 无、阻塞 / 非阻塞；禁用前缀缓存对照</td></tr>
    <tr><td>重复</td><td>每组 5 个种子</td></tr>
  </table>
</div></section>

<!-- 3 总览 -->
<section class="slide"><div class="wrap">
  <span class="tag">总览</span>
  <h2>结果总览（第二轮，case1 / case6）</h2>
  <table>
    <tr><th>方法</th><th>E1 响应 case1 / case6</th><th>E1 成功</th><th>E3 6 s</th><th>E3 9 s</th><th>E3 12 s</th><th>无事件完成</th><th>单次决策</th></tr>
    <tr><td><b>仅快·Jev</b></td><td class="num">0.8 / 0.9 s</td><td class="num">10/10</td><td class="num ok">5/5</td><td class="num ok">5/5</td><td class="num ok">5/5</td><td class="num">26.6 s</td><td class="num">0.40 s</td></tr>
    <tr><td><b>双分支·Jev</b></td><td class="num">0.8 / 1.1 s</td><td class="num">10/10</td><td class="num ok">5/5</td><td class="num ok">5/5</td><td class="num ok">5/5</td><td class="num">26.5 s</td><td class="num">0.42 s</td></tr>
    <tr><td>仅快·文本 + 监控</td><td class="num">4.8 / 8.8 s</td><td class="num">9/10</td><td class="num"><span class="bad">0/5</span>，非阻塞 <span class="ok">5/5</span></td><td class="num">5/5</td><td class="num">5/5</td><td class="num">43.6 s</td><td class="num">2.6 s</td></tr>
    <tr><td>双分支·文本</td><td class="num">5.2 / 17.2 s</td><td class="num">8/10</td><td class="num"><span class="bad">0/5</span>，非阻塞 <span class="ok">5/5</span></td><td class="num">5/5</td><td class="num">5/5</td><td class="num">38.9 s</td><td class="num">2.8 s</td></tr>
    <tr><td>仅慢 + 监控</td><td class="num">7.7 / 7.7 s</td><td class="num">10/10</td><td class="num bad">0/5</td><td class="num">1/5</td><td class="num">4/5</td><td class="num">64.3 s</td><td class="num">8.8 s</td></tr>
    <tr><td>仅快·文本，无监控</td><td class="num">15.2 / 13.1 s</td><td class="num">10/10</td><td class="num">5/5</td><td class="num">未测</td><td class="num">未测</td><td class="num">未测</td><td class="num">2.6 s</td></tr>
    <tr><td>仅慢，无监控</td><td class="num">30.9 / 51.1 s</td><td class="num">10/10</td><td class="num bad">0/5</td><td class="num">未测</td><td class="num">未测</td><td class="num">未测</td><td class="num">9.4 s</td></tr>
  </table>
  <p class="small">E1 响应：目标更新消息到首个指向新目标的放置命令，中位数，每格 5 次。E3：截止前完成放入的次数。E3 6 s 窗中"非阻塞"一栏来自第二批对照实验，其余为第二轮的阻塞式监控。单次决策为快分支调用延迟中位数，仅慢为每步开思考调用。</p>
</div></section>

<!-- 4 决策延迟 -->
<section class="slide"><div class="wrap">
  <span class="tag green">决策延迟</span>
  <h2>单次决策耗时决定能否应对动态事件</h2>
  <figure><img src="{{decision}}" alt="单次决策耗时"></figure>
  <div class="take"><p>Jev 快分支把合法动作列为候选，只生成 1 个 token 读取概率：0.4 s，约为文本快分支的 1/6、开思考的 1/20。慢分支一份完整计划在短任务上约 20 s，长任务上 78 s（p90 142–180 s）。</p></div>
</div></section>

<!-- 5 E1 -->
<section class="slide"><div class="wrap">
  <span class="tag green">E1 目标更新</span>
  <h2>E1：目标更新后的响应延迟</h2>
  <figure><img src="{{e1}}" alt="E1 响应延迟"><figcaption>每点一局，竖线为中位数，横轴为对数刻度。</figcaption></figure>
  <div class="take"><p>Jev 两种方法在两个任务上均约 1 s；带监控的文本与开思考方法 5–9 s。无监控时过时放置 20 次全部执行完，响应 13–51 s。双分支·文本在 case6 上有 2 次始终未响应，3/5 成功。</p></div>
</div></section>

<!-- 6 E1 时间线 -->
<section class="slide"><div class="wrap">
  <span class="tag green">E1 目标更新</span>
  <h2>E1 时间线示例（case1，种子 1）</h2>
  <figure><img src="{{tl_e1}}" alt="E1 时间线"></figure>
  <div class="hint"><p>Jev 监控 0.4 s 内取消过时放置并转向；仅慢的监控同样取消了过时放置，但下一步开思考决策耗时约 8 s；无监控时过时放置执行完，之后需取回黄油再改放。</p></div>
</div></section>

<!-- 7 E3 -->
<section class="slide"><div class="wrap cols fig-left">
  <figure><img src="{{e3}}" alt="E3 成功矩阵"></figure>
  <div>
    <span class="tag green">E3 限时关闭</span>
    <h2>E3：截止前完成率</h2>
    <ul>
      <li>Jev 两种方法在 6 / 9 / 12 s 窗全部按时完成，6 s 窗余量 2.8–2.9 s。</li>
      <li>仅慢在 6 s 窗 0/5、9 s 窗 1/5，开思考的决策延迟超出可行边界。</li>
      <li>诊断 oracle 测得：W 秒窗下每步决策须 ≤ W − 3.8 s，6 s 窗即 ≤ 2.2 s。</li>
    </ul>
    <div class="warn"><p>文本方法带监控在 6 s 窗 0/5、无监控反而 5/5：原因是监控阻塞，见第 9–10 页。</p></div>
  </div>
</div></section>

<!-- 8 KV -->
<section class="slide"><div class="wrap cols wide-left">
  <figure><img src="{{kv}}" alt="共享前缀缓存效果"><figcaption>同场景对照：短任务为 case6 无事件与 E3 6 s，长任务为 Memory_Exploration 三个任务。</figcaption></figure>
  <div>
    <span class="tag green">共享前缀缓存</span>
    <h2>共享 KV 前缀的收益</h2>
    <ul>
      <li>Jev 单次决策：短任务 0.69 → 0.40 s（−42%），长任务 0.99 → 0.52 s（−47%）。</li>
      <li>历史越长收益越大：提示超过 2500 token 时缓存命中率从约 55% 升到 66%（缓存按 784 token 整块复用）。</li>
      <li>无事件完成时间 28.7 → 26.6 s（−7%）；E3 6 s 窗余量 2.2 → 2.9 s。</li>
      <li>在这些任务上不改变成败。</li>
    </ul>
  </div>
</div></section>

<!-- 9 监控时间线 -->
<section class="slide"><div class="wrap">
  <span class="tag orange">事件监控</span>
  <h2>阻塞式监控在紧时间窗下有害</h2>
  <figure><img src="{{tl_e3}}" alt="E3 6 s 窗时间线"></figure>
  <div class="hint"><p>警告在"拿黄油"即将结束时到达。监控判断正确，结论是继续执行；但同步调用约 2 s，下一步决策被推迟约 1.7 s，放置被关闭的抽屉截断。改为非阻塞后，技能结束即进入下一步决策，监控结论若晚于技能结束则作废。</p></div>
</div></section>

<!-- 10 监控对照 -->
<section class="slide"><div class="wrap cols fig-left">
  <figure><img src="{{mon}}" alt="监控方式对照"></figure>
  <div>
    <span class="tag orange">事件监控</span>
    <h2>对照：只改监控方式</h2>
    <table>
      <tr><th>方法</th><th>非阻塞</th><th>阻塞</th></tr>
      <tr><td>仅快·文本</td><td class="ok">5/5</td><td class="bad">0/5</td></tr>
      <tr><td>双分支·文本</td><td class="ok">5/5</td><td class="bad">0/5</td></tr>
    </table>
    <div class="take"><p>监控本身是必要的：E1 中无监控时过时放置 20/20 被执行完。结论是监控必须非阻塞，不能在决策的关键路径上。仅慢的每步决策约 9 s，与监控方式无关。</p></div>
  </div>
</div></section>

<!-- 11 慢分支 -->
<section class="slide"><div class="wrap">
  <span class="tag purple">双分支</span>
  <h2>慢分支的完整计划来得太晚</h2>
  <div class="stats">
    <div class="stat"><b class="num">20 s</b><span>短任务：慢分支一份完整计划的中位数</span></div>
    <div class="stat"><b class="num">78 s</b><span>长任务：一份计划的中位数，p90 142–180 s</span></div>
    <div class="stat"><b class="num">0–12%</b><span>长任务：已执行技能中来自慢计划的比例</span></div>
  </div>
  <ul>
    <li>短任务上 Jev 快分支约 27 s 完成整个任务，慢计划多在快分支完成后才到达，双分支·Jev 与仅快·Jev 无差别。</li>
    <li>长任务上每局最多发布 1 份计划；到达时状态已变，常被状态检查判为不再适用而拒绝。状态检查本身工作正常。</li>
  </ul>
  <div class="take"><p>下一步：慢分支先发布前几步可执行片段，限制思考预算，并在快分支重复失败或循环时触发。</p></div>
</div></section>

<!-- 12 长任务 -->
<section class="slide"><div class="wrap">
  <span class="tag red">长任务</span>
  <h2>长任务：成败目前主要由执行器决定</h2>
  <table>
    <tr><th>方法</th><th>case10（11 个子目标）</th><th>case6（12 个）</th><th>case5（14 个，执行器上限 12）</th></tr>
    <tr><td>仅快·Jev</td><td class="num">5/5，100%</td><td class="num">0/5，60%</td><td class="num">0/5，24%</td></tr>
    <tr><td>双分支·Jev</td><td class="num">5/5，100%</td><td class="num">0/5，75%</td><td class="num">0/5，24%</td></tr>
    <tr><td>仅快·文本</td><td class="num">1/5，27%</td><td class="num">0/5，55%</td><td class="num">0/5，67%</td></tr>
    <tr><td>双分支·文本</td><td class="num">3/5，64%</td><td class="num">1/5，70%</td><td class="num">0/5，39%</td></tr>
    <tr><td>仅慢</td><td class="num">1/5，29%</td><td class="num">0/5，32%</td><td class="num">0/5，17%</td></tr>
  </table>
  <p class="small">每格：5 次中完成整个任务的次数，及子目标完成率均值。</p>
  <div class="warn">
    <p>case10 的失败几乎都是从抽屉里抓碗：抓取在抬升 3 cm 时判成功，随后碗从夹爪滑脱，下一步放置才报"手里没东西"，规划器随后反复抓取已卡歪的碗，结果呈两极，如仅快·文本逐种子 1、1、11、1、1 个子目标。case6 多停在 9/12，卡在抽屉内抓黄油；case5 平底锅超出臂展。</p>
    <p>因此长任务上的方法排序暂不作结论。同时观察到快分支会循环，例如 Jev 在 case5 平均每局开关抽屉 33 次。</p>
  </div>
</div></section>

<!-- 13 基准修正 -->
<section class="slide"><div class="wrap">
  <span class="tag gray">基准修正</span>
  <h2>本轮修正的基准问题及对此前结果的影响</h2>
  <div class="cols" style="grid-template-columns: 1.35fr .65fr;">
    <table>
      <tr><th>问题</th><th>影响与处理</th></tr>
      <tr><td>白色储物盒为前后开口方框，旧执行器竖直放置落在盒顶，v4 计分判为盒内</td><td>第一轮 case1 放盒子目标不可信；计分 v5 要求低于顶板，放置类目标须离手保持 5 帧</td></tr>
      <tr><td>技能结束时规划器读到旧快照，手中物体不准</td><td>第一轮 Jev 23/24 局重复抓取；已改为先发布新快照</td></tr>
      <tr><td>LIBERO 每次建环境随机摆放固定装置，位置差 1–2 cm</td><td>方法间非严格配对；已固定场景种子</td></tr>
      <tr><td>前置检查失败后协调器继续执行过时计划</td><td>第一轮双分支失败；已改为作废计划并按当前状态核对</td></tr>
    </table>
    <div>
      <div class="stats" style="grid-template-columns: 1fr 1fr;">
        <div class="stat"><b class="num" style="color:var(--green)">37/40</b><span>演示回放判为完成：修复版 v5</span></div>
        <div class="stat"><b class="num" style="color:var(--red)">6/40</b><span>官方计分</span></div>
      </div>
      <div class="hint"><p>原协议允许每步重置到演示状态：9 个任务 79 个子目标中，允许重置时完成 75 个，其中 22 个靠重置补上；不允许时 51 个。该组数字为第一轮执行器与 v4 计分，case1 待按 v5 重算。</p></div>
    </div>
  </div>
</div></section>

<!-- 14 结论与下一步 -->
<section class="slide"><div class="wrap cols">
  <div>
    <span class="tag">结论</span>
    <h2>结论</h2>
    <ol>
      <li>动态事件下决策延迟决定成败；Jev 快分支 0.4 s，是唯一在全部 E1 / E3 场景都成功的方法。</li>
      <li>共享前缀缓存使决策延迟降低 42–47%，历史越长收益越大。</li>
      <li>事件监控必要但必须非阻塞：仅改监控方式，文本方法 E3 6 s 窗从 0/5 到 5/5。</li>
      <li>慢分支完整计划 20–78 s，双分支目前无收益；长任务受执行器限制，暂不能评估慢分支。</li>
    </ol>
  </div>
  <div>
    <span class="tag gray">下一步</span>
    <h2>下一步</h2>
    <ol>
      <li>执行器：抓取后保持数步并以双指接触确认再报告成功，滑脱自动重抓；提高抽屉内抓取对物体位置的鲁棒性。</li>
      <li>慢分支：分段发布计划、限制思考预算、在快分支循环或重复失败时触发。</li>
      <li>扩大事件任务覆盖，正式评测 E2；用 v5 重算原始协议对照。</li>
      <li>同预算对照与其他模型基线。</li>
    </ol>
    <p class="small">局限：事件实验覆盖 2 个任务，每组 5 次；抽屉与储物盒为抽象技能；单一模型。</p>
  </div>
</div></section>
"""

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>实时快慢思考基准：第二轮实验结果 · 2026-10-18</title>
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
html_out = NOTES / "实验结果_2026-10-18_群发版.html"; html_out.write_text(HTML, encoding="utf-8")
pdf_out = NOTES / "实时快慢思考基准_实验结果_2026-10-18.pdf"
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=8000", f"--print-to-pdf={pdf_out}", html_out.as_uri()], check=True, capture_output=True)
print("written", html_out, f"{len(HTML) / 1e6:.2f} MB, slides:", HTML.count('<section class="slide'))
print("written", pdf_out, f"{pdf_out.stat().st_size / 1e6:.2f} MB")
