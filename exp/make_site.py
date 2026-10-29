"""基准网站（单个自包含 HTML，离线可用，英文）：仿照 VISTA / RSI-Exam / Realtime-Bench 的单页结构。
数据：调用 analyze_leaderboard.py 一次读入所有结果目录（真实 / token / 暂停时钟），参考线为同一平台上的标准计划（脚本化执行器按演示步骤执行）。
页面里由逐局记录现算：任意时间预算与任务类别下的得分（± 批间 SD）、整任务成功率、pass^3（3 批都成功的任务比例）。
用法: python make_site.py [--wall=目录,...] [--token=目录,...] [--paused=目录,...] [--gt=gtplan_h20_r5a] [--out=../site/index.html]
  目录名以 llm_r5w_ 开头视为 H20 上的真实时钟，llm_h20_r5_ 开头视为 L20 上的真实时钟（仿真都在 H20 上）。
"""
import sys, json, glob, subprocess, tempfile, time, base64
from pathlib import Path
import numpy as np
import rc_env as R

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
lst = lambda k, d: [x for x in opt.get(k, d).split(",") if x]
WALL = lst("wall", "llm_r5w_q38,llm_r5w_vl32b,llm_r5w_vl8b,llm_r5w_vl4b,llm_r5w_vl2b")
TOKEN = lst("token", "llm_h20_r5_q38_token,llm_r5t_vl32b,llm_r5t_vl8b,llm_r5t_vl4b,llm_r5t_vl2b")
PAUSED = lst("paused", "llm_h20_r5_q38_paused,llm_r5p_vl32b,llm_r5p_vl8b,llm_r5p_vl4b,llm_r5p_vl2b")
GT_TAG = opt.get("gt", "gtplan_h20_r5a")
OUT = Path(opt.get("out", str(R.PROJECT_ROOT / "site" / "index.html")))
HERE = Path(__file__).resolve().parent

MODELS = {   # 键 = analyze_leaderboard 的 short_model
    "qwen3.8-27b": {"short": "Qwen3.8-27B", "label": "Qwen3.8-27B", "params": 27, "prec": "FP8", "note": "dense, hybrid attention"},
    "qwen3-vl-32b": {"short": "Qwen3-VL-32B", "label": "Qwen3-VL-32B-Instruct", "params": 32, "prec": "FP8", "note": "dense"},
    "qwen3-vl-8b": {"short": "Qwen3-VL-8B", "label": "Qwen3-VL-8B-Instruct", "params": 8, "prec": "BF16", "note": "dense"},
    "qwen3-vl-4b": {"short": "Qwen3-VL-4B", "label": "Qwen3-VL-4B-Instruct", "params": 4, "prec": "BF16", "note": "dense"},
    "qwen3-vl-2b": {"short": "Qwen3-VL-2B", "label": "Qwen3-VL-2B-Instruct", "params": 2, "prec": "BF16", "note": "dense"},
    "deepseek-v4.1-flash": {"short": "DeepSeek-V4.1-Flash", "label": "DeepSeek-V4.1-Flash", "params": 284, "active": 13, "prec": "FP8 KV", "note": "MoE, 13B active"},
}
MODES = [   # 固定顺序与颜色（与中文排行榜页相同的已校验调色板）
    {"key": "fast_shared_jev", "name": "Fast · Jev", "desc": "All legal actions are listed as lettered options; the model emits a single token."},
    {"key": "fast_shared_text", "name": "Fast · Text", "desc": "Thinking off; one JSON action per decision."},
    {"key": "fast_shared_think", "name": "Slow · Think", "desc": "Thinks before every action (up to 4,096 tokens)."},
    {"key": "dual_shared_jev", "name": "Dual · Plan", "desc": "Fast Jev acts continuously; a slow branch thinks in the background and sends full plans."},
    {"key": "dual_advice_jev", "name": "Dual · Advice", "desc": "Fast Jev acts continuously; a slow branch (thinking off) injects one- or two-sentence advice."},
]
KEYS = [m["key"] for m in MODES]
TYPES = ["Ideal", "Memory_Execution", "Memory_Exploration", "Mix", "Observation_Mismatching", "Random_Disturbance"]
CATS = [
    {"key": "Ideal", "name": "Ideal", "desc": "Static scene; follow a multi-step household instruction."},
    {"key": "Memory_Execution", "name": "Memory · Execution", "desc": "Objects disappear into closed drawers; the agent must remember where they are and act on them."},
    {"key": "Memory_Exploration", "name": "Memory · Exploration", "desc": "Target objects start hidden; the agent must search drawers before acting."},
    {"key": "Mix", "name": "Mix", "desc": "Observation mismatch and random disturbances together."},
    {"key": "Observation_Mismatching", "name": "Observation Mismatch", "desc": "The episode starts mid-way through the demonstration; the instruction no longer matches the scene."},
    {"key": "Random_Disturbance", "name": "Random Disturbance", "desc": "Objects are randomly displaced while the agent works."},
]


