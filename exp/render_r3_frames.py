"""第三轮群发报告用的仿真画面（notes/figs_r3/frames/*.png）：用自定义视角（改写 galleryview 相机位姿）渲染特写。
  slip_hold / slip_drop：r2b case10 失败局，碗被切向夹持抬起、随后滑落（由 states.npz 还原）；bowl_after：r3 同一机位，抽象取物后碗被夹持；
  carry_off / carry_on：case6 白色柜子中层抽屉以抽象技能拉开后，内容物不随动（黄油被弹出）与随动；
  demo_grasp：人类演示中抓起同一块黄油的时刻（抽屉全开、位置与随动一致）；
  abstract_pick：r3 抽象抽屉取物结束时（黄油在两指之间）。
用法: python render_r3_frames.py [名称 ...]（默认全部）
"""
import sys, json
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
import imageio.v2 as imageio

OUT = R.PROJECT_ROOT / "notes" / "figs_r3" / "frames"; OUT.mkdir(parents=True, exist_ok=True)
W, H = 960, 720


def look_at_quat(pos, target, up=(0.0, 0.0, 1.0)):
    """MuJoCo 相机沿自身 -z 看、+y 朝上：返回 (w, x, y, z)。"""
    pos, target, up = map(lambda v: np.asarray(v, float), (pos, target, up))
    z = pos - target; z /= np.linalg.norm(z)
    x = np.cross(up, z); x /= np.linalg.norm(x); y = np.cross(z, x)
    Rm = np.stack([x, y, z], axis=1)
    t = np.trace(Rm)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2; w = 0.25 * s
        qx = (Rm[2, 1] - Rm[1, 2]) / s; qy = (Rm[0, 2] - Rm[2, 0]) / s; qz = (Rm[1, 0] - Rm[0, 1]) / s
    else:
        i = int(np.argmax(np.diag(Rm)))
        if i == 0:
            s = np.sqrt(1.0 + Rm[0, 0] - Rm[1, 1] - Rm[2, 2]) * 2; w = (Rm[2, 1] - Rm[1, 2]) / s; qx = 0.25 * s; qy = (Rm[0, 1] + Rm[1, 0]) / s; qz = (Rm[0, 2] + Rm[2, 0]) / s
        elif i == 1:
            s = np.sqrt(1.0 + Rm[1, 1] - Rm[0, 0] - Rm[2, 2]) * 2; w = (Rm[0, 2] - Rm[2, 0]) / s; qx = (Rm[0, 1] + Rm[1, 0]) / s; qy = 0.25 * s; qz = (Rm[1, 2] + Rm[2, 1]) / s
        else:
            s = np.sqrt(1.0 + Rm[2, 2] - Rm[0, 0] - Rm[1, 1]) * 2; w = (Rm[1, 0] - Rm[0, 1]) / s; qx = (Rm[0, 2] + Rm[2, 0]) / s; qy = (Rm[1, 2] + Rm[2, 1]) / s; qz = 0.25 * s
    q = np.array([w, qx, qy, qz]); return q / np.linalg.norm(q)


def shot(env, name, pos, target, fovy=40.0):
    m = env.sim.model; cid = m.camera_name2id("galleryview")
    m.cam_pos[cid] = pos; m.cam_quat[cid] = look_at_quat(pos, target); m.cam_fovy[cid] = fovy
    env.sim.forward()
    img = env.sim.render(camera_name="galleryview", width=W, height=H)[::-1]
    imageio.imwrite(OUT / f"{name}.png", img); print("saved", OUT / f"{name}.png")


def case(tt, cn, demo=False):
    return R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=demo)


def from_states(ep_dir, step, name, pos, target):
    ep = json.load(open(f"{ep_dir}/episode.json")); tt, cn = ep["case"].split("/")
    z = np.load(f"{ep_dir}/states.npz"); steps = list(z["steps"])
    env = R.make_env(case(tt, cn), use_camera_obs=True); env.reset()
    env.sim.set_state_from_flattened(z["states"][steps.index(step)]); env.sim.forward()
    shot(env, name, pos, target); env.close()


CAM_C10 = ((0.22, -0.05, 0.74), (0.0, -0.40, 0.67))        # case10 木柜上层抽屉（抽屉沿 +y 拉出）：侧前方低机位，能看清两指在碗沿上的位置
CAM_C6 = ((0.30, 0.10, 0.86), (0.0, 0.40, 0.55))           # case6 白色柜子中层抽屉（抽屉沿 −y 拉出）
want = set(sys.argv[1:])

if not want or "slip" in want:  # noqa
    d = R.RUNS_ROOT / "llm_l20_r2b" / "Memory_Exploration_case10" / "noevent_fastshared_text_s1"
    from_states(d, 305, "slip_hold", *CAM_C10)
    from_states(d, 314, "slip_drop", *CAM_C10)
    c = case("Memory_Exploration", "case10")                    # r3：同一机位，抽象取物后碗被前沿径向夹持
    env = R.make_env(c, use_camera_obs=True); env.reset()
    if c.init_state is not None: R.apply_state(env, c.init_state)
    ex = ScriptedExecutor(env, c.goal, scorer=DualScorer(env, c.goal)); ex.hold(15, -1.0, "settle")
    ex.open_drawer("wooden_cabinet_1_top_region"); r = ex.pick("white_bowl_1"); print("bowl pick:", r.ok, r.reason)
    ex.hold(10, 1.0, "hold"); shot(env, "bowl_after", (0.24, -0.02, 0.80), (0.0, -0.40, 0.72)); env.close()

if not want or "carry" in want:
    for carry in (0, 1):
        c = case("Memory_Exploration", "case6")
        env = R.make_env(c, use_camera_obs=True); env.reset()
        if c.init_state is not None: R.apply_state(env, c.init_state)
        ex = ScriptedExecutor(env, c.goal, scorer=DualScorer(env, c.goal)); ex.DRAWER_CARRY = bool(carry)
        ex.hold(15, -1.0, "settle"); ex.open_drawer("white_cabinet_1_middle_region"); ex.hold(20, -1.0, "settle")
        print("carry", carry, "butter", np.round(ex.obj_pos("butter_1"), 3).tolist())
        if carry:
            shot(env, "carry_on", *CAM_C6)
            ex.PICK_RETRY = 0; r = ex.pick("butter_1"); print("abstract pick:", r.ok, r.reason)
            shot(env, "abstract_pick", (0.32, 0.05, 0.98), (0.0, 0.38, 0.66))
        else:
            shot(env, "carry_off", (0.45, 0.25, 1.05), (-0.05, 0.20, 0.50), fovy=50.0)
        env.close()

if not want or "demo" in want:
    c = case("Memory_Exploration", "case6", demo=True)
    env = R.make_env(c, use_camera_obs=True); env.reset()
    env.sim.set_state_from_flattened(c.demo_states[1078]); env.sim.forward()
    shot(env, "demo_grasp", *CAM_C6); env.close()
