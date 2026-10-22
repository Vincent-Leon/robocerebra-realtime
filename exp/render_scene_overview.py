"""任务场景总览图（notes/figs_r3/frames/）：自定义广角视角渲染初始场景，按相机内参把物体 / 装置的三维位置投影到图像上做标注；
另渲染模型实际收到的 agentview 图像（放大到 512×512，模型收到 256×256）。
用法: python render_scene_overview.py <case 类型/名称> <输出名> [抽屉区域，渲染前先拉开]
"""
import sys, json
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
import imageio.v2 as imageio
from render_r3_frames import look_at_quat, OUT

(tt, cn), name = sys.argv[1].split("/"), sys.argv[2]; drawer = sys.argv[3] if len(sys.argv) > 3 else None
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=True); env.reset()
if case.init_state is not None: R.apply_state(env, case.init_state)
ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal)); ex.hold(15, -1.0, "settle")
if drawer: ex.open_drawer(drawer); ex.hold(10, -1.0, "settle")
m = env.sim.model; d = env.sim.data
W, H = 1280, 800
pos, tgt, fovy = np.array([1.05, 0.0, 1.45]), np.array([-0.05, 0.0, 0.45]), 52.0
cid = m.camera_name2id("galleryview"); m.cam_pos[cid] = pos; m.cam_quat[cid] = look_at_quat(pos, tgt); m.cam_fovy[cid] = fovy; env.sim.forward()
img = env.sim.render(camera_name="galleryview", width=W, height=H)[::-1]
Rc = d.cam_xmat[cid].reshape(3, 3); pc = d.cam_xpos[cid]; f = (H / 2) / np.tan(np.radians(fovy) / 2)
def proj(p):
    q = Rc.T @ (np.asarray(p) - pc); zc = -q[2]
    return (W / 2 + f * q[0] / zc, H / 2 - f * q[1] / zc)
pts = {o: proj(ex.obj_pos(o)) for o in env.objects_dict}
for fx in env.fixtures_dict:
    try: pts[fx] = proj(d.body_xpos[m.body_name2id(fx)])
    except Exception: pass
for s in m.site_names:
    if s.endswith(("cook_region",)): pts[s] = proj(d.site_xpos[m.site_name2id(s)])
pts["robot0_base"] = proj(d.body_xpos[m.body_name2id("robot0_base")] + np.array([0, 0, 0.35]))
imageio.imwrite(OUT / f"{name}_wide.png", img)
json.dump({k: [float(v[0]), float(v[1])] for k, v in pts.items()}, open(OUT / f"{name}_wide_pts.json", "w"), indent=1, ensure_ascii=False)
av = env.sim.render(camera_name="agentview", width=512, height=512)[::-1]
imageio.imwrite(OUT / f"{name}_agentview.png", av)
print("saved", OUT / f"{name}_wide.png", OUT / f"{name}_agentview.png"); print({k: [round(v[0]), round(v[1])] for k, v in pts.items()})
env.close()
