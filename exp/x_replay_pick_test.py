"""从实时 episode 保存的逐步状态中恢复某一步，再离线执行一次 pick，复现并检验抓取问题。
用法: python x_replay_pick_test.py <episode 目录> <step> <物体>"""
import sys, json
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
ep_dir, step, obj = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ep = json.load(open(f"{ep_dir}/episode.json")); tt, cn = ep["case"].split("/")
z = np.load(f"{ep_dir}/states.npz"); i = int(np.argmin(np.abs(z["steps"] - step)))
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
for retry in (0, 1):
    env = R.make_env(case, use_camera_obs=False); env.reset()
    env.sim.set_state_from_flattened(z["states"][i]); env.sim.forward()
    ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.PICK_RETRY = retry
    ex.hold(2, -1.0, "settle")
    r = ex.pick(obj)
    print(f"PICK_RETRY={retry}: ok={r.ok} reason={r.reason[:80]} steps={r.steps} obj={np.round(ex.obj_pos(obj), 3).tolist()} held={ex.held}")
    env.close()
