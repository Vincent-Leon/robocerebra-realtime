"""网站示例视频：由 states.npz 回放渲染（不重新仿真），叠加时间、子目标进度、当前技能和模型事件（快分支决策、思考、建议、计划），输出 H.264 MP4、封面图和时间对应关系。
视频时间 = 仿真时间（每个控制步一帧，20 fps）。机位：以任务物体的中位位置和机器人底座为参照，从右前方斜上方看向桌面（改写 galleryview 相机）。
用法: python render_demo.py [示例 id ...]（默认 site_demos.json 中全部） [--out=../site/videos] [--size=768x576]
每局目录下要有 states.npz（结果同步时不拷，需从 H20 单独拷来）。
"""
import sys, json, textwrap, re
from pathlib import Path
import numpy as np
import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont
import rc_env as R
from analyze_events import parse

HERE = Path(__file__).resolve().parent
opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
want = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(opt.get("out", str(HERE.parent / "site" / "videos"))); OUT.mkdir(parents=True, exist_ok=True)
W, H = map(int, opt.get("size", "768x576").split("x"))
FPS, DT, HOLD = 20, 0.05, 2.0
MODEL = {"qwen3.8-27b": "Qwen3.8-27B", "qwen3-vl-32b": "Qwen3-VL-32B", "qwen3-vl-8b": "Qwen3-VL-8B", "qwen3-vl-4b": "Qwen3-VL-4B",
         "qwen3-vl-2b": "Qwen3-VL-2B", "deepseek-v4.1-flash": "DeepSeek-V4.1-Flash"}
MODE = {"fast_shared_jev": "Fast · Jev", "fast_shared_text": "Fast · Text", "fast_shared_think": "Slow · Think",
        "dual_shared_jev": "Dual · Plan", "dual_advice_jev": "Dual · Advice"}
CLOCK = {"wall": "wall clock", "token": "token clock", "paused": "paused clock"}
FONT_PATHS = ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]   # 要含 → ✓ ✗ ▶ 等符号（Helvetica 没有）


def font(size, bold=False):
    for p in FONT_PATHS:
        try: f = ImageFont.truetype(p, size)
        except Exception: continue
        if bold:
            for v in ("Semibold", "Bold"):
                try: f.set_variation_by_name(v); break
                except Exception: pass
        return f
    return ImageFont.load_default()


F1, F1B, F2 = font(17), font(17, True), font(15)


def look_at_quat(pos, target, up=(0.0, 0.0, 1.0)):
    """MuJoCo 相机沿自身 -z 看、+y 朝上：返回 (w, x, y, z)。与 render_r3_frames.py 相同（那个文件导入即运行，不能直接导入）。"""
    pos, target, up = map(lambda v: np.asarray(v, float), (pos, target, up))
    z = pos - target; z /= np.linalg.norm(z); x = np.cross(up, z); x /= np.linalg.norm(x); y = np.cross(z, x)
    Rm = np.stack([x, y, z], axis=1); t = np.trace(Rm)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2; q = [0.25 * s, (Rm[2, 1] - Rm[1, 2]) / s, (Rm[0, 2] - Rm[2, 0]) / s, (Rm[1, 0] - Rm[0, 1]) / s]
    else:
        i = int(np.argmax(np.diag(Rm)))
        if i == 0:
            s = np.sqrt(1.0 + Rm[0, 0] - Rm[1, 1] - Rm[2, 2]) * 2; q = [(Rm[2, 1] - Rm[1, 2]) / s, 0.25 * s, (Rm[0, 1] + Rm[1, 0]) / s, (Rm[0, 2] + Rm[2, 0]) / s]
        elif i == 1:
            s = np.sqrt(1.0 + Rm[1, 1] - Rm[0, 0] - Rm[2, 2]) * 2; q = [(Rm[0, 2] - Rm[2, 0]) / s, (Rm[0, 1] + Rm[1, 0]) / s, 0.25 * s, (Rm[1, 2] + Rm[2, 1]) / s]
        else:
            s = np.sqrt(1.0 + Rm[2, 2] - Rm[0, 0] - Rm[1, 1]) * 2; q = [(Rm[1, 0] - Rm[0, 1]) / s, (Rm[0, 2] + Rm[2, 0]) / s, (Rm[1, 2] + Rm[2, 1]) / s, 0.25 * s]
    q = np.array(q); return q / np.linalg.norm(q)


def place_camera(env):
    m, d = env.sim.model, env.sim.data
    objs = [n for n in (m.body_id2name(i) for i in range(m.nbody)) if n and n.endswith("_main") and not n.startswith(("robot", "gripper", "mount"))]
    c = np.median(np.array([d.body_xpos[m.body_name2id(n)] for n in objs]), axis=0); base = d.body_xpos[m.body_name2id("robot0_base")]
    tgt = np.array([(c[0] + base[0]) / 2 + 0.12, c[1], c[2] + 0.0]); pos = tgt + 1.22 * np.array([0.85, -1.1, 1.05])   # 拉远一些，给上下的文字栏留出位置
    cid = m.camera_name2id("galleryview"); m.cam_pos[cid] = pos; m.cam_quat[cid] = look_at_quat(pos, tgt); m.cam_fovy[cid] = 42.0


