"""Phase 2 动态事件（计划文档 §5.5 / §5.6）。挂在 RealtimeSim.on_tick 上，每个控制步检查触发条件。

事件类型（第一版）：
- E1 目标更新（goal_update）：用户消息改变某物体的目的地；计分目标同步改变（保留已完成前缀）。
  记录：旧目标的过时动作（事件后仍提交 place(旧目标)）、首个与新目标一致的动作/取消的响应延迟。
- E2 容器移动（container_move）：可见地把一个容器物体（带自由关节）在 move_s 秒内平移 (dx,dy)。
  运动学脚本运动（逐步改写 qpos，速度置零），论文中标注为 SCRIPTED-KINEMATIC，不是物理推动。
- E3 限时关闭（deadline_close）：发出警告消息，window_s 秒后抽屉自动关上（1 s 动画）并锁定 lock_s 秒；
  锁定期间 open_drawer 返回失败。用于"是否在响应窗口内完成正确动作"。
触发：{"kind": "time", "t": 秒} | {"kind": "subgoals", "n": 已完成子目标数} | {"kind": "skill", "skill": 名称, "arg": 参数(可选)}
所有事件都写入 sim.events（type=event_fired / event_effect / event_deadline），消息写入 sim.messages（快照可见）。
"""
from __future__ import annotations
import json, time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class EventSpec:
    eid: str
    etype: str                       # "E1_goal_update" | "E2_container_move" | "E3_deadline_close"
    trigger: Dict[str, Any]
    params: Dict[str, Any] = field(default_factory=dict)
    message: Optional[str] = None
    window_s: Optional[float] = None