def hw_of(root, clock):
    if clock != "wall": return "any"
    if "ds41" in root: return "4× H20"
    if root.startswith("llm_r5w_"): return "1× H20"
    if root.startswith("llm_h20_r5_"): return "1× L20"
    return "?"


# ---------- 读数据（一次调用 analyze_leaderboard.py） ----------
roots = [r for r in WALL + TOKEN + PAUSED if list(R.RUNS_ROOT.glob(f"{r}/*/*/episode.json"))]
tmp = Path(tempfile.mkdtemp())
subprocess.run([sys.executable, str(HERE / "analyze_leaderboard.py"), f"--root={','.join(roots)}", "--name=site", f"--gt={GT_TAG}", f"--out={tmp}"],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=HERE)
EPS = json.load(open(tmp / "leaderboard_site_episodes.json")); LBJ = json.load(open(tmp / "leaderboard_site.json"))

cfg_index, cfgs = {}, []
for e in EPS:
    if e["mode"] not in KEYS or e["model"] not in MODELS: continue
    k = (e["model"], e["mode"], e["clock"], hw_of(e["root"], e["clock"]))
    if k not in cfg_index:
        cfg_index[k] = len(cfgs); cfgs.append({"model": k[0], "mode": KEYS.index(k[1]), "clock": k[2], "hw": k[3], "_eps": []})
    cfgs[cfg_index[k]]["_eps"].append(e)

TASKS = sorted({e["task"] for e in EPS}, key=lambda t: (TYPES.index(t.split("/")[0]), int(t.split("case")[1])))
gt = {}
for f in glob.glob(str(R.RUNS_ROOT / GT_TAG / "*" / "result.json")):
    r = json.load(open(f)); x = int(r.get("excluded", 0))
    gt[r["task"]] = [round((r["repaired_done"] - x) / max(r["n_goals"] - x, 1), 4), bool(r["repaired_all"])]
instr = {}
for t in TASKS:
    tt, cn = t.split("/")
    try:
        c = R.load_case(tt, R.BENCH_ROOT / tt / cn); instr[t] = {"text": c.task_line, "n": sum(len(v) for v in c.goal.values())}
    except Exception as ex:
        instr[t] = {"text": "", "n": None}

med = lambda v: float(np.median(v)) if len(v) else None
p95 = lambda v: float(np.percentile(v, 95)) if len(v) else None
eps_out = []
for i, c in enumerate(cfgs):
    v = c.pop("_eps")
    f_ = [x for e in v for x in e["fast"]]; s_ = [x for e in v for x in e["slow"]]
    c["stats"] = {"lat50": med(f_), "lat95": p95(f_), "slow50": med(s_), "time": med([e["time"] for e in v]),
                  "tok": med([e["tok_nc"] for e in v]), "cached": med([e["tok_cached"] for e in v]), "n": len(v),
                  "seeds": sorted({int(e["seed"]) for e in v}), "fail": float(np.mean([e["failed"] for e in v]))}
    c["ntasks"] = len({e["task"] for e in v})                        # 暂停时钟的仅慢 / 完整计划只跑 12 个试点任务，页面上标"12 tasks"而不是"running"
    for e in v:
        eps_out.append([i, TASKS.index(e["task"]), int(e["seed"]), int(e["n"]), int(bool(e["success"])), sorted(round(float(t), 1) for t in e["events"])])

# ---------- 决策事件统计（analyze_events.py 的输出）与示例局（site_demos.json + render_demo.py 的视频） ----------
EV_PATH = Path(opt.get("events", str(R.PROJECT_ROOT / "notes" / "figs_lb" / "events_r5.json")))
EVENTS = json.load(open(EV_PATH)) if EV_PATH.exists() else None
if EVENTS: EVENTS = {k: EVENTS[k] for k in ("time", "advice_timing", "repeat_pos", "plans", "calib", "think", "n_episodes") if k in EVENTS}
VID = OUT.parent / "videos"


