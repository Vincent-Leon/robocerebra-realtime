"""GT 计划 × 脚本化执行器（"oracle 切换"变体：子目标完成即切换，无 150 步时间片）。
双计分器：原始（官方监控器）与修复版（exp/scoring.py）同时记录；技能反馈用修复版。
用法: python run_gt_plan.py <task_type/case> [<task_type/case> ...] [--video] [--tag NAME]
"""
import sys, json, time
import numpy as np
import imageio.v2 as imageio
import rc_env as R
from skills import ScriptedExecutor
from scoring import OriginalScorer, RepairedScorer

args = [a for a in sys.argv[1:] if not a.startswith("--")]
want_video = "--video" in sys.argv
tag = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tag=")), "gtplan")


class DualScorer:
    def __init__(self, env, goal):
        self.orig = OriginalScorer(env, goal); self.rep = RepairedScorer(env, goal)
        self.n_goals = self.rep.n_goals; self.excluded = 0
    def precomplete(self, counts):
        """描述错位：把各物体链开头的 k 个子目标记为已完成（两个计分器都记），并记录扣除数。"""
        self.rep.precomplete(counts)
        env = self.orig.env; sp = getattr(env, "_state_progress", None)
        if sp is None: env._state_progress = sp = {}
        for obj in self.rep.goal: sp.setdefault(obj, 0)
        for obj, k in (counts or {}).items(): sp[obj] = max(sp.get(obj, 0), int(k))
        env.skip_pick_quat_once = True
        self.excluded = int(sum(int(v) for v in (counts or {}).values()))
    def update(self):
        _, n_o, a_o = self.orig.update(); comp, n_r, a_r = self.rep.update()
        self.last = (n_o, a_o, n_r, a_r)
        return comp, n_r, a_r


