"""Jev 式快分支（计划文档 §6.1："通过 Jev 式候选概率、结构化分类或短文本选择动作"；参考 notes/2609.25845_Visual_Jev.md）。
把当前所有**合法**技能调用程序化列成字母候选（不按任务筛选，避免泄露最优解），模型只生成 1 个 token，
读取该位置 top_logprobs 中各字母的对数概率，取概率最高的合法候选。延迟 ≈ 一次预填充（共享前缀命中时更短）。
"""
from __future__ import annotations
import math, string, time
from typing import Any, Dict, List, Optional, Tuple

LETTERS = list(string.ascii_uppercase) + list(string.ascii_lowercase)          # 52 个单 token 选项
CONTAINER_HINTS = ("bowl", "plate", "frypan", "pan", "mug", "basket", "rack", "tray", "pot", "cup")


def candidate_actions(snap, objects: List[str], fixtures: List[str], regions: List[str], drawer_regions: List[str]) -> List[Dict[str, Any]]:
    c: List[Dict[str, Any]] = []
    hid = set(getattr(snap, "hidden", None) or [])
    objects = [o for o in objects if o not in hid]                       # 关闭抽屉内的物体不可见
    containers = [o for o in objects if any(h in o for h in CONTAINER_HINTS)]
    if snap.held is None:
        c += [{"skill": "pick", "args": [o]} for o in objects]
        for r in drawer_regions:
            frac = (snap.drawers or {}).get(r, 0.0)
            c.append({"skill": "close_drawer" if frac >= 0.5 else "open_drawer", "args": [r]})
        c += [{"skill": "turnon", "args": [f]} for f in fixtures if "stove" in f]
    else:
        c += [{"skill": "place", "args": [r]} for r in regions]
        c += [{"skill": "place", "args": [o]} for o in containers if o != snap.held]
        c += [{"skill": "pour", "args": [o]} for o in containers if o != snap.held]
    c.append({"skill": "wait", "args": [20]})
    c.append({"skill": None, "args": [], "done": True})
    return c[:len(LETTERS)]


def candidates_text(cands: List[Dict[str, Any]]) -> str:
    lines = ["CANDIDATE NEXT ACTIONS (all currently valid calls):"]
    for L, a in zip(LETTERS, cands):
        lines.append(f"  {L}) " + ("DONE: the whole task is complete" if a.get("done") else f"{a['skill']}({', '.join(map(str, a['args']))})"))
    lines.append("Answer with the single letter of the best next action, nothing else.")
    return "\n".join(lines)


def jev_choose(client, messages: List[Dict[str, Any]], cands: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """一次前向（max_tokens=1），从第一个生成位置的 top_logprobs 中读出候选字母分布。"""
    t0 = time.time(); info: Dict[str, Any] = {"t_sent": t0}
    eb = {"chat_template_kwargs": {"enable_thinking": False}, "enable_thinking": False}
    if getattr(client, "cache_salt_per_request", False):
        import uuid
        eb["cache_salt"] = uuid.uuid4().hex                                # 禁缓存对照：每个请求随机 salt
    try:
        resp = client.client.chat.completions.create(
            model=client.model, messages=messages, max_tokens=1, temperature=0.0, logprobs=True, top_logprobs=20,
            extra_body=eb)
        info["latency"] = time.time() - t0
        u = resp.usage.model_dump() if resp.usage else {}
        info["usage"] = u
        d = (u.get("prompt_tokens_details") or {}) if isinstance(u, dict) else {}
        info["cached_tokens"] = d.get("cached_tokens") if isinstance(d, dict) else None
        lp = resp.choices[0].logprobs.content[0].top_logprobs if resp.choices[0].logprobs and resp.choices[0].logprobs.content else []
        dist = {}
        for t in lp:
            tok = t.token.strip()
            if tok in LETTERS[:len(cands)] and tok not in dist:
                dist[tok] = t.logprob
        info["dist"] = {k: round(math.exp(v), 4) for k, v in sorted(dist.items(), key=lambda kv: -kv[1])[:6]}
        info["generated"] = resp.choices[0].message.content
        if not dist:
            info["error"] = f"no candidate letter in top_logprobs (generated {resp.choices[0].message.content!r})"
            return None, info
        best = max(dist, key=dist.get)
        info["choice"] = best; info["p_choice"] = round(math.exp(dist[best]), 4)
        return cands[LETTERS.index(best)], info
    except Exception as e:
        info["latency"] = time.time() - t0; info["error"] = repr(e)[:200]
        return None, info
