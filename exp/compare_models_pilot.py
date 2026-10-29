"""本机小试点的跨模型对比：同一批任务 × 3 种核心模式，每个模型一个结果目录。
Qwen3.8 参考：优先用 r5b（失败屏蔽 3），没有的任务用 r5a（屏蔽 2；这些任务失败很少，阈值影响可忽略）。
用法: python compare_models_pilot.py <名称=目录[+备用目录]> ...   例：q38=llm_l20_r5b_pilot+llm_l20_r5a_pilot vl2b=llm_l20_r5b_vl2b_pilot
"""
import sys, json, glob, collections
import numpy as np
import rc_env as R

GT = {}
for f in glob.glob(str(R.RUNS_ROOT / "gtplan_r4_final" / "*" / "result.json")):
    r = json.load(open(f)); x = int(r.get("excluded", 0)); GT[r["task"]] = (r["repaired_done"] - x) / max(r["n_goals"] - x, 1)
NAME = {"fast_shared_jev": "仅快·Jev", "fast_shared_text": "仅快·文本", "dual_advice_jev": "建议注入"}


def load(dirs):
    out = {}
    for d in reversed(dirs):                                   # 前面的目录优先（后读覆盖）
        for f in glob.glob(str(R.RUNS_ROOT / d / "*" / "*" / "episode.json")):
            e = json.load(open(f))
            if e["thinking"] not in NAME or e.get("done_verify", "off") == "think": continue
            fin = e["final"]; x = int(fin.get("excluded", 0)); hist = e["history"]
            calls = e["calls"]; fast = [c["latency"] for c in calls if c.get("branch") == "fast" and c.get("latency")]
            out[(e["case"], e["thinking"])] = {"score": (fin["repaired"] - x) / max(fin["n_goals"] - x, 1), "time": e["sim_time"],
                "fail": sum(1 for h in hist if not h["ok"] and not h["call"].startswith("<")), "invalid": sum(1 for h in hist if h["call"] == "<invalid reply>"),
                "blocked": int(e.get("n_blocked") or 0), "lat": float(np.median(fast)) if fast else np.nan,
                "err": sum(1 for c in calls if c.get("error") and "blocked call" not in str(c.get("error")))}
    return out


models = [(a.split("=")[0], load(a.split("=")[1].split("+"))) for a in sys.argv[1:]]
tasks = sorted({k[0] for _, d in models for k in d})
for m in NAME:
    common = [t for t in tasks if all((t, m) in d for _, d in models)]
    print(f"## {NAME[m]}（{len(common)} 个共同任务；标准计划 {np.mean([GT[t] for t in common]):.3f}）")
    print(f"{'模型':8s} {'得分':>6s} {'决策延迟中位':>10s} {'失败技能':>8s} {'无效回复':>8s} {'出错调用':>8s} {'用时':>6s}")
    for name, d in models:
        v = [d[(t, m)] for t in common]
        print(f"{name:8s} {np.mean([x['score'] for x in v]):6.3f} {np.nanmedian([x['lat'] for x in v]):9.2f}s {np.mean([x['fail'] for x in v]):8.1f} "
              f"{np.mean([x['invalid'] for x in v]):8.1f} {np.mean([x['err'] for x in v]):8.1f} {np.mean([x['time'] for x in v]):5.0f}s")
    print()
