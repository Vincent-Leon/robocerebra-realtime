"""决策事件统计（r5 终版，三种时钟）：把每局时间线里的快分支决策、慢分支思考（建议 / 计划）、技能成败和子目标对齐，回答：
  1. 时间花在哪：执行技能、主动等待、等模型决策（机器人空闲）各占多少；
  2. Jev 置信度（选中字母的概率）能否预测动作失败；
  3. 思考注入（建议）由什么触发、多久到达、到达前快分支已经做了几次决策，以及失败之后是否更少重复同一动作；
  4. 完整计划多久到达、有多少因为世界已经变了而作废（三种时钟对比）；
  5. 开思考的调用有多少因用完输出上限而没有给出答案。
只用满足实时性判据的局（与 analyze_leaderboard.py 相同）。
输出：<out>/events_r5.md（中文报告）、events_r5.json（网站用的汇总）。
用法: python analyze_events.py [--wall=目录,...] [--token=...] [--paused=...] [--out=../notes/figs_lb]
其他脚本可 `from analyze_events import parse` 取单局解析结果（挑选示例局、网站时间线）。
"""
import sys, json, glob, collections, re
from pathlib import Path
import numpy as np
import rc_env as R

SKIP = {"tick", "subgoal_done", "think_start", "think_end", "advice_published", "plan_published", "plan_rejected", "replan_requested", "rc_disturbance", "rc_disturbance_skipped"}
DECISION_ERR = re.compile(r"nothing in hand|is closed; open it first|blocked from above|hand busy|already holding|already open|already closed|not a drawer|no such|unknown")
MODE_NAME = {"fast_shared_jev": "仅快·Jev", "fast_shared_text": "仅快·文本", "fast_shared_think": "仅慢（每步开思考）",
             "dual_shared_jev": "双分支·完整计划", "dual_advice_jev": "双分支·建议注入"}
MODE_ORDER = list(MODE_NAME)
CLOCK_NAME = {"wall": "真实", "token": "token", "paused": "暂停"}
P_BINS = [0.0, 0.5, 0.7, 0.9, 0.99, 1.0001]


def rt_ok(tl):
    st = next((e for e in tl if e["type"] == "episode_start"), {"sim": 0.0})
    ticks = [e for e in tl if e["type"] == "tick" and e["sim"] - st["sim"] > 3.0]
    end = next((e for e in tl if e["type"] == "episode_end"), {})
    return max([t.get("lag", 0) or 0 for t in ticks] or [0]) <= 0.25 and (end.get("lag_p95") or 0) <= 0.05


def short_model(m):
    return (m or "exp-qwen3.8-27b-fp8").replace("exp-", "").replace("-fp8", "").replace("-instruct", "")


def norm_skill(s):
    """cmd_submitted 里是 "pick('plate_1',)"，history 里是 "pick(plate_1)"：统一成后者。"""
    s = str(s); m = re.match(r"(\w+)\((.*)\)$", s)
    if not m: return s
    args = [a.strip().strip("'\"") for a in m.group(2).split(",") if a.strip()]
    return f"{m.group(1)}({','.join(args)})"


def trigger_kind(reason):
    r = str(reason or "")
    if r.startswith("episode start"): return "start"
    if r.startswith("skill failed"): return "failure"
    if r.startswith("possible loop"): return "loop"
    if "message" in r or "event" in r or "disturb" in r: return "event"
    if r.startswith("previous plan"): return "replan"
    return "other"


