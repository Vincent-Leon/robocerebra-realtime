"""诊断：Memory_Execution/case5 拿起布丁后 place_on_object(plate_1) 搬运停滞的逐步轨迹。
打印放置技能的搬运高度计算、每 10 步末端位置、停滞点的接触与关节余量。
用法: python x_case5_trace.py [place|pour]
"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor, CLOSE


def main(skill="place"):
    case = R.load_case("Memory_Execution", R.BENCH_ROOT / "Memory_Execution" / "case5")
    env = R.make_env(case, use_camera_obs=False); env.reset()
    ex = ScriptedExecutor(env, case.goal)
    ex.hold(15, -1.0, "settle")
    r = ex.pick("chocolate_pudding_1")
    print(f"pick ok={r.ok} eef={np.round(ex.eef(), 3)} held_drop={ex.held_drop:.3f} zoff={ex.zoff:.3f} base={np.round(ex.base_xy(), 3)}")
    tgt = ex.obj_pos("plate_1"); top = ex.obj_zrange("plate_1")[1]
    print(f"plate={np.round(tgt, 3)} plate_top={top:.3f} dist_base={np.linalg.norm(tgt[:2] - ex.base_xy()):.3f} local_top(eef)={ex.local_top_z(ex.eef()[:2])}")
    extra = 0.05 if skill == "pour" else 0.0
    print(f"safe_z={ex.safe_z(top + ex.held_drop + extra):.3f} safe_z_for={ex.safe_z_for(tgt, top + ex.held_drop + extra):.3f} Z_SAFE_MAX={ex.Z_SAFE_MAX:.3f}")
    # 记录 move_to 的每次调用与停滞
    orig = ex.move_to
    def traced(target, gripper, sk, *a, **k):
        ok = orig(target, gripper, sk, *a, **k)
        print(f"   move_to {np.round(target, 3)} -> ok={ok} stalled={ex.last_stalled} eef={np.round(ex.eef(), 3)} t={ex.t}")
        if ex.last_stalled:
            m = env.sim.model; d = env.sim.data
            jn = [f"robot0_joint{i}" for i in range(1, 8)]
            margins = []
            for n in jn:
                j = m.joint_name2id(n); lo, hi = m.jnt_range[j]; q = d.qpos[m.jnt_qposadr[j]]
                margins.append(f"{n[-1]}:{q:+.2f}[{lo:+.2f},{hi:+.2f}]")
            print("      关节:", " ".join(margins))
            print("      手持物接触:", ex.contact_bodies())
            robot_contacts = set()
            for i in range(d.ncon):
                c = d.contact[i]; b1 = m.body_id2name(m.geom_bodyid[c.geom1]); b2 = m.body_id2name(m.geom_bodyid[c.geom2])
                if b1.startswith("robot0") or b2.startswith("robot0") or b1.startswith("gripper0") or b2.startswith("gripper0"):
                    robot_contacts.add(f"{b1}<->{b2}")
            print("      机械臂接触:", sorted(robot_contacts))
        return ok
    ex.move_to = traced
    r = ex.pour("plate_1") if skill == "pour" else ex.place_on_object("plate_1")
    print(f"{skill}: ok={r.ok} reason={r.reason}")
    env.close()


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["place"]))
