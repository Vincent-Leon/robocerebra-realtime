"""Original 协议 × 脚本化执行器：复现官方 eval_openvla.py 的时间片切换（switch_steps=150/子步）与可选 resume。
与 run_gt_plan.py（完成即切换）对照，可分离"时间预算"与"切换方式"的影响（计划文档 §5.4）。
用法: python run_original.py <task_type/case> ... [--switch=150] [--resume] [--video] [--tag=NAME]
"""
import sys, json, time
import numpy as np
import imageio.v2 as imageio
import rc_env as R
from skills import ScriptedExecutor
from scoring import OriginalScorer, RepairedScorer
from dispatch import execute_goal_state

args = [a for a in sys.argv[1:] if not a.startswith("--")]
want_video = "--video" in sys.argv
resume = "--resume" in sys.argv
switch = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--switch=")), 150))
tag = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tag=")), f"original_s{switch}{'_resume' if resume else ''}")


class DualScorer:
    def __init__(self, env, goal):
        self.orig = OriginalScorer(env, goal); self.rep = RepairedScorer(env, goal); self.n_goals = self.rep.n_goals
        self.last = (0, False, 0, False)
    def update(self):
        _, n_o, a_o = self.orig.update(); comp, n_r, a_r = self.rep.update(); self.last = (n_o, a_o, n_r, a_r); return comp, n_r, a_r
    def force_progress(self, goal, goal_steps, upto_step):
        """resume：把 task_step < upto_step 的子目标标记为已完成（官方 simulate_resume_completion 的做法），返回强制完成数。"""
        forced = 0
        for obj, acts in goal.items():
            k_target = sum(1 for stp in goal_steps[obj] if stp < upto_step)
            for sc_prog in (getattr(self.orig.env, "_state_progress", None), self.rep._progress):
                if sc_prog is not None and sc_prog.get(obj, 0) < k_target:
                    forced += k_target - sc_prog.get(obj, 0); sc_prog[obj] = k_target
        return forced // 2 if forced else 0


def run_case(task_type, case_name):
    out_dir = R.RUNS_ROOT / tag / f"{task_type}_{case_name}"; out_dir.mkdir(parents=True, exist_ok=True)
    fh = open(out_dir / "log.txt", "w")
    case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name, load_demo=resume)
    R.log(f"[case] {task_type}/{case_name}: {case.task_line} | switch_steps={switch} resume={resume}", fh)
    env = R.make_env(case, use_camera_obs=want_video); env.reset()
    if case.init_state is not None: R.apply_state(env, case.init_state)
    if not hasattr(env, "_state_progress"): env._state_progress = {o: 0 for o in case.goal}
    frames = []
    scorer = DualScorer(env, case.goal)
    budget = {"end": 10**9}
    def on_step(ex):
        if want_video and ex.t % 3 == 0: frames.append(R.to_image(ex.obs["agentview_image"]))
        if ex.t >= budget["end"]: ex.cancel_flag = True
    ex = ScriptedExecutor(env, case.goal, on_step=on_step, scorer=scorer)
    ex.hold(15, -1.0, "settle")                       # 官方 num_steps_wait=15
    site_names = set(env.sim.model.site_names)
    n_seg = case.n_steps
    by_step = {}
    for obj, acts in case.goal.items():
        for act, stp in zip(acts, case.goal_steps[obj]): by_step.setdefault(stp, []).append((obj, act))
    seg_log = []; t_wall0 = time.time(); forced_total = 0
    for seg in range(n_seg):
        seg_start = ex.t; budget["end"] = seg_start + switch; ex.cancel_flag = False
        before = scorer.last[2]
        for obj, act in by_step.get(seg, []):
            if ex.cancel_flag: break
            rs = execute_goal_state(ex, obj, act, site_names, log=lambda m: R.log(m, fh))
            for r in rs:
                R.log(f"[seg {seg}] {r.name}: ok={r.ok} ({r.reason}) steps={r.steps} cancelled={r.cancelled}", fh)
        ex.cancel_flag = False
        # 用完本段预算（官方：策略持续运行直到切换；这里保持静止）
        remain = budget["end"] - ex.t
        if remain > 0: ex.hold(remain, ex.gripper, "idle")
        n_o, a_o, n_r, a_r = scorer.last
        seg_log.append({"seg": seg, "desc": case.steps[seg] if seg < len(case.steps) else "", "steps_used": ex.t - seg_start,
                        "repaired_gain": n_r - before, "original": n_o, "repaired": n_r})
        R.log(f"[seg {seg}] '{case.steps[seg] if seg < len(case.steps) else ''}' done -> original {n_o}/{case.n_goals} repaired {n_r}/{case.n_goals}", fh)
        if resume and seg + 1 < n_seg and case.demo_states is not None and seg + 1 < len(case.step_ranges):
            idx = case.step_ranges[seg + 1][0]
            R.apply_state(env, case.demo_states[idx]); env.skip_pick_quat_once = True
            ex.gripper = -1.0; ex.held = None
            forced_total += scorer.force_progress(case.goal, case.goal_steps, seg + 1)
            R.log(f"[resume] -> demo frame {idx} (start of step {seg+1}); forced completions so far {forced_total}", fh)
    n_o, a_o, n_r, a_r = scorer.last
    summary = {"task": f"{task_type}/{case_name}", "protocol": f"original_s{switch}{'_resume' if resume else ''}", "n_goals": case.n_goals,
               "original_done": int(n_o), "original_all": bool(a_o), "repaired_done": int(n_r), "repaired_all": bool(a_r),
               "forced_by_resume": forced_total, "total_steps": ex.t, "sim_time": round(float(env.sim.data.time), 1),
               "wall": round(time.time() - t_wall0, 1), "segments": seg_log}
    R.log(f"[result] original {n_o}/{case.n_goals} all={a_o} | repaired {n_r}/{case.n_goals} all={a_r} | forced={forced_total} steps={ex.t} sim={env.sim.data.time:.1f}s", fh)
    json.dump(summary | {"steps": [s.__dict__ for s in ex.log]}, open(out_dir / "result.json", "w"), indent=1)
    if want_video and frames: imageio.mimsave(out_dir / "rollout.mp4", frames, fps=10)
    env.close(); fh.close()
    return summary


if __name__ == "__main__":
    out = []
    for a in args:
        tt, cn = a.split("/")
        try: out.append(run_case(tt, cn))
        except Exception as e:
            import traceback; traceback.print_exc(); out.append({"task": a, "error": repr(e)[:200]})
    print("\n=== 汇总 ===")
    for s in out:
        if "error" in s: print(f"  {s['task']}: ERROR {s['error']}"); continue
        print(f"  {s['task']:28s} {s['protocol']:22s} original {s['original_done']}/{s['n_goals']} {'✅' if s['original_all'] else '❌'} | repaired {s['repaired_done']}/{s['n_goals']} {'✅' if s['repaired_all'] else '❌'} | forced={s['forced_by_resume']} steps={s['total_steps']}")
    (R.RUNS_ROOT / tag).mkdir(parents=True, exist_ok=True); json.dump(out, open(R.RUNS_ROOT / tag / "summary.json", "w"), indent=1)
