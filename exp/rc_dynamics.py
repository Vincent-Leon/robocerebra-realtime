"""RoboCerebra 动态条件在本项目协议（实时 / 完成即切换、无固定时间片、无逐段重置）下的实现。

官方评测（repos/RoboCerebra/evaluation/eval_openvla.py）按任务类型设定开关：
  Random_Disturbance → dynamic；Observation_Mismatching → dynamic_shift_description；Mix → 两者都开；
  Ideal、Memory_Execution、Memory_Exploration → 都不开。

描述错位（shift），与官方一致：
  - episode 从演示中第 2 个子步开始时的状态启动（官方 init_state_idx = 1，即 demo_states[step_ranges[1][0]]）；
  - 第 1 个子步（step 0）的子目标视为已完成，同时从分子和分母中扣除（官方 excludes_forced_completions）。
  - 规划器仍只拿到原任务指令，需要自己从观测中发现部分步骤已经完成。

随机扰动（dynamic），为适配连续执行做了改动：
  - 官方：每个 150 步时间片切换后第 10 步，以 50% 概率选当前子步的相关物体（task_description.json 的 object 字段），
    否则随机选一个无关可动物体，把其 y 坐标设为"初始 y ± 0.15 m"；方向交替，从 −0.15 开始；第 1 段不扰动。
  - 本项目没有固定时间片，改为"当前子步"（未完成子目标中最小的子步号）变化后第 10 个控制步触发；第 1 段同样不扰动。
  - 位移相对当前位置 ±0.15 m。官方的"初始 y ± 0.15 m"依赖其每段重置到演示状态；连续执行时这样设会把已放好的物体拉回原处。
  - 跳过手中物体、不在桌面上的物体（抽屉、储物盒、容器内）、上面还压着其他物体的物体。目标位置越出桌面
    或落入固定装置占地范围时改用反方向；两边都不行就换一个物体；都不行则本次不扰动（记入日志）。
"""
from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
import numpy as np

SHIFT_TYPES = ("Observation_Mismatching", "Mix")
DYNAMIC_TYPES = ("Random_Disturbance", "Mix")
DY = 0.15
TRIGGER_DELAY_STEPS = 10


def shift_precomplete_counts(case, start_step: int = 1) -> Dict[str, int]:
    """描述错位：每个物体链开头属于 start_step 之前各子步的子目标数（视为已完成并扣出分母）。"""
    counts = {}
    for obj, steps in case.goal_steps.items():
        k = 0
        while k < len(steps) and steps[k] < start_step:
            k += 1
        if k: counts[obj] = k
    return counts


def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


