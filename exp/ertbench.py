"""Embodied Real-Time Bench — command-line entry point.

Subcommands
  run      run agents on the benchmark against an OpenAI-compatible endpoint (vLLM, SGLang, hosted APIs)
  verify   check a results directory: completeness and real-time validity (optionally archive violators for re-runs)
  analyze  leaderboard statistics for one or more results directories
  site     build the single-page leaderboard website
  pack     package a results directory for submission (manifest + checksums)

Examples
  python ertbench.py run --model my-model --base-url http://127.0.0.1:8000/v1 --clock wall --modes jev,text,advice --seeds 1,2,3 --out my_model_wall
  python ertbench.py verify --out my_model_wall --archive-violations
  python ertbench.py analyze --out my_model_wall
  python ertbench.py pack --out my_model_wall

Protocol defaults follow the reference results: 60 public tasks, 300 s and 40 skills per episode, failure blocking after 3
consecutive failures, completion check with thinking off, two concurrent episodes per model instance under the wall clock.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS_ROOT = HERE / "runs"                                               # same as rc_env.RUNS_ROOT (avoid importing the simulator for CLI-only commands)

TYPES = ["Ideal", "Memory_Execution", "Memory_Exploration", "Mix", "Observation_Mismatching", "Random_Disturbance"]
MODES = {"jev": "--fast=jev --slow=off", "text": "--fast=text --slow=off", "think": "--fast=think --slow=off",
         "plan": "--fast=jev --slow=on", "advice": "--fast=jev --slow=advice --done_verify_wait=0"}
PROTOCOL = "--max_sim=300 --max_skills=40 --fail_block=3 --done_verify=fast"


def tasks_for(spec: str):
    all_t = [f"{t}/case{c}" for c in range(1, 11) for t in TYPES]                 # interleaved: partial runs stay balanced
    if spec in ("all", "public"): return all_t
    out = []
    for s in spec.split(","):
        out += [t for t in all_t if t.split("/")[0] == s] if s in TYPES else [s]
    return out


def git_rev():
    try:
        return subprocess.check_output(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def cmd_run(a):
    tasks = tasks_for(a.tasks); modes = a.modes.split(","); seeds = [int(s) for s in a.seeds.split(",")]
    for m in modes:
        if m not in MODES: sys.exit(f"unknown mode {m}; choose from {list(MODES)}")
    par = a.parallel or (2 if a.clock == "wall" else 8)
    extra = f" --clock={a.clock}" + ("" if a.image == "on" else " --image=off")
    lines = [f"{t} {MODES[m]} {PROTOCOL} --seed={s}{extra}" for s in seeds for t in tasks for m in modes]
    out = RUNS_ROOT / a.out; out.mkdir(parents=True, exist_ok=True)
    jobs = out / "_jobs.txt"; jobs.write_text("# ertbench run\n" + "\n".join(lines) + "\n")
    if a.resume:                                                       # skip episodes that already have results
        rem = subprocess.run([sys.executable, str(HERE / "jobs_remaining.py"), str(jobs), a.out], capture_output=True, text=True, cwd=HERE)
        jobs.write_text(rem.stdout); print(rem.stderr.strip().splitlines()[-1] if rem.stderr.strip() else "")
    manifest = {"benchmark": "Embodied Real-Time Bench", "version": "0.1", "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": a.model, "endpoint": a.base_url.split("//")[-1].split("/")[0].rsplit(":", 1)[0] if a.base_url else None,
                "clock": a.clock, "modes": modes, "seeds": seeds, "tasks": len(tasks), "image": a.image, "parallel_episodes": par,
                "hardware": a.hardware, "code_revision": git_rev(), "protocol": PROTOCOL}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    env = dict(os.environ, RUNS_SUBDIR=a.out, LLM_PROFILE="gateway", LLM_MODEL=a.model, LLM_BASE_URL=a.base_url,
               LLM_API_KEY=os.environ.get(a.api_key_env, "EMPTY"))
    host = a.base_url.split("//")[-1].split("/")[0].rsplit(":", 1)[0]            # the endpoint bypasses any HTTP proxy (exact host; CIDR entries are not honoured by every client)
    for k in ("NO_PROXY", "no_proxy"): env[k] = ",".join(x for x in [host, "localhost", "127.0.0.1", os.environ.get(k, "")] if x)
    if a.render_gpu is not None:
        env.update(MUJOCO_GL="egl", PYOPENGL_PLATFORM="egl", MUJOCO_EGL_DEVICE_ID=str(a.render_gpu), CUDA_VISIBLE_DEVICES=str(a.render_gpu))
    n = sum(1 for ln in jobs.read_text().splitlines() if ln.strip() and not ln.startswith("#"))
    print(f"{n} episodes · clock {a.clock} · {par} in parallel · results in {out}")
    if a.dry_run: return
    sys.exit(subprocess.call([sys.executable, str(HERE / "run_jobs.py"), str(HERE), str(jobs), f"--parallel={par}"], env=env, cwd=HERE))


def rt_ok(tl):
    st = next((e for e in tl if e["type"] == "episode_start"), {"sim": 0.0})
    ticks = [e for e in tl if e["type"] == "tick" and e["sim"] - st["sim"] > 3.0]
    end = next((e for e in tl if e["type"] == "episode_end"), {})
    mx = max([t.get("lag", 0) or 0 for t in ticks] or [0])
    return mx <= 0.25 and (end.get("lag_p95") or 0) <= 0.05, mx


def cmd_verify(a):
    root = RUNS_ROOT / a.out; done = bad = 0; missing, viol = [], []
    for d in sorted(p for p in root.glob("*/*") if p.is_dir() and not p.parent.name.startswith("_")):
        if not (d / "episode.json").exists(): missing.append(d); continue
        ok, mx = rt_ok(json.load(open(d / "timeline.json"))["events"])
        if ok: done += 1
        else: bad += 1; viol.append((d, mx))
    print(f"{a.out}: {done} valid episodes, {bad} real-time violations (max lag > 0.25 s or p95 > 50 ms), {len(missing)} incomplete")
    for d, mx in viol: print(f"  violation: {d.parent.name}/{d.name} (max lag {mx:.2f} s)")
    if a.archive_violations and (viol or missing):
        arc = RUNS_ROOT / f"{a.out}_archived" / time.strftime("%Y%m%d-%H%M%S")
        for d in [v[0] for v in viol] + missing:
            dst = arc / d.parent.name / d.name; dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(d), str(dst))
        print(f"archived {len(viol) + len(missing)} episode directories to {arc}; re-run with `run ... --resume`")


def cmd_analyze(a):
    sys.exit(subprocess.call([sys.executable, str(HERE / "analyze_leaderboard.py"), f"--root={a.out}", f"--gt={a.gt}"] + ([f"--name={a.name}"] if a.name else []), cwd=HERE))


def cmd_site(a):
    args = [sys.executable, str(HERE / "make_site.py")] + [f"--{k}={v}" for k, v in (("wall", a.wall), ("token", a.token), ("paused", a.paused)) if v]
    sys.exit(subprocess.call(args, cwd=HERE))


def cmd_pack(a):
    root = RUNS_ROOT / a.out; tgt = Path(a.dest or ".") / f"{a.out}.tar.gz"
    files = [p for p in root.rglob("*") if p.is_file() and p.name in ("episode.json", "timeline.json", "manifest.json")]
    sums = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (root / "checksums.json").write_text(json.dumps(sums, indent=0))
    with tarfile.open(tgt, "w:gz") as tf:
        for p in files + [root / "checksums.json"]: tf.add(p, arcname=f"{a.out}/{p.relative_to(root)}")
    print(f"wrote {tgt} ({len(files)} files, {tgt.stat().st_size / 1e6:.1f} MB); see docs/submit.md")


def main():
    ap = argparse.ArgumentParser(prog="ertbench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run", help="run agents on the benchmark")
    r.add_argument("--model", required=True, help="served model name at the endpoint")
    r.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. http://127.0.0.1:8000/v1")
    r.add_argument("--api-key-env", default="OPENAI_API_KEY", help="environment variable holding the API key (default OPENAI_API_KEY; EMPTY if unset)")
    r.add_argument("--clock", choices=["wall", "token", "paused"], default="wall")
    r.add_argument("--modes", default="jev,text,advice", help=f"comma-separated, from {','.join(MODES)}")
    r.add_argument("--seeds", default="1,2,3"); r.add_argument("--tasks", default="all", help="all | category name(s) | task ids, comma-separated")
    r.add_argument("--image", choices=["on", "off"], default="on"); r.add_argument("--parallel", type=int, default=None, help="episodes in parallel (default 2 for wall, 8 otherwise)")
    r.add_argument("--out", required=True, help="results directory name under exp/runs/"); r.add_argument("--hardware", default=None, help="hardware label recorded in the manifest, e.g. '1x H20'")
    r.add_argument("--render-gpu", type=int, default=None, help="GPU index for EGL rendering (Linux, headless)")
    r.add_argument("--resume", action="store_true", help="skip episodes that already have results"); r.add_argument("--dry-run", action="store_true")
    r.set_defaults(fn=cmd_run)
    v = sp.add_parser("verify", help="completeness and real-time validity"); v.add_argument("--out", required=True)
    v.add_argument("--archive-violations", action="store_true"); v.set_defaults(fn=cmd_verify)
    n = sp.add_parser("analyze", help="leaderboard statistics"); n.add_argument("--out", required=True, help="results directory, or several comma-separated")
    n.add_argument("--gt", default="gtplan_h20_r5a"); n.add_argument("--name", default=None); n.set_defaults(fn=cmd_analyze)
    s = sp.add_parser("site", help="build the website"); s.add_argument("--wall"); s.add_argument("--token"); s.add_argument("--paused"); s.set_defaults(fn=cmd_site)
    p = sp.add_parser("pack", help="package results for submission"); p.add_argument("--out", required=True); p.add_argument("--dest", default=None); p.set_defaults(fn=cmd_pack)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
