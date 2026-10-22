"""Phase 1 原型：实时异步仿真环境。

设计（对应计划文档 §5.3 Real-time、§6.3 异步执行、§7.1 真实时间闭环）：
- 仿真在**主线程**按 wall-clock 推进（macOS 离屏渲染需主线程 GL 上下文），每个控制步对齐到 t0 + k·dt/RTR；
  推理期间世界不暂停：无命令时机器人保持当前姿态、物理继续。
- 决策层在工作线程：读取最新观测快照（带 version / sim_time / wall_time），通过命令队列提交技能调用或取消。
- 技能由 ScriptedExecutor 在仿真线程内逐步执行；每步都检查 cancel_flag，因此任何技能都可在一个控制步内被中断
  （中断语义：当前动作停止、夹爪保持、机械臂保持位置；是否放下手中物体由上层决定）。
- 时间戳记录：观测采样、命令提交、技能开始/结束/取消、子目标完成、规划器自报的思考开始/结束；
  实际 RTR（realized real-time rate）与每步滞后分布一并记录。
"""
from __future__ import annotations
import threading, queue, time, json, itertools
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import numpy as np

import rc_env as R
from skills import ScriptedExecutor, SkillResult
from scoring import OriginalScorer, RepairedScorer


class Pacer:
    def __init__(self, control_dt: float, rtr: float = 1.0):
        self.dt, self.rtr = control_dt, rtr
        self.t0 = None; self.k = 0; self.lags: List[float] = []; self.slept = 0.0
    def start(self):
        self.t0 = time.time(); self.k = 0
    def wait_for_tick(self):
        if self.t0 is None: self.start()
        self.k += 1
        target = self.t0 + self.k * self.dt / self.rtr
        lag = time.time() - target
        if lag < 0:
            time.sleep(-lag); self.slept += -lag
        self.lags.append(max(lag, 0.0))
    def realized_rtr(self, sim_time_elapsed: float) -> float:
        wall = time.time() - self.t0 if self.t0 else 1e-9
        return sim_time_elapsed / max(wall, 1e-9)


@dataclass
class Snapshot:
    version: int
    step: int
    sim_time: float
    wall_time: float
    eef_pos: List[float]
    gripper: float
    held: Optional[str]
    current_skill: Optional[str]
    n_done_original: int
    n_done_repaired: int
    objects: Dict[str, List[float]]
    drawers: Dict[str, float] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    agentview: Optional[np.ndarray] = None
    eye_in_hand: Optional[np.ndarray] = None
    hidden: List[str] = field(default_factory=list)   # 不可见物体（位于关闭的抽屉内）：规划器看不到其位置


@dataclass
class Command:
    cid: int
    kind: str                     # "skill" | "cancel" | "stop"
    name: str = ""
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    submitted_wall: float = 0.0
    submitted_sim: float = 0.0
    obs_version: int = -1         # 规划器据以决策的观测版本
    plan_id: Optional[str] = None


