"""同模型快慢双分支（缓存友好的共享前缀版，shared_prompt.py）× 实时异步环境 × 可选事件。
所有分支共用同一系统提示与"静态块 → 历史 → 图像 → 当前状态 → 模式指令"布局；--cache_bust=on 时内容相同但禁止复用缓存。
--slow=off 时只有单分支：--fast=text（仅快·文本）、--fast=think（开思考，即仅慢）、--fast=jev（仅快·Jev），所有方法共用同一提示布局与执行路径。
第二轮协调器（2026-10-17）：计划送达时按动作序列对齐、对不上时由快分支判断续接步骤、再从当前状态符号化验证剩余步骤（不可执行则拒绝并反馈）；
执行每一步前按当前状态判断：效果已成立则跳过，前置条件不满足则作废旧计划、由快分支接管并请求重新规划。
第三轮（2026-10-20，组会行动项"Prompt 注入"）：--slow=advice 时慢分支关闭思维链，只输出一两句建议（ADVISE 模式），
注入快分支的上下文（历史与当前状态之后）；在开局、技能失败、检测到循环、新消息时触发（--advice_every=N 另加每 N 个动作定期刷新）。
r3b：建议模式下快分支首次判"完成"后等慢分支核实建议（--done_verify_wait，默认 8 s，0 = 关闭）再决定。
r5（2026-10-26，两项改进，默认关闭即 r4 行为）：
  --fail_block=N：同一调用自上次成功以来失败 N 次即屏蔽（Jev 移出候选；文本 / 思考模式在提示中列出，仍选则按无效回复处理；
                  完整计划中的该步骤作废并重新规划）；任一子目标完成或发生随机扰动时清零。
  --done_verify=think|fast：快分支判"完成"时，由慢分支对照任务逐条核实（think 开思考；fast 关思考，最多 256 token）；未完成则把缺项作为建议交给快分支继续，每局最多 --verify_max 次。
用法: python run_dual_shared_episode.py Ideal/case6 [--events=...] [--fast=text|jev|think] [--slow=on|off|advice] [--cache_bust=on|off] [--monitor=on|off]
                                 [--fast_fallback=on|off] [--semantic_check=on|off] [--image=on|off] [--max_sim=240] [--max_skills=30] [--video] [--tag=NAME] [--seed=0]
                                 [--fail_block=0] [--done_verify=off|think|fast] [--verify_max=2]
                                 [--fast_model=NAME] [--slow_model=NAME] [--fast_profile=exp|gateway] [--slow_profile=exp|gateway]
                                 [--clock=wall|paused|token]
"""
import sys, time, threading, json
import numpy as np
import rc_env as R
from realtime_env import RealtimeSim
from llm_client import LLMClient
from llm_planner import SYSTEM, scene_text, parse_action, validate_action, to_executor_call
from dual_planner import Plan, parse_plan, call_str, step_status, check_plan, align_prefix, apply_effect
from shared_prompt import SharedPromptBuilder, static_block
from jev_fast import candidate_actions, candidates_text, jev_choose as _jev_choose_raw, LETTERS
from events import EventManager, load_specs

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
flags = {a[2:] for a in sys.argv[1:] if a.startswith("--") and "=" not in a}
tt, cn = (args[0] if args else "Ideal/case6").split("/")
fast_fallback = opt.get("fast_fallback", "on") == "on"; semantic_check = opt.get("semantic_check", "on") == "on"
monitor = opt.get("monitor", "on") == "on"; use_image = opt.get("image", "on") == "on"; cache_bust = opt.get("cache_bust", "off") == "on"
BUST_MODE = opt.get("bust_mode", "salt")   # 禁缓存方式：salt（r3b 起，每请求随机 cache_salt，输入不变）| nonce（r2/r3：系统提示开头放随机串）
assert BUST_MODE in ("salt", "nonce"), BUST_MODE
FAST_MODE = opt.get("fast", "text")     # fast: text | jev | think（think = 开思考的单分支 ACT，即"仅慢"）
SLOW_MODE = opt.get("slow", "on")       # slow: on（完整计划）| advice（r3：关思考、只给一两句建议，注入快分支）| off
assert FAST_MODE in ("text", "jev", "think"), FAST_MODE
assert SLOW_MODE in ("on", "off", "advice"), SLOW_MODE
SLOW_ON = SLOW_MODE != "off"; ADVICE = SLOW_MODE == "advice"
ADVICE_MAX_TOKENS = int(opt.get("advice_max_tokens", 120)); ADVICE_EVERY = int(opt.get("advice_every", 0))
DONE_VERIFY_WAIT = float(opt.get("done_verify_wait", 8))   # r3b：建议模式下快分支首次判"完成"后，等慢分支核实建议的最长时间（s）
MON_ASYNC = opt.get("monitor_async", "on") == "on"     # r2b：监控在独立线程判断，技能结束后协调器立即决策，不等监控（off = r2 的阻塞监控）
FAIL_BLOCK = int(opt.get("fail_block", 0))          # r5：失败屏蔽阈值，0 = 关闭
DONE_VERIFY = opt.get("done_verify", "off")         # r5：完成核实，off | think（慢分支开思考）| fast（关思考，也适用于不支持思考的模型）
assert DONE_VERIFY in ("off", "think", "fast"), DONE_VERIFY
CLOCK = opt.get("clock", "wall")                    # 10-27：计时方式 wall（真实时钟，默认）| paused（暂停时钟）| token（token 时钟），见 realtime_env.py
assert CLOCK in ("wall", "paused", "token"), CLOCK
BLOCK_INSIST = int(opt.get("block_insist", 3))      # r5：文本 / 思考模式连续第 N 次坚持选同一个被屏蔽的调用时放行执行（0 = 永不放行）
ADVICE_WAIT = float(opt.get("advice_wait", 0))      # r5d（10-29）：建议模式下技能失败后，快分支先等由这次失败触发的建议送达（最长这么多秒，墙钟）再决策；0 = 不等（r5c 行为）
REPLAN_WAIT = opt.get("replan_wait", "off")         # r5d：完整计划被状态检查 / 对账作废后，off = 立即重新规划（r5c）；state = 等下一个技能结束或仿真时间前进 5 s 再规划
assert REPLAN_WAIT in ("off", "state"), REPLAN_WAIT
VERIFY_MAX = int(opt.get("verify_max", 2)); VERIFY_MAX_TOKENS = int(opt.get("verify_max_tokens", 3072))
R5 = bool(FAIL_BLOCK) or DONE_VERIFY != "off"
max_sim = float(opt.get("max_sim", 240)); max_skills = int(opt.get("max_skills", 30)); seed = int(opt.get("seed", 0))
ev_path = opt.get("events"); ev_name = ev_path.split("/")[-1].replace(".json", "") if ev_path else "noevent"
_sfx = (f"_fb{FAIL_BLOCK}" if FAIL_BLOCK else "") + {"off": "", "think": "_dv", "fast": "_dvf"}[DONE_VERIFY] + ("" if use_image else "_noimg") + ("" if CLOCK == "wall" else f"_clk{CLOCK}") \
    + (f"_aw{ADVICE_WAIT:g}" if ADVICE_WAIT > 0 else "") + ("_rws" if REPLAN_WAIT == "state" else "")