class EventManager:
    def __init__(self, specs: List[EventSpec]):
        self.specs = specs
        self.fired: Dict[str, float] = {}
        self.state: Dict[str, Dict[str, Any]] = {}
        self.locked_regions: Dict[str, float] = {}      # region -> 解锁的仿真时间

    # ---------- 钩子 ----------
    def attach(self, sim):
        self.sim = sim
        if not hasattr(sim, "messages"): sim.messages = []
        prev = sim.on_tick
        def tick(s):
            if prev is not None: prev(s)
            self.on_tick(s)
        sim.on_tick = tick
        # 让执行器在锁定期间拒绝打开抽屉
        self._wrap_open_drawer()

    def _wrap_open_drawer(self):
        mgr = self
        def install(ex):
            if getattr(ex, "_event_wrapped", False): return
            orig = ex.open_drawer
            def guarded(region_site, *a, **k):
                from skills import SkillResult
                t = float(ex.env.sim.data.time)
                if region_site in mgr.locked_regions and t < mgr.locked_regions[region_site]:
                    return SkillResult(f"open({region_site})", False, f"locked until t={mgr.locked_regions[region_site]:.1f}s", 0, ex.n_done, ex.n_done)
                return orig(region_site, *a, **k)
            ex.open_drawer = guarded; ex._event_wrapped = True
        self._install = install

    def sim_time(self) -> float:
        return float(self.sim.env.sim.data.time - self.sim.sim_t0)

    def _triggered(self, spec: EventSpec) -> bool:
        tr = spec.trigger; k = tr.get("kind")
        if k == "time":
            return self.sim_time() >= float(tr["t"])
        if k == "subgoals":
            return int(self.sim.scorer.last[2]) >= int(tr["n"])
        if k == "skill":
            cur = self.sim.current
            if cur is None or cur.name not in (tr["skill"] if isinstance(tr["skill"], list) else [tr["skill"]]): return False
            if tr.get("arg") is not None and not (cur.args and cur.args[0] == tr["arg"]): return False
            if tr.get("arg_prefix") is not None and not (cur.args and str(cur.args[0]).startswith(tr["arg_prefix"])): return False
            if tr.get("held") is not None and self.sim.ex.held != tr["held"]: return False
            return True
        return False

    def on_tick(self, sim):
        if getattr(sim, "sim_t0", None) is None or not getattr(sim, "running", False):
            return                                     # 静置阶段 / episode 未开始：不触发事件
        if hasattr(sim, "ex"): self._install(sim.ex)
        t = self.sim_time()
        for spec in self.specs:
            if spec.eid in self.fired:
                self._update_active(spec, t); continue
            if self._triggered(spec):
                self.fired[spec.eid] = t
                if spec.message:
                    sim.messages.append({"t": round(t, 2), "eid": spec.eid, "text": spec.message})
                sim.log_event("event_fired", eid=spec.eid, event_type=spec.etype, message=spec.message, params=spec.params)
                try:
                    getattr(self, "_fire_" + spec.etype.split("_", 1)[0])(spec, t)
                except Exception as e:
                    import traceback, sys
                    traceback.print_exc(file=sys.stderr)
                    sim.log_event("event_error", eid=spec.eid, error=repr(e)[:300])

    # ---------- E1 目标更新 ----------
    def _fire_E1(self, spec: EventSpec, t: float):
        p = spec.params; obj = p["object"]; old_t, new_t, pred = p["old_target"], p["new_target"], p.get("new_pred", "in")
        is_old = lambda target: str(target).startswith(old_t)
        goal = self.sim.case.goal
        sc = self.sim.scorer
        k = sc.rep._progress.get(obj, 0)
        states = goal[obj]
        prefix = states[:k]
        # 若旧目标已完成，需要重新拿起再放到新目标
        if any(st[0] in ("in", "on") and is_old(st[-1]) for st in prefix):
            new_states = prefix + [["pick", obj], [pred, obj, new_t]]
        else:
            rest = [st for st in states[k:] if not (st[0] in ("in", "on") and is_old(st[-1]))]
            new_states = prefix + rest + [[pred, obj, new_t]]
        goal[obj] = new_states
        # 同步计分器
        sc.rep.n_goals = sum(len(v) for v in goal.values()); sc.n_goals = sc.rep.n_goals
        if hasattr(sc.orig, "n_goals"): sc.orig.n_goals = sc.rep.n_goals
        self.state[spec.eid] = {"t_fire": t, "object": obj, "old_target": old_t, "new_target": new_t, "stale_actions": [],
                                "first_consistent": None, "cancelled_stale": False}
        self.sim.log_event("event_effect", eid=spec.eid, new_goal={obj: new_states})

    # ---------- E2 容器移动 ----------
    def _fire_E2(self, spec: EventSpec, t: float):
        p = spec.params; env = self.sim.env; obj = p["object"]
        jname = env.objects_dict[obj].joints[-1]
        addr = env.sim.model.get_joint_qpos_addr(jname)
        start = np.array(env.sim.data.qpos[addr[0]:addr[0] + 3]) if isinstance(addr, tuple) else None
        self.state[spec.eid] = {"t_fire": t, "object": obj, "addr": addr, "start": start, "delta": np.array([p.get("dx", 0.0), p.get("dy", 0.0), 0.0]),
                                "steps": max(1, int(p.get("move_s", 1.5) * env.control_freq)), "k": 0, "done": False}

    def _update_E2(self, spec: EventSpec, t: float):
        st = self.state.get(spec.eid)
        if not st or st["done"] or st["start"] is None: return
        env = self.sim.env; a0 = st["addr"][0]
        st["k"] += 1; frac = min(1.0, st["k"] / st["steps"])
        env.sim.data.qpos[a0:a0 + 3] = st["start"] + st["delta"] * frac
        qv = env.sim.model.get_joint_qvel_addr(env.objects_dict[st["object"]].joints[-1])
        env.sim.data.qvel[qv[0]:qv[1]] = 0.0
        env.sim.forward()
        if frac >= 1.0:
            st["done"] = True
            self.sim.log_event("event_effect", eid=spec.eid, moved=st["object"], final_pos=list(map(float, env.sim.data.qpos[a0:a0 + 3])))

    # ---------- E3 限时关闭 ----------
    def _fire_E3(self, spec: EventSpec, t: float):
        p = spec.params
        self.state[spec.eid] = {"t_fire": t, "region": p["region"], "deadline": t + float(spec.window_s or p.get("window_s", 10.0)),
                                "closing": False, "closed": False, "k": 0, "anim_steps": int(p.get("close_s", 1.0) * self.sim.env.control_freq),
                                "lock_s": float(p.get("lock_s", 1e6))}

    def _update_E3(self, spec: EventSpec, t: float):
        st = self.state.get(spec.eid)
        if not st or st["closed"]: return
        if t < st["deadline"]: return
        ex = self.sim.ex; env = self.sim.env; m = env.sim.model
        spos, d, half, joint, parent, frac = ex.drawer_geometry(st["region"])
        addr = m.get_joint_qpos_addr(joint)
        art = env.get_object(parent).object_properties["articulation"]
        if not st["closing"]:
            st["closing"] = True; st["q0"] = float(env.sim.data.qpos[addr]); st["q1"] = float(np.mean(art["default_close_ranges"]))
            self.sim.log_event("event_deadline", eid=spec.eid, region=st["region"], open_frac_at_deadline=round(frac, 2))
            # 若此时正在执行与该抽屉有关的技能，取消它（物理上抽屉合上会挡住）
            cur = self.sim.current
            if cur is not None and cur.args and cur.args[0] == st["region"]:
                self.sim.cancel_sources[cur.cid] = f"environment: {st['region']} closed automatically"
                ex.cancel_flag = True
        st["k"] += 1; f = min(1.0, st["k"] / max(st["anim_steps"], 1))
        env.sim.data.qpos[addr] = st["q0"] + (st["q1"] - st["q0"]) * f
        env.sim.data.qvel[m.get_joint_qvel_addr(joint)] = 0.0
        if f >= 1.0:
            st["closed"] = True
            self.locked_regions[st["region"]] = t + st["lock_s"]
            self.sim.log_event("event_effect", eid=spec.eid, closed=st["region"], locked_until=round(t + st["lock_s"], 1))

    def _update_active(self, spec: EventSpec, t: float):
        fn = getattr(self, "_update_" + spec.etype.split("_", 1)[0], None)
        if fn is not None: fn(spec, t)
        if spec.etype.startswith("E1"): self._watch_E1(spec, t)

    def _watch_E1(self, spec: EventSpec, t: float):
        st = self.state.get(spec.eid)
        if not st: return
        cur = self.sim.current
        if cur is None: return
        key = (cur.cid, cur.name, cur.args)
        if st.get("_last_seen") == key: return
        st["_last_seen"] = key
        if cur.name in ("place", "place_on_object") and cur.args and str(cur.args[0]).startswith(st["old_target"]) and self.sim.ex.held == st["object"]:
            st["stale_actions"].append({"t": round(t, 2), "cid": cur.cid, "obs_version": cur.obs_version})
        if st["first_consistent"] is None and cur.args and cur.args[0] == st["new_target"]:
            st["first_consistent"] = {"t": round(t, 2), "cid": cur.cid, "latency_s": round(t - st["t_fire"], 2)}

    def report(self) -> Dict[str, Any]:
        out = {}
        for spec in self.specs:
            st = {k: v for k, v in self.state.get(spec.eid, {}).items() if not k.startswith("_") and k not in ("addr", "start", "delta")}
            out[spec.eid] = {"etype": spec.etype, "fired_at": self.fired.get(spec.eid)} | json.loads(json.dumps(st, default=str))
        return out


def load_specs(path) -> List[EventSpec]:
    return [EventSpec(**d) for d in json.load(open(path))]