def short_reason(r):
    r = str(r)
    for k, v in (("is closed; open it first", "target drawer is closed"), ("blocked from above", "blocked by an open drawer above"), ("nothing in hand", "nothing in hand"),
                 ("not executable at that point", None), ("no longer fits", "the state changed while it was being written"), ("raise failed", "could not lift"),
                 ("pre-grasp failed", "could not reach a grasp pose"), ("descend failed", "could not reach a grasp pose"), ("object not in hand", "grasp slipped"),
                 ("out of reach", "out of reach"), ("approach failed", "could not reach"), ("transport failed", "could not carry"), ("after release", "did not land in place"),
                 ("pour incomplete", "pour incomplete")):
        if k in r:
            if v is None:   # "step 1 pick(popcorn_1) is not executable at that point (hand busy with moka_pot_1); ..."
                m = re.search(r"step (\d+) (\S+) is not executable at that point \(([^)]*)\)", r)
                return f"step {m.group(1)} {m.group(2)} is impossible ({m.group(3).replace('hand busy with', 'already holding')})" if m else "a step is no longer executable"
            return v
    return r[:60]


def events_of(e):
    """按时间排好的'模型事件'（底栏第二行）：(时刻, 显示秒数, 文字, 颜色)。"""
    ev = []
    for x in e["decisions"]:
        nm = x["skill"]["name"] if x["skill"] else {"blocked_choice": "(blocked: this action failed 3 times in a row)", "invalid_action": "(invalid action)",
                                                     "done_verify": "(declares the task done)", "planner_done": "(declares the task done)"}.get(x["res"], "")
        if not nm: continue
        if e["fast_mode"] == "jev" and x["p"] is not None:
            ev.append((x["t1"], 1.6, f"Jev decision → {nm}    p = {x['p']:.2f}", (150, 220, 150) if x["p"] >= 0.5 else (240, 200, 120)))
        elif e["fast_mode"] == "think":
            ev.append((x["t1"], 2.0, f"Thought for {x['t1'] - x['t0']:.1f} s → {nm}", (170, 190, 255)))
        else:
            ev.append((x["t1"], 1.6, f"Decision ({x['t1'] - x['t0']:.1f} s) → {nm}", (170, 190, 255)))
    for a in e["advice"]:
        ev.append((a["t"], 4.5, "Advice: " + str(a["text"]), (255, 196, 120)))
    for s in e["slow"]:
        if s["kind"] != "plan": continue
        rj = next((r for r in e["rejected"] if abs(r["t"] - s["t1"]) < 0.6), None)
        pl = next((p for p in e["plans"] if abs(p["t"] - s["t1"]) < 0.6), None)
        if pl: ev.append((s["t1"], 4.0, f"Plan arrived after {s['t1'] - s['t0']:.1f} s ({pl['n']} steps) → adopted", (150, 220, 150)))
        elif rj: ev.append((s["t1"], 4.0, f"Plan arrived after {s['t1'] - s['t0']:.1f} s → discarded: {short_reason(rj['error'])}", (255, 140, 130)))
        elif s["err"]: ev.append((s["t1"], 3.0, f"Plan call after {s['t1'] - s['t0']:.1f} s returned no plan", (255, 140, 130)))
    for x in e["dist"]:
        ev.append((x["t"], 2.5, f"Disturbance: {x['object']} was displaced", (255, 140, 130)))
    return sorted(ev, key=lambda z: z[0])


def text_box(dr, xy, lines, fonts, pad=8, fill=(0, 0, 0, 150), colors=None, anchor_right=False):
    ws = [dr.textlength(t, font=f) for t, f in zip(lines, fonts)]; hs = [f.size + 5 for f in fonts]
    bw, bh = max(ws) + 2 * pad, sum(hs) + 2 * pad - 3
    x, y = (xy[0] - bw, xy[1]) if anchor_right else xy
    dr.rounded_rectangle([x, y, x + bw, y + bh], radius=8, fill=fill)
    yy = y + pad
    for t, f, h, c in zip(lines, fonts, hs, colors or [(255, 255, 255)] * len(lines)):
        dr.text((x + pad, yy), t, font=f, fill=c); yy += h
    return bw, bh


