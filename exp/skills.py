"""脚本化技能执行器（固定底层控制器原型）。

设计原则（对应计划文档 §4.1）：
- 使用特权仿真状态（物体/区域位姿）做 OSC_POSE 比例控制，确定性、可复现；
- 技能消耗真实仿真步、可失败、可中断（每个控制步都检查 cancel 标志）；
- 不替决策层做任何任务排序/选择；
- 每一步调用一次官方成功监控器（只能调用一次/步），并记录时间戳供异步评测使用。
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

OPEN, CLOSE = -1.0, 1.0
POS_SCALE = 0.05      # OSC_POSE output_max：输入 1.0 → 每步 0.05 m
Z_SAFE_MIN = 0.70     # 咖啡桌场景的默认安全搬运高度（桌面 ≈0.42，储物盒顶 ≈0.60）


@dataclass
class StepRecord:
    t: int
    sim_time: float
    wall_time: float
    skill: str
    action: List[float]
    eef_pos: List[float]
    n_done: int
    event: str = ""


@dataclass
class SkillResult:
    name: str
    ok: bool
    reason: str
    steps: int
    n_done_before: int
    n_done_after: int
    cancelled: bool = False


class ScriptedExecutor:
    def __init__(self, env, goal, log: Optional[List[StepRecord]] = None, on_step: Optional[Callable] = None,
                 kp: float = 1.0, max_speed: float = 1.0, scorer=None):
        self.env, self.goal = env, goal
        self.scorer = scorer              # 需提供 update() -> (completion, n_done, all_done)；None 则用官方监控器
        self.held: Optional[str] = None
        self.held_drop: float = 0.05
        from scoring import RepairedScorer
        self.checker = RepairedScorer(env, {})   # 仅用其几何谓词做技能后置条件检查，不含任何任务目标
        self.log = log if log is not None else []
        self.on_step = on_step            # 每步回调（异步版本中用于推送观测）
        self.kp, self.max_speed = kp, max_speed
        self.t = 0
        self.cancel_flag = False
        self.n_done = 0
        self.obs = None
        self.gripper = OPEN
        # r3：所有绝对高度按机器人底座高度平移（经验常数来自咖啡桌场景，底座 z=0.41；厨房桌场景底座 z≈0.91，整套工作空间抬高约 0.5 m）
        self.zoff = self._base_z() - self.BASE_Z_REF
        self.Z_SAFE_MIN = Z_SAFE_MIN + self.zoff
        self.Z_SAFE_MAX = type(self).Z_SAFE_MAX + self.zoff
        self.HOME = type(self).HOME + np.array([0.0, 0.0, self.zoff])

    BASE_Z_REF = 0.41          # 咖啡桌场景机器人底座高度（各高度经验常数的参照）

    def _base_z(self) -> float:
        m = self.env.sim.model
        for n in ("robot0_base", "robot0_link0"):
            try:
                bid = m.body_name2id(n)
            except Exception:
                continue
            z = float(self.env.sim.data.body_xpos[bid][2])
            if z == 0.0:
                self.env.sim.forward(); z = float(self.env.sim.data.body_xpos[bid][2])
            return z
        return self.BASE_Z_REF

    # ---------- 基础 ----------
    def refresh(self):
        self.obs = self.env._get_observations()
        return self.obs

    def eef(self) -> np.ndarray:
        return np.array(self.env._get_observations()["robot0_eef_pos"])

    def obj_pos(self, name: str) -> np.ndarray:
        return np.array(self.env._get_observations()[f"{name}_pos"])

    def site_pos(self, site: str) -> np.ndarray:
        sid = self.env.sim.model.site_name2id(site)
        return np.array(self.env.sim.data.site_xpos[sid])

    def site_size(self, site: str) -> np.ndarray:
        sid = self.env.sim.model.site_name2id(site)
        return np.array(self.env.sim.model.site_size[sid])

    def step(self, action: List[float], skill: str, event: str = "") -> Tuple[dict, int]:
        self.obs, _, _, _ = self.env.step(list(action))
        if self.scorer is None:
            _, self.n_done, _ = self.env._check_success(self.goal)
        else:
            _, self.n_done, _ = self.scorer.update()
        self.t += 1
        self.log.append(StepRecord(self.t, float(self.env.sim.data.time), time.time(), skill, list(map(float, action)),
                                   list(map(float, self.obs["robot0_eef_pos"])), int(self.n_done), event))
        if self.on_step is not None:
            self.on_step(self)
        return self.obs, self.n_done

    def hold(self, n: int, gripper: float, skill: str):
        for _ in range(n):
            if self.cancel_flag: return False
            self.step([0, 0, 0, 0, 0, 0, gripper], skill)
        return True

    def move_to(self, target: np.ndarray, gripper: float, skill: str, tol: float = 0.01,
                max_steps: int = 120, z_first: bool = False, stall_steps: int = 15, stall_eps: float = 0.0015) -> bool:
        """比例控制移动末端到 target；z_first=True 时先调 z 再调 xy（避免扫到物体）。
        连续 stall_steps 步位移 < stall_eps 视为被挡住（self.last_stalled=True）并提前返回。"""
        self.last_stalled = False
        hist = []
        for _ in range(max_steps):
            if self.cancel_flag: return False
            cur = self.eef()
            err = target - cur
            if np.linalg.norm(err) < tol:
                return True
            hist.append(cur)
            if len(hist) > stall_steps and np.linalg.norm(hist[-1] - hist[-1 - stall_steps]) < stall_eps:
                self.last_stalled = True
                return False
            d = np.clip(self.kp * err / POS_SCALE, -self.max_speed, self.max_speed)
            if z_first and abs(err[2]) > 0.02:
                d[:2] = 0.0
            self.step([*d, 0, 0, 0, gripper], skill)
        return bool(np.linalg.norm(target - self.eef()) < tol * 2)


    # ---------- 分段运动辅助 ----------
    Z_SAFE_MAX = 0.72     # 本场景末端可稳定到达的高度上限（经验值，超过则接近臂展极限易停滞）

    def safe_z(self, *targets_top: float) -> float:
        """安全搬运高度：至少 Z_SAFE_MIN，且高于所有给定障碍顶面 + 余量，但不超过 Z_SAFE_MAX。"""
        z = self.Z_SAFE_MIN
        for t in targets_top:
            z = max(z, t + 0.10)
        return min(z, self.Z_SAFE_MAX)

    CLEAR_LOCAL_OBSTACLE = True    # 第二轮：搬运高度同时越过末端当前所在的敞口容器（如放置被取消后停在储物盒上方）

    def safe_z_for(self, target_xy, *targets_top: float) -> float:
        """远目标（到基座 > 0.62 m）降低安全高度到 0.62，低于 0.62 的障碍顶面仍要让开。
        起点障碍：末端当前位于非抽屉的敞口容器上方时，手持物体的底部也要高出容器顶面。"""
        z = self.safe_z(*targets_top)
        if np.linalg.norm(np.asarray(target_xy)[:2] - self.base_xy()) > 0.62:
            z = min(z, max(0.62 + self.zoff, *[t + 0.08 for t in targets_top] if targets_top else [0.62 + self.zoff]))
        if self.CLEAR_LOCAL_OBSTACLE:
            lt = self.local_top_z(self.eef()[:2])
            if lt is not None:
                z = max(z, min(lt + (self.held_drop if self.held is not None else 0.0) + 0.04, self.Z_SAFE_MAX))
        return z

    FAR_PICK_HOME = True       # 第二轮：抓取离基座 > 0.65 m 的物体前先回标准姿态
    TABLE_NEAR_DROP = True    # 第二轮：放到桌面区域时选末端附近的空闲可达点，而不是 2 m 见方区域的正中心

    def table_drop_point(self, region_site: str, center: np.ndarray) -> np.ndarray:
        """桌面区域内、离末端当前位置最近的放置点：到基座 0.30–0.60 m（可稳定到达）、不在其他区域（储物盒等）范围内、
        离其他物体至少 10 cm。找不到则退回区域中心。"""
        m = self.env.sim.model; hs = self.site_size(region_site); eef = self.eef(); base = self.base_xy()
        others = self.fixture_footprints(exclude=region_site.rsplit("_", 2)[0])     # 柜子、盒子等装置的实际几何外框（含拉出的抽屉）
        rh = min(self.obj_rbound(self.held), 0.08) if self.held is not None else 0.04
        objs = [(self.obj_pos(o)[:2], min(self.obj_rbound(o), 0.10)) for o in self.env.objects_dict if o != self.held]
        best, best_cost = None, 1e9
        for dx in np.arange(-0.40, 0.401, 0.04):
            for dy in np.arange(-0.40, 0.401, 0.04):
                pxy = np.array([eef[0] + dx, eef[1] + dy])
                if abs(pxy[0] - center[0]) > hs[0] - 0.05 or abs(pxy[1] - center[1]) > hs[1] - 0.05: continue
                if not (0.30 <= np.linalg.norm(pxy - base) <= 0.60): continue
                if any(lo_[0] - 0.08 <= pxy[0] <= hi_[0] + 0.08 and lo_[1] - 0.08 <= pxy[1] <= hi_[1] + 0.08 for lo_, hi_ in others): continue
                if any(np.linalg.norm(pxy - q) < max(0.10, rq + rh + 0.02) for q, rq in objs): continue
                cost = float(np.linalg.norm(pxy - eef[:2])) + 0.5 * float(np.linalg.norm(pxy - self.HOME[:2]))   # 同时偏向机械臂舒适区
                if cost < best_cost: best, best_cost = pxy, cost
        return center if best is None else np.array([best[0], best[1], center[2]])

    def retreat_if_needed(self, gripper: float, skill: str) -> None:
        """技能开始时若手中物体（或空夹爪）低于末端所在敞口容器的顶面（例如上一个放置在下降途中被取消），
        先竖直抬到能越过顶面的高度，再朝基座方向水平退出 15 cm，避免在伸直姿态下直接长距离搬运而停滞。"""
        if not self.CLEAR_LOCAL_OBSTACLE: return
        e = self.eef()
        # 末端在前后开口的储物盒里面（顶板以下）：沿开口方向水平退出，不能竖直上抬（会撞顶板）
        for fx in sorted({r.rsplit("_", 2)[0] for r in getattr(self.env, "regions", []) if "storage_box" in r}):
            try:
                c, op, lat, half_d, half_w, floor, ceil = self.cubby_frame(f"{fx}_bottom_side")
            except Exception:
                continue
            rel = e[:2] - c[:2]; along = float(np.dot(rel, op[:2])); across = float(np.dot(rel, lat[:2]))
            if abs(across) <= half_w + 0.03 and abs(along) <= half_d + 0.06 and e[2] < ceil:
                out = c[:2] + op[:2] * (half_d + self.CUBBY_STAGE) + lat[:2] * across
                self.move_to(np.array([out[0], out[1], e[2]]), gripper, skill, tol=0.02, max_steps=80)
                break
        if float(np.arccos(np.clip(-self.approach_axis()[2], -1, 1))) > 0.3:
            self.restore_topdown(gripper, skill)                    # 上一个技能留下的倾斜姿态
        e = self.eef(); lt = self.local_top_z(e[:2])
        if lt is None: return
        drop = self.held_drop if self.held is not None else 0.0
        if e[2] - drop >= lt + 0.02: return
        z_clear = min(lt + drop + 0.04, self.Z_SAFE_MAX)
        self.move_z(z_clear, gripper, skill, tol=0.015, max_steps=60)
        v = self.base_xy() - self.eef()[:2]; n = float(np.linalg.norm(v))
        if n > 1e-6:
            q = self.eef()[:2] + 0.15 * v / n
            self.move_to(np.array([q[0], q[1], max(self.eef()[2], z_clear)]), gripper, skill, tol=0.02, max_steps=60)

    DRAWER_FRONT_FRAC = 0.4    # 第二轮：放入抽屉时沿拉出方向外移半深度的这一比例
    CUBBY_SIDE_INSERT = True   # 第二轮：白色储物盒是前后开口的方框（顶板 + 底板 + 左右侧板），按人类演示从开口水平送入
    CUBBY_TILT_DEG = 80        # 演示中送入时夹爪偏离竖直 74–93°
    CUBBY_STAGE = 0.13         # 开口外的预备距离
    CUBBY_INSERT = 0.02        # 松手时末端伸入开口的深度（手指主体留在盒外才能张开：盒内宽 ≈ 12 cm，张开的手指会碰到侧板）
    CUBBY_OPEN_STEPS = 20      # 松手后等手指完全张开再退出（否则物体会被手指带出盒口）

    def cubby_frame(self, region_site: str):
        """储物盒几何：(底板站点中心, 开口轴(指向机器人一侧), 横向轴(指向 left_side), 半深, 半宽, 底板上表面 z, 顶板下表面 z)。"""
        fx = region_site.rsplit("_", 2)[0]
        m = self.env.sim.model; d = self.env.sim.data
        sid = m.site_name2id(f"{fx}_bottom_side"); c = d.site_xpos[sid].copy(); R_ = d.site_xmat[sid].reshape(3, 3); hs = m.site_size[sid]
        lx = d.site_xpos[m.site_name2id(f"{fx}_left_side")] - d.site_xpos[m.site_name2id(f"{fx}_right_side")]
        lat = np.array([lx[0], lx[1], 0.0]); lat /= (np.linalg.norm(lat) + 1e-9)
        op = np.array([-lat[1], lat[0], 0.0])                      # 与侧板连线垂直的水平方向 = 开口方向
        if np.dot(op[:2], self.base_xy() - c[:2]) < 0: op = -op     # 用朝向机器人基座一侧的开口
        half_w = float(abs(np.dot(R_[:, 0], lat)) * hs[0] + abs(np.dot(R_[:, 1], lat)) * hs[1])
        half_d = float(abs(np.dot(R_[:, 0], op)) * hs[0] + abs(np.dot(R_[:, 1], op)) * hs[1])
        floor = float(c[2] + 0.01)
        ceil = float(d.site_xpos[m.site_name2id(f"{fx}_top_side")][2] - 0.013)
        return c, op, lat, half_d, half_w, floor, ceil

    CUBBY_MODE = "kinematic"   # "kinematic"（抽象技能，见下）| "physical"（倾斜夹爪物理送入，盒口过窄、成功率不稳定，开发中）

    def _cubby_kinematic(self, region_site: str, name: str, before: int, t0: int, anim_steps: int = 30) -> SkillResult:
        """抽象技能（ABSTRACT）：机械臂竖直夹持把物体真实搬到盒口前方 10 cm 并降到底板高度，松手的同时
        把物体位姿在 anim_steps 步内线性推到盒子中央（底板上方），速度置零；每步照常走物理与计分，可取消。
        原因：盒内宽约 12 cm，张开的手指会碰到侧板，人类演示用倾斜夹爪伸入开口，脚本化复现不稳定。"""
        def fail(why):
            return SkillResult(name, False, why, self.t - t0, before, self.n_done, self.cancel_flag)
        try:
            c, op, lat, half_d, half_w, floor, ceil = self.cubby_frame(region_site)
        except Exception as e:
            return fail(f"cubby geometry unavailable ({e!r})"[:80])
        obj = self.held
        lo, hi = self.obj_zrange(obj)
        if hi - lo > ceil - floor - 0.01:
            return fail(f"{obj} too tall for the box opening (ABSTRACT cubby)")
        stage = c[:2] + op[:2] * (half_d + 0.10)
        self.retreat_if_needed(CLOSE, name)
        zs = self.safe_z_for(np.array([stage[0], stage[1], 0.0]), self.fixture_top_z(region_site) + self.held_drop)
        if not self.move_z(zs, CLOSE, name): return fail("raise failed")
        if not self.transport_xy(np.array([stage[0], stage[1], zs]), CLOSE, name, zs) or self.cancel_flag:
            return fail(("cancelled" if self.cancel_flag else "transport failed") + " (ABSTRACT cubby) " + self.err_str(np.array([stage[0], stage[1], zs])) + f" stalled={self.last_stalled}")
        z_low = floor + 0.01 + self.held_drop                           # 物体底面与底板齐平略高
        self.move_to(np.array([stage[0], stage[1], z_low]), CLOSE, name, tol=0.015, max_steps=80)
        if self.cancel_flag:                                            # 尚未松手：物体仍在手中
            return fail("cancelled (ABSTRACT cubby)")
        m = self.env.sim.model; jn = self.env.objects_dict[obj].joints[-1]
        qa = m.get_joint_qpos_addr(jn); qv = m.get_joint_qvel_addr(jn); a0 = qa[0]
        p0 = np.array(self.env.sim.data.qpos[a0:a0 + 3]); lo, hi = self.obj_zrange(obj)
        # 落点：按目标侧横向错开（left / right / bottom = 中央），被其他物体占据时沿进深方向挪动；物体底面落在底板上方 5 mm
        side = region_site.rsplit("_", 2)[1]
        lat_off = {"left": 1.0, "right": -1.0}.get(side, 0.0) * max(half_w - 0.03, 0.0)
        others = [self.obj_pos(o)[:2] for o in self.env.objects_dict if o != obj]
        spot = None
        for lo_ in (lat_off, 0.0, max(half_w - 0.03, 0.0), -max(half_w - 0.03, 0.0)):
            for dd in (0.0, -0.03, 0.025):
                q = c[:2] + lat[:2] * lo_ + op[:2] * dd
                if all(np.linalg.norm(q - o2) > 0.05 for o2 in others): spot = q; break
            if spot is not None: break
        spot = c[:2] + lat[:2] * lat_off if spot is None else spot
        p1 = np.array([spot[0], spot[1], p0[2] + (floor + 0.005 - lo)])
        self.held = None; self.gripper = OPEN
        for i in range(1, anim_steps + 1):
            if self.cancel_flag:
                return SkillResult(name, False, "cancelled (ABSTRACT cubby)", self.t - t0, before, self.n_done, True)
            self.env.sim.data.qpos[a0:a0 + 3] = p0 + (p1 - p0) * i / anim_steps
            self.env.sim.data.qvel[qv[0]:qv[1]] = 0.0
            self.step([0, 0, 0, 0, 0, 0, OPEN], name, event="abstract_cubby")
        for _ in range(6):                                              # 保持数步再交还物理
            self.env.sim.data.qpos[a0:a0 + 3] = p1; self.env.sim.data.qvel[qv[0]:qv[1]] = 0.0
            self.step([0, 0, 0, 0, 0, 0, OPEN], name, event="abstract_cubby")
        self.move_z(zs, OPEN, name, tol=0.015, max_steps=80)
        ok = bool(self.checker.in_relaxed(obj, region_site))
        return SkillResult(name, ok, "ok ABSTRACT cubby" if ok else f"{obj} not in {region_site} (ABSTRACT cubby)", self.t - t0, before, self.n_done, self.cancel_flag)

    def cubby_containing(self, obj: str):
        """物体若在前后开口的储物盒内（顶板以下、底板范围内），返回该盒的 bottom_side 站点名。"""
        p = self.obj_pos(obj)
        for fx in sorted({r.rsplit("_", 2)[0] for r in getattr(self.env, "regions", []) if "storage_box" in r}):
            try:
                c, op, lat, half_d, half_w, floor, ceil = self.cubby_frame(f"{fx}_bottom_side")
            except Exception:
                continue
            rel = p[:2] - c[:2]
            if abs(float(np.dot(rel, lat[:2]))) <= half_w + 0.01 and abs(float(np.dot(rel, op[:2]))) <= half_d + 0.01 and floor - 0.02 <= p[2] < ceil:
                return f"{fx}_bottom_side"
        return None

    def _cubby_pick_kinematic(self, obj: str, region_site: str, name: str, before: int, t0: int, anim_steps: int = 30) -> SkillResult:
        """抽象技能（ABSTRACT）：取出储物盒内的物体。机械臂竖直姿态移到盒口前方 10 cm、降到物体高度并张开夹爪，
        物体位姿在 anim_steps 步内线性移到两指之间，随后闭合夹持、抬起（与 _cubby_kinematic 对称）。"""
        def fail(why):
            return SkillResult(name, False, why, self.t - t0, before, self.n_done, self.cancel_flag)
        c, op, lat, half_d, half_w, floor, ceil = self.cubby_frame(region_site)
        p0 = self.obj_pos(obj); across = float(np.dot(p0[:2] - c[:2], lat[:2]))
        stage = c[:2] + op[:2] * (half_d + 0.10) + lat[:2] * across
        self.retreat_if_needed(OPEN, name)
        zs = self.safe_z_for(np.array([stage[0], stage[1], 0.0]), self.fixture_top_z(region_site) + 0.05)
        if not self.move_z(zs, OPEN, name): return fail("raise failed")
        if not self.transport_xy(np.array([stage[0], stage[1], zs]), OPEN, name, zs) or self.cancel_flag:
            return fail(("cancelled" if self.cancel_flag else "approach failed") + " (ABSTRACT cubby pick)")
        z_g = float(p0[2] + self.GRASP_OFFSETS.get(obj.rsplit("_", 1)[0], (0.0, 0.0, 0.0))[2])
        self.move_to(np.array([stage[0], stage[1], max(z_g, floor + 0.02)]), OPEN, name, tol=0.015, max_steps=80)
        if self.cancel_flag: return fail("cancelled (ABSTRACT cubby pick)")
        m = self.env.sim.model; jn = self.env.objects_dict[obj].joints[-1]
        a0 = m.get_joint_qpos_addr(jn)[0]; qv = m.get_joint_qvel_addr(jn)
        q0 = np.array(self.env.sim.data.qpos[a0:a0 + 3]); target = q0 + (self.eef() - self.obj_pos(obj))   # 物体中心移到两指之间
        for i in range(1, anim_steps + 1):
            if self.cancel_flag: return fail("cancelled (ABSTRACT cubby pick)")
            self.env.sim.data.qpos[a0:a0 + 3] = q0 + (target - q0) * i / anim_steps
            self.env.sim.data.qvel[qv[0]:qv[1]] = 0.0
            self.step([0, 0, 0, 0, 0, 0, OPEN], name, event="abstract_cubby")
        for _ in range(10):                                              # 闭合夹持（期间保持物体位置）
            self.env.sim.data.qpos[a0:a0 + 3] = target; self.env.sim.data.qvel[qv[0]:qv[1]] = 0.0
            self.step([0, 0, 0, 0, 0, 0, CLOSE], name, event="abstract_cubby")
        self.gripper = CLOSE
        z_before = float(self.obj_pos(obj)[2])
        self.move_z(zs, CLOSE, name, tol=0.015, max_steps=100)
        rb = self.obj_rbound(obj)
        ok = bool(np.linalg.norm(self.obj_pos(obj) - self.eef()) < max(0.06, min(rb, 0.12) + 0.03) and self.obj_pos(obj)[2] > z_before + 0.02)
        self.held = obj if ok else None
        if ok: self.held_drop = float(self.eef()[2] - self.obj_zrange(obj)[0])
        return SkillResult(name, ok, "ok ABSTRACT cubby" if ok else "object not in hand (ABSTRACT cubby pick)", self.t - t0, before, self.n_done, self.cancel_flag)

    DRAWER_PICK_MODE = "kinematic"   # r3："kinematic"（抽象技能，见 _drawer_pick_kinematic）| "physical"（竖直下抓）

    def short_axis_yaw(self, obj: str):
        """使手指闭合方向沿物体水平最窄方向的末端 yaw（yaw=0 时闭合方向为世界 y）；水平截面近似圆形时返回 None。"""
        m = self.env.sim.model; d = self.env.sim.data; bid = self.env.obj_body_id[obj]; pts = []
        for g in range(m.ngeom):
            if m.geom_bodyid[g] != bid or m.geom_contype[g] == 0: continue
            c = d.geom_xpos[g]
            if m.geom_type[g] == 6:
                Rg = d.geom_xmat[g].reshape(3, 3)
                pts += [c + Rg @ (m.geom_size[g] * np.array([sx, sy, sz])) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]   # 8 个角点（盒子局部 z 不一定竖直）
            else:
                r = float(m.geom_rbound[g]); pts += [c + np.array([r * np.cos(a), r * np.sin(a), 0.0]) for a in np.linspace(0, np.pi, 6, endpoint=False)]
        if not pts: return None
        xy = np.array(pts)[:, :2]; angs = np.radians(np.arange(0, 180, 5))
        w = [float(np.ptp(xy @ np.array([np.cos(a), np.sin(a)]))) for a in angs]
        if max(w) < 1.15 * min(w): return None
        return float(angs[int(np.argmin(w))] - np.pi / 2)

    def _drawer_pick_kinematic(self, obj: str, drawer: str, name: str, before: int, t0: int, anim_steps: int = 30) -> SkillResult:
        """抽象技能（ABSTRACT）：取出已拉开抽屉内的物体。机械臂在安全高度悬停于抓取点上方、张开夹爪，
        物体位姿在 anim_steps 步内线性移到两指之间，随后闭合夹持并确认在手中（与 _cubby_pick_kinematic 对称）。
        原因：抽屉内空间受侧板、柜体顶板和上层抽屉把手限制，竖直下抓常被手掌或手指挡住；人类演示靠细微倾斜手腕完成，
        脚本化复现不稳定（case6 黄油仅倾斜 -5° 一档可行）。抽屉未拉开或上方抽屉拉开挡住时照常报失败。"""
        def fail(why):
            return SkillResult(name, False, why, self.t - t0, before, self.n_done, self.cancel_flag)
        try:
            frac = self.drawer_geometry(drawer)[5]
        except Exception:
            frac = 1.0
        if frac < 0.5:                                                  # 不透露所在抽屉（记忆探索类任务要求规划器自己记住物体位置）
            why = f"{obj} is not accessible (enclosed)" if frac < 0.3 else f"{obj} is not accessible: its drawer is not open enough"
            return SkillResult(name, False, why, 0, before, before)
        blk = self.drawer_above_open(obj)
        if blk:
            return SkillResult(name, False, "blocked from above: open drawer " + ", ".join(blk) + "; close it first", 0, before, before)
        otype = obj.rsplit("_", 1)[0]; off = self.GRASP_OFFSETS.get(otype)
        if otype in self.GRASP_OFFSETS_LOCAL or (off is not None and np.hypot(off[0], off[1]) > 0.01):
            yaw = self.grasp_yaw(obj)                                   # 把手类：闭合方向垂直于把手；边沿类（碗、盘）：抓拉出方向一侧的前沿
        else:
            yaw = self.short_axis_yaw(obj)                              # 其余：沿水平最窄方向夹持
        yaw = self.eef_yaw() if yaw is None else yaw
        gp = self.grasp_point(obj, yaw)
        if not self.reachable(gp):
            return SkillResult(name, False, f"out of reach (dist to base {np.linalg.norm(gp[:2] - self.base_xy()):.2f} m)", 0, before, before)
        self.retreat_if_needed(OPEN, name)
        zs = self.safe_z_for(gp, self.fixture_top_z(drawer))
        if not self.move_z(zs, OPEN, name): return fail("raise failed")
        self.rotate_yaw_to(self.wrist_yaw_for(yaw), OPEN, name, max_steps=60)
        if not self.transport_xy(np.array([gp[0], gp[1], zs]), OPEN, name, zs) or self.cancel_flag:
            return fail(("cancelled" if self.cancel_flag else "approach failed") + " (ABSTRACT drawer pick) " + self.err_str(np.array([gp[0], gp[1], zs])))
        gp = self.grasp_point(obj, yaw)
        self.move_to(np.array([gp[0], gp[1], zs]), OPEN, name, tol=0.006, max_steps=40); self.hold(3, OPEN, name)   # 对准并停稳
        m = self.env.sim.model; jn = self.env.objects_dict[obj].joints[-1]
        a0 = m.get_joint_qpos_addr(jn)[0]; qv = m.get_joint_qvel_addr(jn)
        q0 = np.array(self.env.sim.data.qpos[a0:a0 + 3]); off = gp - self.obj_pos(obj)
        dest = lambda: self.eef() - off                                  # 物体原点（自由关节位置）的目标：抓取点落在两指之间，每步按当前末端位置重算
        # 物体悬空期间施加与重力相抵的外力（否则每个控制步 50 ms 内自由下落约 1.2 cm，手指合拢前就掉出两指之间）
        bodies = [b for b in range(m.nbody) if (m.body_id2name(b) or "").startswith(obj)]
        def gravcomp(on: bool):
            for b in bodies:
                self.env.sim.data.xfrc_applied[b, :3] = (-m.opt.gravity * m.body_mass[b]) if on else 0.0
        gravcomp(True)
        try:
            for i in range(1, anim_steps + 1):
                if self.cancel_flag: return fail("cancelled (ABSTRACT drawer pick)")
                self.env.sim.data.qpos[a0:a0 + 3] = q0 + (dest() - q0) * i / anim_steps
                self.env.sim.data.qvel[qv[0]:qv[1]] = 0.0
                self.step([0, 0, 0, 0, 0, 0, OPEN], name, event="abstract_drawer_pick")
            for _ in range(10):                                          # 闭合夹持（期间保持物体位置）
                self.env.sim.data.qpos[a0:a0 + 3] = dest(); self.env.sim.data.qvel[qv[0]:qv[1]] = 0.0
                self.step([0, 0, 0, 0, 0, 0, CLOSE], name, event="abstract_drawer_pick")
        finally:
            gravcomp(False)
        self.gripper = CLOSE
        self.hold(max(self.PICK_VERIFY_STEPS, 6), CLOSE, name)
        rb = self.obj_rbound(obj)
        ok = bool(self.checker._in_hand(obj)) and bool(np.linalg.norm(self.obj_pos(obj) - self.eef()) < max(0.06, min(rb, 0.12) + 0.03) + 0.02)
        self.held = obj if ok else None
        if ok: self.held_drop = float(self.eef()[2] - self.obj_zrange(obj)[0])
        return SkillResult(name, ok, "ok ABSTRACT drawer pick" if ok else "object not in hand (ABSTRACT drawer pick)", self.t - t0, before, self.n_done, self.cancel_flag)

    def place_into_cubby(self, region_site: str, name: str, before: int, t0: int, open_steps: int = 10) -> SkillResult:
        """开口外预备 → 夹爪转为近水平朝向盒内 → 降到底板上方 → 水平送入（手掌停在开口处）→ 松手 → 水平退出 → 抬起并恢复竖直。"""
        def fail(why):
            return SkillResult(name, False, why, self.t - t0, before, self.n_done, self.cancel_flag)
        try:
            c, op, lat, half_d, half_w, floor, ceil = self.cubby_frame(region_site)
        except Exception as e:
            return fail(f"cubby geometry unavailable ({e!r})"[:80])
        # 各侧目标都放在盒子横向中央：手指在盒内要沿横向张开，靠近侧板会张不开（演示中 left_side 的黄油也在中央）
        mouth = c[:2] + op[:2] * half_d
        stage = mouth + op[:2] * self.CUBBY_STAGE
        ins = mouth - op[:2] * self.CUBBY_INSERT                     # 末端伸进开口的深度（手掌停在开口处，手掌宽于盒口）
        self.retreat_if_needed(CLOSE, name)
        zs = self.safe_z_for(np.array([stage[0], stage[1], 0.0]), self.fixture_top_z(region_site) + self.held_drop)
        if not self.move_z(zs, CLOSE, name): return fail("raise failed")
        if not self.transport_xy(np.array([stage[0], stage[1], zs]), CLOSE, name, zs):
            return fail("transport failed " + self.err_str(np.array([stage[0], stage[1], zs])) + f" stalled={self.last_stalled}")
        # 先绕竖直轴转腕，使手指开合方向（末端 y 轴）沿盒子横向；随后的倾斜绕横向轴进行，手指方向保持横向，
        # 否则手指在盒内竖直张开会抵住顶板和底板而松不开手
        yax = self.eef_rotmat()[:, 1]
        ang = float(np.arctan2(lat[1], lat[0]) - np.arctan2(yax[1], yax[0])); ang = (ang + np.pi / 2) % np.pi - np.pi / 2
        self.rotate_yaw_to(self.eef_yaw() + ang, CLOSE, name, max_steps=60)
        th = np.radians(self.CUBBY_TILT_DEG)
        app = -op * np.sin(th) + np.array([0.0, 0.0, -np.cos(th)])
        if not self.rotate_approach_to(app, CLOSE, name, max_steps=80):
            self.restore_topdown(CLOSE, name); return fail("rotate failed")
        lo, hi = self.obj_zrange(self.held)
        z_ins = floor + 0.015 + float(self.eef()[2] - lo)               # 物体底面在底板上方 1.5 cm
        if hi - lo > ceil - floor - 0.01:
            self.restore_topdown(CLOSE, name); return fail(f"{self.held} too tall for the box opening")
        if not self.move_to(np.array([stage[0], stage[1], z_ins]), CLOSE, name, tol=0.012, max_steps=100) \
                and np.linalg.norm(self.eef() - np.array([stage[0], stage[1], z_ins])) > 0.025:
            self.restore_topdown(CLOSE, name); return fail("lower failed " + self.err_str(np.array([stage[0], stage[1], z_ins])))
        reached = self.move_to(np.array([ins[0], ins[1], z_ins]), CLOSE, name, tol=0.012, max_steps=100)
        if not reached and (self.cancel_flag or np.linalg.norm(self.eef()[:2] - ins) > 0.05):
            return fail("insert failed " + self.err_str(np.array([ins[0], ins[1], z_ins])) + f" stalled={self.last_stalled}")
        if not self.hold(max(open_steps, self.CUBBY_OPEN_STEPS), OPEN, name):
            return SkillResult(name, False, "cancelled", self.t - t0, before, self.n_done, True)
        released = self.held
        self.gripper = OPEN; self.held = None
        g = self.obs["robot0_gripper_qpos"]
        self._dbg = {"pre_release_eef": np.round(self.eef(), 3).tolist(), "after_open_obj": np.round(self.obj_pos(released), 3).tolist(),
                     "finger_gap": round(float(g[0] - g[1]), 3)}
        # 推入：退到物体后方 → 合拢手指 → 用指尖把物体推到盒子中央（前后都开口，不能推过头）
        po = self.obj_pos(released); rb = min(self.obj_rbound(released), 0.07)
        behind = po[:2] + op[:2] * (rb + 0.03); z_push = floor + 0.02                # 指尖贴近底板推物体下部，避免推翻
        self.move_to(np.array([behind[0], behind[1], self.eef()[2]]), OPEN, name, tol=0.015, max_steps=60)
        self.hold(10, CLOSE, name)
        push = float(np.dot(self.obj_pos(released)[:2] - c[:2], op[:2]))       # 物体中心到盒子中心沿开口方向的距离
        if push > 0.005:
            tip = self.eef()[:2] - op[:2] * (float(np.dot(self.eef()[:2] - self.obj_pos(released)[:2], op[:2])) - rb + push)
            self.move_to(np.array([tip[0], tip[1], z_push]), CLOSE, name, tol=0.012, max_steps=80)
        self._dbg["after_push_obj"] = np.round(self.obj_pos(released), 3).tolist()
        self.move_to(np.array([stage[0], stage[1], self.eef()[2]]), CLOSE, name, tol=0.015, max_steps=80)   # 水平退出
        self.gripper = CLOSE
        self._dbg["after_retract_obj"] = np.round(self.obj_pos(released), 3).tolist()
        self.move_z(zs, CLOSE, name, tol=0.015, max_steps=80)
        self.restore_topdown(CLOSE, name); self.hold(5, OPEN, name); self.gripper = OPEN
        ok = bool(released is not None and self.checker.in_relaxed(released, region_site))
        return SkillResult(name, ok, "ok" if ok else f"{released} not in {region_site} after release", self.t - t0, before, self.n_done, self.cancel_flag)

    def fixture_footprints(self, exclude: str = ""):
        """各固定装置（桌子除外）所有几何体的水平外框 [(xy_min, xy_max)]，按当前位姿计算（拉出的抽屉随之变化）。"""
        m = self.env.sim.model; d = self.env.sim.data; out = []
        names = [f for f in getattr(self.env, "fixtures_dict", {}) if "table" not in f and f != exclude]
        for f in names:
            gids = [g for g in range(m.ngeom) if (m.body_id2name(m.geom_bodyid[g]) or "").startswith(f) and m.geom_contype[g] != 0]
            if not gids: continue
            pts = np.array([d.geom_xpos[g][:2] for g in gids]); rb = np.array([m.geom_rbound[g] for g in gids])[:, None]
            out.append(((pts - rb).min(axis=0), (pts + rb).max(axis=0)))
        return out

    SETTLE_SPEED = 0.02        # r2b：抓取前物体线速度低于此值（m/s）才开始，最多等 SETTLE_MAX 步
    SETTLE_MAX = 20

    def obj_speed(self, obj: str) -> float:
        m = self.env.sim.model; qv = m.get_joint_qvel_addr(self.env.objects_dict[obj].joints[-1])
        return float(np.linalg.norm(self.env.sim.data.qvel[qv[0]:qv[0] + 3]))

    def wait_settle(self, obj: str, skill: str) -> None:
        for _ in range(self.SETTLE_MAX):
            if self.cancel_flag or self.obj_speed(obj) < self.SETTLE_SPEED: return
            self.hold(1, self.gripper, skill)

    def drawer_above_open(self, obj: str):
        """物体所在抽屉的上方（同一柜子、更高）拉开的抽屉区域名列表（竖直抓取会被它们挡住）；没有则返回空列表。"""
        r = self.containing_drawer(obj)
        if r is None: return []
        so = self.env.object_sites_dict.get(r); parent = getattr(so, "parent_name", None); z = float(self.site_pos(r)[2]); out = []
        for r2, o2 in self.env.object_sites_dict.items():
            if r2 == r or getattr(o2, "parent_name", None) != parent or not (o2.joints or []): continue
            try:
                if float(self.site_pos(r2)[2]) > z + 0.02 and self.drawer_geometry(r2)[5] > 0.3: out.append(r2)
            except Exception:
                continue
        return sorted(out)

    def contact_bodies(self):
        """机械臂（含夹爪）当前接触到的非机器人物体 / 装置名（不含手中物体）。"""
        m = self.env.sim.model; d = self.env.sim.data; out = set()
        names = list(getattr(self.env, "objects_dict", {})) + list(getattr(self.env, "fixtures_dict", {}))
        for i in range(d.ncon):
            c = d.contact[i]
            b1 = m.body_id2name(m.geom_bodyid[c.geom1]) or ""; b2 = m.body_id2name(m.geom_bodyid[c.geom2]) or ""
            for rb, ob in ((b1, b2), (b2, b1)):
                if rb.startswith(("robot0", "gripper0")) and not ob.startswith(("robot0", "gripper0")):
                    hit = next((n for n in names if ob.startswith(n)), None)
                    if hit and hit != self.held: out.add(hit)
        return sorted(out)

    def blocked_note(self, obj: str = None) -> str:
        """失败原因补充：上方抽屉阻挡、接触到的物体或装置（供规划器理解失败原因）。"""
        notes = []
        if obj is not None:
            blk = self.drawer_above_open(obj)
            if blk: notes.append("blocked from above: open drawer " + ", ".join(blk))
        cb = [n for n in self.contact_bodies() if n != obj]
        if cb: notes.append("touching " + ", ".join(cb))
        return (" (" + "; ".join(notes) + ")") if notes else ""

    def local_top_z(self, xy):
        """末端当前 xy 所在的非抽屉区域（储物盒、篮子等敞口容器）的顶面高度；不在任何此类区域上方则返回 None。"""
        m = self.env.sim.model; best = None
        for r in getattr(self.env, "regions", []):
            if "table_region" in r: continue                                   # 桌面本身不是障碍
            so = self.env.object_sites_dict.get(r)
            if so is not None and (so.joints or []): continue                   # 抽屉：退出路径由抽屉技能处理
            try:
                sid = m.site_name2id(r)
            except Exception:
                continue
            c = self.env.sim.data.site_xpos[sid]; hs = m.site_size[sid]
            if abs(xy[0] - c[0]) <= hs[0] + 0.03 and abs(xy[1] - c[1]) <= hs[1] + 0.03:
                t = self.fixture_top_z(r); best = t if best is None else max(best, t)
        return best

    def fixture_top_z(self, site: str) -> float:
        """用同一固定装置（site 名前缀）的所有站点估计其顶面高度。"""
        prefix = site.rsplit("_", 2)[0] if site.count("_") >= 2 else site
        tops = []
        for n in self.env.sim.model.site_names:
            if n.startswith(prefix):
                sid = self.env.sim.model.site_name2id(n)
                tops.append(float(self.env.sim.data.site_xpos[sid][2] + self.env.sim.model.site_size[sid][2]))
        return max(tops) if tops else float(self.site_pos(site)[2])

    def move_z(self, z: float, gripper: float, skill: str, tol: float = 0.012, max_steps: int = 80) -> bool:
        cur = self.eef(); ok = self.move_to(np.array([cur[0], cur[1], z]), gripper, skill, tol, max_steps)
        return ok or abs(self.eef()[2] - z) < 0.03

    def move_xy(self, x: float, y: float, gripper: float, skill: str, tol: float = 0.012, max_steps: int = 200) -> bool:
        cur = self.eef()
        ok = self.move_to(np.array([x, y, cur[2]]), gripper, skill, tol, max_steps)
        if not ok and self.last_stalled and self.eef()[2] > 0.66 + self.zoff:
            # 高处停滞（接近工作空间边界）：降低 6 cm 再试一次
            z2 = self.eef()[2] - 0.06
            self.move_to(np.array([*self.eef()[:2], z2]), gripper, skill, 0.015, 40)
            ok = self.move_to(np.array([x, y, z2]), gripper, skill, tol, max_steps // 2)
        return ok

    track_targets = False      # True：搬运/下降过程中持续重读目标物体位置（闭环跟踪，"控制层恢复"消融）

    def track_xy(self, target_fn, gripper: float, skill: str, zs: float, tol: float = 0.012, max_steps: int = 220, tol_fail: float = 0.05) -> bool:
        """闭环水平搬运：每步重读目标 xy。"""
        for _ in range(max_steps):
            if self.cancel_flag: return False
            txy = np.asarray(target_fn(), float)[:2]
            cur = self.eef(); err = np.array([txy[0] - cur[0], txy[1] - cur[1], zs - cur[2]])
            if np.linalg.norm(err) < tol: return True
            d = np.clip(self.kp * err / POS_SCALE, -self.max_speed, self.max_speed)
            self.step([*d, 0, 0, 0, gripper], skill)
        return bool(np.linalg.norm(self.eef()[:2] - np.asarray(target_fn(), float)[:2]) <= tol_fail)

    def transport_xy(self, tgt, gripper: float, skill: str, zs: float, tol_fail: float = 0.05) -> bool:
        """水平搬运到 tgt 的 xy；停滞则回中立位、重新抬到 zs 再试一次；最终按 tol_fail 判定。"""
        tgt = np.asarray(tgt, float)
        ok = self.move_xy(tgt[0], tgt[1], gripper, skill)
        if not ok and np.linalg.norm(self.eef()[:2] - tgt[:2]) > tol_fail and self.last_stalled:
            self.go_home(gripper, skill); self.move_z(zs, gripper, skill)
            ok = self.move_xy(tgt[0], tgt[1], gripper, skill)
        return ok or np.linalg.norm(self.eef()[:2] - tgt[:2]) <= tol_fail

    def err_str(self, target: np.ndarray) -> str:
        e = target - self.eef(); return f"err={np.round(e, 3).tolist()}"

    # ---------- 技能 ----------
    PICK_VERIFY_STEPS = 6      # r3：抬起后保持数步、以双指接触或距离确认仍在手中再报告成功（E4.5：碗抬起后滑脱却报告成功）
    PICK_RETRY = 1             # r3：确认失败（滑脱）时自动重抓的次数
    RIM_GAP_STEPS = 3          # r3：抽屉内边沿抓取下降前的闭合步数（每步约 1.5 cm，全开 8 cm → 约 5 cm）；0 = 关闭

    def rim_in_drawer(self, obj: str) -> bool:
        """物体是否为抽屉内、按边沿偏移抓取的物体（碗、盘）。"""
        off = self.GRASP_OFFSETS.get(obj.rsplit("_", 1)[0])
        return bool(off is not None and np.hypot(off[0], off[1]) > 0.01 and self.containing_drawer(obj) is not None)

    def pick(self, obj: str, pre_h: float = 0.10, close_steps: int = 10, descend_tol: float = 0.02, _retry: int = 0) -> SkillResult:
        """抬到安全高度 → 水平移到抓取点上方 → 下降到预抓取（高于物体顶部）→ 下降到抓取点 → 闭合 → 抬到安全高度 → 保持并确认仍在手中。"""
        name = f"pick({obj})"; before = self.n_done; t0 = self.t
        if self.held is not None and not self.held_in_hand():
            self.held = None                                   # 物体已滑落：记录的手持状态作废
        if self.held is not None:
            why = f"already holding {obj}" if self.held == obj else f"hand busy (holding {self.held}); put it down first"
            return SkillResult(name, False, why, 0, before, before)
        try:
            self.wait_settle(obj, name)                                  # r2b：物体仍在运动（如抽屉刚拉开）时先等其停稳
        except KeyError:
            return SkillResult(name, False, "unknown object", 0, before, before)
        try:
            yaw_t = self.grasp_yaw(obj); yaw_eff = 0.0 if yaw_t is None else yaw_t
            gp = self.grasp_point(obj, yaw_eff); p = self.obj_pos(obj)
        except KeyError:
            return SkillResult(name, False, "unknown object", 0, before, before)
        rb = self.obj_rbound(obj); z_lo, z_hi = self.obj_zrange(obj)
        if self.CUBBY_SIDE_INSERT and self.CUBBY_MODE == "kinematic":
            cb = self.cubby_containing(obj)
            if cb is not None: return self._cubby_pick_kinematic(obj, cb, name, before, t0)
        if self.DRAWER_PICK_MODE == "kinematic":
            dr = self.containing_drawer(obj)
            if dr is not None: return self._drawer_pick_kinematic(obj, dr, name, before, t0)
        self.retreat_if_needed(OPEN, name)
        if self.FAR_PICK_HOME and np.linalg.norm(gp[:2] - self.base_xy()) > 0.65 and np.linalg.norm(self.eef()[:2] - self.HOME[:2]) > 0.15:
            self.go_home(OPEN, name)                                    # 远端抓取前先回标准姿态：到达姿态与之前路径无关（远端易伸直卡住）
        if not self.reachable(gp):
            return SkillResult(name, False, f"out of reach (dist to base {np.linalg.norm(gp[:2]-self.base_xy()):.2f} m)", 0, before, before)
        zs = self.safe_z_for(gp, z_hi + 0.05)
        if not self.move_z(zs, OPEN, name):
            return SkillResult(name, False, "raise failed " + self.err_str(np.array([*self.eef()[:2], zs])), self.t - t0, before, self.n_done, self.cancel_flag)
        if self.YAW_FOLD:
            self.rotate_yaw_to(self.wrist_yaw_for(yaw_eff), OPEN, name, max_steps=60)   # 抓取点偏移仍按 yaw_eff 旋转，手腕只需闭合方向一致
        else:
            self.rotate_yaw_to(yaw_eff, OPEN, name)
        if not self.move_xy(gp[0], gp[1], OPEN, name) and np.linalg.norm(self.eef()[:2] - gp[:2]) > 0.03:
            return SkillResult(name, False, "approach failed " + self.err_str(np.array([gp[0], gp[1], zs])) + f" stalled={self.last_stalled}", self.t - t0, before, self.n_done, self.cancel_flag)
        gp = self.grasp_point(obj, yaw_eff); p = self.obj_pos(obj)        # 重新读取（物体可能被移动）
        z_lo, z_hi = self.obj_zrange(obj)
        pre_z = max(gp[2] + pre_h, z_hi + 0.03)
        if not self.move_to(np.array([gp[0], gp[1], pre_z]), OPEN, name, tol=0.01, max_steps=80) and np.linalg.norm(self.eef() - np.array([gp[0], gp[1], pre_z])) > 0.03:
            return SkillResult(name, False, "pre-grasp failed " + self.err_str(np.array([gp[0], gp[1], pre_z])) + self.blocked_note(obj), self.t - t0, before, self.n_done, self.cancel_flag)
        gp = self.grasp_point(obj, yaw_eff)
        g_desc = OPEN
        if self.RIM_GAP_STEPS and self.rim_in_drawer(obj):
            # r3：抽屉内碗、盘的前沿径向抓取：先部分闭合到约 5 cm 再下降（动作 0 = 保持开度），
            # 否则全开时伸向物体中心的内侧手指会落在柜体顶板前沿上（case10 碗滑到抽屉靠里时）
            self.hold(self.RIM_GAP_STEPS, CLOSE, name); g_desc = 0.0
        reached = self.move_to(gp, g_desc, name, tol=0.008, max_steps=80, z_first=True)
        if not reached and (self.cancel_flag or abs(self.eef()[2] - gp[2]) > descend_tol):
            return SkillResult(name, False, "descend failed " + self.err_str(gp) + self.blocked_note(obj), self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.hold(close_steps, CLOSE, name):
            return SkillResult(name, False, "cancelled", self.t - t0, before, self.n_done, True)
        self.gripper = CLOSE
        z_before = float(self.obj_pos(obj)[2])
        lifted = self.move_z(min(max(zs, gp[2] + 0.08), 0.75 + self.zoff), CLOSE, name, tol=0.015, max_steps=100)
        held = bool(np.linalg.norm(self.obj_pos(obj) - self.eef()) < max(0.06, min(rb, 0.12) + 0.03) and self.obj_pos(obj)[2] > z_before + 0.02)
        ok = bool(held)
        self.held = obj if ok else None
        if ok:
            self.held_drop = float(self.eef()[2] - self.obj_zrange(obj)[0])     # 手持物体最低点到末端的距离
            if np.linalg.norm(gp[:2] - self.base_xy()) > 0.62:                   # 远端抓取：先向基座方向回收，避免卡在工作空间边界
                back = self.eef()[:2] + 0.5 * (self.HOME[:2] - self.eef()[:2])
                self.move_xy(back[0], back[1], CLOSE, name, tol=0.02, max_steps=60)
        if ok and self.PICK_VERIFY_STEPS and not self.cancel_flag:
            self.hold(self.PICK_VERIFY_STEPS, CLOSE, name)
            still = bool(self.checker._in_hand(obj)) or np.linalg.norm(self.obj_pos(obj) - self.eef()) < max(0.06, min(rb, 0.12) + 0.03)
            if not still:                                                        # 抬起后滑脱：如实报告，必要时重抓一次
                self.held = None
                if _retry < self.PICK_RETRY and not self.cancel_flag:
                    return self.pick(obj, pre_h, close_steps, descend_tol, _retry=_retry + 1)
                return SkillResult(name, False, "object slipped out of the gripper after lifting" + self.blocked_note(obj),
                                   self.t - t0, before, self.n_done, self.cancel_flag)
        return SkillResult(name, ok, "ok" if ok else (("object not in hand" if lifted else "lift failed") + self.blocked_note(obj)),
                           self.t - t0, before, self.n_done, self.cancel_flag)

    PLACE_OFFSET_COMP = False  # r4 试验：放置时补偿夹爪与物体中心的水平偏移。实测未解决平底锅上灶（case3/4 仍失败且引发连锁失败），默认关闭

    def place(self, region_site: str, drop_h: float = 0.06, open_steps: int = 10, release_max_gap: float = 0.12) -> SkillResult:
        """（手持物体）抬到安全高度 → 水平移到目标区域中心上方 → 垂直下降到区域面 + drop_h → 张开 → 抬回安全高度。"""
        name = f"place({region_site})"; before = self.n_done; t0 = self.t
        if self.held is not None and not self.held_in_hand(): self.held = None     # 物体已不在夹爪中（如松手途中被取消）
        if self.held is None:
            return SkillResult(name, False, "nothing in hand", 0, before, before)
        so = self.env.object_sites_dict.get(region_site)
        if so is not None and (so.joints or []):
            try:
                if self.drawer_geometry(region_site)[5] < 0.5:
                    return SkillResult(name, False, f"target drawer {region_site} is closed; open it first", 0, before, before)
            except Exception:
                pass
        try:
            tgt = self.site_pos(region_site); top = self.fixture_top_z(region_site)
        except Exception:
            return SkillResult(name, False, "unknown region", 0, before, before)
        if self.CUBBY_SIDE_INSERT and "storage_box" in region_site:
            if self.CUBBY_MODE == "kinematic":
                return self._cubby_kinematic(region_site, name, before, t0)
            return self.place_into_cubby(region_site, name, before, t0, open_steps)
        if so is not None and (so.joints or []) and self.DRAWER_FRONT_FRAC > 0:
            try:                                                   # 抽屉：放在靠外侧的位置（拉出后露在柜体外），之后才能再取出来
                _, d_open, half_d, _, _, _ = self.drawer_geometry(region_site)
                tgt = tgt + d_open * (self.DRAWER_FRONT_FRAC * half_d)
            except Exception:
                pass
        self.retreat_if_needed(CLOSE, name)
        if "table_region" in region_site and self.TABLE_NEAR_DROP:
            tgt = self.table_drop_point(region_site, tgt)
        is_drawer = so is not None and (so.joints or [])
        if self.PLACE_OFFSET_COMP and not is_drawer:
            # r4：让物体中心（而不是夹爪）落在目标点。抓把手搬运平底锅时，夹爪与锅心水平相距约 14 cm，
            # 原先按夹爪对准灶台中心，锅心落在灶台区域外（Memory_Exploration case3/4/5、Mix case2 放不上灶）
            off = self.eef()[:2] - self.obj_pos(self.held)[:2]
            if float(np.linalg.norm(off)) > 0.03:
                tgt = np.array(tgt, float); tgt[:2] = tgt[:2] + off
        zs = self.safe_z_for(tgt, top + self.held_drop)
        if not self.move_z(zs, CLOSE, name):
            return SkillResult(name, False, "raise failed", self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.transport_xy(tgt, CLOSE, name, zs):
            return SkillResult(name, False, "transport failed " + self.err_str(np.array([tgt[0], tgt[1], zs])) + f" stalled={self.last_stalled}" + self.blocked_note(), self.t - t0, before, self.n_done, self.cancel_flag)
        low_z = tgt[2] + drop_h
        reached = self.move_to(np.array([tgt[0], tgt[1], low_z]), CLOSE, name, tol=0.01, max_steps=100)
        if not reached:
            gap = float(self.eef()[2] - low_z)
            if self.cancel_flag or gap > release_max_gap:
                return SkillResult(name, False, f"descend failed ({'stalled' if self.last_stalled else 'timeout'}) gap={gap:.3f} " + self.err_str(np.array([tgt[0], tgt[1], low_z])), self.t - t0, before, self.n_done, self.cancel_flag)
            # 被挡住但已足够接近：从低处松手（人类演示也是在区域面上方 ~5 cm 松手）
        if not self.hold(open_steps, OPEN, name):
            return SkillResult(name, False, "cancelled", self.t - t0, before, self.n_done, True)
        released = self.held
        self.gripper = OPEN; self.held = None
        self.move_z(zs, OPEN, name, tol=0.015, max_steps=80)
        ok = bool(released is not None and self.checker.in_relaxed(released, region_site))
        return SkillResult(name, ok, "ok" if ok else f"{released} not in {region_site} after release", self.t - t0, before, self.n_done, self.cancel_flag)


    # ---------- 固定装置几何 ----------
    def body_pos(self, body: str) -> np.ndarray:
        return np.array(self.env.sim.data.body_xpos[self.env.sim.model.body_name2id(body)])

    def drawer_geometry(self, region_site: str):
        """返回 (站点中心, 世界开启方向单位向量, 半深度, 关节名, 父固定装置名, 关节当前开度比例)。"""
        m = self.env.sim.model
        so = self.env.object_sites_dict[region_site]
        joint = (so.joints or [None])[0]; parent = so.parent_name
        sid = m.site_name2id(region_site); spos = np.array(self.env.sim.data.site_xpos[sid]); ssize = np.array(m.site_size[sid])
        jid = m.joint_name2id(joint); bid = m.jnt_bodyid[jid]
        axis_w = self.env.sim.data.body_xmat[bid].reshape(3, 3) @ m.jnt_axis[jid]
        art = self.env.get_object(parent).object_properties["articulation"]
        sign = 1.0 if np.mean(art["default_open_ranges"]) > np.mean(art["default_close_ranges"]) else -1.0
        d = sign * axis_w / (np.linalg.norm(axis_w) + 1e-9)
        half_depth = float(abs(np.dot(np.abs(d), ssize)))
        q = float(self.env.sim.data.qpos[m.get_joint_qpos_addr(joint)])
        frac = (q - np.mean(art["default_close_ranges"])) / (np.mean(art["default_open_ranges"]) - np.mean(art["default_close_ranges"]))
        return spos, d, half_depth, joint, parent, float(frac)

    HANDLE_PROTRUSION = {"short_cabinet": 0.07, "wooden_cabinet": 0.035, "white_cabinet": 0.035}
    # 抓取偏移（世界系，eef - 物体中心），来自演示统计 E0.6；未列出的按中心抓取
    GRASP_OFFSETS = {"wine_bottle": (0.0, 0.0, 0.11), "bbq_sauce": (0.0, 0.0, 0.036), "tomato_sauce": (0.0, 0.0, 0.007),
                     "white_bowl": (0.0, -0.040, 0.014), "akita_black_bowl": (0.0, -0.040, 0.014), "plate": (0.0, -0.043, 0.013)}
    # 物体局部系抓取偏移（大物体，如平底锅把手），由 x_grasp_frame_offsets.py 提取；值为 (dx, dy, dz, 是否需要把手指闭合方向对齐到垂直于局部 x 轴)
    GRASP_OFFSETS_LOCAL = {"chefmate_8_frypan": (0.14, 0.0, 0.02, True)}

    def obj_rotmat(self, obj: str):
        import robosuite.utils.transform_utils as T
        return T.quat2mat(np.array(self.env._get_observations()[f"{obj}_quat"]))

    REACH_MAX = 0.87      # Panda 水平可达半径（r4：0.80 → 0.87；实测竖直下抓在 0.86 m 可达，0.88–0.92 m 停在差约 3 cm 处，超出时立即报告够不着）

    def base_xy(self) -> np.ndarray:
        m = self.env.sim.model
        for n in ("robot0_base", "robot0_link0"):
            try:
                return np.array(self.env.sim.data.body_xpos[m.body_name2id(n)][:2])
            except Exception:
                continue
        return np.zeros(2)

    def reachable(self, xy) -> bool:
        return bool(np.linalg.norm(np.asarray(xy)[:2] - self.base_xy()) <= self.REACH_MAX)

    def containing_drawer(self, obj: str):
        """若物体位于某个柜子/冰箱的抽屉区域内，返回该区域站点名，否则 None。
        r4：要求物体中心低于抽屉区域的顶面——LIBERO 的 in 谓词把放在柜顶上的物体也判为在上层抽屉区域内
        （Ideal case5 的布丁），会被误当作"在关着的抽屉里"，既无法抓取，也被实时环境当作不可见。"""
        p = None
        for r in self.env.regions:
            if any(k in r for k in ("cabinet", "fridge")) and r.endswith("_region"):
                try:
                    if self.env._eval_predicate(["in", obj, r]):
                        m = self.env.sim.model; sid = m.site_name2id(r)
                        ext = np.abs(self.env.sim.data.site_xmat[sid].reshape(3, 3)) @ m.site_size[sid]
                        top_side = r.rsplit("_", 2)[0] + "_top_side"
                        on_top = top_side in self.env.object_sites_dict and self.env._eval_predicate(["in", obj, top_side])
                        p = self.obj_zrange(obj)[0] if p is None else p          # 物体最低点（原点可能在底部，如碗）
                        if on_top or p > float(self.env.sim.data.site_xpos[sid][2] + ext[2]) - 0.01:
                            continue
                        return r
                except Exception:
                    pass
        return None

    def grasp_point(self, obj: str, yaw: float = 0.0) -> np.ndarray:
        """抓取点 = 物体位置 + 偏移；世界系偏移随末端 yaw 绕 z 旋转（手指闭合方向随之转动）。"""
        p = self.obj_pos(obj); otype = obj.rsplit("_", 1)[0]
        if otype in self.GRASP_OFFSETS_LOCAL:
            off = self.GRASP_OFFSETS_LOCAL[otype]
            return p + self.obj_rotmat(obj) @ np.array(off[:3])
        off = np.array(self.GRASP_OFFSETS.get(otype, (0.0, 0.0, 0.0)))
        if abs(off[0]) < 1e-6 and abs(off[1]) < 1e-6:
            return p + self.obj_rotmat(obj) @ off            # r3：纯竖直偏移（瓶颈等）按物体局部系计算：直立时不变，倒伏时指向躺倒的瓶颈
        c, s_ = np.cos(yaw), np.sin(yaw)
        return p + np.array([c * off[0] - s_ * off[1], s_ * off[0] + c * off[1], off[2]])

    TIPPED_DEG = 45            # r3：物体竖直轴倾角超过此值视为倒伏（如被碰倒的酒瓶）

    def is_tipped(self, obj: str) -> bool:
        return bool(np.degrees(np.arccos(np.clip(self.obj_rotmat(obj)[2, 2], -1.0, 1.0))) > self.TIPPED_DEG)

    def grasp_yaw(self, obj: str):
        """返回目标 eef yaw（None 表示保持 0）：
        - 带把手的大物体：手指闭合方向垂直于物体局部 x 轴；
        - 位于抽屉内的物体：手掌宽边沿抽屉长轴（垂直于拉出方向），避免卡在抽屉壁上（人类演示 yaw≈1.0）。"""
        otype = obj.rsplit("_", 1)[0]
        off0 = self.GRASP_OFFSETS.get(otype)
        if self.is_tipped(obj) and (off0 is None or float(np.hypot(off0[0], off0[1])) <= 0.01) and otype not in self.GRASP_OFFSETS_LOCAL:
            # r3：倒伏物体：手指闭合方向垂直于物体轴线（局部 z 的水平投影）；轴线近竖直时退回水平最窄方向
            a = self.obj_rotmat(obj)[:, 2]
            if float(np.hypot(a[0], a[1])) > 0.3: return float(np.arctan2(a[1], a[0]))
            return self.short_axis_yaw(obj)
        off = self.GRASP_OFFSETS_LOCAL.get(otype)
        if off and off[3]:
            h = self.obj_rotmat(obj)[:, 0]
            yaw = float(np.arctan2(h[1], h[0]))
            return (yaw + np.pi / 2) % np.pi - np.pi / 2          # 折到 (-90°, 90°]
        drawer = self.containing_drawer(obj)
        if drawer is not None:
            try:
                _, d, _, _, _, _ = self.drawer_geometry(drawer)
                off0 = self.GRASP_OFFSETS.get(otype)
                if off0 is not None and float(np.hypot(off0[0], off0[1])) > 0.01:
                    # r2b：带边沿偏移的物体（碗、盘）在抽屉里时，把抓取点转到拉出方向一侧的前沿，避开柜体框架
                    #（case10 碗：原规则首抓 7 个偏航角全部失败，前沿 yaw=π 首抓成功）
                    yaw = float(np.arctan2(d[1], d[0]) - np.arctan2(off0[1], off0[0]))
                    return (yaw + np.pi) % (2 * np.pi) - np.pi
                f = np.array([-d[1], d[0]])                          # 手指轴目标 = 抽屉长轴
                yaw = float(np.arctan2(-f[0], f[1]))
                return (yaw + np.pi / 2) % np.pi - np.pi / 2
            except Exception:
                return None
        return None

    def eef_yaw(self) -> float:
        import robosuite.utils.transform_utils as T
        q = np.array(self.env._get_observations()["robot0_eef_quat"])
        return float(T.mat2euler(T.quat2mat(q))[2])

    YAW_FOLD = True            # r3：手腕目标 yaw 按 180° 折叠（平行夹爪转 180° 闭合方向不变）

    def wrist_yaw_for(self, target: float) -> float:
        """与 target 闭合方向相同、相对当前 yaw 转动不超过 ±90° 的手腕 yaw；若第 7 关节会越限则改用另一等价角。
        （case10 碗：前沿抓取目标 yaw=±180° 超出第 7 关节范围，手腕停在约 106°，变成沿碗沿切向夹持，抬起后滑脱）"""
        cur = self.eef_yaw()
        delta = (target - cur + np.pi / 2) % np.pi - np.pi / 2
        try:
            m = self.env.sim.model; d = self.env.sim.data
            jid = m.joint_name2id("robot0_joint7"); lo, hi = m.jnt_range[jid]
            q = float(d.qpos[m.get_joint_qpos_addr("robot0_joint7")])
            az = float((d.body_xmat[m.jnt_bodyid[jid]].reshape(3, 3) @ m.jnt_axis[jid])[2])     # 关节轴的世界 z 分量：yaw 增量 ≈ az × 关节增量
            if abs(az) > 0.5 and not (lo + 0.1 <= q + delta / az <= hi - 0.1):
                alt = delta - np.sign(delta) * np.pi
                if lo + 0.1 <= q + alt / az <= hi - 0.1: delta = alt
        except Exception:
            pass
        return cur + delta

    def rotate_yaw_to(self, target: float, gripper: float, skill: str, tol: float = 0.05, max_steps: int = 40) -> bool:
        for _ in range(max_steps):
            if self.cancel_flag: return False
            err = (target - self.eef_yaw() + np.pi) % (2 * np.pi) - np.pi
            if abs(err) < tol: return True
            self.step([0, 0, 0, 0, 0, float(np.clip(err / 0.5, -0.4, 0.4)), gripper], skill)
        return abs((target - self.eef_yaw() + np.pi) % (2 * np.pi) - np.pi) < tol * 2

    def obj_zrange(self, obj: str):
        """物体碰撞体的最低/最高 z（用 geom 中心 ± 包围球半径近似），比 body 原点 ± rbound 更稳。"""
        m = self.env.sim.model; d = self.env.sim.data; bid = self.env.obj_body_id[obj]
        zs = [(float(d.geom_xpos[g][2] - m.geom_rbound[g]), float(d.geom_xpos[g][2] + m.geom_rbound[g]))
              for g in range(m.ngeom) if m.geom_bodyid[g] == bid and m.geom_contype[g] != 0]
        if not zs:
            p = self.obj_pos(obj); rb = self.obj_rbound(obj); return p[2] - rb, p[2] + rb
        return min(z[0] for z in zs), max(z[1] for z in zs)

    HOME = np.array([-0.05, 0.0, 0.66])

    def go_home(self, gripper: float, skill: str) -> bool:
        """停滞恢复：先抬到当前高度与 0.66 的较大值，再回到基座前方中立位。"""
        cur = self.eef()
        self.move_to(np.array([cur[0], cur[1], max(cur[2], 0.62 + self.zoff)]), gripper, skill, 0.02, 30)
        return self.move_to(self.HOME.copy(), gripper, skill, 0.03, 80)

    def obj_rbound(self, obj: str) -> float:
        m = self.env.sim.model; bid = self.env.obj_body_id[obj]
        rb = [float(m.geom_rbound[g]) for g in range(m.ngeom) if m.geom_bodyid[g] == bid]
        return max(rb) if rb else 0.05

    def held_in_hand(self) -> bool:
        """记录的手持物体是否仍在夹爪中（与 pick 的成功判定同一距离准则，留 2 cm 余量）。"""
        o = self.held
        if o is None or self.gripper <= 0: return False
        try:
            return bool(np.linalg.norm(self.obj_pos(o) - self.eef()) < max(0.06, min(self.obj_rbound(o), 0.12) + 0.03) + 0.02)
        except KeyError:
            return False

    # ---------- 末端姿态控制 ----------
    def eef_rotmat(self):
        import robosuite.utils.transform_utils as T
        return T.quat2mat(np.array(self.env._get_observations()["robot0_eef_quat"]))

    def approach_axis(self) -> np.ndarray:
        """夹爪接近方向（末端坐标系 z 轴在世界系的方向；俯视抓取时为 (0,0,-1)）。"""
        return self.eef_rotmat()[:, 2]

    def rotate_approach_to(self, target_dir: np.ndarray, gripper: float, skill: str, tol: float = 0.08, max_steps: int = 60) -> bool:
        """用 OSC 旋转增量把接近方向转到 target_dir（世界系单位向量），位置保持。"""
        target_dir = np.asarray(target_dir, float); target_dir /= (np.linalg.norm(target_dir) + 1e-9)
        for _ in range(max_steps):
            if self.cancel_flag: return False
            a = self.approach_axis()
            axis = np.cross(a, target_dir); sin_ = np.linalg.norm(axis); ang = float(np.arctan2(sin_, np.dot(a, target_dir)))
            if ang < tol: return True
            axis = axis / (sin_ + 1e-9)
            step_ang = min(ang, 0.15)                              # 每步最多 0.15 rad（OSC 旋转 output_max 0.5 rad/步 → 输入 0.3）
            rot = axis * (step_ang / 0.5)
            self.step([0, 0, 0, *rot, gripper], skill)
        return False

    def restore_topdown(self, gripper: float, skill: str) -> bool:
        return self.rotate_approach_to(np.array([0, 0, -1.0]), gripper, skill)

    DRAWER_MODE = "kinematic"   # "kinematic"（抽象技能：机械臂就位后关节匀速动画，40 步）| "physical"（水平夹持拉动，开发中）

    DRAWER_CARRY = True        # r3：抽象开关抽屉时，抽屉内物体随抽屉一起平移（原实现只推关节、速度清零，物体被后板推着穿插，停在顶板下方）
    DRAWER_HOVER = True        # r3：抽象开关抽屉时夹爪停在安全高度（原先降到把手高度、离面板仅约 4.5 cm，拉出 15 cm 的抽屉会扫过夹爪并撞动抽屉内物体）

    def drawer_contents(self, region_site: str):
        """位于该抽屉区域内的物体的自由关节 (qpos 地址, qvel 地址) 列表。"""
        m = self.env.sim.model; out = []
        for o, mo in getattr(self.env, "objects_dict", {}).items():
            try:
                if not self.env._eval_predicate(["in", o, region_site]): continue
                jn = mo.joints[-1]; qa = m.get_joint_qpos_addr(jn); va = m.get_joint_qvel_addr(jn)
                qa = qa[0] if isinstance(qa, tuple) else qa; va = va[0] if isinstance(va, tuple) else va
                if m.jnt_type[m.joint_name2id(jn)] == 0: out.append((qa, va))          # 仅自由关节
            except Exception:
                continue
        return out

    def _drawer_kinematic(self, region_site: str, open_: bool, name: str, before: int, t0: int, anim_steps: int = 40) -> SkillResult:
        """抽象技能（ABSTRACT）：机械臂移到抽屉前方把手高度，然后把抽屉关节 qpos 在 anim_steps 步内线性推到目标；每步仍走物理与计分，可取消。"""
        spos, d, half, joint, parent, frac0 = self.drawer_geometry(region_site)
        m = self.env.sim.model; addr = m.get_joint_qpos_addr(joint)
        art = self.env.get_object(parent).object_properties["articulation"]
        if open_:
            q_target = float(np.mean(art["default_open_ranges"]))
        else:
            cr = art["default_close_ranges"]; q_target = float(max(cr, key=abs) if min(cr) < 0 <= max(cr) else np.mean(cr))
            q_target = float(np.clip(q_target, min(cr), max(cr)))
        pre = spos + d * (half + 0.12); pre[2] = spos[2] + 0.02
        zs = min(max(self.Z_SAFE_MIN, pre[2] + 0.12), self.Z_SAFE_MAX)
        self.move_z(zs, OPEN, name)
        if not self.move_xy(pre[0], pre[1], OPEN, name) and np.linalg.norm(self.eef()[:2] - pre[:2]) > 0.04:
            return SkillResult(name, False, "approach failed (ABSTRACT drawer) " + self.err_str(np.array([pre[0], pre[1], zs])), self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.DRAWER_HOVER:
            self.move_to(pre, OPEN, name, tol=0.015, max_steps=60)
        q0 = float(self.env.sim.data.qpos[addr])
        jid = m.joint_name2id(joint)
        axis_w = self.env.sim.data.body_xmat[m.jnt_bodyid[jid]].reshape(3, 3) @ m.jnt_axis[jid]
        carry = self.drawer_contents(region_site) if (self.DRAWER_CARRY and int(m.jnt_type[jid]) == 2) else []   # 只对滑轨（抽屉）随动；转轴门不平移内容物
        q_prev = q0
        for i in range(1, anim_steps + 1):
            if self.cancel_flag:
                return SkillResult(name, False, "cancelled (ABSTRACT drawer)", self.t - t0, before, self.n_done, True)
            q_new = q0 + (q_target - q0) * i / anim_steps
            self.env.sim.data.qpos[addr] = q_new
            self.env.sim.data.qvel[m.get_joint_qvel_addr(joint)] = 0.0
            for qa, va in carry:                             # 抽屉内物体随抽屉平移（相当于静摩擦带动）
                self.env.sim.data.qpos[qa:qa + 3] += axis_w * (q_new - q_prev)
                self.env.sim.data.qvel[va:va + 6] = 0.0
            q_prev = q_new
            self.step([0, 0, 0, 0, 0, 0, OPEN], name, event="abstract_drawer")
        for _ in range(8):                                   # 保持数步，抵消物理回弹
            if self.cancel_flag: break
            self.env.sim.data.qpos[addr] = q_target; self.env.sim.data.qvel[m.get_joint_qvel_addr(joint)] = 0.0
            self.step([0, 0, 0, 0, 0, 0, OPEN], name, event="abstract_drawer")
        self.move_z(zs, OPEN, name, tol=0.015, max_steps=60)
        _, _, _, _, _, frac1 = self.drawer_geometry(region_site)
        ok = bool(self.checker.open_relaxed(region_site)) if open_ else bool(self.checker.close_relaxed(region_site))
        return SkillResult(name, ok, f"ok ABSTRACT frac={frac0:.2f}->{frac1:.2f}" if ok else f"drawer not {'open' if open_ else 'closed'} (ABSTRACT frac {frac0:.2f}->{frac1:.2f})", self.t - t0, before, self.n_done, self.cancel_flag)

    def open_drawer(self, region_site: str, pull: float = 0.15, close_steps: int = 10, standoff: float = 0.14) -> SkillResult:
        if self.held is not None:
            return SkillResult(f"open({region_site})", False, f"hand must be empty to operate a drawer (holding {self.held}); put it down first", 0, self.n_done, self.n_done)
        if self.DRAWER_MODE == "kinematic":
            name = f"open({region_site})"; before = self.n_done; t0 = self.t
            try:
                return self._drawer_kinematic(region_site, True, name, before, t0)
            except Exception as e:
                return SkillResult(name, False, f"geometry error {e}", 0, before, before)
        return self.open_drawer_physical(region_site, pull, close_steps, standoff)

    def open_drawer_physical(self, region_site: str, pull: float = 0.15, close_steps: int = 10, standoff: float = 0.14) -> SkillResult:
        """水平夹持拉抽屉（复现人类策略：手腕 roll 90°，夹爪水平朝向柜面，上下夹住把手横条后沿开启方向拉出）。
        步骤：抬到安全高度 → 移到把手正前方 standoff 处上方 → 下降到把手高度 → 把接近方向转向柜面(-d) → 前进到把手 → 闭合 → 拉出 → 张开 → 后退 → 恢复俯视姿态 → 抬起。"""
        name = f"open({region_site})"; before = self.n_done; t0 = self.t
        try:
            spos, d, half, joint, parent, frac0 = self.drawer_geometry(region_site)
        except Exception as e:
            return SkillResult(name, False, f"geometry error {e}", 0, before, before)
        prot = next((v for k, v in self.HANDLE_PROTRUSION.items() if k in parent), 0.04)
        handle = spos + d * (half + 0.005); handle[2] = spos[2] + 0.005          # 把手碰撞体贴在抽屉前面板上、略高于区域中心
        pre = handle + d * standoff
        zs = min(max(self.Z_SAFE_MIN, handle[2] + 0.12), self.Z_SAFE_MAX)
        if not self.move_z(zs, OPEN, name):
            return SkillResult(name, False, "raise failed", self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.move_xy(pre[0], pre[1], OPEN, name) and np.linalg.norm(self.eef()[:2] - pre[:2]) > 0.03:
            return SkillResult(name, False, "approach failed " + self.err_str(np.array([pre[0], pre[1], zs])) + f" stalled={self.last_stalled}", self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.move_to(np.array([pre[0], pre[1], handle[2]]), OPEN, name, tol=0.01, max_steps=80) and abs(self.eef()[2] - handle[2]) > 0.03:
            return SkillResult(name, False, "descend failed " + self.err_str(np.array([pre[0], pre[1], handle[2]])), self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.rotate_approach_to(-d, OPEN, name):
            self.restore_topdown(OPEN, name); return SkillResult(name, False, "rotate failed", self.t - t0, before, self.n_done, self.cancel_flag)
        # 前进到把手（允许被挡住：把手或面板会挡住指尖）
        self.move_to(handle, OPEN, name, tol=0.008, max_steps=80)
        if not self.hold(close_steps, CLOSE, name):
            return SkillResult(name, False, "cancelled", self.t - t0, before, self.n_done, True)
        grip_w = float(self.obs["robot0_gripper_qpos"][0] - self.obs["robot0_gripper_qpos"][1])
        self.move_to(self.eef() + d * pull, CLOSE, name, tol=0.01, max_steps=120)
        _, _, _, _, _, frac1 = self.drawer_geometry(region_site)
        self.hold(5, OPEN, name); self.gripper = OPEN
        self.move_to(self.eef() + d * 0.06, OPEN, name, tol=0.01, max_steps=40)
        self.restore_topdown(OPEN, name)
        self.move_z(zs, OPEN, name, tol=0.015, max_steps=60)
        ok = bool(self.checker.open_relaxed(region_site))
        return SkillResult(name, ok, f"ok frac={frac1:.2f} grip={grip_w:.3f}" if ok else f"not judged open (frac {frac0:.2f}->{frac1:.2f}, grip={grip_w:.3f}) handle={np.round(handle,3).tolist()}", self.t - t0, before, self.n_done, self.cancel_flag)

    def close_drawer(self, region_site: str, push_extra: float = 0.04, standoff: float = 0.10) -> SkillResult:
        if self.held is not None:
            return SkillResult(f"close({region_site})", False, f"hand must be empty to operate a drawer (holding {self.held}); put it down first", 0, self.n_done, self.n_done)
        if self.DRAWER_MODE == "kinematic":
            name = f"close({region_site})"; before = self.n_done; t0 = self.t
            try:
                return self._drawer_kinematic(region_site, False, name, before, t0)
            except Exception as e:
                return SkillResult(name, False, f"geometry error {e}", 0, before, before)
        return self.close_drawer_physical(region_site, push_extra, standoff)

    def close_drawer_physical(self, region_site: str, push_extra: float = 0.04, standoff: float = 0.10) -> SkillResult:
        """水平姿态用闭合的夹爪从前方把抽屉推回。"""
        name = f"close({region_site})"; before = self.n_done; t0 = self.t
        try:
            spos, d, half, joint, parent, frac0 = self.drawer_geometry(region_site)
        except Exception as e:
            return SkillResult(name, False, f"geometry error {e}", 0, before, before)
        front = spos + d * (half + 0.01); front[2] = spos[2] + 0.005
        pre = front + d * standoff
        zs = min(max(self.Z_SAFE_MIN, front[2] + 0.12), self.Z_SAFE_MAX)
        if not self.move_z(zs, OPEN, name): return SkillResult(name, False, "raise failed", self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.move_xy(pre[0], pre[1], OPEN, name) and np.linalg.norm(self.eef()[:2] - pre[:2]) > 0.03:
            return SkillResult(name, False, "approach failed", self.t - t0, before, self.n_done, self.cancel_flag)
        self.move_to(np.array([pre[0], pre[1], front[2]]), CLOSE, name, tol=0.01, max_steps=80)
        if not self.rotate_approach_to(-d, CLOSE, name):
            self.restore_topdown(OPEN, name); return SkillResult(name, False, "rotate failed", self.t - t0, before, self.n_done, self.cancel_flag)
        travel = (frac0 if frac0 > 0 else 1.0) * 0.16 + standoff + push_extra
        self.move_to(self.eef() - d * travel, CLOSE, name, tol=0.01, max_steps=120)
        _, _, _, _, _, frac1 = self.drawer_geometry(region_site)
        self.move_to(self.eef() + d * 0.08, OPEN, name, tol=0.01, max_steps=40); self.gripper = OPEN
        self.restore_topdown(OPEN, name); self.move_z(zs, OPEN, name, tol=0.015, max_steps=60)
        ok = bool(self.checker.close_relaxed(region_site))
        return SkillResult(name, ok, f"ok frac={frac1:.2f}" if ok else f"not judged closed (frac {frac0:.2f}->{frac1:.2f})", self.t - t0, before, self.n_done, self.cancel_flag)

    def turnon(self, stove: str, yaw: float = 0.3, rot_steps: int = 30) -> SkillResult:
        """夹住旋钮并绕竖直轴旋转。"""
        name = f"turnon({stove})"; before = self.n_done; t0 = self.t
        if self.held is not None:
            return SkillResult(name, False, f"hand must be empty to turn a knob (holding {self.held}); put it down first", 0, before, before)
        try:
            knob = self.body_pos(f"{stove}_button")
        except Exception as e:
            return SkillResult(name, False, f"no button body {e}", 0, before, before)
        zs = self.safe_z(knob[2] + 0.15)
        if not self.move_z(zs, OPEN, name): return SkillResult(name, False, "raise failed", self.t - t0, before, self.n_done, self.cancel_flag)
        if not self.move_xy(knob[0], knob[1], OPEN, name): return SkillResult(name, False, "approach failed", self.t - t0, before, self.n_done, self.cancel_flag)
        self.move_to(np.array([knob[0], knob[1], knob[2] + 0.02]), OPEN, name, tol=0.008, max_steps=100)
        if not self.hold(8, CLOSE, name): return SkillResult(name, False, "cancelled", self.t - t0, before, self.n_done, True)
        def knob_on():
            try: return bool(self.env._eval_predicate(["turnon", stove]))
            except Exception: return False
        for _ in range(rot_steps):
            if self.cancel_flag or knob_on(): break
            self.step([0, 0, 0, 0, 0, yaw, CLOSE], name)
        self.hold(4, OPEN, name); self.gripper = OPEN
        self.move_z(zs, OPEN, name, tol=0.015, max_steps=60)
        ok = knob_on()
        return SkillResult(name, ok, "ok" if ok else "knob not turned enough", self.t - t0, before, self.n_done, self.cancel_flag)

    def pour(self, target_obj: str, height: float = 0.15, offset_x: float = 0.03, tilt: float = 0.25,
             tilt_steps: int = 20, hold_steps: int = 10) -> SkillResult:
        """手持物体移到目标容器上方，绕 roll 轴倾斜、保持、回正。"""
        name = f"pour(->{target_obj})"; before = self.n_done; t0 = self.t
        if self.held is not None and not self.held_in_hand(): self.held = None     # 物体已不在夹爪中（如松手途中被取消）
        if self.held is None:
            return SkillResult(name, False, "nothing in hand", 0, before, before)
        try:
            tgt = self.obj_pos(target_obj)
        except KeyError:
            return SkillResult(name, False, "unknown target", 0, before, before)
        self.retreat_if_needed(CLOSE, name)
        zs = self.safe_z_for(tgt, self.obj_zrange(target_obj)[1] + self.held_drop + 0.05)
        if not self.move_z(zs, CLOSE, name): return SkillResult(name, False, "raise failed", self.t - t0, before, self.n_done, self.cancel_flag)
        if self.track_targets:
            ok_t = self.track_xy(lambda: self.obj_pos(target_obj)[:2] + np.array([offset_x, 0.0]), CLOSE, name, zs, tol_fail=0.06)
            tgt = self.obj_pos(target_obj)
        else:
            ok_t = self.transport_xy(np.array([tgt[0] + offset_x, tgt[1]]), CLOSE, name, zs, tol_fail=0.06)
        if not ok_t:
            return SkillResult(name, False, "transport failed " + self.err_str(np.array([tgt[0] + offset_x, tgt[1], zs])), self.t - t0, before, self.n_done, self.cancel_flag)
        self.move_to(np.array([tgt[0] + offset_x, tgt[1], tgt[2] + height]), CLOSE, name, tol=0.01, max_steps=80)
        min_d = 9.9; q0 = np.array(self.env.sim.data.body_xquat[self.env.obj_body_id[self.held]]); max_dq = 0.0
        for _ in range(tilt_steps):
            if self.cancel_flag: break
            self.step([0, 0, 0, -tilt, 0, 0, CLOSE], name)
            min_d = min(min_d, float(np.linalg.norm(self.obj_pos(self.held) - self.obj_pos(target_obj))))
            max_dq = max(max_dq, float(np.linalg.norm(np.array(self.env.sim.data.body_xquat[self.env.obj_body_id[self.held]]) - q0)))
        self.hold(hold_steps, CLOSE, name)
        for _ in range(tilt_steps):
            if self.cancel_flag: break
            self.step([0, 0, 0, +tilt, 0, 0, CLOSE], name)
        self.move_z(zs, CLOSE, name, tol=0.015, max_steps=60)
        held_still = self.held is not None and np.linalg.norm(self.obj_pos(self.held) - self.eef()) < 0.15
        ok = bool(not self.cancel_flag and min_d < 0.3 and max_dq > 0.2 and held_still)
        return SkillResult(name, ok, "ok" if ok else f"pour incomplete (min_dist={min_d:.2f}, tilt={max_dq:.2f}, held={held_still})", self.t - t0, before, self.n_done, self.cancel_flag)

    def place_on_object(self, target_obj: str, drop_h: float = 0.10, release_max_gap: float = 0.15) -> SkillResult:
        """把手中物体放到目标物体（架子/碗/盘/锅）上方中心并松手。"""
        name = f"place_on({target_obj})"; before = self.n_done; t0 = self.t
        if self.held is not None and not self.held_in_hand(): self.held = None     # 物体已不在夹爪中（如松手途中被取消）
        if self.held is None:
            return SkillResult(name, False, "nothing in hand", 0, before, before)
        try:
            tgt = self.obj_pos(target_obj)
        except KeyError:
            return SkillResult(name, False, "unknown target", 0, before, before)
        self.retreat_if_needed(CLOSE, name)
        zs = self.safe_z_for(tgt, self.obj_zrange(target_obj)[1] + self.held_drop)
        if not self.move_z(zs, CLOSE, name): return SkillResult(name, False, "raise failed", self.t - t0, before, self.n_done, self.cancel_flag)
        if self.track_targets:
            ok_t = self.track_xy(lambda: self.obj_pos(target_obj)[:2], CLOSE, name, zs); tgt = self.obj_pos(target_obj)
        else:
            ok_t = self.transport_xy(tgt, CLOSE, name, zs)
        if not ok_t:
            return SkillResult(name, False, "transport failed " + self.err_str(np.array([tgt[0], tgt[1], zs])), self.t - t0, before, self.n_done, self.cancel_flag)
        low = np.array([tgt[0], tgt[1], tgt[2] + drop_h])
        reached = self.move_to(low, CLOSE, name, tol=0.01, max_steps=100)
        if not reached and (self.cancel_flag or self.eef()[2] - low[2] > release_max_gap):
            return SkillResult(name, False, "descend failed", self.t - t0, before, self.n_done, self.cancel_flag)
        released = self.held
        self.hold(10, OPEN, name); self.gripper = OPEN; self.held = None
        self.move_z(zs, OPEN, name, tol=0.015, max_steps=60)
        ok = bool(released is not None and (self.checker.on_relaxed(released, target_obj) or self.checker.in_relaxed(released, target_obj)))
        return SkillResult(name, ok, "ok" if ok else f"{released} not on/in {target_obj} after release", self.t - t0, before, self.n_done, self.cancel_flag)

    def wait(self, n_steps: int) -> SkillResult:
        before = self.n_done; t0 = self.t
        ok = self.hold(n_steps, self.gripper, "wait")
        return SkillResult("wait", ok, "ok" if ok else "cancelled", self.t - t0, before, self.n_done, not ok)