def demo_episode(item):
    from analyze_events import parse
    e = parse(R.RUNS_ROOT / item["dir"]); r3 = lambda v: round(float(v), 2)
    tt, cn = e["task"].split("/")
    meta = json.load(open(VID / f"{item['id']}.json")) if (VID / f"{item['id']}.json").exists() else None
    dec = []
    for x in e["decisions"]:
        lab = x["skill"]["name"] if x["skill"] else {"blocked_choice": "(blocked: failed 3× in a row)", "blocked_override": "(blocked choice allowed)", "invalid_action": "(invalid action)",
                                                      "done_verify": "(declares done)", "planner_done": "(declares done)"}.get(x["res"], "")
        dec.append([r3(x["t0"]), r3(x["t1"]), None if x["p"] is None else round(x["p"], 3), lab])
    slow = []
    for x in e["slow"]:
        out = ""
        if x["kind"] == "plan":
            pl = next((q for q in e["plans"] if abs(q["t"] - x["t1"]) < 0.6), None); rj = next((q for q in e["rejected"] if abs(q["t"] - x["t1"]) < 0.6), None)
            out = (f"adopted ({pl['n']} steps): " + ", ".join(pl["steps"] or [])) if pl else (f"discarded: {rj['error']}" if rj else ("no plan returned" if x["err"] else ""))
        slow.append([r3(x["t0"]), r3(x["t1"]), x["kind"], str(x["reason"] or "")[:160], out[:400]])
    return {"id": item["id"], "model": e["model"], "mode": KEYS.index(e["mode"]), "clock": e["clock"], "task": e["task"], "seed": e["seed"],
            "instr": instr.get(e["task"], {}).get("text") or "", "T": r3(e["T"]), "n": e["n"], "done": e["done"], "success": e["success"],
            "skills": [[r3(c["t0"]), r3(c["t1"]), c["name"], int(c["ok"]), c["reason"][:120]] for c in e["skills"]],
            "dec": dec, "slow": slow, "adv": [[r3(a["t"]), a["text"]] for a in e["advice"]], "sub": [r3(t) for t in e["sub"]],
            "dist": [[r3(d["t"]), d["object"]] for d in e["dist"]],
            "video": None if meta is None else {"src": f"videos/{item['id']}.mp4", "poster": f"videos/{item['id']}.jpg", "t_first": meta["t_first"], "hold": meta["hold"]}}


DEMOS = []
spec_path = HERE / "site_demos.json"
if spec_path.exists():
    for st in json.load(open(spec_path))["stories"]:
        try: DEMOS.append({"id": st["id"], "title": st["title"], "lead": st["lead"], "eps": [demo_episode(it) for it in st["episodes"]]})
        except FileNotFoundError as ex: print("跳过示例", st["id"], ex)

ORGS = [("University of Toronto", "toronto"), ("McGill University", "mcgill"), ("Carnegie Mellon University", "cmu"),
        ("University of Alberta", "alberta"), ("Georgia Institute of Technology", "gatech"), ("UC Berkeley", "berkeley")]   # 标志取自维基百科词条信息框，缩到 120 px 高
orgs = [{"name": n, "logo": "data:image/png;base64," + base64.b64encode((HERE / "site_assets" / "logos" / f"{k}.png").read_bytes()).decode()} for n, k in ORGS]
DATA = {
    "orgs": orgs,
    "models": MODELS, "modes": MODES, "cats": CATS, "cfgs": cfgs, "eps": eps_out, "events": EVENTS, "demos": DEMOS,
    "tasks": [{"id": t, "cat": TYPES.index(t.split("/")[0]), "instr": instr[t]["text"], "n": instr[t]["n"], "gt": gt.get(t, [None, False])} for t in TASKS],
    "meta": {"built": time.strftime("%Y-%m-%d"), "episodes": len(eps_out), "token_rates": [0.145, 2821.0, 23.6],
             "clocks": sorted({c["clock"] for c in cfgs}), "gt_mean": float(np.mean([g[0] for g in gt.values()])) if gt else None,
             "gt_succ": float(np.mean([g[1] for g in gt.values()])) if gt else None},
}

HTML = (HERE / "site_template.html").read_text(encoding="utf-8")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False, separators=(",", ":"))), encoding="utf-8")
print(f"{OUT}：{len(cfgs)} 个配置，{len(eps_out)} 局，{OUT.stat().st_size / 1024:.0f} KB；时钟 {DATA['meta']['clocks']}")
