"""在实时 episode 的给定步，比较两指垫连线（手指闭合方向）与“物体中心→末端”的径向方向，并列出各指垫接触到的物体几何。
用法: python x_grasp_axis.py <episode 目录> <物体> <步> [<步> ...]"""
import sys, json
import numpy as np
import rc_env as R
ep_dir, obj = sys.argv[1], sys.argv[2]; qs = [int(s) for s in sys.argv[3:]]
ep = json.load(open(f"{ep_dir}/episode.json")); tt, cn = ep["case"].split("/")
z = np.load(f"{ep_dir}/states.npz"); steps = list(z["steps"])
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
env = R.make_env(case, use_camera_obs=False); env.reset()
m = env.sim.model; d = env.sim.data; bid = env.obj_body_id[obj]
g1, g2 = m.geom_name2id("gripper0_finger1_pad_collision"), m.geom_name2id("gripper0_finger2_pad_collision")
for s in qs:
    env.sim.set_state_from_flattened(z["states"][steps.index(s)]); env.sim.forward()
    o = env._get_observations(force_update=True); p, e = np.array(o[f"{obj}_pos"]), np.array(o["robot0_eef_pos"])
    close = d.geom_xpos[g2] - d.geom_xpos[g1]; close_xy = close[:2] / (np.linalg.norm(close[:2]) + 1e-9)
    rad = (e - p)[:2]; rad_n = rad / (np.linalg.norm(rad) + 1e-9)
    ang = np.degrees(np.arccos(np.clip(abs(float(np.dot(close_xy, rad_n))), 0, 1)))
    hits = []
    for i in range(d.ncon):
        c = d.contact[i]
        for a, b in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
            if a in (g1, g2) and m.geom_bodyid[b] == bid:
                gp = d.geom_xpos[b] - p; hits.append(f"{'pad1' if a == g1 else 'pad2'}->{m.geom_id2name(b)} r={np.linalg.norm(gp[:2]):.3f} dz={gp[2]:.3f}")
    print(f"step {s}: eef-obj={np.round(e - p, 3).tolist()} |radial|={np.linalg.norm(rad):.3f} pad gap={np.linalg.norm(close):.3f} "
          f"angle(closing, radial)={ang:.0f}deg  contacts: {hits}")
env.close()
