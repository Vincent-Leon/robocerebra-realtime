"""重建实时 episode 中某一时刻快分支（Jev，CHOOSE 模式）实际收到的提示文本（不含图像），用于报告展示。
用法: python x_prompt_example.py <episode 目录> <时刻 s（相对开局）>"""
import sys, json
from types import SimpleNamespace
import numpy as np
import rc_env as R
from skills import ScriptedExecutor
from run_gt_plan import DualScorer
from shared_prompt import SharedPromptBuilder, static_block, SHARED_SYSTEM
from jev_fast import candidate_actions, candidates_text
ep_dir, t_q = sys.argv[1], float(sys.argv[2])
ep = json.load(open(f"{ep_dir}/episode.json")); tl = json.load(open(f"{ep_dir}/timeline.json"))["events"]; t0 = tl[0]["sim"]
tt, cn = ep["case"].split("/")
case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn, load_demo=False)
z = np.load(f"{ep_dir}/states.npz"); steps = list(z["steps"]); step = int(round((t_q + t0) * 20))
env = R.make_env(case, use_camera_obs=False); env.reset()
env.sim.set_state_from_flattened(z["states"][steps.index(min(steps, key=lambda s: abs(s - step)))]); env.sim.forward()
o = env._get_observations(force_update=True); ex = ScriptedExecutor(env, case.goal, scorer=DualScorer(env, case.goal))
m = env.sim.model
objects, fixtures, regions = list(env.objects_dict), list(env.fixtures_dict), list(env.regions)          # r3 的区域列表（不含灶台站点）
drawers = [r for r in regions if env.object_sites_dict.get(r) is not None and (env.object_sites_dict[r].joints or [])]
centers = {r: list(map(float, env.sim.data.site_xpos[m.site_name2id(r)])) for r in regions}
hidden = [ob for ob in objects if (dr := ex.containing_drawer(ob)) is not None and ex.drawer_geometry(dr)[5] < 0.3]
held = next((ob for ob in objects if ex.checker._in_hand(ob)), None)
snap = SimpleNamespace(sim_time=t_q + t0, version=step, held=held, gripper=float(o["robot0_gripper_qpos"][0] < 0.035) * 2 - 1,
                       objects={ob: list(map(float, o[f"{ob}_pos"])) for ob in objects}, drawers={r: round(float(ex.drawer_geometry(r)[5]), 2) for r in drawers},
                       messages=[], hidden=hidden, agentview=None)
hist = [h for h in ep["history"] if h["t_sim"] <= t_q]
adv = [c for c in ep["calls"] if c.get("mode") == "ADVISE" and c.get("advice") and c["t_obs"] + c["latency"] <= t_q]
extra = ""
if adv:
    a = adv[-1]; extra = "ADVICE from the deliberate planner (given at sim time %.1fs; it was asked because: %s): %s" % (a["t_obs"], a["reason"][:100], a["advice"])
cands = candidate_actions(snap, objects, fixtures, regions, drawers)
b = SharedPromptBuilder(static_block(case.task_line, objects, fixtures, regions, centers, drawers), use_image=False)
msgs = b.messages(snap, objects, hist, "CHOOSE", extra=(extra + "\n\n" + candidates_text(cands)).strip())
print("=== SYSTEM ===\n" + msgs[0]["content"] + "\n=== USER ===")
for part in msgs[1]["content"]:
    if part["type"] == "text": print(part["text"])
