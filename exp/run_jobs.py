"""批量运行实时 episode：从作业文件按固定并行度依次启动 run_dual_shared_episode.py。
作业文件每行一个 episode：任务 + 参数（如 `Ideal/case1 --fast=jev --slow=off --seed=1`），# 开头为注释。
每个作业的输出写到 runs/<RUNS_SUBDIR>/_logs/<作业文件名>/<行号>.log（同一目录跑多个作业文件时互不覆盖）；进度追加到 runs/<RUNS_SUBDIR>/_logs/progress.txt。
用法: RUNS_SUBDIR=llm_xxx LLM_PROFILE=exp python run_jobs.py <代码快照目录> <作业文件> [--parallel=2] [--python=解释器]
"""
import os, sys, time, subprocess, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
snap, jobs_file = Path(args[0]).resolve(), Path(args[1]).resolve()
parallel = int(opt.get("parallel", 2)); py = opt.get("python", sys.executable)
sub = os.environ.get("RUNS_SUBDIR")
assert sub, "需要设置 RUNS_SUBDIR"
logs = snap.parent / "exp" / "runs" / sub / "_logs"; jlogs = logs / jobs_file.stem; jlogs.mkdir(parents=True, exist_ok=True)
jobs = [(i, ln.strip()) for i, ln in enumerate(jobs_file.read_text().splitlines(), 1) if ln.strip() and not ln.strip().startswith("#")]
lock = threading.Lock()


def note(msg):
    with lock:
        with open(logs / "progress.txt", "a") as f: f.write(f"[{time.strftime('%m-%d %H:%M:%S')}] {msg}\n")


def run(job):
    i, line = job
    note(f"start #{i} {line}")
    t0 = time.time()
    with open(jlogs / f"{i:03d}.log", "w") as out:
        rc = subprocess.call([py, "run_dual_shared_episode.py", *line.split()], cwd=snap, stdout=out, stderr=subprocess.STDOUT)
    note(f"done  #{i} rc={rc} {time.time() - t0:.0f}s {line}")
    return rc


note(f"== {len(jobs)} 个作业，并行 {parallel}，快照 {snap.name}，作业文件 {jobs_file.name}")
with ThreadPoolExecutor(parallel) as ex:
    rcs = list(ex.map(run, jobs))
note(f"== 全部结束：失败 {sum(1 for r in rcs if r)} 个")
