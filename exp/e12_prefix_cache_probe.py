"""E1.2 前缀缓存探测：服务端是否复用相同前缀的 KV（决定 Phase 3 能否直接在实验室服务上测共享上下文收益）。
条件（关闭思考、max_tokens=1，测首 token 时间 TTFT）：
  A 冷前缀：全新的长前缀（随机 nonce 开头，避免命中）
  B 同前缀重复：与 A 完全相同的请求
  C 同前缀 + 不同后缀：A 的前缀 + 另一个短问题（快分支场景）
  D 同长度不同前缀：另一个全新长前缀（对照）
  E 图像前缀：同一图像 + 同一文本前缀，不同后缀；F 新图像 + 同文本前缀
每组重复 N 次，交错执行。用法: python e12_prefix_cache_probe.py [--n=5] [--words=3000] [--model=sal-pro]
"""
import sys, time, json, uuid, random
import numpy as np
import rc_env as R
from llm_client import LLMClient

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
N = int(opt.get("n", 5)); WORDS = int(opt.get("words", 3000)); model = opt.get("model")
c = LLMClient(model=model)
rng = random.Random(0)
vocab = "robot table drawer cabinet bowl plate butter cookies wine bottle microwave stove gripper place pick pour region object region shelf mug rack".split()
def long_text(nonce):
    return f"[session {nonce}] Scene log. " + " ".join(rng.choice(vocab) for _ in range(WORDS))
def ask(prefix, suffix, image=None):
    msgs = c.build_messages("You are a robot planner. Answer with one word.", prefix + "\n\nQuestion: " + suffix, images=[image] if image is not None else None)
    r = c.chat(msgs, max_tokens=1, thinking=False)
    return r
rows = []
for i in range(N):
    nonce_a = uuid.uuid4().hex; pa = long_text(nonce_a)
    rA = ask(pa, "Is the drawer open?")
    rB = ask(pa, "Is the drawer open?")
    rC = ask(pa, "Which object is closest to the gripper?")
    rD = ask(long_text(uuid.uuid4().hex), "Is the drawer open?")
    img = (np.random.default_rng(i).random((256, 256, 3)) * 255).astype(np.uint8)
    img2 = (np.random.default_rng(1000 + i).random((256, 256, 3)) * 255).astype(np.uint8)
    pe = long_text(uuid.uuid4().hex)
    rE0 = ask(pe, "Is the drawer open?", img)
    rE = ask(pe, "Which object is closest to the gripper?", img)
    rF = ask(pe, "Which object is closest to the gripper?", img2)
    row = {k: (None if r.ttft is None else round(r.ttft, 3)) for k, r in zip(["A_cold", "B_repeat", "C_same_prefix_new_suffix", "D_new_prefix", "E0_img_cold", "E_img_same", "F_img_new"], [rA, rB, rC, rD, rE0, rE, rF])}
    row["prompt_tokens"] = rA.usage.get("prompt_tokens"); row["prompt_tokens_img"] = rE0.usage.get("prompt_tokens")
    row["cached_report"] = [r.usage.get("prompt_tokens_details") for r in (rB, rC, rE)]
    rows.append(row); print(json.dumps(row), flush=True)
keys = ["A_cold", "B_repeat", "C_same_prefix_new_suffix", "D_new_prefix", "E0_img_cold", "E_img_same", "F_img_new"]
summary = {k: {"median_s": float(np.median([r[k] for r in rows if r[k] is not None])), "min_s": float(np.min([r[k] for r in rows if r[k] is not None]))} for k in keys}
summary["prompt_tokens"] = rows[0]["prompt_tokens"]; summary["prompt_tokens_img"] = rows[0]["prompt_tokens_img"]
print(json.dumps(summary, indent=1))
out = R.RUNS_ROOT / "e12"; out.mkdir(parents=True, exist_ok=True)
json.dump({"model": c.model, "words": WORDS, "rows": rows, "summary": summary}, open(out / f"prefix_probe_{c.model}_{WORDS}w.json", "w"), indent=1)