class RealtimeSim:
    def __init__(self, case: R.Case, rtr: float = 1.0, camera: bool = True, max_sim_time: float = 300.0,
                 on_tick=None, log_every: int = 20):
        self.case, self.rtr, self.camera, self.max_sim_time = case, rtr, camera, max_sim_time
        self.on_tick = on_tick                     # Phase 2 事件注入钩子: f(sim) 每步调用
        self.cmd_q: "queue.Queue[Command]" = queue.Queue()
        self._cid = itertools.count(1)
        self._latest: Optional[Snapshot] = None
        self._lock = threading.Lock()
        self.events: List[Dict[str, Any]] = []
        self.outcomes: Dict[int, Dict[str, Any]] = {}
        self.running = False
        self.log_every = log_every
        self.version = 0
        self.messages: List[Dict[str, Any]] = []
        self.sim_t0: Optional[float] = None          # episode 开始（静置结束）时的仿真时间；之前事件与日志不生效
        self.cancel_sources: Dict[int, str] = {}     # cid -> 谁取消了它（monitor / planner / environment:...）

    # ---------- 规划器侧 API（线程安全） ----------
    def latest(self) -> Optional[Snapshot]:
        with self._lock: return self._latest
    def submit_skill(self, name: str, *args, obs_version: int = -1, plan_id: Optional[str] = None, **kwargs) -> int:
        cid = next(self._cid)
        snap = self.latest()
        cmd = Command(cid, "skill", name, args, kwargs, time.time(), snap.sim_time if snap else 0.0, obs_version, plan_id)
        self.cmd_q.put(cmd); self.log_event("cmd_submitted", cid=cid, skill=f"{name}{args}", obs_version=obs_version, plan_id=plan_id)
        return cid
    def cancel(self, reason: str = "", source: str = "planner") -> None:
        cur = self.current
        if cur is not None: self.cancel_sources[cur.cid] = source
        self.cmd_q.put(Command(next(self._cid), "cancel", submitted_wall=time.time())); self.log_event("cancel_requested", reason=reason, source=source)
    def stop(self) -> None:
        self.cmd_q.put(Command(next(self._cid), "stop", submitted_wall=time.time()))
    def log_event(self, etype: str, **kw):
        snap = self._latest
        ev = {"type": etype, "wall": time.time(), "sim": snap.sim_time if snap else 0.0, "step": snap.step if snap else 0} | kw
        with self._lock: self.events.append(ev)
    def wait_outcome(self, cid: int, timeout: float = 120.0) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self._lock:
                if cid in self.outcomes: return self.outcomes[cid]
            time.sleep(0.02)
        return None

    # ---------- 仿真侧（主线程） ----------
    def _publish(self, ex: ScriptedExecutor, current_skill: Optional[str]):
        obs = ex.obs if ex.obs is not None else self.env._get_observations()
        objs = {o: list(map(float, obs[f"{o}_pos"])) for o in self.env.objects_dict if f"{o}_pos" in obs}
        drawers = {}
        for r in self.env.regions:
            if any(k in r for k in ("cabinet", "fridge")) and r.endswith("_region"):
                try: drawers[r] = round(float(ex.drawer_geometry(r)[5]), 2)
                except Exception: pass
        hidden = []
        if getattr(self, "hide_closed", True):
            for o in objs:
                r = ex.containing_drawer(o)
                if r is not None and drawers.get(r, 1.0) < 0.3: hidden.append(o)
        self.version += 1
        snap = Snapshot(self.version, ex.t, float(self.env.sim.data.time), time.time(), list(map(float, obs["robot0_eef_pos"])),
                        float(ex.gripper), ex.held, current_skill, int(self.scorer.last[0]), int(self.scorer.last[2]), objs, drawers, list(getattr(self, "messages", [])),
                        R.to_image(obs["agentview_image"]) if self.camera and "agentview_image" in obs else None,
                        R.to_image(obs["robot0_eye_in_hand_image"]) if self.camera and "robot0_eye_in_hand_image" in obs else None, hidden)
        with self._lock: self._latest = snap

    def run(self, planner_thread: Optional[threading.Thread] = None):
        """阻塞运行：直到 stop 命令、全部完成或超过 max_sim_time。planner_thread 若给出则在此处启动。"""
        from run_gt_plan import DualScorer
        self.env = R.make_env(self.case, use_camera_obs=self.camera); self.env.reset()
        if self.case.init_state is not None: R.apply_state(self.env, self.case.init_state)
        self.scorer = DualScorer(self.env, self.case.goal)
        dyn = getattr(self, "dynamics", None)                     # RoboCerebra 动态条件（rc_dynamics.RCDynamics）：描述错位 / 随机扰动
        if dyn is not None and dyn.apply_start(self.env, self.scorer):
            self.log_event("rc_shift_start", precompleted=dyn.precompleted)
        self.pacer = Pacer(1.0 / self.env.control_freq, self.rtr)
        self.current: Optional[Command] = None
        state = {"skill": None}
        self.state_log: List[np.ndarray] = []; self.state_log_step: List[int] = []
        def on_step(ex):
            self.pacer.wait_for_tick() if False else None   # 占位：节拍在 step 前完成（见下方 paced_step）
            if self.sim_t0 is not None:                     # 逐步保存仿真状态，供离线重算计分（scoring 与执行解耦）
                self.state_log.append(self.env.sim.get_state().flatten().astype(np.float64)); self.state_log_step.append(ex.t)
            if dyn is not None and self.sim_t0 is not None:
                dyn.tick(self.env, ex, self.scorer, ex.t, log_fn=lambda rec: self.log_event(rec["type"], **{k: v for k, v in rec.items() if k != "type"}))
            self._publish(ex, state["skill"])
            if self.on_tick is not None: self.on_tick(self)
            if ex.t % self.log_every == 0 and self.sim_t0 is not None:
                self.log_event("tick", lag=self.pacer.lags[-1] if self.pacer.lags else 0.0, realized_rtr=self.pacer.realized_rtr(self.env.sim.data.time - self.sim_t0))
            n_r = self.scorer.last[2]
            if n_r > state.get("n_r", 0):
                self.log_event("subgoal_done", repaired=n_r, original=self.scorer.last[0]); state["n_r"] = n_r
            if state["skill"] is not None and self._cancel_pending():
                ex.cancel_flag = True
        ex = ScriptedExecutor(self.env, self.case.goal, on_step=on_step, scorer=self.scorer)
        for _k, _v in getattr(self, "ex_attrs", {}).items(): setattr(ex, _k, _v)   # 执行器消融开关（如 track_targets）
        # 用节拍器包裹 env.step：每个控制步先等 tick
        orig_step = ex.step
        def paced_step(action, skill, event=""):
            self.pacer.wait_for_tick(); return orig_step(action, skill, event)
        ex.step = paced_step
        self.ex = ex
        if dyn is not None: dyn.sync_executor(ex)                  # 描述错位起点夹爪可能正拿着物体
        ex.hold(15, ex.gripper, "settle")
        self.sim_t0 = float(self.env.sim.data.time); self.pacer.start()
        self.running = True; self.log_event("episode_start", rtr=self.rtr)
        if planner_thread is not None: planner_thread.start()
        try:
            while self.running:
                if self.env.sim.data.time - self.sim_t0 > self.max_sim_time:
                    self.log_event("timeout"); break
                if self.scorer.last[3]:
                    self.log_event("all_done"); break
                try:
                    cmd = self.cmd_q.get_nowait()
                except queue.Empty:
                    ex.hold(1, ex.gripper, "idle"); continue        # 无命令：世界继续推进
                if cmd.kind == "stop": self.log_event("stop"); break
                if cmd.kind == "cancel": continue                   # 空闲时的取消：无事可做
                # 执行技能（阻塞仿真线程，但每步按节拍推进并可取消）
                state["skill"] = f"{cmd.name}{cmd.args}"; ex.cancel_flag = False
                self.current = cmd
                self.log_event("skill_started", cid=cmd.cid, skill=state["skill"], queue_delay=time.time() - cmd.submitted_wall)
                fn = getattr(ex, cmd.name, None)
                if fn is None:
                    res = SkillResult(cmd.name, False, "unknown skill", 0, ex.n_done, ex.n_done)
                else:
                    try: res = fn(*cmd.args, **cmd.kwargs)
                    except Exception as e: res = SkillResult(cmd.name, False, f"exception {e!r}"[:200], 0, ex.n_done, ex.n_done)
                # 技能返回后立即发布一帧快照：技能在最后一步之后才更新 ex.held 等状态，
                # 否则规划器拿到结果时读到的仍是技能内部最后一步的旧快照（手中物体过时）
                if res.cancelled and ex.held is not None and not ex.held_in_hand(): ex.held = None   # 被取消时物体可能已离手
                state["skill"] = None; self._publish(ex, None)
                outcome = asdict(res) | {"cid": cmd.cid, "finished_wall": time.time(), "finished_sim": float(self.env.sim.data.time),
                                         "cancel_source": self.cancel_sources.get(cmd.cid) if res.cancelled else None, "snap_version": self.version}
                with self._lock: self.outcomes[cmd.cid] = outcome
                self.log_event("skill_finished" if not res.cancelled else "skill_cancelled", cid=cmd.cid, skill=state["skill"], ok=res.ok, reason=res.reason, steps=res.steps)
                state["skill"] = None; self.current = None; ex.cancel_flag = False
        finally:
            self.running = False
            self.log_event("episode_end", realized_rtr=self.pacer.realized_rtr(self.env.sim.data.time - self.sim_t0),
                           lag_p50=float(np.percentile(self.pacer.lags, 50)) if self.pacer.lags else 0.0,
                           lag_p95=float(np.percentile(self.pacer.lags, 95)) if self.pacer.lags else 0.0)

    def _cancel_pending(self) -> bool:
        """技能执行中检查队列头部是否有 cancel（不消费其它命令）。"""
        try:
            with self.cmd_q.mutex:
                items = list(self.cmd_q.queue)
            for it in items:
                if it.kind == "cancel":
                    with self.cmd_q.mutex:
                        self.cmd_q.queue.remove(it)
                    self.log_event("cancel_applied", cid=self.current.cid if self.current else None)
                    return True
        except Exception:
            pass
        return False

    def dump(self, path):
        try:
            from pathlib import Path as _P
            if getattr(self, "state_log", None):
                np.savez_compressed(_P(path).with_name("states.npz"), states=np.stack(self.state_log), steps=np.array(self.state_log_step),
                                    sim_t0=np.array([self.sim_t0]))
        except Exception as e:
            print("state log save failed:", e)
        json.dump({"case": f"{self.case.task_type}/{self.case.name}", "rtr": self.rtr, "events": self.events,
                   "outcomes": self.outcomes, "final": {"original": self.scorer.last[0], "repaired": self.scorer.last[2], "n_goals": self.case.n_goals}},
                  open(path, "w"), indent=1, default=str)