tag = opt.get("tag", f"{ev_name}_{'dualadvice' if ADVICE else ('dualshared' if SLOW_ON else 'fastshared')}_{FAST_MODE}{'_bust' if cache_bust else ''}{'' if monitor else '_nomon'}{'_monsync' if (monitor and not MON_ASYNC) else ''}{_sfx}_s{seed}")
import os as _os
out = R.RUNS_ROOT / _os.environ.get("RUNS_SUBDIR", "llm") / f"{tt}_{cn}" / tag
if "skip_existing" in flags and (out / "episode.json").exists():
    print("skip existing:", out); sys.exit(0)
out.mkdir(parents=True, exist_ok=True)
from rc_dynamics import RCDynamics, SHIFT_TYPES
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=tt in SHIFT_TYPES)
sim = RealtimeSim(case, rtr=1.0, camera=True, max_sim_time=max_sim, clock=CLOCK)
sim.dynamics = RCDynamics(case, seed=seed)          # r4：RoboCerebra 官方动态条件（Random_Disturbance / Observation_Mismatching / Mix）
hide_closed = opt.get("hide_closed", "on") == "on"; sim.hide_closed = hide_closed      # 关闭抽屉内的物体不可见（保留原任务的探索/记忆要求）
frames = []
def grab(s):
    snap = s.latest()
    if "video" in flags and snap is not None and snap.agentview is not None and snap.step % 4 == 0: frames.append(snap.agentview)
sim.on_tick = grab
mgr = None
if ev_path: mgr = EventManager(load_specs(ev_path)); mgr.attach(sim)
# r5：快慢分支可分别指定模型与服务（--fast_model / --slow_model，--fast_profile / --slow_profile = exp | gateway）；默认两分支同一模型
slow_client = LLMClient(model=opt.get("slow_model"), profile=opt.get("slow_profile"))
fast_client = LLMClient(model=opt.get("fast_model"), profile=opt.get("fast_profile"))
slow_client.seed = seed; fast_client.seed = seed + 1000
if cache_bust and BUST_MODE == "salt":
    for _c in (slow_client, fast_client): _c.cache_salt_per_request = True
for _c in (slow_client, fast_client):                    # 开局前预热连接，避免首个请求与仿真主线程争用 GIL
    _c.chat(_c.build_messages(None, "ok"), max_tokens=1, thinking=False); _c.log.clear()


def _clocked_chat(fn):
    """暂停 / token 时钟：调用在途时仿真冻结，返回后按时钟规则推进到交付时刻再把结果交给调用方；真实时钟下为空操作。"""
    def w(*a, **k):
        sim.clock_begin(); r = None
        try:
            r = fn(*a, **k); return r
        finally:
            u = (getattr(r, "usage", None) or {}) if r is not None else {}
            sim.clock_wait(sim.clock_end(u.get("prompt_tokens"), cached_of(r) if r is not None else None, u.get("completion_tokens"),
                                         getattr(r, "latency", None) if r is not None else None))
    return w


if CLOCK != "wall":
    for _c in (slow_client, fast_client): _c.chat = _clocked_chat(_c.chat)

lock = threading.Lock()
st = {"plan": None, "cursor": 0, "seq": 0, "replan_reason": None, "executed": [], "done": False, "slow_busy": False, "inflight": None,
      "advice": None, "since_advice": 0,
      "fail_streak": {}, "world": None, "n_verify": 0, "n_blocked": 0, "insist": {"call": None, "n": 0}, "n_override": 0,
      "adv_calls": 0, "adv_last_reason": None}                                                                            # r5d：建议调用完成计数（失败后等建议用）      # r5：失败计数、进展 / 扰动签名、核实次数、被拒的屏蔽调用数
replan_evt = threading.Event()
history, calls_log = [], []


def rel(t): return t - sim.sim_t0


def request_replan(reason):
    with lock:
        st["replan_reason"] = reason
    replan_evt.set(); sim.log_event("replan_requested", reason=reason[:120])


builder = {"b": None}


def get_builder():
    if builder["b"] is None:
        env = sim.env; m = env.sim.model
        objects, fixtures, regions = list(env.objects_dict.keys()), list(env.fixtures_dict.keys()), R.agent_regions(env)   # r4：含灶台等功能性站点
        centers = {r: list(map(float, env.sim.data.site_xpos[m.site_name2id(r)])) for r in regions if r in m.site_names}
        drawers = [r for r in regions if env.object_sites_dict.get(r) is not None and (env.object_sites_dict[r].joints or [])]
        builder["b"] = SharedPromptBuilder(static_block(case.task_line, objects, fixtures, regions, centers, drawers), use_image=use_image,
                                           cache_bust=cache_bust and BUST_MODE == "nonce")
    return builder["b"]


_drawers = {"d": None}


def drawer_regions():
    if _drawers["d"] is None:
        env = sim.env
        _drawers["d"] = [r_ for r_ in env.regions if env.object_sites_dict.get(r_) is not None and (env.object_sites_dict[r_].joints or [])]
    return _drawers["d"]


