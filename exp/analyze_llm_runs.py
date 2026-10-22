"""汇总 runs/llm/<task>/<tag>/episode.json：最终得分、时长、调用延迟、事件响应指标。
E1：事件触发时正在执行的过时技能是被取消还是执行完、取消延迟；事件后新提交的过时动作数；首个与新目标一致的动作延迟。
E3：目标子目标完成时间相对截止时间的余量（正=按时）。
用法: python analyze_llm_runs.py [task_dir_glob] [--md=out.md]"""
import sys, json, glob
from pathlib import Path
import numpy as np
import rc_env as R

def extract_rows(pat="*", root="llm"):
  rows = []
  for f in sorted(glob.glob(str(R.RUNS_ROOT / root / pat / "*" / "episode.json"))):
      ep = json.load(open(f)); tl_path = Path(f).with_name("timeline.json")
      rs_path = Path(f).with_name("rescored.json")
      if rs_path.exists():                                   # 优先使用离线重算（当前计分器版本）的结果
          rs = json.load(open(rs_path))
          ep["final"] = {"original": rs["original"], "repaired": rs["repaired"], "n_goals": rs["n_goals"], "all_done": rs["repaired_all"]}
          ep["subgoal_events"] = rs["subgoal_events"]; ep["scorer_version"] = rs.get("scorer_version")
      tl = json.load(open(tl_path)) if tl_path.exists() else {"events": []}
      ev = tl["events"]; t0 = next((e["sim"] for e in ev if e["type"] == "episode_start"), 0.0)
      ticks = [e for e in ev if e["type"] == "tick"]
      endev = next((e for e in ev if e["type"] == "episode_end"), {})
      max_lag = max([t.get("lag", 0) or 0 for t in ticks if t["sim"] - t0 > 3.0] or [0])     # 不计开局 3 s 启动瞬态
      rt_ok = (max_lag <= 0.25) and ((endev.get("lag_p95") or 0) <= 0.05)       # 计划 §7.1：仿真跟不上目标速率时该运行标记/重跑
      rel = lambda e: round(e["sim"] - t0, 2)
      fired = [e for e in ev if e["type"] == "event_fired"]
      m = {}
      if fired:
          fe = fired[0]; t_fire = rel(fe); etype = fe.get("event_type") or fe.get("etype", "")
          m["t_fire"] = t_fire
          if etype.startswith("E1"):
              p = fe["params"]; old_t, new_t = p["old_target"], p["new_target"]
              # 事件时刻在执行的技能
              started = {e["cid"]: e for e in ev if e["type"] == "skill_started"}
              ended = {e["cid"]: e for e in ev if e["type"] in ("skill_finished", "skill_cancelled")}
              inflight = [c for c, e in started.items() if rel(e) <= t_fire and (c not in ended or rel(ended[c]) >= t_fire)]
              if inflight:
                  c = inflight[0]; e_end = ended.get(c)
                  m["inflight"] = started[c]["skill"]
                  m["inflight_stale"] = old_t in started[c]["skill"]
                  m["inflight_outcome"] = (e_end["type"].replace("skill_", "") if e_end else "unfinished")
                  if e_end: m["inflight_end_after_s"] = round(rel(e_end) - t_fire, 2)
              subs = [e for e in ev if e["type"] == "cmd_submitted" and rel(e) > t_fire]
              fire_step = fe.get("step", 0)
              stale = (ep.get("event_report", {}).get(fe["eid"], {}) or {}).get("stale_actions", []) or []
              m["stale_after_event"] = sum(1 for a in stale if (a.get("obs_version") or 0) > fire_step)
              # 只认放置类命令（case6 中 pour(plate_1) 是原任务的一部分，不能算作对改目标的响应）
              first_new = next((e for e in subs if new_t in e["skill"] and str(e["skill"]).startswith("place")), None)
              m["first_new_target_cmd_s"] = None if first_new is None else round(rel(first_new) - t_fire, 2)
          if etype.startswith("E3"):
              dl = next((e for e in ev if e["type"] == "event_deadline"), None)
              window = None
              try: window = float(ep["event_report"][fe["eid"]]["deadline"]) - float(ep["event_report"][fe["eid"]]["t_fire"])
              except Exception: pass
              m["window_s"] = window
              tgt_region = fe["params"]["region"]
              done_t = next((t for t, what in ep.get("subgoal_events", []) if tgt_region in what and ("'in'" in what or '"in"' in what or "in'," in what)), None)
              m["target_done_s"] = done_t
              m["margin_s"] = None if (done_t is None or window is None) else round(t_fire + window - done_t, 2)
              m["drawer_closed_before_done"] = done_t is None
      lat = [c["latency"] for c in ep.get("calls", [])]
      m["api_retries"] = sum(int(c.get("n_retries") or 0) for c in ep.get("calls", []))
      m["api_retry_wait_s"] = round(sum(float(c.get("retry_wait_s") or 0) for c in ep.get("calls", [])), 1)
      tagname = Path(f).parent.name
      mon_flag = ("_mon" in tagname)
      mon_list = ep.get("monitor_log") or (ep["monitor"] if isinstance(ep.get("monitor"), list) else [])
      if ep["thinking"] == "dual": mode = "dual"
      elif isinstance(ep["thinking"], str): mode = ep["thinking"]              # 新运行器：dual_shared_text / dual_shared_jev / fast_shared_jev（可带 _bust）
      else: mode = ("think" if ep["thinking"] else "nothink") + ("+mon" if mon_flag else "")
      rows.append({"task": ep["case"], "events": ep["events"], "mode": mode,
                   "seed": ep.get("seed", 0), "score": f"{ep['final']['repaired']}/{ep['final']['n_goals']}", "all": ep["final"]["all_done"],
                   "sim_s": ep["sim_time"], "calls": ep["n_calls"], "lat_p50": round(float(np.median(lat)), 2) if lat else None,
                   "lat_max": round(float(np.max(lat)), 2) if lat else None, "mon_calls": len(mon_list), "tag": tagname,
                   "rt_ok": rt_ok, "max_lag_s": round(max_lag, 2), "file": f, **m})
  return rows


if __name__ == "__main__":
  pat = next((a for a in sys.argv[1:] if not a.startswith("--")), "*")
  md_out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--md=")), None)
  rows = extract_rows(pat)
  keys = ["task", "events", "mode", "seed", "rt_ok", "max_lag_s", "score", "all", "sim_s", "calls", "lat_p50", "lat_max", "mon_calls", "api_retries", "api_retry_wait_s", "t_fire", "inflight", "inflight_outcome", "inflight_end_after_s",
          "stale_after_event", "first_new_target_cmd_s", "window_s", "target_done_s", "margin_s"]
  present = [k for k in keys if any(k in r for r in rows)]
  lines = ["| " + " | ".join(present) + " |", "|" + "---|" * len(present)]
  for r in rows:
      lines.append("| " + " | ".join("" if r.get(k) is None else str(r.get(k)) for k in present) + " |")
  out = "\n".join(lines); print(out)
  if md_out: Path(md_out).write_text(out + "\n", encoding="utf-8"); print("wrote", md_out)
