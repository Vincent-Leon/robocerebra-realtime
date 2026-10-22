"""离线重算计分：用 episode 目录下保存的逐步仿真状态（states.npz）与时间线中的目标更新事件，
以**当前版本**的计分器重算原始 / 修复版得分与子目标完成时刻，写入 rescored.json。计分器改动后无需重跑实验。
用法: python rescore.py runs/llm/<task>/<tag> [...]   或   python rescore.py --all [--root=llm]
"""
import sys, json, glob, copy
from pathlib import Path
import numpy as np
import rc_env as R
from scoring import OriginalScorer, RepairedScorer


def rescore(ep_dir: Path):
    ep = json.load(open(ep_dir / "episode.json")); tl = json.load(open(ep_dir / "timeline.json"))
    st_f = ep_dir / "states.npz"
    if not st_f.exists(): return None
    d = np.load(st_f); states = d["states"]; steps = d["steps"]; t0 = float(d["sim_t0"][0])
    tt, cn = ep["case"].split("/")
    case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
    goal = copy.deepcopy(case.goal)
    # 目标更新（E1）：按事件发生的控制步应用
    updates = sorted([(e.get("step", 0), e["new_goal"]) for e in tl["events"] if e["type"] == "event_effect" and e.get("new_goal")], key=lambda x: x[0])
    env = R.make_env(case, use_camera_obs=False); env.reset()
    env._state_progress = {o: 0 for o in goal}
    orig = OriginalScorer(env, goal); rep = RepairedScorer(env, goal)
    from rc_dynamics import SHIFT_TYPES, shift_precomplete_counts
    excluded = 0
    if tt in SHIFT_TYPES:                                    # 描述错位：第 1 个子步的子目标预先完成并扣出分母（与运行时一致）
        counts = shift_precomplete_counts(case); rep.precomplete(counts)
        for o, k in counts.items(): env._state_progress[o] = max(env._state_progress.get(o, 0), k)
        env.skip_pick_quat_once = True; excluded = int(sum(counts.values()))
    ui = 0; n_o = n_r = 0; a_o = a_r = False
    for s, k in zip(states, steps):
        while ui < len(updates) and updates[ui][0] <= k:
            for obj, new_states in updates[ui][1].items():
                goal[obj] = [list(x) for x in new_states]
            rep.n_goals = sum(len(v) for v in goal.values()); ui += 1
            for o in goal:
                env._state_progress.setdefault(o, 0); rep._progress.setdefault(o, 0)
        env.sim.set_state_from_flattened(s); env.sim.forward()
        _, n_o, a_o = orig.update(); _, n_r, a_r = rep.update()
    env.close()
    out = {"scorer_version": "v6", "original": int(n_o), "original_all": bool(a_o), "repaired": int(n_r), "repaired_all": bool(a_r),
           "n_goals": int(rep.n_goals), "excluded": excluded, "subgoal_events": [(round(t - t0, 2), w) for t, w in rep.events], "n_states": int(len(states))}
    json.dump(out, open(ep_dir / "rescored.json", "w"), indent=1)
    return out


if __name__ == "__main__":
    dirs = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    if "--all" in sys.argv:
        root = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--root=")), "llm")
        dirs = [Path(p).parent for p in sorted(glob.glob(str(R.RUNS_ROOT / root / "*" / "*" / "states.npz")))]
    for d in dirs:
        r = rescore(d)
        print(d.name, "->", None if r is None else f"repaired {r['repaired']}/{r['n_goals']} all={r['repaired_all']} (orig {r['original']})", flush=True)