class RCDynamics:
    def __init__(self, case, seed: int = 0):
        self.case = case
        self.shift = case.task_type in SHIFT_TYPES
        self.dynamic = case.task_type in DYNAMIC_TYPES
        self.rng = np.random.default_rng(10007 + int(seed))
        self.toggle = -1
        self.cur_step: Optional[int] = None
        self.trigger_t: Optional[int] = None
        self.start_step = 0
        self.excluded = 0
        self.precompleted: Dict[str, int] = {}
        self.log: List[Dict[str, Any]] = []
        self._inited = False
        try:
            self.json_objects = [str(d.get("object", "")) for d in json.load(open(case.dir / "task_description.json"))]
        except Exception:
            self.json_objects = []

    # ---------- 描述错位 ----------
    def apply_start(self, env, scorer) -> int:
        """把仿真状态设为演示中第 2 个子步开始时的状态，并把第 1 个子步的子目标记为已完成（扣出分母）。返回扣除的子目标数。"""
        if not self.shift:
            return 0
        if self.case.demo_states is None or len(self.case.step_ranges) < 2:
            raise RuntimeError(f"{self.case.task_type}/{self.case.name}: 描述错位需要演示状态与至少 2 个子步")
        frame = int(self.case.step_ranges[1][0])
        env.sim.set_state_from_flattened(self.case.demo_states[frame]); env.sim.forward()
        self.start_step = 1
        counts = shift_precomplete_counts(self.case)
        scorer.precomplete(counts)
        self.precompleted = counts; self.excluded = int(sum(counts.values()))
        self.log.append({"type": "shift_start", "frame": frame, "precompleted": counts})
        return self.excluded

    def sync_executor(self, ex) -> None:
        """描述错位：演示中第 2 个子步开始时夹爪可能正拿着物体；按物理接触同步执行器的手持状态，静置时保持闭合。"""
        if not self.shift:
            return
        for o in ex.env.objects_dict:
            try:
                if ex.checker._in_hand(o):
                    ex.held = o; ex.gripper = 1.0
                    # 恢复仿真状态只恢复手指位置；夹爪控制器内部的指令值（不在仿真状态里）仍是重置后的"张开"，
                    # 不同步的话接下来几步手指会先张开、物体掉落。robosuite Panda 夹爪闭合 = [-1, +1]
                    g = getattr(ex.env.robots[0], "gripper", None)
                    if g is not None and hasattr(g, "current_action"): g.current_action = np.array([-1.0, 1.0])
                    ex.held_drop = float(ex.eef()[2] - ex.obj_zrange(o)[0])
                    self.log.append({"type": "shift_held", "object": o}); return
            except Exception:
                continue

    # ---------- 随机扰动 ----------
    def current_step(self, scorer) -> Optional[int]:
        """未完成子目标中最小的子步号；全部完成时返回 None。"""
        rep = scorer.rep; best = None
        for obj, states in rep.goal.items():
            steps = self.case.goal_steps.get(obj, [])
            L = rep.explore_prefix_len(states); pd = rep._pdone.get(obj, set())
            idx = next((i for i in range(L) if i not in pd), None)
            if idx is None:
                k = max(rep._progress.get(obj, 0), L)
                idx = k if k < len(states) else None
            if idx is not None and idx < len(steps):
                best = steps[idx] if best is None else min(best, steps[idx])
        return best

    def tick(self, env, ex, scorer, t: int, log_fn=None) -> None:
        if not self.dynamic:
            return
        step = self.current_step(scorer)
        if not self._inited:                                        # 第 1 段：只记录当前子步，不触发
            self._inited = True; self.cur_step = step; self.log.append({"type": "dyn_init", "step": step, "t": t}); return
        if step != self.cur_step:
            self.cur_step = step
            self.trigger_t = (t + TRIGGER_DELAY_STEPS) if step is not None else None
        if self.trigger_t is not None and t >= self.trigger_t:
            self.trigger_t = None
            rec = self._disturb(env, ex, step, t)
            self.log.append(rec)
            if log_fn is not None: log_fn(rec)

    def _table_bounds(self, env):
        m = env.sim.model
        for r in getattr(env, "regions", []):
            if r.endswith("table_region"):
                sid = m.site_name2id(r); c = env.sim.data.site_xpos[sid]; h = m.site_size[sid]
                Rm = env.sim.data.site_xmat[sid].reshape(3, 3); ext = np.abs(Rm) @ h
                return c[:2] - ext[:2], c[:2] + ext[:2], float(c[2])
        return np.array([-1.0, -1.0]), np.array([1.0, 1.0]), None

    def _eligible(self, env, ex, o: str, table_z) -> bool:
        try:
            if ex.checker._in_hand(o): return False
            lo, hi = ex.obj_zrange(o)
            if table_z is not None and lo > table_z + 0.04: return False          # 不在桌面上（容器、抽屉、架子里）
            if ex.containing_drawer(o) is not None or ex.cubby_containing(o) is not None: return False
            p = ex.obj_pos(o); rb = min(ex.obj_rbound(o), 0.12)
            for q in env.objects_dict:                                         # 上面压着其他物体
                if q == o: continue
                pq = ex.obj_pos(q)
                if np.linalg.norm(pq[:2] - p[:2]) < rb and pq[2] > p[2] + 0.01: return False
            return True
        except Exception:
            return False

    def _target_ok(self, env, ex, o: str, y_new: float, lo_b, hi_b) -> bool:
        p = ex.obj_pos(o); rb = min(ex.obj_rbound(o), 0.12)
        if not (lo_b[1] + rb <= y_new <= hi_b[1] - rb): return False
        q = np.array([p[0], y_new])
        for flo, fhi in ex.fixture_footprints():
            if np.all(q >= flo - rb * 0.5) and np.all(q <= fhi + rb * 0.5): return False
        for other in env.objects_dict:
            if other == o: continue
            po = ex.obj_pos(other)
            if np.linalg.norm(po[:2] - q) < rb + min(ex.obj_rbound(other), 0.12) * 0.7: return False
        return True

    def _disturb(self, env, ex, step: Optional[int], t: int) -> Dict[str, Any]:
        objs = list(env.objects_dict)
        step_names = {_norm(n) for n in self.json_objects if n}
        rel_name = _norm(self.json_objects[step]) if (step is not None and step < len(self.json_objects) and self.json_objects[step]) else ""
        related = [o for o in objs if rel_name and o.rsplit("_", 1)[0] == rel_name]
        unrelated = [o for o in objs if o.rsplit("_", 1)[0] not in step_names]
        lo_b, hi_b, table_z = self._table_bounds(env)
        use_related = self.rng.random() < 0.5
        order = (related + list(self.rng.permutation(unrelated))) if use_related else (list(self.rng.permutation(unrelated)) + related)
        direction = self.toggle; self.toggle *= -1
        for o in order:
            if not self._eligible(env, ex, o, table_z):
                continue
            y0 = float(ex.obj_pos(o)[1])
            for d in (direction, -direction):
                y_new = y0 + DY * d
                if not self._target_ok(env, ex, o, y_new, lo_b, hi_b):
                    continue
                m = env.sim.model; jn = env.objects_dict[o].joints[-1]
                a0 = m.get_joint_qpos_addr(jn)[0]; qv = m.get_joint_qvel_addr(jn)
                env.sim.data.qpos[a0 + 1] += y_new - y0
                env.sim.data.qvel[qv[0]:qv[1]] = 0.0
                env.sim.forward()
                return {"type": "rc_disturbance", "t": t, "step": step, "object": o, "related": o in related,
                        "dy": round(DY * d, 3), "flipped": d != direction}
        return {"type": "rc_disturbance_skipped", "t": t, "step": step, "reason": "no eligible object / target"}
