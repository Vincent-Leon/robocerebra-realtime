"""r5d 两个实验的配对对比（输出 notes/figs_lb/r5d_experiments.md）：
  实验 1（真实时钟）：建议注入 r5c（失败后不等）对 r5d（--advice_wait=3：技能失败后快分支先等这次失败触发的建议，最长 3 s）。
    同一模型、任务、种子配对；比较全程 / 60 s / 120 s 得分、整任务成功、每局失败技能、失败后第 1、2 次决策重复失败动作的比例、实际等待时间；
    另比较两批快分支（Jev）决策延迟，确认硬件与负载条件相当（真实时钟下延迟会直接影响得分）。
  实验 2（暂停时钟）：完整计划 r5c（作废后立即重新规划）对 r5d（--replan_wait=state：等下一个技能结束或仿真时间前进 5 s 再规划）。
    同一模型、任务（种子 1）配对；比较得分、成功、计划请求 / 采用 / 作废次数、来自计划的技能比例、每局墙钟耗时。
用法: python compare_r5d.py
"""
import glob, json
from pathlib import Path
import numpy as np
import rc_env as R
from analyze_events import parse

MODELS = [("deepseek-v4.1-flash", "ds41"), ("qwen3.8-27b", "q38"), ("qwen3-vl-32b", "vl32b"), ("qwen3-vl-8b", "vl8b"), ("qwen3-vl-4b", "vl4b"), ("qwen3-vl-2b", "vl2b")]
rng = np.random.default_rng(0)


def load(root, pat):
    out = {}
    for f in glob.glob(str(R.RUNS_ROOT / root / "*" / pat / "episode.json")):
        x = parse(Path(f).parent)
        if x is not None:
            x["wall"] = json.load(open(f)).get("wall"); out[(x["task"], x["seed"])] = x
    return out


def paired(d):
    """均值、自助法 95% 区间、随机符号翻转的双侧 p 值。"""
    d = np.asarray(d, float)
    if len(d) == 0: return None
    bs = rng.choice(d, (10000, len(d))).mean(1); flips = (rng.choice([-1, 1], (20000, len(d))) * d).mean(1)
    return {"mean": float(d.mean()), "lo": float(np.percentile(bs, 2.5)), "hi": float(np.percentile(bs, 97.5)), "p": float(np.mean(np.abs(flips) >= abs(d.mean()) - 1e-12)), "n": len(d)}


def fmt(r, pct=False):
    if r is None: return "—"
    f = (lambda v: f"{v * 100:+.1f}") if pct else (lambda v: f"{v:+.3f}")
    return f"{f(r['mean'])}（{f(r['lo'])}, {f(r['hi'])}；p={r['p']:.3f}）"


def at(e, B): return sum(1 for t in e["sub"] if t <= B) / max(e["n"], 1)


def repeat_k(eps, kind=None):
    """失败后第 1、2 次决策重复失败动作的比例；kind = "dec"（决策错误：前置条件不满足）| "exe"（执行器没做成）| None（全部）。"""
    acc = [[0, 0], [0, 0]]
    for e in eps:
        for f in (c for c in e["skills"] if c["kind"] != "wait" and not c["ok"] and not c["cancelled"] and (kind is None or c["dec_err"] == (kind == "dec"))):
            ds = [x for x in e["decisions"] if x["t0"] >= f["t1"] - 1e-6 and x["skill"] is not None][:2]
            for k, x in enumerate(ds): acc[k][0] += x["skill"]["name"] == f["name"]; acc[k][1] += 1
    return [a[0] / a[1] if a[1] else None for a in acc]


def jev_lat(eps):
    v = [x["t1"] - x["t0"] for e in eps for x in e["decisions"] if x["p"] is not None]
    return (float(np.median(v)), float(np.percentile(v, 95))) if v else (None, None)


def waits(root):
    """r5d 的 advice_wait 事件：每次等待是否等到、等了多久（墙钟）。"""
    got = n = 0; w = []; per_ep = []
    for f in glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "timeline.json")):
        ev = [e for e in json.load(open(f))["events"] if e["type"] == "advice_wait"]
        n += len(ev); got += sum(1 for e in ev if e.get("got")); w += [e.get("waited_s", 0) for e in ev]; per_ep.append(sum(e.get("waited_s", 0) for e in ev))
    return {"n": n, "got": got / n if n else None, "med": float(np.median(w)) if w else None, "per_ep": float(np.mean(per_ep)) if per_ep else None}


