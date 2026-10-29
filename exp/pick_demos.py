"""为网站"单局时间线 + 视频"挑选示例局：按几个主题在真实时钟（H20）的结果里找候选，打印前几名供人工确认。
  think   同一任务、同一种子：Qwen3.8 仅快·Jev 很快做完，每步开思考做完但慢得多（机器人大部分时间在等）；
  advice  同一任务、同一种子：仅快·Jev 连续重复同一个失败动作、得分低，建议注入做完；
  plan    完整计划：计划写了十几秒以上，到达时世界已经变了而作废，快分支照常把任务做完；
  disturb 随机扰动：物体被推开后技能失败，随后恢复并做完；
  size    同一任务、同一种子：Qwen3.8 仅快·Jev 做完，Qwen3-VL-2B 反复失败。
用法: python pick_demos.py [主题 ...]
"""
import sys, glob, collections
from pathlib import Path
from analyze_events import parse

RUNS = Path(__file__).resolve().parent / "runs"
want = set(sys.argv[1:]) or {"think", "advice", "plan", "disturb", "size"}


def load(root, tag):
    out = {}
    for f in glob.glob(str(RUNS / root / "*" / f"noevent_{tag}_fb3_dvf_s*" / "episode.json")):
        x = parse(Path(f).parent)
        if x: out[(x["task"], x["seed"])] = x
    return out


def longest_repeat(e):
    best = run = 0; prev = None
    for c in sorted((c for c in e["skills"] if c["kind"] != "wait"), key=lambda c: c["t0"]):
        if not c["ok"] and c["name"] == prev: run += 1
        elif not c["ok"]: run = 1
        else: run = 0
        prev = c["name"] if not c["ok"] else None; best = max(best, run)
    return best


def at(e, t):
    return sum(1 for x in e["sub"] if x <= t) / max(e["n"], 1)


if "think" in want:
    J, K = load("llm_r5w_q38", "fastshared_jev"), load("llm_r5w_q38", "fastshared_think")
    c = [(K[k]["T"] - J[k]["T"], k) for k in J if k in K and J[k]["success"] and K[k]["success"] and J[k]["T"] < 70 and K[k]["T"] < 220]
    print("== think（Jev 用时 / 思考用时 / 60 s 得分）")
    for d, k in sorted(c, reverse=True)[:8]:
        print(f"  {k}: Jev {J[k]['T']:.0f}s / Think {K[k]['T']:.0f}s；60 s 得分 {at(J[k], 60):.2f} / {at(K[k], 60):.2f}；思考 {len(K[k]['decisions'])} 次")

if "advice" in want:
    for root in ("llm_r5w_q38", "llm_r5w_vl8b", "llm_r5w_ds41"):
        J, A = load(root, "fastshared_jev"), load(root, "dualadvice_jev")
        c = []
        for k in J:
            if k not in A or not A[k]["success"]: continue
            rep = longest_repeat(J[k])
            if rep >= 3 and J[k]["score"] < A[k]["score"] - 0.2 and A[k]["T"] < 150:
                fa = [a for a in A[k]["advice"] if any(abs(s["t1"] - a["t"]) < 0.11 and str(s["reason"]).startswith("skill failed") for s in A[k]["slow"])]
                c.append((A[k]["score"] - J[k]["score"], rep, k, len(fa)))
        print(f"== advice {root}（得分差，Jev 最长重复失败，失败触发的建议数）")
        for d, rep, k, nf in sorted(c, reverse=True)[:6]:
            print(f"  {k}: Jev {J[k]['score']:.2f}（{J[k]['T']:.0f}s，重复 {rep} 次） / Advice {A[k]['score']:.2f}（{A[k]['T']:.0f}s，失败触发建议 {nf}）")

if "plan" in want:
    for root in ("llm_r5w_q38", "llm_r5w_ds41"):
        P = load(root, "dualshared_jev"); c = []
        for k, e in P.items():
            rj = [r for r in e["rejected"] if "not executable" in r["error"] or "no longer fits" in r["error"]]
            pl = [s for s in e["slow"] if s["kind"] == "plan" and not s["err"]]
            if rj and e["plans"] and e["success"] and e["T"] < 160 and any(s["t1"] - s["t0"] > 12 for s in pl):
                c.append((len(rj), k, len(e["plans"]), max(s["t1"] - s["t0"] for s in pl), e["T"]))
        print(f"== plan {root}（作废数，采用数，最长计划用时，局长）")
        for n, k, npub, mx, T in sorted(c, key=lambda x: (-min(x[0], 2), x[4]))[:6]:
            print(f"  {k}: 作废 {n}，采用 {npub}，最长计划 {mx:.0f}s，局长 {T:.0f}s；作废原因：{P[k]['rejected'][0]['error'][:90]}")

if "disturb" in want:
    J = load("llm_r5w_q38", "fastshared_jev"); c = []
    for k, e in J.items():
        if e["type"] not in ("Random_Disturbance", "Mix") or not e["success"]: continue
        for d in e["dist"]:
            if not d["related"]: continue
            f = next((s for s in e["skills"] if not s["ok"] and s["t0"] <= d["t"] + 1 and s["t1"] >= d["t"] and s["t1"] - d["t"] < 15), None)
            if f: c.append((e["T"], k, d, f)); break
    print("== disturb（局长，扰动物体，随后失败的技能）")
    for T, k, d, f in sorted(c, key=lambda x: x[0])[:8]:
        print(f"  {k}: {T:.0f}s；{d['t']:.1f}s 推开 {d['object']}，{f['name']} 失败（{f['reason'][:50]}）")

if "size" in want:
    Q, S2 = load("llm_r5w_q38", "fastshared_jev"), load("llm_r5w_vl2b", "fastshared_jev"); c = []
    for k in Q:
        if k in S2 and Q[k]["success"] and Q[k]["T"] < 80 and S2[k]["score"] <= 0.4:
            nf = sum(1 for s in S2[k]["skills"] if not s["ok"])
            c.append((Q[k]["score"] - S2[k]["score"], k, nf))
    print("== size（得分差，2B 失败技能数）")
    for d, k, nf in sorted(c, reverse=True)[:8]:
        print(f"  {k}: Qwen3.8 {Q[k]['score']:.2f}（{Q[k]['T']:.0f}s） / 2B {S2[k]['score']:.2f}（{S2[k]['T']:.0f}s，失败 {nf}）")
