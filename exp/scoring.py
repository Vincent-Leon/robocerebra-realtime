"""成功计分器：原始（官方监控器）与修复版（文档化的谓词修复，见 notes/Phase0_实验记录 §E0.5）。

修复版规则（R1–R5）：
R1 区域语义：*_side / *_top_side 等薄片站点 → "在该固定装置内部/顶面上"的体积判定；
R6' 桌面区域：物体中心高出桌面 ≤ 20 cm（原 5 cm）、不在手中（双指未同时接触），且不在任何其他受监控装置区域内；容积型区域（heating/contain/cook）高度容差放宽到顶部 +12 cm；
R9 抽屉区域：同一柜子的抽屉区域在高度上重叠，物体按高度就近归属；
R2 谓词类型：对非可倾倒的刚体（盒装食品等）`pour X Y` 放宽为 pour 或 in(X,Y)；
R3' pick：靠近末端且（抬升 > 4 cm 或离开所有受监控区域），连续保持 ≥ 10 帧；不做四元数抑制；
R4 on：原规则或（接触 且 物体不低于目标 且 水平距离在目标水平半径+3 cm 内）；
R5 open：关节行程 ≥ 全程 50%（官方：抽屉 ≥ 87.5%，微波炉门 ≥ 62%）；
R7 close：关节距关闭位置 ≤ 1.5 cm（抽屉）/ 0.1 rad（门）；
R8 pour：被倒物体在手中、位于目标容器上方（水平 ≤ 半径 + 6 cm）且在上方期间姿态变化 > 0.2（替代官方的 0.3 m 距离规则）；或放进容器。
v5（2026-10-17）：R1 白色储物盒（前后开口的方框）bottom/left/right 侧要求物体中心低于顶板；
R10 in/on 放置类子目标要求物体已离手且连续保持 5 帧（手持经过区域或放置途中被取消不算完成）。
v6（2026-10-21）：R11 探索前缀不计顺序：物体状态序列开头连续的开/关步骤（Memory 类任务中演示者逐个翻找抽屉的路径）
各自独立计分——open X 在 X 曾被打开时计入，close X 在 X 被打开过之后又关上时计入；其后的操作步骤照常按顺序推进，
且不必等探索前缀全部完成。原因：官方序列要求复现演示的翻找顺序（开上层→关上层→开中层→关中层→开下层），
智能体换一种同样合理的顺序（三个都打开再关上两个）会卡在第 2 步，其后已经完成的取放全部不计（r3 case8：实际做完仍只得 8/15）。
链中间的开/关（如先开微波炉门再放入）仍是前置条件，保持顺序。
两个计分器都按 goal.json 的每物体状态序列顺序推进（修复版的探索前缀除外），进度只增不减，每步调用一次 update()。
"""
from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple


class OriginalScorer:
    def __init__(self, env, goal):
        self.env, self.goal = env, goal
        self.n_goals = sum(len(v) for v in goal.values())
        self.events: List[Tuple[float, str]] = []
        self._last_total = 0

    def update(self):
        comp, total, all_done = self.env._check_success(self.goal)
        if total > self._last_total:
            self.events.append((float(self.env.sim.data.time), f"+{total - self._last_total}"))
            self._last_total = total
        return comp, int(total), bool(all_done)

    @property
    def progress(self):
        return dict(getattr(self.env, "_state_progress", {}))


