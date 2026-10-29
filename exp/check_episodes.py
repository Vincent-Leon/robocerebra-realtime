"""快速检查一批 episode 的模型调用是否正常（部署新模型后的冒烟测试用）：
每局的得分、结束原因、调用次数、出错调用、无效回复、各分支延迟中位数，以及 Jev 选中字母的概率分布。
用法: python check_episodes.py <RUNS_SUBDIR>
"""
import sys, json, glob
from pathlib import Path
import numpy as np
import rc_env as R

root = sys.argv[1]
for f in sorted(glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "episode.json"))):
    p = Path(f); ep = json.load(open(f)); tl = json.load(open(p.with_name("timeline.json")))["events"]
    calls = ep.get("calls", []); hist = ep.get("history", []); fin = ep["final"]
    end = next((e["type"] for e in tl if e["type"] in ("all_done", "planner_done", "abort")), "limit")
    errs = [c for c in calls if c.get("error")]
    lat = {}
    for c in calls:
        if c.get("latency"): lat.setdefault(c.get("branch", "?"), []).append(c["latency"])
    pc = [c["p_choice"] for c in calls if c.get("p_choice") is not None]
    print(f"{p.parent.parent.name}/{p.parent.name}: 得分 {fin['repaired']}/{fin['n_goals']} 结束 {end} 用时 {ep['sim_time']:.0f}s | 模型 {ep.get('models', {}).get('fast')}"
          f" | 调用 {len(calls)}，出错 {len(errs)}，无效回复 {sum(1 for h in hist if h['call'] == '<invalid reply>')}，技能 {sum(1 for h in hist if not h['call'].startswith('<'))}"
          + "".join(f" | {b} 延迟中位 {np.median(v):.2f}s" for b, v in lat.items())
          + (f" | Jev 选中概率中位 {np.median(pc):.2f}，<0.5 的占 {np.mean(np.array(pc) < 0.5):.0%}" if pc else ""))
    for c in errs[:3]: print(f"    出错: {str(c['error'])[:160]}")