def parse(d):
    """单局解析：返回 dict（时间都是相对开局的仿真秒），不满足实时性判据时返回 None。"""
    d = Path(d); ep = json.load(open(d / "episode.json")); tl = json.load(open(d / "timeline.json"))["events"]
    if not rt_ok(tl): return None
    st = next(e for e in tl if e["type"] == "episode_start"); t0 = st["sim"]
    end = next((e for e in tl if e["type"] == "episode_end"), tl[-1]); T = end["sim"] - t0
    fin = ep["final"]; exc = int(fin.get("excluded", 0))
    if (d / "rescored.json").exists():
        rs = json.load(open(d / "rescored.json")); fin = {"repaired": rs["repaired"], "n_goals": rs["n_goals"], "all_done": rs["repaired_all"]}; exc = int(rs.get("excluded", exc))
    n = fin["n_goals"] - exc; done = fin["repaired"] - exc
    cmds, skills = {}, []
    for e in tl:
        if e["type"] == "cmd_submitted":
            cmds[e["cid"]] = {"cid": e["cid"], "name": norm_skill(e["skill"]), "src": e.get("plan_id") or "fast", "t_sub": e["sim"] - t0}
        elif e["type"] == "skill_started" and e.get("cid") in cmds:
            cmds[e["cid"]]["t0"] = e["sim"] - t0
        elif e["type"] == "skill_finished" and e.get("cid") in cmds and "t0" in cmds[e["cid"]]:
            c = cmds[e["cid"]]; c.update(t1=e["sim"] - t0, ok=bool(e.get("ok")), reason=str(e.get("reason") or "")); skills.append(c)
    for c in skills:
        c["kind"] = c["name"].split("(")[0]
        c["cancelled"] = "cancel" in c["reason"]
        c["dec_err"] = (not c["ok"]) and bool(DECISION_ERR.search(c["reason"]))
    by_cid = {c["cid"]: c for c in skills}
    start_of, pend = {}, collections.defaultdict(collections.deque)   # 同一 step_idx 会重复使用（如暂停时钟下反复重新规划），按先进先出配对
    for e in tl:
        if e["type"] == "think_start": pend[e.get("step_idx")].append(e)
        elif e["type"] == "think_end" and pend[e.get("step_idx")]: start_of[id(e)] = pend[e.get("step_idx")].popleft()
    calls = ep.get("calls", [])
    fcalls = [c for c in calls if c.get("branch") == "fast"]
    fends = [(i, e) for i, e in enumerate(tl) if e["type"] == "think_end" and str(e.get("step_idx", "")).startswith("fast")]
    decisions, misalign = [], 0
    for k, (i, e) in enumerate(fends):
        c = fcalls[k] if k < len(fcalls) else {}
        if c and e.get("latency") is not None and c.get("latency") is not None and abs(e["latency"] - round(c["latency"], 3)) > 0.01: misalign += 1
        s = start_of.get(id(e))
        nxt = next((x for x in tl[i + 1:] if x["type"] not in SKIP), None)
        res, cid = "none", None
        if nxt is not None and abs(nxt["sim"] - e["sim"]) < 0.11:
            res = nxt["type"]; cid = nxt.get("cid") if res == "cmd_submitted" else None
        u = c.get("usage") or {}
        decisions.append({"t0": (s["sim"] if s else e["sim"]) - t0, "t1": e["sim"] - t0, "w0": (s or e)["wall"], "w1": e["wall"], "p": c.get("p_choice"), "n_cand": c.get("n_candidates"),
                          "dist": c.get("dist"), "res": res, "cid": cid, "skill": by_cid.get(cid), "err": c.get("error"), "empty": c.get("error") == "empty response",
                          "out_tok": u.get("completion_tokens"), "lat": c.get("latency")})
    slow = []
    scalls = [c for c in calls if c.get("branch") == "slow"]
    sends = [e for e in tl if e["type"] == "think_end" and str(e.get("step_idx", "")).startswith(("adv", "slow"))]
    for k, e in enumerate(sends):
        s = start_of.get(id(e)); c = scalls[k] if k < len(scalls) else {}
        slow.append({"t0": (s["sim"] if s else e["sim"]) - t0, "t1": e["sim"] - t0, "w0": (s or e)["wall"], "w1": e["wall"], "reason": (s or {}).get("reason") or c.get("reason"),
                     "kind": "advice" if str(e["step_idx"]).startswith("adv") else "plan", "err": e.get("error") or c.get("error"),
                     "empty": (e.get("error") or c.get("error")) == "empty response",   # 只算模型没给出答案（用完输出上限），不含计划被作废
                     "out_tok": (c.get("usage") or {}).get("completion_tokens")})
    advice = [{"t": e["sim"] - t0, "id": e.get("advice_id"), "lat": e.get("latency"), "text": e.get("text")} for e in tl if e["type"] == "advice_published"]
    plans = [{"t": e["sim"] - t0, "id": e.get("plan_id"), "n": e.get("n_steps"), "lat": e.get("latency"), "steps": e.get("steps"), "obs": e.get("obs_version")} for e in tl if e["type"] == "plan_published"]
    rejected = [{"t": e["sim"] - t0, "stage": e.get("stage"), "error": str(e.get("error") or "")} for e in tl if e["type"] == "plan_rejected"]
    dist = [{"t": e["sim"] - t0, "object": e.get("object"), "related": e.get("related")} for e in tl if e["type"] == "rc_disturbance"]
    verify = [{"t": e["sim"] - t0, "complete": e.get("complete"), "missing": e.get("missing")} for e in tl if e["type"] == "done_verify"]
    blocked = [{"t": e["sim"] - t0, "reason": e.get("reason")} for e in tl if e["type"] in ("blocked_choice", "blocked_override")]
    sub = sorted(float(t) for t, _ in ep.get("subgoal_events", []))
    mods = ep.get("models") or {}
    return {"dir": str(d), "task": ep["case"], "type": ep["case"].split("/")[0], "seed": int(ep["seed"]), "mode": ep["thinking"], "fast_mode": ep.get("fast_mode"),
            "clock": ep.get("clock", "wall"), "model": short_model(mods.get("fast")), "T": T, "score": done / max(n, 1), "n": n, "done": done,
            "success": bool(fin["all_done"]), "skills": skills, "decisions": decisions, "slow": slow, "advice": advice, "plans": plans,
            "rejected": rejected, "dist": dist, "verify": verify, "blocked": blocked, "sub": sub, "misalign": misalign,
            "end": next((e["type"] for e in tl if e["type"] in ("all_done", "planner_done", "abort")), "limit")}