class RepairedScorer:
    PLACE_SUSTAIN = 5          # R10：放置类子目标需连续保持的帧数（0.25 s）
    POURABLE = ("wine_bottle", "tomato_sauce", "bbq_sauce", "ketchup", "milk", "orange_juice", "salad_dressing",
                "new_salad_dressing", "alphabet_soup", "cream_cheese", "butter", "chocolate_pudding", "cookies", "popcorn",
                "macaroni_and_cheese")   # 全部允许 pour-or-in（盒装食品的"倒"在演示里常是放入）
    OPEN_FRAC = 0.5

    def __init__(self, env, goal):
        self.env, self.goal = env, goal
        self.n_goals = sum(len(v) for v in goal.values())
        self._progress = {o: 0 for o in goal}
        self._prev_regions: Dict[str, List[str]] = {}
        self._ref_z: Dict[Tuple[str, int], float] = {}
        self._pour_logs: Dict[Tuple[str, str], list] = {}
        self._place_hold: Dict[Tuple[str, int], int] = {}
        self._pdone: Dict[str, set] = {}       # R11：每个物体已计分的探索前缀下标
        self._was_open: set = set()            # R11：本 episode 中曾经打开过的可开合目标
        self.events: List[Tuple[float, str]] = []
        m = env.sim.model
        self._site_names = set(m.site_names)

    # ---------- 几何工具 ----------
    def _obj_pos(self, name):
        return np.array(self.env.sim.data.body_xpos[self.env.obj_body_id[name]])

    def _obj_quat(self, name):
        return np.array(self.env.sim.data.body_xquat[self.env.obj_body_id[name]])

    def _site(self, name):
        m = self.env.sim.model; sid = m.site_name2id(name)
        return np.array(self.env.sim.data.site_xpos[sid]), np.array(m.site_size[sid])

    def _eef(self):
        return np.array(self.env.sim.data.site_xpos[self.env.sim.model.site_name2id("gripper0_grip_site")])

    def _fixture_of(self, site_name):
        if site_name in self.env.object_sites_dict:
            return self.env.object_sites_dict[site_name].parent_name
        return None

    def _horizontal_radius(self, obj_name):
        """物体水平半径：该 body 下所有 geom 的 (水平偏移 + 包围球半径) 的最大值。"""
        m = self.env.sim.model; d = self.env.sim.data
        bid = self.env.obj_body_id[obj_name]; bpos = d.body_xpos[bid]
        # 包含子 body（固定装置有多个 body）
        name = self.env.sim.model.body_id2name(bid)
        prefix = name.rsplit("_", 1)[0] if name.endswith("_main") else name
        r = 0.0
        for gid in range(m.ngeom):
            b = m.geom_bodyid[gid]
            bn = m.body_id2name(b) or ""
            if b == bid or bn.startswith(prefix):
                r = max(r, float(np.linalg.norm(d.geom_xpos[gid][:2] - bpos[:2]) + m.geom_rbound[gid]))
        return min(r, 0.25)

    def _in_hand(self, obj) -> bool:
        """在手中 = 两个手指都接触该物体（robosuite _check_grasp）。"""
        try:
            return bool(self.env._check_grasp(gripper=self.env.robots[0].gripper, object_geoms=self.env.get_object(obj)))
        except Exception:
            return bool(np.linalg.norm(self._obj_pos(obj) - self._eef()) < 0.10)

    def _near_thresh(self, obj) -> float:
        """"在手中"的距离阈值：max(0.10, 物体最大包围半径 + 4 cm)——瓶子等从瓶颈抓取时原点离末端较远。"""
        if not hasattr(self, "_near_cache"): self._near_cache = {}
        if obj not in self._near_cache:
            m = self.env.sim.model; bid = self.env.obj_body_id[obj]
            rb = max([float(m.geom_rbound[g]) for g in range(m.ngeom) if m.geom_bodyid[g] == bid] or [0.05])
            self._near_cache[obj] = max(0.10, min(rb, 0.15) + 0.04)
        return self._near_cache[obj]

    def _regions_of(self, obj):
        return [r for r in self.env.regions if self.env._eval_predicate(["in", obj, r])]

    def _contact(self, a, b):
        try:
            return bool(self.env.check_contact(self.env.get_object(a), self.env.get_object(b)))
        except Exception:
            return False

    # ---------- 放宽谓词 ----------
    def _drawer_siblings(self, region):
        so = self.env.object_sites_dict.get(region)
        if so is None or not (so.joints or []): return []
        parent = so.parent_name
        return [r for r, o in self.env.object_sites_dict.items() if getattr(o, "parent_name", None) == parent and (o.joints or [])]

    def _in_fixture_region(self, obj, region) -> bool:
        """物体是否在某个装置区域内（用于 R6' 排除），包含 R1 盒子体积与 R9 抽屉消歧。"""
        if region.endswith("_table_region"): return False
        return self.in_relaxed(obj, region, _allow_table=False)

    def in_relaxed(self, obj, target, _allow_table=True) -> bool:
        sibs = self._drawer_siblings(target) if target in getattr(self, "_site_names", set()) else []
        if sibs:
            # R9：同一柜子的抽屉区域在高度上重叠（LIBERO 站点半高 0.088、中心相距 0.043），按高度就近归属
            p = self._obj_pos(obj)
            try:
                if not self.env._eval_predicate(["in", obj, target]): return False
            except Exception:
                return False
            zc = {r: float(self._site(r)[0][2]) for r in sibs}
            return min(zc, key=lambda r: abs(zc[r] - p[2])) == target
        if not _allow_table and str(target).endswith("_table_region"):
            return False
        try:
            if self.env._eval_predicate(["in", obj, target]):
                return True
        except Exception:
            pass
        p = self._obj_pos(obj)
        if target in self._site_names:
            spos, ssize = self._site(target)
            fixture = self._fixture_of(target)
            if target.endswith("_table_region"):
                # R6' 桌面区域：原 in_box 只允许物体中心高出桌面 5 cm，高物体（牛奶盒、酒瓶）永远不满足；
                # 放宽为 ≤ 20 cm，且不在手中；并且**不在任何其他受监控装置区域内**（盒子、抽屉、微波炉、架子等）
                if not (np.all(np.abs(p[:2] - spos[:2]) <= ssize[:2]) and -0.02 <= p[2] - spos[2] <= 0.20
                        and not self._in_hand(obj)):
                    return False
                for r in self.env.regions:
                    if r == target or r.endswith("_table_region"): continue
                    try:
                        if self._in_fixture_region(obj, r): return False
                    except Exception:
                        continue
                return True
            if fixture and "storage_box" in fixture:
                # R1 盒子任意侧：物体在盒内体积中。v5（2026-10-17）：白色储物盒是上下左右四块板、前后开口的方框，
                # bottom/left/right 侧要求物体中心低于顶板（放在顶板上面不算"在盒内"）；top_side 语义未定，保持原容差
                try:
                    bpos, bsize = self._site(f"{fixture}_bottom_side"); tpos, _ = self._site(f"{fixture}_top_side")
                    upper = tpos[2] + 0.03 if target.endswith("_top_side") else tpos[2] - 0.01
                    return bool(np.all(np.abs(p[:2] - bpos[:2]) <= bsize[:2] + 0.01) and bpos[2] - 0.02 <= p[2] <= upper)
                except Exception:
                    return False
            if target.endswith("_heating_region") or target.endswith("_contain_region") or target.endswith("_cook_region"):
                # 容积型区域：水平在站点范围(+2 cm)内，高度在 [站点底 -2 cm, 站点顶 +12 cm]
                return bool(np.all(np.abs(p[:2] - spos[:2]) <= ssize[:2] + 0.02) and spos[2] - ssize[2] - 0.02 <= p[2] <= spos[2] + ssize[2] + 0.12)
            if target.endswith("_top_side"):
                # 顶面薄片：物体中心在平面水平范围(+3 cm)内，且高于平面 ≤ 15 cm
                return bool(np.all(np.abs(p[:2] - spos[:2]) <= ssize[:2] + 0.03) and -0.01 <= p[2] - spos[2] <= 0.15)
            if ssize[0] < 0.01 or ssize[1] < 0.01:
                # 其它竖直薄片（如柜子侧壁）：退化为与站点同一固定装置内部
                return False
            return False
        if target in self.env.obj_body_id:
            # 容器物体（碗/盘/锅/篮）：接触 且 水平距离在容器半径内 且 高度在容器 [-3cm, +15cm]
            tp = self._obj_pos(target)
            return bool(self._contact(obj, target) and np.linalg.norm(p[:2] - tp[:2]) <= self._horizontal_radius(target) + 0.02
                        and -0.03 <= p[2] - tp[2] <= 0.15)
        return False

    def on_relaxed(self, obj, target) -> bool:
        try:
            if self.env._eval_predicate(["on", obj, target]):
                return True
        except Exception:
            pass
        p = self._obj_pos(obj)
        if target in self._site_names:
            spos, ssize = self._site(target)
            return bool(np.all(np.abs(p[:2] - spos[:2]) <= ssize[:2] + 0.03) and -0.01 <= p[2] - spos[2] <= 0.15)
        if target in self.env.obj_body_id:
            tp = self._obj_pos(target)
            return bool(self._contact(obj, target) and p[2] >= tp[2] - 0.02
                        and np.linalg.norm(p[:2] - tp[:2]) <= self._horizontal_radius(target) + 0.03)
        return False

    POUR_WINDOW = 40          # 帧
    POUR_MIN_ABOVE = 5        # 窗口内至少多少帧处于容器上方
    POUR_TILT = 0.2           # 四元数变化阈值（与官方一致）

    def pour_relaxed(self, obj, target) -> bool:
        """R8：倒 = 窗口内被倒物体被抓在手中、位于目标容器上方（水平距离 ≤ 容器半径 + 6 cm，且高于容器），
        且在上方期间发生了 > 0.2 的姿态变化。官方规则（40 帧内最小距离 < 0.3 且姿态变化 > 0.2）会把搬运途中的晃动误判为倒。
        另保留 R2：放进容器也算。"""
        key = (obj, target)
        logs = self._pour_logs.setdefault(key, [])
        p = self._obj_pos(obj); q = self._obj_quat(obj); tp = self._obj_pos(target)
        r = self._horizontal_radius(target) + 0.06
        above = bool(np.linalg.norm(p[:2] - tp[:2]) <= r and p[2] > tp[2] + 0.02 and np.linalg.norm(p - self._eef()) < self._near_thresh(obj) + 0.02)
        logs.append((above, q))
        if len(logs) > self.POUR_WINDOW:
            del logs[:-self.POUR_WINDOW]
        idx = [i for i, (a, _) in enumerate(logs) if a]
        if len(idx) >= self.POUR_MIN_ABOVE:
            q0 = logs[idx[0]][1]
            if max(float(np.linalg.norm(logs[i][1] - q0)) for i in idx) > self.POUR_TILT:
                return True
        return self.in_relaxed(obj, target)

    PICK_SUSTAIN = 10         # 连续帧数（0.5 s）

    def pick_relaxed(self, obj, k) -> bool:
        """R3'：拿起 = 物体靠近末端（< 10 cm）且（相对激活后最低高度抬升 > 4 cm，或已离开所有受监控区域），连续保持 ≥ 10 帧。
        瞬时满足（例如盘子被夹爪掀起一侧）不算。"""
        cur = self._regions_of(obj)
        p = self._obj_pos(obj)
        ref = self._ref_z.get((obj, k))
        self._ref_z[(obj, k)] = p[2] if ref is None else min(ref, p[2])
        seen_in_region = self._prev_regions.get(obj + "#ever", False) or len(cur) > 0
        self._prev_regions[obj + "#ever"] = seen_in_region
        near = np.linalg.norm(p - self._eef()) < self._near_thresh(obj)
        cond = near and ((p[2] - self._ref_z[(obj, k)] > 0.04) or (seen_in_region and len(cur) == 0))
        cnt = self._prev_regions.get(obj + "#cnt", 0)
        cnt = cnt + 1 if cond else 0
        self._prev_regions[obj + "#cnt"] = cnt
        return bool(cnt >= self.PICK_SUSTAIN)

    def open_relaxed(self, target) -> bool:
        try:
            if self.env._eval_predicate(["open", target]):
                return True
        except Exception:
            pass
        if target in self.env.object_sites_dict:
            joints = self.env.object_sites_dict[target].joints or []
            parent = self.env.object_sites_dict[target].parent_name
        else:
            joints = list(getattr(self.env.get_object(target), "joints", []) or []); parent = target
        if not joints:
            return False
        art = self.env.get_object(parent).object_properties.get("articulation", {})
        open_r = art.get("default_open_ranges") or []; close_r = art.get("default_close_ranges") or [0.0, 0.0]
        if not open_r:
            return False
        closed = float(np.mean(close_r)); full_open = min(open_r, key=lambda v: abs(v - closed))  # 最近的"算开"边界
        full_range = float(np.mean(open_r)) - closed
        m = self.env.sim.model
        for j in joints:
            q = float(self.env.sim.data.qpos[m.get_joint_qpos_addr(j)])
            frac = (q - closed) / full_range if abs(full_range) > 1e-6 else 0.0
            if frac >= self.OPEN_FRAC:
                return True
        return False

    def close_relaxed(self, target) -> bool:
        try:
            if self.env._eval_predicate(["close", target]):
                return True
        except Exception:
            pass
        if target in self.env.object_sites_dict:
            joints = self.env.object_sites_dict[target].joints or []; parent = self.env.object_sites_dict[target].parent_name
        else:
            joints = list(getattr(self.env.get_object(target), "joints", []) or []); parent = target
        if not joints:
            return False
        art = self.env.get_object(parent).object_properties.get("articulation", {})
        close_r = art.get("default_close_ranges") or [0.0, 0.0]
        m = self.env.sim.model
        tol = 0.015 if int(m.jnt_type[m.joint_name2id(joints[0])]) == 2 else 0.1   # 滑动关节 1.5 cm / 铰链 0.1 rad
        return all(abs(float(self.env.sim.data.qpos[m.get_joint_qpos_addr(j)]) - float(np.mean(close_r))) <= tol for j in joints)

    def eval_state(self, obj, state, k) -> bool:
        pred = state[0]
        if pred == "pick":
            return self.pick_relaxed(obj, k)
        if pred == "pour":
            return self.pour_relaxed(obj, state[2])
        if pred in ("in", "on"):
            # R10（v5）：放置类子目标要求物体已离手（双指未同时接触）且连续保持 PLACE_SUSTAIN 帧，
            # 避免手持物体经过区域、或放置途中被取消时被记为完成（进度只增不减）
            ok = (self.in_relaxed(obj, state[2]) if pred == "in" else self.on_relaxed(obj, state[2])) and not self._in_hand(obj)
            key = (obj, k); n = (self._place_hold.get(key, 0) + 1) if ok else 0; self._place_hold[key] = n
            return n >= self.PLACE_SUSTAIN
        if pred == "open":
            return self.open_relaxed(state[1])
        if pred == "close":
            return self.close_relaxed(state[1])
        try:
            return bool(self.env._eval_predicate(state))
        except Exception:
            return False

    def precomplete(self, counts) -> None:
        """把每个物体链开头的 k 个子目标记为已完成（RoboCerebra 描述错位：episode 从第 2 个子步开始，此前的子目标不计分，
        由调用方从分子分母中扣除）。兼容 R11 探索前缀。"""
        for obj, k in (counts or {}).items():
            states = self.goal.get(obj, [])
            k = int(min(k, len(states))); L = self.explore_prefix_len(states)
            pd = self._pdone.setdefault(obj, set())
            for i in range(min(k, L)): pd.add(i)
            self._progress[obj] = max(self._progress.get(obj, 0), max(k, L))
        self.excluded = int(sum(int(v) for v in (counts or {}).values()))

    EXPLORE_ORDER_FREE = True  # v6 R11；False 还原 v5（完全按序）

    def explore_prefix_len(self, states) -> int:
        """状态序列开头连续的开/关步骤数（R11 探索前缀）。"""
        if not self.EXPLORE_ORDER_FREE: return 0
        n = 0
        for st in states:
            if st[0] in ("open", "close"): n += 1
            else: break
        return n

    def update(self):
        completion = {}; total = 0; t_now = float(self.env.sim.data.time)
        prefixes = {obj: self.explore_prefix_len(states) for obj, states in self.goal.items()}
        if any(prefixes.values()):                       # R11：记录曾经打开过的目标（close 只在打开过之后计入）
            for obj, states in self.goal.items():
                for st in states[:prefixes[obj]]:
                    if st[1] not in self._was_open and self.open_relaxed(st[1]): self._was_open.add(st[1])
        for obj, states in self.goal.items():
            L = prefixes[obj]; pd = self._pdone.setdefault(obj, set())
            for i in range(L):                           # 探索前缀：各步独立计分
                if i in pd: continue
                st = states[i]
                ok = self.open_relaxed(st[1]) if st[0] == "open" else (st[1] in self._was_open and self.close_relaxed(st[1]))
                if ok:
                    pd.add(i); self.events.append((t_now, f"{obj}:{st}"))
            k = max(self._progress.get(obj, 0), L); self._progress[obj] = k     # 其后的步骤按顺序推进，不等前缀完成
            if k < len(states) and self.eval_state(obj, states[k], k):
                self._progress[obj] = k + 1
                self.events.append((t_now, f"{obj}:{states[k]}"))
            n_done = len(pd) + (self._progress[obj] - L)
            total += n_done
            completion[obj] = n_done / len(states) * 100.0 if states else 100.0
        return completion, int(total), bool(total == self.n_goals)

    @property
    def progress(self):
        return dict(self._progress)
