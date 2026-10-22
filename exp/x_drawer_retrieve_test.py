"""case6：打开中层抽屉 → 拿起黄油 → 放入抽屉（沿拉出方向外移 DRAWER_FRONT_FRAC × 半深）→ 再取出 → 放到盘子上。
用法: python x_drawer_retrieve_test.py 0.0,0.3,0.4,0.5 [reps=2]"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from scoring import RepairedScorer
fracs = [float(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "0.0,0.4").split(",")]
reps = int(dict(a.split("=") for a in sys.argv[2:] if "=" in a).get("reps", 2))
case = R.load_case("Ideal", R.BENCH_ROOT / "Ideal" / "case6", load_demo=False)
D = "short_cabinet_1_middle_region"
for fr in fracs:
    for rep in range(reps):
        env = R.make_env(case, use_camera_obs=False); env.reset(); R.apply_state(env, case.init_state)
        sc = RepairedScorer(env, case.goal)
        ex = ScriptedExecutor(env, case.goal, scorer=sc); ex.DRAWER_FRONT_FRAC = fr
        ex.hold(15, -1.0, "settle")
        r = [ex.open_drawer(D), ex.pick("butter_1"), ex.place(D)]
        in_d = sc.in_relaxed("butter_1", D); pos = np.round(ex.obj_pos("butter_1"), 3).tolist()
        r += [ex.pick("butter_1"), ex.place("plate_1") if False else ex.place_on_object("plate_1")]
        print(f"frac={fr} rep={rep} " + " | ".join(f"{x.name.split('(')[0]}:{'OK' if x.ok else 'FAIL '+x.reason[:40]}" for x in r) + f" | in_drawer_after_place={in_d} pos={pos}", flush=True)
        env.close()
