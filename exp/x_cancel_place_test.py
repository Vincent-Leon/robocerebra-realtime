"""确定性复现：拿起黄油 → 放入储物盒途中第 K 步取消 → 放回桌面。比较是否越过起点障碍（CLEAR_LOCAL_OBSTACLE）。
用法: python x_cancel_place_test.py K1,K2,... [clear=0|1|both] [reps=N]"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from scoring import RepairedScorer

Ks = [int(k) for k in (sys.argv[1] if len(sys.argv) > 1 else "20,35,50,65,80").split(",")]
kw = dict(a.split("=") for a in sys.argv[2:] if "=" in a)
clears = {"0": [False], "1": [True]}.get(kw.get("clear", "both"), [False, True]); reps = int(kw.get("reps", 1))
case = R.load_case("Ideal", R.BENCH_ROOT / "Ideal" / "case1", load_demo=False)
for clear in clears:
    for K in Ks:
        for rep in range(reps):
            env = R.make_env(case, use_camera_obs=False); env.reset(); R.apply_state(env, case.init_state)
            cnt = {"n": None, "trace": False}; trace = []
            def on_step(ex):
                if cnt["n"] is not None:
                    cnt["n"] += 1
                    if cnt["n"] >= K: ex.cancel_flag = True
                if cnt["trace"]: trace.append((ex.t, np.round(ex.eef(), 3).tolist(), np.round(ex.obj_pos("butter_1"), 3).tolist()))
            ex = ScriptedExecutor(env, case.goal, on_step=on_step, scorer=RepairedScorer(env, case.goal))
            ex.CLEAR_LOCAL_OBSTACLE = clear
            ex.hold(15, -1.0, "settle")
            r1 = ex.pick("butter_1")
            cnt["n"] = 0; r2 = ex.place("white_storage_box_1_bottom_side"); cnt["n"] = None; ex.cancel_flag = False
            eef = np.round(ex.eef(), 3).tolist(); bpos = np.round(ex.obj_pos("butter_1"), 3).tolist()
            cnt["trace"] = True; r3 = ex.place("coffee_table_table_region")
            print(f"clear={clear} K={K:3d} rep={rep} box_place: {r2.reason[:30]:30s} eef_after_cancel={eef} butter={bpos} -> table ok={r3.ok} {r3.reason[:60]}", flush=True)
            if not r3.ok:
                for t, e, b in trace[::6]: print(f"      t={t} eef={e} butter={b}")
            env.close()