def jev_choose(client, msgs, cands):
    """Jev 一次前向；暂停 / token 时钟下与 chat 相同地冻结仿真并按时钟规则交付（真实时钟下为空操作）。"""
    sim.clock_begin(); act = info = None
    try:
        act, info = _jev_choose_raw(client, msgs, cands); return act, info
    finally:
        inf = info or {}; u = inf.get("usage") or {}
        sim.clock_wait(sim.clock_end(u.get("prompt_tokens"), inf.get("cached_tokens"), u.get("completion_tokens"), inf.get("latency")))


def cached_of(r):
    d = (r.usage or {}).get("prompt_tokens_details") or {}
    return d.get("cached_tokens") if isinstance(d, dict) else None


def ctx():
    env = sim.env
    import llm_planner as LP
    regions = R.agent_regions(env)                      # r4：含灶台等功能性站点
    LP.DRAWER_REGIONS = [r for r in regions if env.object_sites_dict.get(r) is not None and (env.object_sites_dict[r].joints or [])]
    return list(env.objects_dict.keys()), list(env.fixtures_dict.keys()), regions


def slow_thread():
    objects, fixtures, regions = ctx()
    while sim.running:
        if not replan_evt.wait(timeout=0.2): continue
        replan_evt.clear()
        with lock: reason = st["replan_reason"]; st["slow_busy"] = True
        snap = sim.latest()
        if ADVICE:
            advise(snap, objects, reason); continue
        msgs = get_builder().messages(snap, objects, list(history), "PLAN", extra=f"REPLAN REASON: {reason}")
        sim.log_event("think_start", step_idx=f"slow{st['seq']}", obs_version=snap.version, branch="slow", reason=reason[:80])
        r = slow_client.chat(msgs, max_tokens=4096, thinking=True)
        sim.log_event("think_end", step_idx=f"slow{st['seq']}", latency=round(r.latency, 2), completion_tokens=r.usage.get("completion_tokens"), error=r.error)
        d, err = parse_plan(r.text)
        steps = []; plan_err = None
        if d is not None:
            for i_, s_ in enumerate(d["plan"]):
                if not isinstance(s_, dict): plan_err = f"step {i_+1} is not an object"; break
                e_ = validate_action(s_, objects, regions, fixtures)
                if e_ is not None: plan_err = f"step {i_+1} {call_str(s_)}: {e_}"; break
                steps.append(s_)
            if plan_err is not None:
                d = None; err = plan_err                 # 整体拒绝：不静默丢弃非法步骤
        slow_rec = {"branch": "slow", "t_obs": rel(snap.sim_time), "latency": r.latency, "ttft": r.ttft, "cached_tokens": cached_of(r), "usage": r.usage, "response": r.text, "error": r.error or err, "n_steps": len(steps), "reason": reason,
                    "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s}
        calls_log.append(slow_rec)
        if d is None:
            with lock: st["slow_busy"] = False
            sim.log_event("plan_rejected", error=str(r.error or err)[:120])
            time.sleep(2.0)                                     # 退避，避免对服务端形成重试风暴
            request_replan(f"previous plan output invalid: {str(r.error or err)[:200]}"); continue
        # 对账（第二轮）：① 计划观测之后成功执行的动作按顺序与计划开头匹配；② 有对不上的动作时，由快分支判断从计划哪一步继续；
        # ③ 从当前状态（加上正在执行动作的预期效果）符号化验证剩余步骤；不可执行则整体拒绝，并把原因反馈给慢分支重新规划
        with lock: done_after = [c for (t_end, c, ok) in st["executed"] if ok and t_end > snap.sim_time]
        k, unexplained = align_prefix(steps, done_after); how = "prefix"
        if unexplained and steps:
            k2 = fast_resume_point(sim.latest(), steps, snap.sim_time); how = "fast"
            if k2 is None: plan_err = "the plan no longer fits the current state (other actions were executed while it was being made)"
            else: k = k2
        if plan_err is None and steps:
            now = sim.latest()
            with lock: infl = st["inflight"]
            held, drw = now.held, dict(now.drawers or {}); k_chk = k
            if infl is not None:
                if k < len(steps) and call_str(steps[k]) == call_str(infl): k_chk = k + 1
                held, drw = apply_effect(infl, held, drw)
            perr = check_plan(steps[k_chk:], held, drw, drawer_regions())
            if perr is not None: plan_err = f"{perr}; the robot is currently holding {now.held or 'nothing'}"
        if plan_err is not None:
            with lock: st["slow_busy"] = False; n_ex = len(st["executed"])
            slow_rec["error"] = plan_err; slow_rec["rejected_stage"] = "state check"
            sim.log_event("plan_rejected", error=plan_err[:160], stage="state check", align=how, steps=[call_str(s_) for s_ in steps][:12])
            if REPLAN_WAIT == "state":
                # r5d：等世界状态变化再重新规划。暂停时钟下规划期间仿真冻结，快分支已提交但未执行的动作不在规划快照里，
                # 立即重新规划会在同一快照上得到同一份计划、再次作废（r5c 中单局最多作废近 300 次）
                t_s = sim.latest().sim_time; t_w = time.time()
                while sim.running:
                    with lock: changed = len(st["executed"]) > n_ex
                    if changed or sim.latest().sim_time - t_s >= 5.0: break
                    time.sleep(0.05)
                sim.log_event("replan_wait", changed=changed, waited_sim=round(sim.latest().sim_time - t_s, 2), waited_wall=round(time.time() - t_w, 2))
            request_replan(f"previous plan rejected: {plan_err[:200]}"); continue
        with lock:
            st["seq"] += 1
            st["plan"] = Plan(st["seq"], snap.version, snap.sim_time, len(snap.messages), steps, d.get("thought", ""), r.latency)
            st["cursor"] = k; st["slow_busy"] = False
            if not steps: st["done"] = True
        sim.log_event("plan_published", plan_id=st["seq"], obs_version=snap.version, n_steps=len(steps), skipped_already_done=k, align=how, unexplained=unexplained,
                      latency=round(r.latency, 2), steps=[call_str(s_) for s_ in steps][:12])


def advise(snap, objects, reason):
    """r3 建议模式：关闭思维链，慢分支只输出一两句建议；成功解析后替换当前建议（快分支下一次决策即可看到）。"""
    with lock: blk = set(st.get("blocked") or ())
    msgs = get_builder().messages(snap, objects, list(history), "ADVISE", extra=(f"WHY YOU ARE ASKED NOW: {reason}" + ("\n" + blocked_note(blk) if blk else "")))
    sim.log_event("think_start", step_idx=f"adv{st['seq']}", obs_version=snap.version, branch="slow", reason=reason[:80])
    r = slow_client.chat(msgs, max_tokens=ADVICE_MAX_TOKENS, thinking=False)
    sim.log_event("think_end", step_idx=f"adv{st['seq']}", latency=round(r.latency, 2), completion_tokens=(r.usage or {}).get("completion_tokens"), error=r.error)
    text, err = "", r.error
    if not err:
        try:
            text = str(json.loads(r.text[r.text.index("{"):r.text.rindex("}") + 1]).get("advice", ""))
        except Exception:
            text = r.text or ""                                  # 非 JSON：直接用原文
        text = " ".join(text.split())[:400]
        if not text: err = "empty advice"
    calls_log.append({"branch": "slow", "mode": "ADVISE", "t_obs": rel(snap.sim_time), "latency": r.latency, "ttft": r.ttft, "cached_tokens": cached_of(r), "usage": r.usage,
                      "response": r.text, "error": err, "reason": reason, "advice": text, "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
    with lock:
        st["slow_busy"] = False; st["adv_calls"] += 1; st["adv_last_reason"] = reason
        if not err:
            st["seq"] += 1; st["advice"] = {"text": text, "t": snap.sim_time, "reason": reason, "seq": st["seq"]}; st["since_advice"] = 0
    if err:
        sim.log_event("advice_invalid", error=str(err)[:120]); time.sleep(1.0)
    else:
        sim.log_event("advice_published", advice_id=st["seq"], obs_version=snap.version, latency=round(r.latency, 2), text=text[:200])


_loop = {"sig": None, "at": -99}


def loop_reason(n_skills):
    """检测快分支是否陷入循环：同一调用连续 3 次，或两个调用交替（A B A B）；同一模式 4 个动作内不重复触发。"""
    calls = [h["call"] for h in history[-4:]]
    sig = None
    if len(calls) >= 3 and calls[-1] == calls[-2] == calls[-3]:
        sig = f"the same action {calls[-1]} was chosen three times in a row"
    elif len(calls) >= 4 and calls[-1] == calls[-3] and calls[-2] == calls[-4] and calls[-1] != calls[-2]:
        sig = f"the controller is alternating between {calls[-2]} and {calls[-1]}"
    if sig is None or (sig == _loop["sig"] and n_skills - _loop["at"] < 4): return None
    _loop["sig"], _loop["at"] = sig, n_skills
    return "possible loop: " + sig


def fast_resume_point(snap, steps, t_obs):
    """计划生成期间执行过与计划开头对不上的动作：由快分支判断从计划第几步继续（返回 0 起的下标；None 表示计划已不适用）。"""
    objects, _, _ = ctx()
    listing = "\n".join(f"  {i + 1}. {call_str(s_)}" for i, s_ in enumerate(steps))
    extra = (f"NEW PLAN from the deliberate planner, made from the observation at sim time {rel(t_obs):.1f} s "
             f"(HISTORY entries after that time were executed while it was being made):\n{listing}")
    sim.log_event("think_start", step_idx=f"res{len(calls_log)}", obs_version=snap.version, branch="monitor")
    if FAST_MODE == "jev":
        opts = [f"resume at step {i + 1}: {call_str(s_)}" for i, s_ in enumerate(steps)][:len(LETTERS) - 1] + ["none: the plan no longer fits the current state"]
        opt_txt = ("Which plan step should be executed next so that nothing already achieved is repeated and nothing still needed is skipped?\nOPTIONS:\n"
                   + "\n".join(f"  {LETTERS[i]}) {o}" for i, o in enumerate(opts)))
        msgs = get_builder().messages(snap, objects, list(history), "DECIDE", extra=extra + "\n" + opt_txt)
        pick, info = jev_choose(fast_client, msgs, [{"skill": o, "args": []} for o in opts])
        idx = opts.index(pick["skill"]) if pick else len(opts) - 1
        k = idx if idx < len(opts) - 1 else None
        sim.log_event("think_end", step_idx=f"res{len(calls_log)}", latency=round(info.get("latency", 0), 3), resume=k)
        calls_log.append({"branch": "check", "mode": "RESUME-jev", "t_obs": rel(snap.sim_time), "latency": info.get("latency"), "ttft": info.get("latency"),
                          "cached_tokens": info.get("cached_tokens"), "usage": info.get("usage"), "response": info.get("generated"), "decision": k, "dist": info.get("dist")})
        return k
    r = fast_client.chat(get_builder().messages(snap, objects, list(history), "RESUME", extra=extra), max_tokens=80, thinking=False)
    k = None
    try:
        dd = json.loads(r.text[r.text.index("{"):r.text.rindex("}") + 1]); n = int(dd.get("resume_step", 0))
        k = n - 1 if 1 <= n <= len(steps) else None
    except Exception:
        pass
    sim.log_event("think_end", step_idx=f"res{len(calls_log)}", latency=round(r.latency, 3), resume=k)
    calls_log.append({"branch": "check", "mode": "RESUME", "t_obs": rel(snap.sim_time), "latency": r.latency, "ttft": r.ttft, "cached_tokens": cached_of(r), "usage": r.usage,
                      "response": r.text, "decision": k, "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
    return k


_last_err = {"e": None, "blocked": False}


def verify_done(snap, objects):
    """r5：快分支判"完成"时，由慢分支对照任务逐条核实（--done_verify=think 开思考，fast 关思考），返回 (complete, missing)。
    出错或无法解析时按"完成"处理，不因核实本身失败把 episode 卡住。"""
    k = st["n_verify"]
    msgs = get_builder().messages(snap, objects, list(history), "VERIFY")
    sim.log_event("think_start", step_idx=f"ver{k}", obs_version=snap.version, branch="verify")
    think = DONE_VERIFY == "think"
    r = slow_client.chat(msgs, max_tokens=VERIFY_MAX_TOKENS if think else 256, thinking=think)
    sim.log_event("think_end", step_idx=f"ver{k}", latency=round(r.latency, 2), completion_tokens=(r.usage or {}).get("completion_tokens"), error=r.error)
    complete, missing, perr = True, "", None
    if not r.error:
        try:
            d = json.loads(r.text[r.text.index("{"):r.text.rindex("}") + 1])
            complete = bool(d.get("complete", True)); missing = " ".join(str(d.get("missing", "")).split())[:300]
        except Exception as e:
            perr = f"unparsable verify reply: {e!r}"[:120]
    calls_log.append({"branch": "verify", "mode": "VERIFY", "t_obs": rel(snap.sim_time), "latency": r.latency, "ttft": r.ttft, "cached_tokens": cached_of(r), "usage": r.usage,
                      "response": r.text, "error": r.error or perr, "complete": complete, "missing": missing, "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
    sim.log_event("done_verify", complete=complete, missing=missing[:120], latency=round(r.latency, 2), error=(r.error or perr))
    return complete, missing


def blocked_note(blocked):
    return (f"BLOCKED CALLS (each failed {FAIL_BLOCK} times since its last success or the last progress; do not choose them again): "
            + "; ".join(sorted(blocked))) if blocked else ""


def fast_next_action(snap, objects, fixtures, regions, blocked=frozenset()):
    plan_txt = ""
    with lock:
        p = st["plan"]; adv = st["advice"]
        if p is not None:
            plan_txt = "\nCURRENT PLAN from the deliberate planner (made at sim time %.1fs, may be outdated): %s" % (rel(p.sim_time), " -> ".join(call_str(s_) for s_ in p.steps[st["cursor"]:]) or "(finished)")
        elif adv is not None:
            plan_txt = "\nADVICE from the deliberate planner (given at sim time %.1fs; it was asked because: %s): %s" % (rel(adv["t"]), adv["reason"][:100], adv["text"])
    if blocked:
        plan_txt = (plan_txt + "\n" + blocked_note(blocked)).strip()
    if FAST_MODE == "jev":
        drawers = [r_ for r_ in regions if sim.env.object_sites_dict.get(r_) is not None and (sim.env.object_sites_dict[r_].joints or [])]
        cands = candidate_actions(snap, objects, fixtures, regions, drawers)
        if blocked:                                              # r5：屏蔽的调用移出候选（至少留下一个技能候选，否则不过滤）
            kept = [c for c in cands if c.get("done") or c.get("skill") in (None, "wait") or call_str(c) not in blocked]
            if any(c.get("skill") not in (None, "wait") and not c.get("done") for c in kept): cands = kept
        msgs = get_builder().messages(snap, objects, list(history), "CHOOSE", extra=(plan_txt.strip() + "\n\n" + candidates_text(cands)).strip())
        sim.log_event("think_start", step_idx=f"fast{len(calls_log)}", obs_version=snap.version, branch="fast")
        act, info = jev_choose(fast_client, msgs, cands)
        sim.log_event("think_end", step_idx=f"fast{len(calls_log)}", latency=round(info.get("latency", 0), 3))
        calls_log.append({"branch": "fast", "mode": "jev", "t_obs": rel(snap.sim_time), "latency": info.get("latency"), "ttft": info.get("latency"),
                          "cached_tokens": info.get("cached_tokens"), "usage": info.get("usage"), "response": info.get("generated"), "error": info.get("error"),
                          "dist": info.get("dist"), "n_candidates": len(cands), "choice": info.get("choice"), "p_choice": info.get("p_choice")})
        class _R: pass
        r_ = _R(); r_.latency = info.get("latency", 0); r_.text = ""; r_.usage = info.get("usage") or {}; r_.error = info.get("error")
        _last_err["e"] = info.get("error")
        return act, r_
    msgs = get_builder().messages(snap, objects, list(history), "ACT", extra=plan_txt.strip())
    sim.log_event("think_start", step_idx=f"fast{len(calls_log)}", obs_version=snap.version, branch="fast")
    think = FAST_MODE == "think"
    r = fast_client.chat(msgs, max_tokens=int(opt.get("think_max_tokens", 4096)) if think else 256, thinking=think)
    sim.log_event("think_end", step_idx=f"fast{len(calls_log)}", latency=round(r.latency, 2), completion_tokens=(r.usage or {}).get("completion_tokens"))
    act, perr = parse_action(r.text)
    verr = validate_action(act, objects, regions, fixtures) if act else None
    _last_err["blocked"] = False
    if act and not verr and not act.get("done") and blocked and call_str(act) in blocked:     # r5：仍选被屏蔽的调用 → 退回让模型另选
        c = call_str(act)
        with lock:
            ins = st["insist"]; ins["n"] = ins["n"] + 1 if ins["call"] == c else 1; ins["call"] = c; k = ins["n"]
            st["n_blocked"] += 1
        if BLOCK_INSIST and k >= BLOCK_INSIST:                   # 连续坚持 N 次：放行执行，避免陷在拒绝循环里（例如手上的东西只能放这里）
            with lock: st["n_override"] += 1; ins["n"] = 0
            sim.log_event("blocked_override", call=c, insist=k)
        else:
            verr = f"blocked call chosen again: {c} (failed {FAIL_BLOCK} times; choose something else)"
            _last_err["blocked"] = True
    elif act and not verr:
        with lock: st["insist"]["n"] = 0
    calls_log.append({"branch": "fast", "t_obs": rel(snap.sim_time), "latency": r.latency, "ttft": r.ttft, "cached_tokens": cached_of(r), "usage": r.usage, "response": r.text, "error": r.error or perr or verr,
                      "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
    _last_err["e"] = r.error or perr or verr
    return (None if (act is None or verr) else act), r


def fast_check_step(snap, step, executing=False):
    objects, _, _ = ctx()
    mode = "MONITOR" if executing else "CHECK"
    extra = (f"CURRENTLY EXECUTING: {call_str(step)}" if executing else f"NEXT PLANNED STEP: {call_str(step)}")
    if FAST_MODE == "jev":
        opts = (["continue", "cancel"] if executing else ["execute", "skip", "wait_for_replan"])
        opt_txt = "OPTIONS:\n" + "\n".join(f"  {LETTERS[i]}) {o}" for i, o in enumerate(opts))
        msgs = get_builder().messages(snap, objects, list(history), "DECIDE", extra=extra + "\n" + opt_txt)
        sim.log_event("think_start", step_idx=f"chk{len(calls_log)}", obs_version=snap.version, branch="monitor")
        pick, info = jev_choose(fast_client, msgs, [{"skill": o, "args": []} for o in opts])
        sim.log_event("think_end", step_idx=f"chk{len(calls_log)}", latency=round(info.get("latency", 0), 3))
        dec = (pick or {}).get("skill") or "execute"
        if dec == "continue": dec = "execute"
        calls_log.append({"branch": "check", "mode": mode + "-jev", "t_obs": rel(snap.sim_time), "latency": info.get("latency"), "ttft": info.get("latency"),
                          "cached_tokens": info.get("cached_tokens"), "usage": info.get("usage"), "response": info.get("generated"), "decision": dec,
                          "dist": info.get("dist"), "step": call_str(step)})
        return dec
    msgs = get_builder().messages(snap, objects, list(history), mode, extra=extra)
    sim.log_event("think_start", step_idx=f"chk{len(calls_log)}", obs_version=snap.version, branch="monitor")
    r = fast_client.chat(msgs, max_tokens=80, thinking=False)
    sim.log_event("think_end", step_idx=f"chk{len(calls_log)}", latency=round(r.latency, 2))
    dec = "execute"
    try:
        dd = json.loads(r.text[r.text.index("{"):r.text.rindex("}") + 1]); dec = str(dd.get("decision", "execute")).lower()
    except Exception:
        pass
    if dec == "continue": dec = "execute"
    calls_log.append({"branch": "check", "mode": mode, "t_obs": rel(snap.sim_time), "latency": r.latency, "ttft": r.ttft, "cached_tokens": cached_of(r), "usage": r.usage, "response": r.text, "decision": dec, "step": call_str(step),
                      "n_retries": r.n_retries, "retry_wait_s": r.retry_wait_s})
    return dec


def _monitor_job(cur, act, cid):
    """非阻塞监控：判断进行中的技能是否应取消；若技能已结束，结论作废（只记录）。"""
    dec = fast_check_step(cur, act, executing=True)
    if dec == "execute": return
    with sim._lock: finished = cid in sim.outcomes
    cur_cmd = getattr(sim, "current", None)
    if not finished and cur_cmd is not None and cur_cmd.cid == cid:
        sim.cancel(reason=f"fast check: {dec}", source="fast monitor")
    else:
        sim.log_event("monitor_late", cid=cid, decision=dec)


def run_skill(act, snap, objects, source, plan_obj=None):
    name, cargs = to_executor_call(act, objects)
    cs = call_str(act)
    with lock: st["inflight"] = act
    cid = sim.submit_skill(name, *cargs, obs_version=snap.version, plan_id=source)
    seen = len(snap.messages); oc = None; t_wait = time.time(); s_wait = sim.latest().sim_time
    # 超时 90 s：真实时钟按真实时间（与 r5b 相同）；暂停 / token 时钟按仿真时间（冻结期间不计）
    while (time.time() - t_wait < 90) if CLOCK == "wall" else (sim.latest().sim_time - s_wait < 90):
        with sim._lock: oc = sim.outcomes.get(cid)
        if oc is not None or not sim.running: break
        cur = sim.latest()
        if cur is not None and len(cur.messages) > seen:
            seen = len(cur.messages)
            if SLOW_ON: request_replan("new message: " + cur.messages[-1]["text"][:80])
            if monitor and cur.current_skill is not None:
                if MON_ASYNC:
                    threading.Thread(target=_monitor_job, args=(cur, act, cid), daemon=True).start()
                else:
                    dec = fast_check_step(cur, act, executing=True)
                    if dec != "execute": sim.cancel(reason=f"fast check: {dec}", source="fast monitor")
        time.sleep(0.05)
    if oc is None:
        with lock: st["inflight"] = None
        history.append({"t_sim": rel(sim.latest().sim_time), "call": cs, "ok": False, "reason": "timeout"}); return False
    ok = bool(oc["ok"])
    history.append({"t_sim": rel(oc["finished_sim"]), "call": cs, "ok": ok, "reason": oc["reason"][:200] + (f" (interrupted: {oc.get('cancel_source') or 'unknown'})" if oc.get("cancelled") else "")})
    with lock:
        st["inflight"] = None
        st["executed"].append((oc["finished_sim"], cs, ok))
        # 去重：成功动作若等于当前计划的下一步（计划在该动作执行期间到达，来源可以是快分支或上一份计划），推进游标
        p = st["plan"]
        if ok and p is not None and p is not plan_obj and st["cursor"] < len(p.steps) and call_str(p.steps[st["cursor"]]) == cs:
            st["cursor"] += 1; sim.log_event("plan_step_dedup", step=cs, plan_id=p.plan_id)
    return ok


def world_sig():
    """r5：进展 / 扰动签名（修复版计分已完成的子目标数、已执行的随机扰动次数），变化时清零失败计数。"""
    return (int(sim.scorer.last[2]), sum(1 for e in sim.dynamics.log if e.get("type") == "rc_disturbance"))


def note_outcome(ok):
    """r5：把最近一次技能结果计入失败计数（成功则清零该调用）。"""
    if not FAIL_BLOCK or not history: return
    cs = history[-1]["call"]
    with lock:
        fs = st["fail_streak"]
        if ok: fs.pop(cs, None)
        else: fs[cs] = fs.get(cs, 0) + 1


def current_blocked():
    """r5：当前被屏蔽的调用集合；同时写入 st["blocked"] 供慢分支建议使用。"""
    if not FAIL_BLOCK: return frozenset()
    sig = world_sig()
    with lock:
        if sig != st["world"]: st["world"] = sig; st["fail_streak"].clear()
        b = frozenset(c for c, n in st["fail_streak"].items() if n >= FAIL_BLOCK)
        st["blocked"] = b
    return b


def coordinator():
    while sim.latest() is None: time.sleep(0.05)
    objects, fixtures, regions = ctx()
    if SLOW_ON: request_replan("episode start")
    n_skills = 0; checked = set(); fast_done_streak = 0; n_invalid = 0
    while sim.running and n_skills < max_skills:
        with lock:
            p = st["plan"]; cur = st["cursor"]; done = st["done"]; busy = st["slow_busy"] or replan_evt.is_set()
        if done and not busy:
            sim.log_event("planner_done"); break
        snap = sim.latest()
        step = p.steps[cur] if (p is not None and cur < len(p.steps)) else None
        if step is not None:
            # 第二轮：先按当前可观测状态判断这一步。效果已成立 → 跳过；前置条件不满足 → 与技能失败相同，作废旧计划、由快分支接管并请求重新规划
            stt, why = step_status(step, snap.held, snap.drawers or {}, drawer_regions())
            if stt == "done":
                sim.log_event("plan_step_satisfied", step=call_str(step), why=why, plan_id=p.plan_id)
                with lock:
                    if st["plan"] is p: st["cursor"] += 1
                continue
            if stt == "blocked":
                sim.log_event("precondition_failed", step=call_str(step), why=why, plan_id=p.plan_id)
                with lock:
                    if st["plan"] is p: st["plan"] = None
                if SLOW_ON and not busy: request_replan(f"precondition failed for {call_str(step)}: {why}")
                continue
            # 语义检查：计划之后出现了新消息
            if semantic_check and len(snap.messages) > p.n_messages and (p.plan_id, cur, len(snap.messages)) not in checked:
                checked.add((p.plan_id, cur, len(snap.messages)))
                dec = fast_check_step(snap, step)
                if dec == "skip":
                    with lock:
                        if st["plan"] is p: st["cursor"] += 1
                    continue
                if dec == "wait_for_replan":
                    with lock:
                        if st["plan"] is p: st["plan"] = None
                    if not busy: request_replan("plan invalidated by new message")
                    continue
            if FAIL_BLOCK and call_str(step) in current_blocked():   # r5：计划步骤已反复失败 → 作废计划、请求换一种做法
                sim.log_event("plan_step_blocked", step=call_str(step), plan_id=p.plan_id)
                with lock:
                    if st["plan"] is p: st["plan"] = None
                if SLOW_ON and not busy: request_replan(f"step {call_str(step)} failed {FAIL_BLOCK} times; plan another way")
                continue
            ok = run_skill(step, snap, objects, f"plan{p.plan_id}", plan_obj=p)
            note_outcome(ok)
            n_skills += 1
            with lock:
                if st["plan"] is p: st["cursor"] += 1
            if SLOW_ON and not ok and not (st["slow_busy"] or replan_evt.is_set()):
                request_replan(f"skill failed: {history[-1]['call']} ({history[-1]['reason'][:60]})")
                with lock:
                    if st["plan"] is p: st["plan"] = None
            continue
        # 没有可执行的计划步骤：快分支兜底或等待
        if SLOW_ON and p is not None and cur >= len(p.steps) and not busy:
            request_replan("plan exhausted"); continue
        if fast_fallback:
            act, r = fast_next_action(snap, objects, fixtures, regions, current_blocked())
            if act is None and _last_err.get("blocked"):
                # r5：选了被屏蔽的调用：写进历史作为反馈，但不计入"连续 5 次无效回复即中止"（它不是格式错误）
                history.append({"t_sim": rel(snap.sim_time), "call": "<blocked choice>", "ok": False, "reason": str(_last_err["e"])[:220]})
                sim.log_event("blocked_choice", reason=str(_last_err["e"])[:120])
                time.sleep(0.2); continue
            if act is None:
                n_invalid += 1
                history.append({"t_sim": rel(snap.sim_time), "call": "<invalid reply>", "ok": False, "reason": str(_last_err["e"])[:220]})
                sim.log_event("invalid_action", reason=str(_last_err["e"])[:120])
                if n_invalid >= 5: sim.log_event("abort", reason="5 consecutive invalid replies"); break
                time.sleep(0.2); continue
            n_invalid = 0
            if act.get("done") and DONE_VERIFY != "off" and st["n_verify"] < VERIFY_MAX:
                # r5：先由慢分支逐条核实；未完成则把缺项作为建议交给快分支继续
                complete, missing = verify_done(snap, objects)
                st["n_verify"] += 1
                if complete:
                    sim.log_event("planner_done", by="fast branch, verified"); break
                with lock:
                    st["seq"] += 1
                    st["advice"] = {"text": "NOT DONE YET (completion check): " + (missing or "some requirement of the task is not met"),
                                    "t": snap.sim_time, "reason": "completion check before finishing", "seq": st["seq"]}
                fast_done_streak = 0
                continue
            if act.get("done"):
                fast_done_streak += 1
                if fast_done_streak >= 2:
                    sim.log_event("planner_done", by="fast branch (2 consecutive)"); break
                if ADVICE and DONE_VERIFY_WAIT > 0:
                    # r3b："完成"须经慢分支核实：等核实建议到达（每次约 2–3 s）再让快分支重新决定；
                    # r3 中第二次"完成"约 1 s 后就到，核实建议来不及到达（case5 两局因此提前收尾）
                    request_replan("fast branch thinks the task is done; verify")
                    t_w = time.time(); got = False
                    while sim.running and time.time() - t_w < DONE_VERIFY_WAIT:
                        with lock: adv = st["advice"]
                        if adv is not None and "thinks the task is done" in adv["reason"] and adv["t"] >= snap.sim_time: got = True; break
                        time.sleep(0.1)
                    sim.log_event("done_verify", got_advice=got, waited_s=round(time.time() - t_w, 2))
                    continue
                if SLOW_ON and not busy: request_replan("fast branch thinks the task is done; verify")
                time.sleep(0.5); continue
            fast_done_streak = 0
            ok = run_skill(act, snap, objects, "fast"); n_skills += 1
            note_outcome(ok)
            if ADVICE:
                with lock:
                    st["since_advice"] += 1; busy2 = st["slow_busy"] or replan_evt.is_set(); n_since = st["since_advice"]
                why = (f"skill failed: {history[-1]['call']} ({history[-1]['reason'][:60]})" if not ok else loop_reason(n_skills))
                if why is None and ADVICE_EVERY and n_since >= ADVICE_EVERY: why = "periodic refresh"
                if why is not None and ADVICE_WAIT > 0 and not ok:
                    with lock: n0 = st["adv_calls"]
                if why is not None: request_replan(why)                 # 慢分支忙时排队：完成当前建议后按最新原因再给一次
                if why is not None and ADVICE_WAIT > 0 and not ok:
                    # r5d：失败后先等这次失败触发的建议送达（或超时）再决策；r5c 中失败后的下一次决策 91–100% 早于这条建议
                    t_w = time.time(); got = False
                    while sim.running and time.time() - t_w < ADVICE_WAIT:
                        with lock: got = st["adv_calls"] > n0 and st["adv_last_reason"] == why
                        if got: break
                        time.sleep(0.02)
                    sim.log_event("advice_wait", got=got, waited_s=round(time.time() - t_w, 2))
        else:
            time.sleep(0.1)
    time.sleep(0.3)
    if sim.running: sim.stop()


th_slow = threading.Thread(target=slow_thread, daemon=True)
th_coord = threading.Thread(target=coordinator, daemon=True)
def start_both():
    if SLOW_ON: th_slow.start()
    th_coord.start()
starter = threading.Thread(target=lambda: (time.sleep(0.01), start_both()), daemon=True)
t0 = time.time()
sim.run(planner_thread=starter)
sim.dump(out / "timeline.json")
final = {"original": int(sim.scorer.last[0]), "repaired": int(sim.scorer.last[2]), "n_goals": int(sim.scorer.n_goals), "all_done": bool(sim.scorer.last[3]),
         "excluded": int(sim.dynamics.excluded)}
ends = [e for e in sim.events if e["type"] == "episode_end"]
summary = {"case": f"{tt}/{cn}", "events": ev_name, "thinking": ("dual_advice" if ADVICE else ("dual_shared" if SLOW_ON else "fast_shared")) + "_" + FAST_MODE + ("_bust" if cache_bust else "") + ("" if monitor else "_nomon") + ("_monsync" if (monitor and not MON_ASYNC) else ""), "coordinator": ("r5" if R5 else "r4"), "fail_block": FAIL_BLOCK, "done_verify": DONE_VERIFY, "n_verify": st["n_verify"], "n_blocked": st["n_blocked"], "n_override": st["n_override"], "block_insist": BLOCK_INSIST, "clock": CLOCK, "token_rates": list(sim.token_rates) if CLOCK == "token" else None, "frozen_wall": round(sim.frozen_wall, 2), "models": {"fast": fast_client.model, "slow": slow_client.model, "profile": getattr(fast_client, "profile", None), "slow_profile": getattr(slow_client, "profile", None)}, "rc_dynamics": sim.dynamics.log, "slow_mode": SLOW_MODE, "done_verify_wait": DONE_VERIFY_WAIT if ADVICE else None, "advice_wait": ADVICE_WAIT if ADVICE else None, "replan_wait": REPLAN_WAIT if (SLOW_ON and not ADVICE) else None, "advice_max_tokens": ADVICE_MAX_TOKENS if ADVICE else None, "advice_every": ADVICE_EVERY if ADVICE else None, "hide_closed": hide_closed, "monitor_async": MON_ASYNC, "fast_mode": FAST_MODE, "slow_on": SLOW_ON, "monitor": monitor, "cache_bust": cache_bust, "bust_mode": BUST_MODE if cache_bust else None, "fast_fallback": fast_fallback, "semantic_check": semantic_check,
           "image": use_image, "seed": seed, "final": final, "sim_time": round(float(sim.env.sim.data.time - sim.sim_t0), 2), "wall": round(time.time() - t0, 1),
           "realized_rtr": ends[0]["realized_rtr"] if ends else None, "n_calls": len(calls_log),
           "event_report": mgr.report() if mgr else {}, "history": history, "subgoal_events": [(round(t - sim.sim_t0, 2), w) for t, w in sim.scorer.rep.events]}
json.dump(summary | {"calls": calls_log}, open(out / "episode.json", "w"), indent=1, ensure_ascii=False, default=str)
if "video" in flags and frames:
    import imageio.v2 as imageio; imageio.mimsave(out / "video.mp4", frames, fps=5)
lat = {b: [c["latency"] for c in calls_log if c["branch"] == b] for b in ("slow", "fast", "check")}
cache_stats = {b: [(c.get("cached_tokens"), (c.get("usage") or {}).get("prompt_tokens"), c.get("ttft")) for c in calls_log if c.get("branch") == b] for b in ("slow", "fast", "check")}
for b, v in cache_stats.items():
    if v:
        hit = [x[0] or 0 for x in v]; pt = [x[1] or 0 for x in v]; tf = [x[2] for x in v if x[2] is not None]
        print(f"   cache[{b}]: calls={len(v)} cached/prompt tokens={sum(hit)}/{sum(pt)} ({100*sum(hit)/max(sum(pt),1):.0f}%) ttft p50={np.median(tf) if tf else float('nan'):.2f}s")
print(f"[DUAL] {tt}/{cn} {tag}: final repaired {final['repaired']}/{final['n_goals']} original {final['original']} all={final['all_done']} | sim={summary['sim_time']}s "
      + " ".join(f"{b}:n={len(v)},p50={np.median(v):.1f}s" for b, v in lat.items() if v) + f" rtr={summary['realized_rtr']}")
for h in history: print(f"   [{h['t_sim']:6.1f}s] {h['call']:46s} {'OK ' if h['ok'] else 'FAIL'} {h['reason'][:80]}")
print("out:", out)
