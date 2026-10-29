"""列出作业文件中尚未完成（没有 episode.json）的作业，供中断后续跑或换机器继续。
输出目录的命名与 run_dual_shared_episode.py 一致：runs/<RUNS_SUBDIR>/<类型>_<case>/<tag>/episode.json。
用法: python jobs_remaining.py <作业文件> <RUNS_SUBDIR> [> 剩余作业文件]
"""
import sys
from pathlib import Path
import rc_env as R


def tag_of(line: str) -> str:
    parts = line.split(); opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in parts[1:] if a.startswith("--") and "=" in a}
    fast, slow = opt.get("fast", "text"), opt.get("slow", "on")
    ev = opt.get("events"); ev_name = ev.split("/")[-1].replace(".json", "") if ev else "noevent"
    branch = "dualadvice" if slow == "advice" else ("dualshared" if slow == "on" else "fastshared")
    fb = int(opt.get("fail_block", 0)); dv = opt.get("done_verify", "off"); img = opt.get("image", "on") == "on"; clock = opt.get("clock", "wall")
    sfx = (f"_fb{fb}" if fb else "") + {"off": "", "think": "_dv", "fast": "_dvf"}[dv] + ("" if img else "_noimg") + ("" if clock == "wall" else f"_clk{clock}")
    aw = float(opt.get("advice_wait", 0)); sfx += (f"_aw{aw:g}" if aw > 0 else "") + ("_rws" if opt.get("replan_wait", "off") == "state" else "")   # r5d
    bust = "_bust" if opt.get("cache_bust", "off") == "on" else ""
    mon = "" if opt.get("monitor", "on") == "on" else "_nomon"
    monsync = "_monsync" if (opt.get("monitor", "on") == "on" and opt.get("monitor_async", "on") != "on") else ""
    return opt.get("tag", f"{ev_name}_{branch}_{fast}{bust}{mon}{monsync}{sfx}_s{int(opt.get('seed', 0))}")


jobs, sub = Path(sys.argv[1]), sys.argv[2]
left = done = 0
for ln in jobs.read_text().splitlines():
    s = ln.strip()
    if not s or s.startswith("#"):
        if s: print(s)
        continue
    tt, cn = s.split()[0].split("/")
    if (R.RUNS_ROOT / sub / f"{tt}_{cn}" / tag_of(s) / "episode.json").exists(): done += 1; continue
    print(s); left += 1
print(f"# 剩余 {left} 个（已完成 {done} 个）", file=sys.stderr)