def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


def auc(pos, neg):
    """P(score_pos > score_neg)，并列记一半（Mann–Whitney）。"""
    if not pos or not neg: return None
    allv = np.array(pos + neg); r = allv.argsort().argsort().astype(float) + 1
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=r); r = (sums / cnt)[inv]
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main():
    opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    lst = lambda k, dft: [x for x in opt.get(k, dft).split(",") if x]
    roots = {"wall": lst("wall", "llm_r5w_ds41,llm_r5w_q38,llm_r5w_vl32b,llm_r5w_vl8b,llm_r5w_vl4b,llm_r5w_vl2b"),
             "token": lst("token", "llm_r5t_ds41,llm_h20_r5_q38_token,llm_r5t_vl32b,llm_r5t_vl8b,llm_r5t_vl4b,llm_r5t_vl2b"),
             "paused": lst("paused", "llm_r5p_ds41,llm_h20_r5_q38_paused,llm_r5p_vl32b,llm_r5p_vl8b,llm_r5p_vl4b,llm_r5p_vl2b")}
    out = Path(opt.get("out", str(R.PROJECT_ROOT / "notes" / "figs_lb"))); out.mkdir(parents=True, exist_ok=True)
    E, bad, mis = [], 0, 0
    for clock, rs in roots.items():
        for rt in rs:
            for f in sorted(glob.glob(str(R.RUNS_ROOT / rt / "*" / "*" / "episode.json"))):
                x = parse(Path(f).parent)
                if x is None: bad += 1; continue
                if x["clock"] != clock: continue
                mis += x["misalign"]; E.append(x)
    ORDER = ["deepseek-v4.1-flash", "qwen3.8-27b", "qwen3-vl-32b", "qwen3-vl-8b", "qwen3-vl-4b", "qwen3-vl-2b"]
    models = sorted({e["model"] for e in E}, key=lambda m: ORDER.index(m) if m in ORDER else 99)
    G = collections.defaultdict(list)
    for e in E: G[(e["model"], e["mode"], e["clock"])].append(e)
    S = {"n_episodes": len(E), "n_bad": bad, "misaligned_calls": mis, "models": models}
    L = [f"# 决策事件统计（r5 终版）", "", f"共 {len(E)} 局（实时性违规剔除 {bad} 局）；快分支调用与时间线对齐检查：{mis} 次延迟不一致。", ""]

    # ---------- 1. 时间花在哪 ----------
    L += ["## 1. 时间花在哪", "", "每局时长（仿真秒）分成三部分：执行技能（不含 wait）、主动等待（wait 技能）、其余时间——机器人空闲，基本都在等模型决策。按时长加权（各局之和之比）。", "",
          "| 模型 | 模式 | 时钟 | 执行 | 主动等待 | 等决策 | 每局决策次数 | 动作间隔中位数 | 局数 |", "|---|---|---|---|---|---|---|---|---|"]
    S["time"] = []
    for (m, md, ck), v in sorted(G.items(), key=lambda kv: (models.index(kv[0][0]), MODE_ORDER.index(kv[0][1]) if kv[0][1] in MODE_ORDER else 9, list(roots).index(kv[0][2]))):
        Tt = sum(e["T"] for e in v)
        ex = sum(min(c["t1"], e["T"]) - c["t0"] for e in v for c in e["skills"] if c["kind"] != "wait")
        wt = sum(min(c["t1"], e["T"]) - c["t0"] for e in v for c in e["skills"] if c["kind"] == "wait")
        gaps = []
        for e in v:
            sk = sorted(e["skills"], key=lambda c: c["t0"])
            gaps += [b["t0"] - a["t1"] for a, b in zip(sk, sk[1:]) if b["t0"] >= a["t1"] - 1e-6]
        nd = np.mean([len(e["decisions"]) for e in v])
        row = {"model": m, "mode": md, "clock": ck, "exec": ex / Tt, "wait": wt / Tt, "idle": max(0.0, 1 - (ex + wt) / Tt), "dec": float(nd),
               "gap": float(np.median(gaps)) if gaps else None, "n": len(v), "T": Tt / len(v)}
        S["time"].append(row)
        L.append(f"| {m} | {MODE_NAME.get(md, md)} | {CLOCK_NAME[ck]} | {row['exec']:.0%} | {row['wait']:.0%} | {row['idle']:.0%} | {nd:.1f} | {row['gap'] or 0:.2f} s | {len(v)} |")

    # ---------- 2. Jev 置信度与动作失败 ----------
    L += ["", "## 2. Jev 置信度能否预测动作失败", "",
          "Jev 快分支（仅快·Jev、建议注入、完整计划的快分支）每次决策选中字母的概率 p，对应它提交的技能是否失败（不含 wait、被取消的技能）。三种时钟合并。"
          "决策错误 = 失败原因是前置条件不满足（手里没东西、抽屉没开、被上层抽屉挡住等），其余失败是执行器没做成（抓取滑脱、够不着等）。AUC = 用 1 − p 区分失败与成功的能力（0.5 为随机）。", "",
          "| 模型 | " + " | ".join(f"p ∈ [{a:.2f}, {min(b, 1):.2f}{']' if b > 1 else ')'}" for a, b in zip(P_BINS, P_BINS[1:])) + " | AUC（失败） | AUC（决策错误） | 决策数 |",
          "|---|" + "---|" * (len(P_BINS) - 1) + "---|---|---|"]
    S["calib"] = []
    for m in models + ["all"]:
        ds = [x for e in E if (m == "all" or e["model"] == m) and e["fast_mode"] == "jev" for x in e["decisions"]
              if x["p"] is not None and x["skill"] and x["skill"]["kind"] != "wait" and not x["skill"]["cancelled"]]
        if not ds: continue
        bins = []
        for a, b in zip(P_BINS, P_BINS[1:]):
            sel = [x for x in ds if a <= x["p"] < b]; k = sum(not x["skill"]["ok"] for x in sel); kd = sum(x["skill"]["dec_err"] for x in sel)
            bins.append({"lo": a, "hi": min(b, 1.0), "n": len(sel), "fail": k / len(sel) if sel else None, "ci": wilson(k, len(sel)), "dec_err": kd / len(sel) if sel else None})
        fa = auc([1 - x["p"] for x in ds if not x["skill"]["ok"]], [1 - x["p"] for x in ds if x["skill"]["ok"]])
        fd = auc([1 - x["p"] for x in ds if x["skill"]["dec_err"]], [1 - x["p"] for x in ds if x["skill"]["ok"]])
        share = [b["n"] / len(ds) for b in bins]
        S["calib"].append({"model": m, "bins": bins, "auc": fa, "auc_dec": fd, "n": len(ds), "share": share})
        L.append(f"| {m} | " + " | ".join(f"{b['fail']:.0%}（{b['n']}）" if b["fail"] is not None else "—" for b in bins) + f" | {fa:.2f} | {fd:.2f} | {len(ds)} |")
    L += ["", "表中为失败率（括号内为决策数）。"]

    # ---------- 3. 思考注入（建议）----------
    L += ["", "## 3. 思考注入（双分支·建议注入）", "",
          "触发：开局、技能失败、疑似循环（交替或重复同一动作）、其他。到达用时：触发到建议写入快分支上下文的仿真时间（真实时钟 = 实测；token 时钟 = 按 token 折算；暂停时钟 = 0）。"
          "到达前的决策：建议到达之前快分支已经做出的决策次数（这些决策还没看到新建议）。", "",
          "| 模型 | 时钟 | 每局建议数 | 开局 | 失败 | 循环 | 其他 | 到达用时中位数 | 到达前快分支已决策（失败触发，中位数） | 局数 |", "|---|---|---|---|---|---|---|---|---|---|"]
    S["advice"] = []
    for (m, md, ck), v in sorted(G.items(), key=lambda kv: (models.index(kv[0][0]), list(roots).index(kv[0][2]))):
        if md != "dual_advice_jev": continue
        sl = [s for e in v for s in e["slow"] if s["kind"] == "advice"]
        kinds = collections.Counter(trigger_kind(s["reason"]) for s in sl)
        lat = [s["t1"] - s["t0"] for s in sl]
        before = []
        for e in v:
            for s in e["slow"]:
                if s["kind"] != "advice" or trigger_kind(s["reason"]) != "failure": continue
                before.append(sum(1 for x in e["decisions"] if s["t0"] - 1e-6 <= x["t0"] < s["t1"]))
        row = {"model": m, "clock": ck, "per_ep": len(sl) / len(v), "kinds": {k: kinds[k] / max(len(sl), 1) for k in ("start", "failure", "loop", "event", "replan", "other")},
               "lat": float(np.median(lat)) if lat else None, "before": float(np.median(before)) if before else None, "before_mean": float(np.mean(before)) if before else None, "n": len(v)}
        S["advice"].append(row)
        kk = row["kinds"]
        L.append(f"| {m} | {CLOCK_NAME[ck]} | {row['per_ep']:.1f} | {kk['start']:.0%} | {kk['failure']:.0%} | {kk['loop']:.0%} | {kk['event'] + kk['replan'] + kk['other']:.0%} | {row['lat'] or 0:.2f} s | {row['before'] if row['before'] is not None else '—'} | {len(v)} |")

    # 失败之后：重复同一动作、下一动作再失败（仅快·Jev 对 建议注入；同模型同时钟）
    L += ["", "### 失败之后发生了什么", "",
          "对每个失败的技能（不含 wait），看之后第一个技能：与失败的完全相同（重复）的比例、它再次失败的比例，以及失败后到下一个子目标完成的时间（中位数，没有再完成子目标的不计）。", "",
          "| 模型 | 时钟 | 模式 | 失败次数/局 | 下一动作重复 | 下一动作再失败 | 到下一个子目标 | 局数 |", "|---|---|---|---|---|---|---|---|"]
    S["after_fail"] = []
    for (m, md, ck), v in sorted(G.items(), key=lambda kv: (models.index(kv[0][0]), list(roots).index(kv[0][2]), MODE_ORDER.index(kv[0][1]) if kv[0][1] in MODE_ORDER else 9)):
        nf = rep = refail = 0; rec = []
        for e in v:
            sk = sorted([c for c in e["skills"] if c["kind"] != "wait"], key=lambda c: c["t0"])
            for a, b in zip(sk, sk[1:]):
                if a["ok"] or a["cancelled"]: continue
                nf += 1; rep += b["name"] == a["name"]; refail += not b["ok"]
                nxt = next((t for t in e["sub"] if t > a["t1"]), None)
                if nxt is not None: rec.append(nxt - a["t1"])
        row = {"model": m, "clock": ck, "mode": md, "fails": nf / len(v), "repeat": rep / nf if nf else None, "refail": refail / nf if nf else None,
               "recover": float(np.median(rec)) if rec else None, "n": len(v), "nf": nf}
        S["after_fail"].append(row)
        if md in ("fast_shared_jev", "dual_advice_jev", "fast_shared_text"):
            L.append(f"| {m} | {CLOCK_NAME[ck]} | {MODE_NAME[md]} | {row['fails']:.1f} | {row['repeat'] or 0:.0%} | {row['refail'] or 0:.0%} | {row['recover'] or 0:.1f} s | {len(v)} |")

    # 失败触发的建议：失败后的下一次决策有没有看到它（按墙钟判断先后：暂停时钟下仿真时间相同）
    L += ["", "### 失败触发的建议来得及吗", "",
          "技能失败后，快分支立即重新决策；同一次失败也触发慢分支写建议。按墙钟时间判断失败后的决策是在建议写入之前还是之后发出的（之前发出的决策看不到这条建议），"
          "并比较两种决策重复失败动作的比例（只看失败后的前两次决策）。对照为仅快·Jev 失败后的第一次决策。", "",
          "| 模型 | 时钟 | 失败触发的建议 | 失败后第一次决策早于建议 | 早于建议的决策：重复 | 晚于建议的决策：重复 | 对照：仅快·Jev 第一次决策重复 |", "|---|---|---|---|---|---|---|"]
    S["advice_timing"] = []
    def first_after(e, f, k=2):
        return [x for x in e["decisions"] if x["t0"] >= f["t1"] - 1e-6 and x["skill"] is not None][:k]
    for (m, md, ck), v in sorted(G.items(), key=lambda kv: (models.index(kv[0][0]), list(roots).index(kv[0][2]))):
        if md != "dual_advice_jev": continue
        nadv = early = 0; rb = [0, 0]; ra = [0, 0]
        for e in v:
            for f in (c for c in e["skills"] if c["kind"] != "wait" and not c["ok"] and not c["cancelled"]):
                sv = next((x for x in e["slow"] if x["kind"] == "advice" and trigger_kind(x["reason"]) == "failure" and abs(x["t0"] - f["t1"]) < 0.25), None)
                ds = first_after(e, f)
                if sv is None or not ds: continue
                nadv += 1; early += ds[0]["w0"] < sv["w1"]
                for x in ds:
                    acc = rb if x["w0"] < sv["w1"] else ra; acc[0] += x["skill"]["name"] == f["name"]; acc[1] += 1
        base = [0, 0]
        for e in G.get((m, "fast_shared_jev", ck), []):
            for f in (c for c in e["skills"] if c["kind"] != "wait" and not c["ok"] and not c["cancelled"]):
                ds = first_after(e, f, 1)
                if ds: base[0] += ds[0]["skill"]["name"] == f["name"]; base[1] += 1
        row = {"model": m, "clock": ck, "n": nadv, "early": early / nadv if nadv else None, "rep_before": rb[0] / rb[1] if rb[1] else None, "n_before": rb[1],
               "rep_after": ra[0] / ra[1] if ra[1] else None, "n_after": ra[1], "rep_jev_first": base[0] / base[1] if base[1] else None}
        S["advice_timing"].append(row)
        fm = lambda x: "—" if x is None else f"{x:.0%}"
        L.append(f"| {m} | {CLOCK_NAME[ck]} | {nadv} | {fm(row['early'])} | {fm(row['rep_before'])}（{rb[1]}） | {fm(row['rep_after'])}（{ra[1]}） | {fm(row['rep_jev_first'])} |")

    # 按位置对齐：失败后第 k 次决策（k = 1, 2）重复失败动作的比例。失败后第二次决策本来就更少重复（第一次重复多半又失败了），
    # 所以"建议到达前 / 后"的对比混有位置效应；同位置比较仅快·Jev 与建议注入才是建议的作用。
    L += ["", "### 同位置对比：失败后第 k 次决策重复失败动作的比例", "", "| 模型 | 时钟 | 仅快·Jev k=1 | 建议注入 k=1 | 仅快·Jev k=2 | 建议注入 k=2 |", "|---|---|---|---|---|---|"]
    S["repeat_pos"] = []
    for m in models:
        for ck in roots:
            r = {"model": m, "clock": ck}
            for md, key in (("fast_shared_jev", "jev"), ("dual_advice_jev", "adv")):
                acc = [[0, 0], [0, 0]]
                for e in G.get((m, md, ck), []):
                    for f in (c for c in e["skills"] if c["kind"] != "wait" and not c["ok"] and not c["cancelled"]):
                        for k, x in enumerate(first_after(e, f)):
                            acc[k][0] += x["skill"]["name"] == f["name"]; acc[k][1] += 1
                for k in (0, 1):
                    r[f"{key}{k + 1}"] = acc[k][0] / acc[k][1] if acc[k][1] else None; r[f"{key}{k + 1}_n"] = acc[k][1]
            if r["jev1"] is None or r["adv1"] is None: continue
            S["repeat_pos"].append(r)
            L.append(f"| {m} | {CLOCK_NAME[ck]} | {r['jev1']:.0%} | {r['adv1']:.0%} | {r['jev2']:.0%} | {r['adv2']:.0%} |")

    # ---------- 4. 完整计划 ----------
    L += ["", "## 4. 完整计划（双分支·完整计划）：到达用时与作废", "",
          "慢分支开思考写出完整计划，快分支照常行动。计划到达时先做状态检查与对齐：不再适用（前提已变、步骤不可执行）即作废。采用率 = 通过检查的计划 /（通过 + 作废）；来自计划的技能 = 执行的技能中由计划步骤提交的比例。", "",
          "| 模型 | 时钟 | 每局计划请求 | 计划用时中位数 | 采用率 | 作废原因（前两位） | 来自计划的技能 | 局数 |", "|---|---|---|---|---|---|---|---|"]
    S["plans"] = []
    for (m, md, ck), v in sorted(G.items(), key=lambda kv: (models.index(kv[0][0]), list(roots).index(kv[0][2]))):
        if md != "dual_shared_jev": continue
        sl = [s for e in v for s in e["slow"] if s["kind"] == "plan"]
        lat = [s["t1"] - s["t0"] for s in sl]
        pub = sum(len(e["plans"]) for e in v); rej = [r for e in v for r in e["rejected"]]
        why = collections.Counter(("不可执行" if "not executable" in r["error"] else "状态已变" if "no longer fits" in r["error"] else "输出无效" if "empty" in r["error"] or "invalid" in r["error"] else r["stage"] or "其他") for r in rej)
        sk = [c for e in v for c in e["skills"]]; fromplan = sum(1 for c in sk if c["src"] != "fast") / max(len(sk), 1)
        row = {"model": m, "clock": ck, "req": len(sl) / len(v), "lat": float(np.median(lat)) if lat else None, "adopt": pub / max(pub + len(rej), 1),
               "why": dict(why), "from_plan": fromplan, "n": len(v), "pub": pub, "rej": len(rej), "empty": sum(1 for s in sl if s["empty"]) / max(len(sl), 1)}
        S["plans"].append(row)
        L.append(f"| {m} | {CLOCK_NAME[ck]} | {row['req']:.1f} | {row['lat'] or 0:.1f} s | {row['adopt']:.0%}（{pub}/{pub + len(rej)}） | " + "，".join(f"{k} {n}" for k, n in why.most_common(2)) + f" | {fromplan:.1%} | {len(v)} |")

    # ---------- 5. 开思考的调用没给出答案 ----------
    L += ["", "## 5. 开思考的调用：用完输出上限而没有答案", "", "空回复 = 模型把 4096 token 的输出上限全用在思考上、没有给出答案（客户端报 empty response）；不含计划被作废、被屏蔽的选择等。", "",
          "| 模型 | 时钟 | 仅慢：每步思考调用中空回复 | 完整计划：慢分支调用中空回复 | 仅慢：输出 token 中位数 |", "|---|---|---|---|---|"]
    S["think"] = []
    for m in models:
        for ck in roots:
            th = [x for e in G.get((m, "fast_shared_think", ck), []) for x in e["decisions"]]
            pl = [s for e in G.get((m, "dual_shared_jev", ck), []) for s in e["slow"]]
            if not th and not pl: continue
            r1 = sum(1 for x in th if x["empty"]) / len(th) if th else None; r2 = sum(1 for s in pl if s["empty"]) / len(pl) if pl else None
            ot = [x["out_tok"] for x in th if x["out_tok"]]
            S["think"].append({"model": m, "clock": ck, "think_empty": r1, "plan_empty": r2, "think_tok": float(np.median(ot)) if ot else None})
            L.append(f"| {m} | {CLOCK_NAME[ck]} | " + (f"{r1:.1%}（{len(th)}）" if r1 is not None else "—") + " | " + (f"{r2:.1%}（{len(pl)}）" if r2 is not None else "—") + f" | {np.median(ot) if ot else 0:.0f} |")

    L += ["", "暂停时钟下仅慢只跑了 12 个试点任务（种子 1）。相同任务、相同种子上的对比：", "", "| 模型 | 时钟 | 空回复 | 输出 token 中位数 | 每局思考调用 | 局数 |", "|---|---|---|---|---|---|"]
    S["think_matched"] = []
    for m in models:
        pz = G.get((m, "fast_shared_think", "paused"), [])
        keep = {(e["task"], e["seed"]) for e in pz}
        if not keep: continue
        for ck in roots:
            v = [e for e in G.get((m, "fast_shared_think", ck), []) if (e["task"], e["seed"]) in keep]
            th = [x for e in v for x in e["decisions"]]
            if not th: continue
            ot = [x["out_tok"] for x in th if x["out_tok"]]
            r = {"model": m, "clock": ck, "empty": sum(1 for x in th if x["empty"]) / len(th), "tok": float(np.median(ot)) if ot else None, "calls": len(th) / len(v), "n": len(v)}
            S["think_matched"].append(r)
            L.append(f"| {m} | {CLOCK_NAME[ck]} | {r['empty']:.1%} | {r['tok'] or 0:.0f} | {r['calls']:.1f} | {len(v)} |")
    # 暂停时钟 + 完整计划：计划被作废后立即重新规划、世界仍冻结，反复作废
    loops = []
    for (m, md, ck), v in G.items():
        if md != "dual_shared_jev": continue
        for e in v:
            n_rej = len(e["rejected"]); loops.append((m, ck, e["task"], len(e["plans"]), n_rej))
    L += ["", "完整计划被作废次数最多的局（暂停时钟下作废后立即重新规划、世界仍冻结；规划用的快照不含快分支已提交但尚未执行的动作，所以同一份计划反复被判不可执行）：", ""]
    for m, ck, t, npub, nrej in sorted(loops, key=lambda x: -x[4])[:8]:
        L.append(f"- {m} · {CLOCK_NAME[ck]} · {t}：采用 {npub} 次，作废 {nrej} 次")
    S["plan_loops"] = [{"model": m, "clock": ck, "task": t, "pub": a, "rej": b} for m, ck, t, a, b in sorted(loops, key=lambda x: -x[4])[:20]]

    (out / "events_r5.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "events_r5.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out / "events_r5.md")


if __name__ == "__main__":
    main()