def draw_hud(img, t, e, ev, head, final=False):
    im = Image.fromarray(img).convert("RGBA"); ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    text_box(dr, (10, 10), head, [F1B, F2], colors=[(255, 255, 255), (215, 215, 215)])
    k = sum(1 for x in e["sub"] if x <= t + 1e-6)
    _, bh = text_box(dr, (W - 10, 10), [f"t = {t:5.1f} s", f"subgoals {k} / {e['n']}"], [F1B, F2], colors=[(255, 255, 255), (215, 215, 215)], anchor_right=True)
    bx0, by = W - 10 - 150, 10 + bh + 6
    dr.rounded_rectangle([bx0, by, W - 10, by + 8], radius=4, fill=(0, 0, 0, 150))
    if e["n"]: dr.rounded_rectangle([bx0, by, bx0 + 150 * k / e["n"], by + 8], radius=4, fill=(110, 200, 120, 230))
    sl = next((s for s in e["slow"] if s["t0"] <= t < s["t1"]), None)
    if sl: text_box(dr, (W - 10, by + 16), [f"slow branch thinking … {t - sl['t0']:.1f} s"], [F2], colors=[(255, 200, 130)], anchor_right=True)
    # 底栏：机器人在做什么 + 最近的模型事件
    run = next((c for c in e["skills"] if c["t0"] <= t < c["t1"]), None)
    done = max((c for c in e["skills"] if c["t1"] <= t < c["t1"] + 1.2), key=lambda c: c["t1"], default=None)
    if final:
        l1, c1 = f"Episode over: {e['done']} / {e['n']} subgoals" + (" — task complete" if e["success"] else ""), (255, 255, 255)
    elif done is not None and (run is None or done["t1"] > run["t0"] - 0.05):
        l1, c1 = (f"✓  {done['name']}", (150, 220, 150)) if done["ok"] else (f"✗  {done['name']} — {short_reason(done['reason'])}", (255, 140, 130))
    elif run is not None:
        l1, c1 = f"▶  {run['name']}", (255, 255, 255)
    else:
        th = next((x for x in e["decisions"] if x["t0"] <= t < x["t1"]), None)
        l1, c1 = (f"…  robot idle, model thinking for {t - th['t0']:.1f} s", (200, 200, 200)) if th and th["t1"] - th["t0"] > 0.8 else ("…  robot idle", (200, 200, 200))
    cur = [z for z in ev if z[0] <= t < z[0] + z[1]]
    pri = [z for z in cur if not z[2].startswith(("Jev", "Decision", "Thought"))] or cur
    l2 = pri[-1] if pri and not final else None
    lines = [(l1, F1B, c1)]
    if l2:
        wrap = textwrap.wrap(l2[2], width=78)[:2]
        if len(textwrap.wrap(l2[2], width=78)) > 2: wrap[-1] = wrap[-1][:75] + " …"
        lines += [(s, F2, l2[3]) for s in wrap]
    bh = sum(f.size + 6 for _, f, _ in lines) + 16
    dr.rectangle([0, H - bh, W, H], fill=(0, 0, 0, 165))
    y = H - bh + 9
    for s, f, c in lines: dr.text((14, y), s, font=f, fill=c); y += f.size + 6
    return np.array(Image.alpha_composite(im, ov).convert("RGB"))


def render(item):
    d = R.RUNS_ROOT / item["dir"]; e = parse(d)
    ep = json.load(open(d / "episode.json")); tl = json.load(open(d / "timeline.json"))["events"]
    t0 = next(x for x in tl if x["type"] == "episode_start")["sim"]
    tt, cn = ep["case"].split("/")
    case = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cn)
    env = R.make_env(case, use_camera_obs=True); env.reset()
    z = np.load(d / "states.npz"); st, steps = z["states"], z["steps"]
    env.sim.set_state_from_flattened(st[0]); env.sim.forward(); place_camera(env)
    head = [f"{MODEL[e['model']]} · {MODE[e['mode']]}", f"{CLOCK[e['clock']]} · {e['task']} · seed {e['seed']}"]
    ev = events_of(e); path = OUT / f"{item['id']}.mp4"
    wr = imageio.get_writer(path, fps=FPS, codec="libx264", quality=None, pixelformat="yuv420p", macro_block_size=16,
                            ffmpeg_params=["-crf", "27", "-preset", "slow", "-movflags", "+faststart"])
    tfirst, n, last = None, 0, None
    for s, k in zip(st, steps):
        t = k * DT - t0
        if t < -1e-6: continue
        if t > e["T"] + 0.05: break
        tfirst = t if tfirst is None else tfirst
        env.sim.set_state_from_flattened(s); env.sim.forward()
        img = env.sim.render(camera_name="galleryview", width=W, height=H)[::-1]
        fr = draw_hud(img, t, e, ev, head); wr.append_data(fr); n += 1; last = (img, t)
        if n == 1: Image.fromarray(fr).save(OUT / f"{item['id']}.jpg", quality=85)
    for _ in range(int(HOLD * FPS)): wr.append_data(draw_hud(last[0], last[1], e, ev, head, final=True))
    wr.close(); env.close()
    meta = {"id": item["id"], "t_first": round(tfirst, 3), "dt": DT, "frames": n, "hold": HOLD, "w": W, "h": H}
    (OUT / f"{item['id']}.json").write_text(json.dumps(meta))
    print(f"{path}: {n} 帧 + 停留 {HOLD} s，{path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    spec = json.load(open(HERE / "site_demos.json"))
    for story in spec["stories"]:
        for it in story["episodes"]:
            if not want or it["id"] in want or story["id"] in want: render(it)
