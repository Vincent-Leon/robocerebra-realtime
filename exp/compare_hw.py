"""硬件校准：同一模型、同一代码与设置，只换推理所用的 GPU，逐任务比较得分与延迟。
默认比较 L20 GPU3（runs/llm_h20_r5_q38，取 3 种核心模式）与 H20 GPU0（runs/llm_h20_r5_q38_h20gpu）上的 Qwen3.8-27B；仿真都在 H20 上。
得分口径与排行榜相同（有效子目标完成率；时间预算 B 秒得分 = 前 B 秒内完成的子目标比例）。
配对差：H20 − L20，按任务重抽样 10000 次给 95% 区间。
用法: python compare_hw.py [--a=llm_h20_r5_q38] [--b=llm_h20_r5_q38_h20gpu] [--na=L20] [--nb=H20] [--out=../notes/figs_lb/hw_calibration_q38.md]
"""
import sys, json, glob
from pathlib import Path
import numpy as np
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
A, B = opt.get("a", "llm_h20_r5_q38"), opt.get("b", "llm_h20_r5_q38_h20gpu")
NA, NB = opt.get("na", "L20"), opt.get("nb", "H20")
OUT = Path(opt.get("out", str(R.PROJECT_ROOT / "notes" / "figs_lb" / "hw_calibration_q38.md")))
NAME = {"fast_shared_jev": "仅快·Jev", "fast_shared_text": "仅快·文本", "dual_advice_jev": "双分支·建议注入"}
BUDGETS = (30, 60, 120, None)


def load(root):
    out = {}
    for f in glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "episode.json")):
        e = json.load(open(f))
        if e["thinking"] not in NAME: continue
        fin = e["final"]; x = int(fin.get("excluded", 0)); n = max(fin["n_goals"] - x, 1)
        ev = [float(t) for t, _ in e.get("subgoal_events", [])]
        calls = e.get("calls", [])
        out[(e["case"], e["thinking"])] = {
            "score": {str(b): ((fin["repaired"] - x) / n if b is None else sum(t <= b for t in ev) / n) for b in BUDGETS},
            "fast": [c["latency"] for c in calls if c.get("branch") == "fast" and c.get("latency")],
            "slow": [c["latency"] for c in calls if c.get("branch") == "slow" and c.get("latency")],
            "ttft": [c["ttft"] for c in calls if c.get("branch") == "fast" and c.get("ttft")],
            "time": e["sim_time"], "success": bool(fin["all_done"])}
    return out


def boot(d, rng):
    m = d[rng.integers(0, len(d), size=(10000, len(d)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


a, b = load(A), load(B)
rng = np.random.default_rng(20261027)
L = [f"# 硬件校准：同一 Qwen3.8-27B，{NA} 对 {NB}", "",
     f"- {NA}：`runs/{A}`；{NB}：`runs/{B}`。仿真都在 H20 上，代码 r5b，60 个任务 × 3 种核心模式，每种 1 批。",
     "- 两边同一镜像（vLLM 0.27.1）、同一权重（18 个分片 sha256 一致）、FP8 在线量化与其余参数相同；可用显存都约 43.2 GiB，KV 缓存 12.15 / 12.61 GiB。", "",
     f"| 模式 | 决策延迟 p50（{NA} → {NB}） | p95 | 慢分支 p50 | 全程得分 | 60 s 得分 | 120 s 得分 | 每局用时中位 |", "|---|---|---|---|---|---|---|---|"]
pairs = []
for m, nm in NAME.items():
    ks = sorted(k for k in a if k[1] == m and k in b)
    if not ks: continue
    fa = np.array([x for k in ks for x in a[k]["fast"]]); fb = np.array([x for k in ks for x in b[k]["fast"]])
    sa = [x for k in ks for x in a[k]["slow"]]; sb = [x for k in ks for x in b[k]["slow"]]
    sc = lambda d, B_: np.mean([d[k]["score"][str(B_)] for k in ks])
    slow = f"{np.median(sa):.2f} → {np.median(sb):.2f} s" if sa and sb else "–"
    L.append(f"| {nm} | {np.median(fa):.2f} → {np.median(fb):.2f} s（×{np.median(fa) / np.median(fb):.2f}） | {np.percentile(fa, 95):.2f} → {np.percentile(fb, 95):.2f} s | {slow} | "
             f"{sc(a, None):.3f} → {sc(b, None):.3f} | {sc(a, 60):.3f} → {sc(b, 60):.3f} | {sc(a, 120):.3f} → {sc(b, 120):.3f} | "
             f"{np.median([a[k]['time'] for k in ks]):.0f} → {np.median([b[k]['time'] for k in ks]):.0f} s |")
    for B_ in BUDGETS:
        d = np.array([b[k]["score"][str(B_)] - a[k]["score"][str(B_)] for k in ks])
        lo, hi = boot(d, rng)
        pairs.append((nm, B_, len(ks), float(d.mean()), lo, hi, int((d > 1e-9).sum()), int((abs(d) <= 1e-9).sum()), int((d < -1e-9).sum())))
L += ["", f"## 逐任务配对差（{NB} − {NA}）", "", "同一任务、同一模式的得分差；95% 区间按任务重抽样（10000 次），包含 0 即差异不显著。", "",
      "| 模式 | 时间预算 | 任务数 | 平均差 | 95% 区间 | 更好 / 相同 / 更差 |", "|---|---|---|---|---|---|"]
L += [f"| {nm} | {'全程' if B_ is None else f'{B_} s'} | {n} | {dm:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {w} / {t} / {l} |" for nm, B_, n, dm, lo, hi, w, t, l in pairs]
txt = "\n".join(L) + "\n"; OUT.write_text(txt, encoding="utf-8"); print(txt)
