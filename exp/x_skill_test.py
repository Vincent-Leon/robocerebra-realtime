"""单技能靶向测试：在某任务（可从演示第 N 帧状态起步）上执行一个技能，录视频并打印末端/夹爪轨迹摘要。
用法: python x_skill_test.py task_type case skill arg1 [arg2] [--frame=N] [--tag=NAME]
例:   python x_skill_test.py Ideal case3 pick wine_bottle_1
      python x_skill_test.py Ideal case6 open_drawer short_cabinet_1_middle_region
"""
import sys, json
import numpy as np
import imageio.v2 as imageio
import rc_env as R
from skills import ScriptedExecutor
from scoring import RepairedScorer

args = [a for a in sys.argv[1:] if not a.startswith("--")]
task_type, case_name, skill, sargs = args[0], args[1], args[2], args[3:]
frame = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--frame=")), None)
tag = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tag=")), f"{skill}_{'_'.join(sargs)}")
out = R.RUNS_ROOT / "skilltest" / f"{task_type}_{case_name}_{tag}"; out.mkdir(parents=True, exist_ok=True)
case = R.load_case(task_type, R.BENCH_ROOT / ("Ideal" if task_type in R.USE_IDEAL_FILES else task_type) / case_name, load_demo=frame is not None)
env = R.make_env(case, use_camera_obs=True); env.reset()
R.apply_state(env, case.demo_states[frame] if frame is not None else case.init_state)
frames = []; trace = []
def on_step(ex):
    if ex.t % 2 == 0: frames.append(np.concatenate([R.to_image(ex.obs["agentview_image"]), R.to_image(ex.obs["robot0_eye_in_hand_image"])], axis=1))
    g = ex.obs["robot0_gripper_qpos"]; trace.append((ex.t, ex.log[-1].skill, list(np.round(ex.obs["robot0_eef_pos"], 3)), round(float(g[0] - g[1]), 3), round(ex.eef_yaw(), 2)))
sc = RepairedScorer(env, case.goal)
ex = ScriptedExecutor(env, case.goal, on_step=on_step, scorer=sc)
for a in sys.argv:
    if a.startswith("--grasp_dz="):          # 覆盖第一个参数物体类别的抓取 z 偏移（测试用）
        otype = sargs[0].rsplit("_", 1)[0]; ex.GRASP_OFFSETS = dict(ex.GRASP_OFFSETS); ex.GRASP_OFFSETS[otype] = (0.0, 0.0, float(a.split("=")[1]))
    if a.startswith("--kp="): ex.kp = float(a.split("=")[1])
ex.hold(15, -1.0, "settle")
res = getattr(ex, skill)(*sargs)
print(f"[{task_type}/{case_name}] {skill}{tuple(sargs)} -> ok={res.ok} reason={res.reason} steps={res.steps} done={res.n_done_before}->{res.n_done_after}")
# 轨迹摘要：每 10 步一行 + 夹爪宽度变化点
prev_g = None
for t, sk, eef, g, yaw in trace:
    if t % 10 == 0 or (prev_g is not None and abs(g - prev_g) > 0.01):
        print(f"   t={t:4d} {sk[:28]:28s} eef={eef} grip={g:.3f} yaw={yaw:+.2f}")
    prev_g = g
if sargs and sargs[0] in env.objects_dict:
    o = sargs[0]; print(f"   final {o} pos={np.round(ex.obj_pos(o),3)} eef={np.round(ex.eef(),3)} dist={np.linalg.norm(ex.obj_pos(o)-ex.eef()):.3f} rbound={ex.obj_rbound(o):.3f} grasp_point={np.round(ex.grasp_point(o),3)}")
imageio.mimsave(out / "video.mp4", frames, fps=10); json.dump({"ok": bool(res.ok), "reason": res.reason, "steps": res.steps, "trace": trace}, open(out / "trace.json", "w"))
print(f"   video: {out/'video.mp4'}")
env.close()