def run_case(task_type, case_name):
    out_dir = R.RUNS_ROOT / tag / f"{task_type}_{case_name}"; out_dir.mkdir(parents=True, exist_ok=True)
    fh = open(out_dir / "log.txt", "w")
    from rc_dynamics import RCDynamics, SHIFT_TYPES
    case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name, load_demo=task_type in SHIFT_TYPES)
    R.log(f"[case] {task_type}/{case_name}: {case.task_line}", fh)
    env = R.make_env(case, use_camera_obs=want_video); env.reset()
    if case.init_state is not None: R.apply_state(env, case.init_state)
    frames = []
    scorer = DualScorer(env, case.goal)
    dyn = RCDynamics(case, seed=0)                       # RoboCerebra 动态条件：描述错位（起始状态）/ 随机扰动（rc_dynamics.py）
    if dyn.apply_start(env, scorer): R.log(f"[dyn] 描述错位：从演示第 2 个子步开始，预先完成 {dyn.precompleted}", fh)
    def on_step(ex):
        if want_video and ex.t % 3 == 0: frames.append(R.to_image(ex.obs["agentview_image"]))
        dyn.tick(env, ex, scorer, ex.t, log_fn=lambda rec: R.log(f"[dyn] t={ex.t} {rec}", fh))
    ex = ScriptedExecutor(env, case.goal, on_step=on_step, scorer=scorer)
    dyn.sync_executor(ex)
    ex.hold(15, ex.gripper, "settle")
    plan = sorted([(stp, obj, act) for obj, acts in case.goal.items() for act, stp in zip(acts, case.goal_steps[obj]) if stp >= dyn.start_step], key=lambda x: x[0])
    R.log("[plan] " + " ; ".join(f"s{stp}:{act}" for stp, obj, act in plan), fh)
    results = []; t_wall0 = time.time()
    site_names = set(env.sim.model.site_names)
    table_region = next((r for r in env.regions if r.endswith("table_region")), None)
    def put_down_if_busy(target_obj=None):
        """r4：要拿的不是手中物体（或要开关、开灶）时，先把手中物体放回桌面。官方子目标在"倒入"后不一定有"放回"，
        标准计划逐条执行会一直拿着上一个物体（\"hand busy\"）；语言模型规划时会自己先放下。"""
        if ex.held is not None and ex.held != target_obj and table_region is not None:
            r0 = ex.place(table_region); results.append(r0)
            R.log(f"[skill] (auto) put down {r0.name}: ok={r0.ok} ({r0.reason})", fh)
    for stp, obj, act in plan:
        verb = act[0]; tgt = act[2] if len(act) > 2 else (act[1] if len(act) > 1 else None)
        if verb in ("pick", "in", "on", "pour"): put_down_if_busy(obj)
        elif verb in ("open", "close", "turnon"): put_down_if_busy(None)
        if verb == "pick":
            res = ex.pick(obj)
        elif verb in ("in", "on"):
            if ex.held != obj and ex.held is not None:
                R.log(f"[warn] s{stp}: 手中是 {ex.held}，目标物体是 {obj}", fh)
            if ex.held is None:
                r0 = ex.pick(obj); results.append(r0); R.log(f"[skill] s{stp} (auto) {r0.name}: ok={r0.ok} ({r0.reason}) steps={r0.steps}", fh)
                if not r0.ok:
                    ex.hold(5, -1.0, "recover"); ex.gripper = -1.0; ex.held = None; ex.go_home(-1.0, "recover")
                    R.log(f"[skip] s{stp} {act}: 抓取失败，跳过放置", fh); continue
            res = ex.place(tgt) if tgt in site_names else ex.place_on_object(tgt)
        elif verb == "pour":
            if ex.held is None:
                r0 = ex.pick(obj); results.append(r0); R.log(f"[skill] s{stp} (auto) {r0.name}: ok={r0.ok} ({r0.reason}) steps={r0.steps}", fh)
                if not r0.ok:
                    ex.hold(5, -1.0, "recover"); ex.gripper = -1.0; ex.held = None; ex.go_home(-1.0, "recover")
                    R.log(f"[skip] s{stp} {act}: 抓取失败，跳过倾倒", fh); continue
            res = ex.pour(tgt)
        elif verb == "open":
            if tgt in site_names: res = ex.open_drawer(tgt)
            else:
                from skills import SkillResult; res = SkillResult(f"open({tgt})", False, "door opening not implemented", 0, ex.n_done, ex.n_done)
        elif verb == "close":
            if tgt in site_names: res = ex.close_drawer(tgt)
            else:
                from skills import SkillResult; res = SkillResult(f"close({tgt})", False, "door closing not implemented", 0, ex.n_done, ex.n_done)
        elif verb == "turnon":
            res = ex.turnon(tgt)
        else:
            R.log(f"[skip] s{stp} {act}", fh); continue
        results.append(res)
        n_o, a_o, n_r, a_r = scorer.last
        R.log(f"[skill] s{stp} {res.name}: ok={res.ok} ({res.reason}) steps={res.steps} sim_t={env.sim.data.time:.1f}s  original={n_o}/{case.n_goals} repaired={n_r}/{case.n_goals}", fh)
        if not res.ok and verb == "pick":
            ex.hold(5, -1.0, "recover"); ex.gripper = -1.0; ex.held = None; ex.go_home(-1.0, "recover")
    n_o, a_o, n_r, a_r = scorer.last
    summary = {"task": f"{task_type}/{case_name}", "n_goals": case.n_goals, "excluded": dyn.excluded, "dynamics": dyn.log,
               "original_done": int(n_o), "original_all": bool(a_o),
               "repaired_done": int(n_r), "repaired_all": bool(a_r), "total_steps": ex.t, "sim_time": round(float(env.sim.data.time), 1),
               "wall": round(time.time() - t_wall0, 1), "skills": [{k: (bool(v) if isinstance(v, (bool, np.bool_)) else v) for k, v in r.__dict__.items()} for r in results]}
    R.log(f"[result] original {n_o}/{case.n_goals} all={a_o} | repaired {n_r}/{case.n_goals} all={a_r} | excluded={dyn.excluded} | steps={ex.t} sim={env.sim.data.time:.1f}s wall={summary['wall']}s", fh)
    summary["scorer_events"] = {"original": scorer.orig.events, "repaired": scorer.rep.events}
    for t_sim, what in scorer.rep.events: R.log(f"[repaired-event] sim={t_sim:.2f}s {what}", fh)
    json.dump(summary | {"steps": [s.__dict__ for s in ex.log]}, open(out_dir / "result.json", "w"), indent=1, default=str)
    if want_video and frames:
        imageio.mimsave(out_dir / "rollout.mp4", frames, fps=10)
    env.close(); fh.close()
    return summary


if __name__ == "__main__":
    summaries = []
    for a in args:
        tt, cn = a.split("/")
        try:
            summaries.append(run_case(tt, cn))
        except Exception as e:
            import traceback; traceback.print_exc()
            summaries.append({"task": a, "error": repr(e)[:200]})
    print("\n=== 汇总 ===")
    for s in summaries:
        if "error" in s: print(f"  {s['task']}: ERROR {s['error']}"); continue
        print(f"  {s['task']:28s} original {s['original_done']}/{s['n_goals']} {'✅' if s['original_all'] else '❌'} | repaired {s['repaired_done']}/{s['n_goals']} {'✅' if s['repaired_all'] else '❌'} | steps={s['total_steps']} sim={s['sim_time']}s")
    (R.RUNS_ROOT / tag).mkdir(parents=True, exist_ok=True)
    json.dump(summaries, open(R.RUNS_ROOT / tag / "summary.json", "w"), indent=1)
