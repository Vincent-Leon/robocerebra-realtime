"""case1：按任务把三个盒装食品从开口送入白色储物盒（底部 / 右侧 / 左侧），v5 计分检查。用法: python x_cubby_test.py [reps=2] [--video]"""
import sys
import numpy as np
import imageio.v2 as imageio
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
reps = int(dict(a.split("=") for a in sys.argv[1:] if "=" in a).get("reps", 2)); video = "--video" in sys.argv
case = R.load_case("Ideal", R.BENCH_ROOT / "Ideal" / "case1", load_demo=False)
seq = [("cream_cheese_1", "white_storage_box_1_bottom_side"), ("popcorn_1", "white_storage_box_1_right_side"), ("butter_1", "white_storage_box_1_left_side")]
for rep in range(reps):
    env = R.make_env(case, use_camera_obs=video); env.reset(); R.apply_state(env, case.init_state)
    sc = DualScorer(env, case.goal); frames = []
    def on_step(ex):
        if video and ex.t % 3 == 0: frames.append(R.to_image(ex.obs["agentview_image"]))
    ex = ScriptedExecutor(env, case.goal, on_step=on_step, scorer=sc); ex.hold(15, -1.0, "settle")
    out = []
    for o, r in seq:
        ex._dbg = {}; a = ex.pick(o); b = ex.place(r) if a.ok else None
        if b is not None and not b.ok: print("      dbg", o, ex._dbg, flush=True)
        out.append(f"{o}: pick={'OK' if a.ok else 'FAIL '+a.reason[:30]} place={'-' if b is None else ('OK' if b.ok else 'FAIL '+b.reason[:40])} pos={np.round(ex.obj_pos(o), 3).tolist()} steps={a.steps + (b.steps if b else 0)}")
    print(f"rep={rep} repaired={sc.last[2]}/{sc.n_goals} original={sc.last[0]}  " + " || ".join(out), flush=True)
    if video and frames: imageio.mimsave(R.RUNS_ROOT / "skilltest" / f"cubby_rep{rep}.mp4", frames, fps=15)
    env.close()
# 放入后再取出、放回桌面（E1 恢复路径）
env = R.make_env(case, use_camera_obs=False); env.reset(); R.apply_state(env, case.init_state)
sc = DualScorer(env, case.goal); ex = ScriptedExecutor(env, case.goal, scorer=sc); ex.hold(15, -1.0, "settle")
rs = [ex.pick("butter_1"), ex.place("white_storage_box_1_left_side"), ex.pick("butter_1"), ex.place("coffee_table_table_region")]
print("place-then-retrieve:", " | ".join(f"{r.name}:{'OK' if r.ok else 'FAIL '+r.reason[:40]}" for r in rs), "butter", np.round(ex.obj_pos("butter_1"), 3).tolist())
