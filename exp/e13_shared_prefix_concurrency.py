"""E1.3（GPU 服务器）共享前缀 × 并发：同一模型的慢分支长解码与快分支短问题并发时，快分支首 token 延迟（TTFT）与缓存命中。
需要自部署 vLLM（--enable-prefix-caching --enable-prompt-tokens-details）或 SGLang（RadixAttention）。实验室网关无可控前缀缓存（见 E1.2）。

条件（每条件 N 次，交错）：
  S0 快分支单独、冷前缀           —— 基线
  S1 快分支单独、与上一请求共享前缀 —— 缓存收益上限
  C0 慢分支并发解码 + 快分支冷前缀
  C1 慢分支并发解码 + 快分支与慢分支共享前缀（同一场景提示 + 同一图像）
  C2 C1 + 新观测：前缀中的图像换成下一帧（计划文档 §6.2："新图像不能原样复用旧 KV"）
记录：TTFT、总延迟、usage.prompt_tokens_details.cached_tokens、慢分支解码速度受影响程度。
用法: python e13_shared_prefix_concurrency.py --base_url=http://host:8000/v1 --model=qwen27b [--n=10] [--prefix_words=2500] [--images=on]
"""
import sys, time, json, uuid, random, threading
import numpy as np
import rc_env as R
from llm_client import LLMClient

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
N = int(opt.get("n", 10)); WORDS = int(opt.get("prefix_words", 2500)); use_img = opt.get("images", "on") == "on"
mk = lambda: LLMClient(base_url=opt.get("base_url"), api_key=opt.get("api_key"), model=opt.get("model"))   # 未给参数时按 LLM_PROFILE 读 .env
fast, slow = mk(), mk()
rng = random.Random(0)
vocab = "robot table drawer cabinet bowl plate butter cookies wine bottle microwave stove gripper place pick pour region object shelf mug rack".split()
SYS = "You are the planner of a robot arm. Answer briefly."
def scene(nonce): return f"[episode {nonce}] Scene description and history. " + " ".join(rng.choice(vocab) for _ in range(WORDS))
def img(seed): return (np.random.default_rng(seed).random((256, 256, 3)) * 255).astype(np.uint8)
def fast_q(prefix, image):
    msgs = fast.build_messages(SYS, prefix + "\n\nFAST QUESTION: Is the current skill still valid? Answer yes or no.", images=[image] if image is not None else None)
    return fast.chat(msgs, max_tokens=4, thinking=False)
def slow_q(prefix, image, out):
    msgs = slow.build_messages(SYS, prefix + "\n\nSLOW QUESTION: Think step by step and write a detailed 20-step plan.", images=[image] if image is not None else None)
    out.append(slow.chat(msgs, max_tokens=int(opt.get("slow_tokens", 1500)), thinking=True))
def cached(r):
    d = (r.usage or {}).get("prompt_tokens_details") or {}
    return d.get("cached_tokens") if isinstance(d, dict) else None
rows = []
for i in range(N):
    nonce = uuid.uuid4().hex; pre = scene(nonce); im = img(i) if use_img else None; im2 = img(10_000 + i) if use_img else None
    r_s0 = fast_q(scene(uuid.uuid4().hex), img(20_000 + i) if use_img else None)
    _ = fast_q(pre, im); r_s1 = fast_q(pre, im)                       # 预热同前缀后再测
    outs = []; th = threading.Thread(target=slow_q, args=(pre, im, outs)); th.start(); time.sleep(1.0)
    r_c1 = fast_q(pre, im)                                             # 并发 + 共享前缀
    r_c0 = fast_q(scene(uuid.uuid4().hex), img(30_000 + i) if use_img else None)   # 并发 + 冷前缀
    r_c2 = fast_q(pre, im2)                                            # 并发 + 前缀中图像换成新帧
    th.join()
    rs = outs[0] if outs else None
    row = {"S0_alone_cold": r_s0.ttft, "S1_alone_shared": r_s1.ttft, "C0_conc_cold": r_c0.ttft, "C1_conc_shared": r_c1.ttft, "C2_conc_newimage": r_c2.ttft,
           "cached_S1": cached(r_s1), "cached_C1": cached(r_c1), "cached_C2": cached(r_c2), "prompt_tokens": r_s1.usage.get("prompt_tokens"),
           "slow_latency": rs.latency if rs else None, "slow_tokens": rs.usage.get("completion_tokens") if rs else None,
           "slow_decode_tps": (rs.usage.get("completion_tokens") / max(rs.latency - (rs.ttft or 0), 1e-6)) if rs and rs.usage.get("completion_tokens") else None}
    rows.append(row); print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
keys = ["S0_alone_cold", "S1_alone_shared", "C0_conc_cold", "C1_conc_shared", "C2_conc_newimage"]
summ = {k: round(float(np.median([r[k] for r in rows if r[k] is not None])), 3) for k in keys}
summ["prompt_tokens"] = rows[0]["prompt_tokens"]; summ["slow_decode_tps_median"] = round(float(np.median([r["slow_decode_tps"] for r in rows if r["slow_decode_tps"]])), 1) if any(r["slow_decode_tps"] for r in rows) else None
print("SUMMARY (median TTFT, s):", json.dumps(summ, indent=1))
out = R.RUNS_ROOT / "e13"; out.mkdir(parents=True, exist_ok=True)
json.dump({"opt": {k: v for k, v in opt.items() if k != "api_key"}, "base_url": fast.base_url, "model": fast.model, "rows": rows, "summary": summ}, open(out / f"shared_prefix_{int(time.time())}.json", "w"), indent=1)
