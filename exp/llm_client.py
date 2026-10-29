"""OpenAI 兼容的 LLM/VLM 客户端，带完整时间戳埋点（计划文档 §7.1 的"请求发送 / 首 token / 结果返回"）。

环境变量：LLM_BASE_URL（如 http://host:8000/v1）、LLM_API_KEY、LLM_MODEL。
用法：
    from llm_client import LLMClient
    c = LLMClient(); r = c.chat([{"role": "user", "content": "..."}], images=[np_img], max_tokens=256)
    r.text, r.t_sent, r.t_first_token, r.t_done, r.usage
命令行探测：python llm_client.py --probe
"""
from __future__ import annotations
import base64, io, os, sys, time, json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class LLMResult:
    text: str
    t_sent: float
    t_first_token: Optional[float]
    t_done: float
    usage: Dict[str, Any] = field(default_factory=dict)
    model: str = ""
    error: Optional[str] = None
    reasoning: str = ""
    t_first_content: Optional[float] = None      # 正文首 token（思考结束）时间
    n_chunks: int = 0
    n_retries: int = 0                           # 因限流/服务端错误的重试次数
    retry_wait_s: float = 0.0                    # 重试前的退避等待总时长（已计入 latency）
    rate_limited: bool = False

    @property
    def latency(self) -> float:
        return self.t_done - self.t_sent

    @property
    def ttft(self) -> Optional[float]:
        return None if self.t_first_token is None else self.t_first_token - self.t_sent

    @property
    def think_time(self) -> Optional[float]:
        """思考耗时：首个 reasoning token 到首个正文 token。"""
        if self.t_first_token is None or self.t_first_content is None: return None
        return self.t_first_content - self.t_first_token

    @property
    def decode_tps(self) -> Optional[float]:
        ct = self.usage.get("completion_tokens") if self.usage else None
        if not ct or self.t_first_token is None: return None
        return ct / max(self.t_done - self.t_first_token, 1e-6)


def _img_to_data_url(img: np.ndarray, fmt: str = "PNG") -> str:
    import imageio.v2 as imageio
    buf = io.BytesIO(); imageio.imwrite(buf, img, format=fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def load_dotenv(path: Optional[str] = None) -> None:
    """从 exp/.env 读取 LLM_* 变量（不覆盖已设置的环境变量；文件不入 git）。"""
    p = Path(path) if path else Path(__file__).resolve().parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())


class LLMClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None, timeout: float = 120.0,
                 profile: Optional[str] = None):
        load_dotenv()
        from openai import OpenAI
        # 配置档：LLM_PROFILE=exp → 读 LLM_EXP_*（L20 自部署实验实例，可控前缀缓存）；默认读 LLM_*（实验室网关）
        # profile 参数（exp | gateway）优先于环境变量，用于快慢分支分别连不同服务（r5 异构组合）
        prof = (profile or os.environ.get("LLM_PROFILE", "")).lower()
        pre = "LLM_EXP_" if prof == "exp" else "LLM_"
        self.profile = "exp" if pre == "LLM_EXP_" else "gateway"
        self.base_url = base_url or os.environ.get(pre + "BASE_URL", "http://localhost:8000/v1")
        self.api_key = api_key or os.environ.get(pre + "API_KEY", "EMPTY")
        self.model = model or os.environ.get(pre + "MODEL", "qwen27b")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=timeout)
        self.log: List[LLMResult] = []

    def build_messages(self, system: Optional[str], user_text: str, images: Optional[List[np.ndarray]] = None,
                       history: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = []
        if system: msgs.append({"role": "system", "content": system})
        if history: msgs.extend(history)
        if images:
            content = [{"type": "image_url", "image_url": {"url": _img_to_data_url(im)}} for im in images]
            content.append({"type": "text", "text": user_text})
            msgs.append({"role": "user", "content": content})
        else:
            msgs.append({"role": "user", "content": user_text})
        return msgs

    RETRY_MAX = 6

    def chat(self, messages: List[Dict[str, Any]], max_tokens: int = 512, temperature: Optional[float] = None,
             stream: bool = True, thinking: Optional[bool] = None, extra: Optional[Dict[str, Any]] = None,
             top_p: Optional[float] = None, seed: Optional[int] = None) -> LLMResult:
        """带退避重试的调用：429 / 5xx / 连接错误时等待 min(8, 0.8·2^k)·(0.5–1.5) 秒后重试，最多 RETRY_MAX 次。
        返回的 latency 从第一次发送算起（包含退避等待——智能体实际承受的延迟）。"""
        import random as _r
        t0 = time.time(); waited = 0.0; n = 0; rl = False
        while True:
            r = self._chat_once(messages, max_tokens, temperature, stream, thinking, extra, top_p, seed)
            err = r.error or ""
            transient = ("429" in err or "RateLimit" in err or "APIConnectionError" in err or "APITimeoutError" in err
                         or "InternalServerError" in err or " 50" in err or "502" in err or "503" in err or "504" in err)
            if not transient or n >= self.RETRY_MAX:
                break
            rl = rl or ("429" in err or "RateLimit" in err)
            w = min(8.0, 0.8 * (2 ** n)) * (0.5 + _r.random()); time.sleep(w); waited += w; n += 1
        r.t_sent = t0; r.n_retries = n; r.retry_wait_s = round(waited, 2); r.rate_limited = rl
        self.log.append(r)
        return r

    def _chat_once(self, messages: List[Dict[str, Any]], max_tokens: int = 512, temperature: Optional[float] = None,
             stream: bool = True, thinking: Optional[bool] = None, extra: Optional[Dict[str, Any]] = None,
             top_p: Optional[float] = None, seed: Optional[int] = None) -> LLMResult:
        """thinking=False 关闭 Qwen3 思考模式（快分支）；None 用服务端默认。流式时分别收集 reasoning_content 与 content。
        采样参数默认取 Qwen3 官方推荐：思考模式 T=0.6/top_p=0.95，非思考模式 T=0.7/top_p=0.8（官方不建议思考模式用贪心解码）。"""
        if temperature is None: temperature = 0.6 if thinking is not False else 0.7
        if top_p is None: top_p = 0.95 if thinking is not False else 0.8
        if seed is None: seed = getattr(self, "seed", None)
        t_sent = time.time(); t_first = None; t_first_content = None; chunks = []; rchunks = []; usage = {}; n = 0
        extra_body = dict((extra or {}).get("extra_body", {}))
        if getattr(self, "cache_salt_per_request", False):        # 禁缓存对照（推荐）：每个请求随机 salt，输入 token 不变、命中归零（vLLM cache_salt）
            import uuid as _uuid
            extra_body["cache_salt"] = _uuid.uuid4().hex
        if thinking is not None:
            extra_body["enable_thinking"] = thinking
            extra_body["chat_template_kwargs"] = {"enable_thinking": thinking}
        kw = {k: v for k, v in (extra or {}).items() if k != "extra_body"}
        kw["top_p"] = top_p
        if seed is not None: kw["seed"] = int(seed)
        try:
            if stream:
                resp = self.client.chat.completions.create(model=self.model, messages=messages, max_tokens=max_tokens,
                                                           temperature=temperature, stream=True,
                                                           stream_options={"include_usage": True}, extra_body=extra_body or None, **kw)
                for ev in resp:
                    n += 1
                    if getattr(ev, "usage", None):
                        usage = ev.usage.model_dump() if hasattr(ev.usage, "model_dump") else dict(ev.usage)
                    if not ev.choices: continue
                    delta = ev.choices[0].delta
                    rc = None
                    if delta:                                    # vLLM 新版字段名为 reasoning，旧版/部分网关为 reasoning_content
                        ex_ = delta.model_extra or {}
                        rc = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None) or ex_.get("reasoning_content") or ex_.get("reasoning")
                    if rc:
                        if t_first is None: t_first = time.time()
                        rchunks.append(rc)
                    if delta and delta.content:
                        now = time.time()
                        if t_first is None: t_first = now
                        if t_first_content is None: t_first_content = now
                        chunks.append(delta.content)
                text = "".join(chunks)
            else:
                resp = self.client.chat.completions.create(model=self.model, messages=messages, max_tokens=max_tokens,
                                                           temperature=temperature, extra_body=extra_body or None, **kw)
                msg = resp.choices[0].message
                ex_ = msg.model_extra or {}
                text = msg.content or ""; rchunks = [getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ex_.get("reasoning_content") or ex_.get("reasoning") or ""]
                usage = resp.usage.model_dump() if resp.usage else {}
            r = LLMResult(text, t_sent, t_first, time.time(), usage, self.model, reasoning="".join(rchunks), t_first_content=t_first_content, n_chunks=n)
        except Exception as e:
            r = LLMResult("", t_sent, t_first, time.time(), {}, self.model, error=repr(e)[:300], reasoning="".join(rchunks))
        return r

    def probe(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"base_url": self.base_url, "model": self.model}
        try:
            out["models"] = [m.id for m in self.client.models.list().data]
        except Exception as e:
            out["models_error"] = repr(e)[:200]
        def rec(tag, r):
            out[tag] = {"text": r.text[:120], "reasoning_chars": len(r.reasoning), "latency_s": round(r.latency, 3),
                        "ttft_s": None if r.ttft is None else round(r.ttft, 3), "think_s": None if r.think_time is None else round(r.think_time, 3),
                        "decode_tps": None if r.decode_tps is None else round(r.decode_tps, 1), "usage": r.usage, "error": r.error}
        rec("text_default", self.chat(self.build_messages(None, "Reply with the single word: ready"), max_tokens=512))
        rec("text_nothink", self.chat(self.build_messages(None, "Reply with the single word: ready"), max_tokens=64, thinking=False))
        rec("text_think", self.chat(self.build_messages(None, "What is 17*23? Answer with the number only."), max_tokens=1024, thinking=True))
        img = np.zeros((128, 128, 3), np.uint8); img[:, :64] = (220, 30, 30); img[:, 64:] = (30, 30, 220)
        rec("image_nothink", self.chat(self.build_messages(None, "The image is split into two halves. Name the color of the left half and the right half in one short sentence.", images=[img]), max_tokens=64, thinking=False))
        out["image_supported"] = bool(out["image_nothink"]["text"]) and out["image_nothink"]["error"] is None
        return out


if __name__ == "__main__":
    if "--probe" in sys.argv:
        model = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--model=")), None)
        print(json.dumps(LLMClient(model=model).probe(), ensure_ascii=False, indent=2))
    else:
        c = LLMClient(); print(json.dumps(asdict(c.chat(c.build_messages(None, " ".join(sys.argv[1:]) or "hello"))), ensure_ascii=False, indent=2))