L = ["# r5d 实验（10-29）", ""]
L += ["## 实验 1：技能失败后等建议（真实时钟，H20）", "",
      "对照 = r5c 的双分支·建议注入（`runs/llm_r5w_<模型>`）；处理 = r5d `--advice_wait=3`（`runs/llm_r5w_aw_<模型>`）。同一任务、种子配对，差值 = 处理 − 对照，括号内为自助法 95% 区间与随机符号翻转检验的 p 值。", "",
      "失败分两类：决策错误（前置条件不满足，如抽屉没开、手里没东西，重复必然再失败）与执行失败（抓取滑脱、够不着等，重试可能成功）。", "",
      "| 模型 | 配对局数 | 全程得分 对照 → 处理 | 差值 | 60 s 得分差 | 120 s 得分差 | 成功率差（百分点） | 每局失败技能 对照 → 处理 | 失败后第 1 次决策重复 对照 → 处理 | 其中决策错误后 | 其中执行失败后 | 第 2 次 | 实际等待：等到建议 / 每次中位数 / 每局合计 | Jev 决策延迟 p50/p95 对照 → 处理 |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for m, k in MODELS:
    A = load(f"llm_r5w_{k}", "noevent_dualadvice_jev_fb3_dvf_s*"); B = load(f"llm_r5w_aw_{k}", "noevent_dualadvice_jev_fb3_dvf_aw3_s*")
    keys = sorted(set(A) & set(B))
    if not keys: continue
    a, b = [A[x] for x in keys], [B[x] for x in keys]
    d_full = paired([y["score"] - x["score"] for x, y in zip(a, b)]); d60 = paired([at(y, 60) - at(x, 60) for x, y in zip(a, b)])
    d120 = paired([at(y, 120) - at(x, 120) for x, y in zip(a, b)]); dsucc = paired([float(y["success"]) - float(x["success"]) for x, y in zip(a, b)])
    fa = np.mean([sum(1 for c in e["skills"] if not c["ok"] and c["kind"] != "wait") for e in a]); fb = np.mean([sum(1 for c in e["skills"] if not c["ok"] and c["kind"] != "wait") for e in b])
    ra, rb = repeat_k(a), repeat_k(b); la, lb = jev_lat(a), jev_lat(b); w = waits(f"llm_r5w_aw_{k}")
    rda, rdb, rea, reb = repeat_k(a, "dec"), repeat_k(b, "dec"), repeat_k(a, "exe"), repeat_k(b, "exe")
    pc = lambda v: "—" if v is None else f"{v:.0%}"
    L.append(f"| {m} | {len(keys)} | {np.mean([x['score'] for x in a]):.3f} → {np.mean([y['score'] for y in b]):.3f} | {fmt(d_full)} | {fmt(d60)} | {fmt(d120)} | {fmt(dsucc, True)} | {fa:.1f} → {fb:.1f} | "
             f"{pc(ra[0])} → {pc(rb[0])} | {pc(rda[0])} → {pc(rdb[0])} | {pc(rea[0])} → {pc(reb[0])} | {pc(ra[1])} → {pc(rb[1])} | {pc(w['got'])} / {w['med'] or 0:.2f} s / {w['per_ep'] or 0:.1f} s | {la[0]:.2f}/{la[1]:.2f} → {lb[0]:.2f}/{lb[1]:.2f} s |")

L += ["", "## 实验 2：完整计划作废后等状态变化再重新规划（暂停时钟）", "",
      "对照 = r5c 暂停时钟的双分支·完整计划（试点任务，种子 1）；处理 = r5d `--replan_wait=state`（`runs/llm_r5p2_<模型>`）。按任务配对。", "",
      "| 模型 | 配对任务 | 得分 对照 → 处理 | 差值 | 成功 对照 → 处理 | 每局计划请求 对照 → 处理 | 每局作废 对照 → 处理 | 采用率 对照 → 处理 | 来自计划的技能 对照 → 处理 | 每局墙钟耗时中位数 对照 → 处理 |", "|---|---|---|---|---|---|---|---|---|---|"]
for m, k, base in (("qwen3.8-27b", "q38", "llm_h20_r5_q38_paused"), ("deepseek-v4.1-flash", "ds41", "llm_r5p_ds41")):
    A = load(base, "noevent_dualshared_jev_fb3_dvf_clkpaused_s1"); B = load(f"llm_r5p2_{k}", "noevent_dualshared_jev_fb3_dvf_clkpaused_rws_s1")
    keys = sorted(set(A) & set(B))
    if not keys: continue
    a, b = [A[x] for x in keys], [B[x] for x in keys]
    req = lambda v: np.mean([sum(1 for s in e["slow"] if s["kind"] == "plan") for e in v]); rej = lambda v: np.mean([len(e["rejected"]) for e in v])
    ado = lambda v: sum(len(e["plans"]) for e in v) / max(sum(len(e["plans"]) + len(e["rejected"]) for e in v), 1)
    fp = lambda v: sum(1 for e in v for c in e["skills"] if c["src"] != "fast") / max(sum(len(e["skills"]) for e in v), 1)
    wl = lambda v: np.median([e["wall"] or 0 for e in v]) / 60
    L.append(f"| {m} | {len(keys)} | {np.mean([x['score'] for x in a]):.3f} → {np.mean([y['score'] for y in b]):.3f} | {fmt(paired([y['score'] - x['score'] for x, y in zip(a, b)]))} | "
             f"{sum(x['success'] for x in a)}/{len(a)} → {sum(y['success'] for y in b)}/{len(b)} | {req(a):.1f} → {req(b):.1f} | {rej(a):.1f} → {rej(b):.1f} | {ado(a):.0%} → {ado(b):.0%} | {fp(a):.0%} → {fp(b):.0%} | {wl(a):.1f} → {wl(b):.1f} min |")
out = R.PROJECT_ROOT / "notes" / "figs_lb" / "r5d_experiments.md"; out.write_text("\n".join(L) + "\n", encoding="utf-8"); print(out)
