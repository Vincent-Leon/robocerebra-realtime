"""RoboCerebra 环境与数据加载工具（独立于 OpenVLA 依赖）。

用法: 由 exp/ 下的实验脚本 import。所有路径以项目根目录（具身智能/）为基准。
"""
from __future__ import annotations

import json
import os
import pickle
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import random
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent          # 具身智能/
LIBERO_ROOT = PROJECT_ROOT / "repos" / "RoboCerebra" / "LIBERO"  # 捆绑版 LIBERO
BENCH_ROOT = PROJECT_ROOT / "data" / "RoboCerebra_Bench"
RUNS_ROOT = PROJECT_ROOT / "exp" / "runs"

TASK_TYPES = [
    "Ideal", "Memory_Execution", "Memory_Exploration",
    "Mix", "Observation_Mismatching", "Random_Disturbance",
]
# 与官方 evaluation/utils.py 一致：这三类复用 Ideal 目录的任务与 init 文件
USE_IDEAL_FILES = {"Ideal", "Observation_Mismatching", "Random_Disturbance"}


def bootstrap_libero_config() -> None:
    """在导入 libero 之前写好 config.yaml，避免首次导入时的交互式 input()。"""
    cfg_dir = PROJECT_ROOT / "exp" / ".libero"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("LIBERO_CONFIG_PATH", str(cfg_dir))
    cfg_file = Path(os.environ["LIBERO_CONFIG_PATH"]) / "config.yaml"
    pkg_root = LIBERO_ROOT / "libero" / "libero"
    if not cfg_file.exists():
        import yaml
        cfg = {
            "benchmark_root": str(pkg_root),
            "bddl_files": str(pkg_root / "bddl_files"),
            "init_states": str(pkg_root / "init_files"),
            "datasets": str(PROJECT_ROOT / "data" / "libero_datasets"),
            "assets": str(pkg_root / "assets"),
        }
        cfg_file.write_text(yaml.safe_dump(cfg))


bootstrap_libero_config()

# 延迟导入：确保 config 已写好
import libero.libero.envs.bddl_utils as BDDLUtils  # noqa: E402
from libero.libero.envs import TASK_MAPPING  # noqa: E402
from robosuite import load_controller_config  # noqa: E402

BRACKET_RE = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")


@dataclass
class Case:
    task_type: str
    name: str
    dir: Path
    bddl_path: Path
    problem_name: str
    scene: str
    task_line: str
    steps: List[str]
    step_ranges: List[Tuple[int, int]]
    step_objects: List[str]
    goal: Dict[str, List[List[str]]]
    goal_steps: Dict[str, List[int]]
    distractor: Optional[str]
    init_state: Optional[np.ndarray] = None
    demo_actions: Optional[np.ndarray] = None
    demo_states: Optional[np.ndarray] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def n_steps(self) -> int:
        return len(self.steps)

    @property
    def n_goals(self) -> int:
        return sum(len(v) for v in self.goal.values())


def parse_task_description(txt_path: Path):
    lines = [ln.strip() for ln in txt_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    task_line, steps, ranges, related = "", [], [], []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("Task:"):
            task_line = ln.split(":", 1)[1].strip()
        elif ln.startswith("Step"):
            steps.append(ln.split(":", 1)[1].strip())
            rng, rel = (None, None), ""
            if i + 1 < len(lines):
                m = BRACKET_RE.match(lines[i + 1])
                if m:
                    rng = (int(m.group(1)), int(m.group(2)))
                    i += 1
            if i + 1 < len(lines) and lines[i + 1].startswith("Related Objects:"):
                rel = lines[i + 1].split(":", 1)[1].strip()
                i += 1
            ranges.append(rng)
            related.append(rel)
        i += 1
    return task_line, steps, ranges, related


def load_goal(json_path: Path):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    goal, goal_steps = {}, {}
    for obj, items in data.items():
        acts, stp = [], []
        for k, it in enumerate(items):
            if isinstance(it, dict) and "state_pair" in it:
                pair = it["state_pair"]
                acts.append([pair[0].lower(), *pair[1:]])
                stp.append(it.get("task_step", k))
            elif isinstance(it, list):
                acts.append([it[0].lower(), *it[1:]])
                stp.append(k)
        goal[obj], goal_steps[obj] = acts, stp
    return goal, goal_steps


def case_dirs(task_types=None) -> List[Tuple[str, Path]]:
    out = []
    for t in task_types or TASK_TYPES:
        src = BENCH_ROOT / ("Ideal" if t in USE_IDEAL_FILES else t)
        for d in sorted(src.iterdir(), key=lambda p: (len(p.name), p.name)):
            if d.is_dir() and list(d.glob("*.bddl")):
                out.append((t, d))
    return out


def load_case(task_type: str, case_dir: Path, load_demo: bool = True) -> Case:
    bddl = sorted(case_dir.glob("*.bddl"))[0]
    info = BDDLUtils.get_problem_info(str(bddl))
    task_line, steps, ranges, related = parse_task_description(case_dir / "task_description.txt")
    goal, goal_steps = load_goal(case_dir / "goal.json")
    step_objects = []
    tj = case_dir / "task_description.json"
    if tj.exists():
        try:
            step_objects = [x.get("object", "") for x in json.loads(tj.read_text())]
        except Exception:
            step_objects = []
    distractor = None
    dn = case_dir / "distractor_name.txt"
    if dn.exists():
        distractor = dn.read_text().strip() or None
    init_state = None
    init_dir = "Ideal" if task_type in USE_IDEAL_FILES else task_type
    init_file = BENCH_ROOT / "init_files" / init_dir / f"{case_dir.name}.init"
    if init_file.exists():
        with open(init_file, "rb") as f:
            init_state = pickle.load(f)
    actions = states = None
    if load_demo and (case_dir / "demo.hdf5").exists():
        import h5py
        with h5py.File(case_dir / "demo.hdf5", "r") as h:
            g = h["data"]["demo_1"]
            actions = g["actions"][()]
            states = g["states"][()]
    scene = bddl.name.split("_")[0] + "_" + bddl.name.split("_")[1]
    return Case(task_type, case_dir.name, case_dir, bddl, info["problem_name"], scene, task_line,
                steps, ranges, related, goal, goal_steps, distractor, init_state, actions, states)


def agent_regions(env) -> list:
    """提供给规划器的区域 id：BDDL 声明的区域（env.regions），再加上物体自带的功能性站点（灶台 cook_region、托盘 contain_region、
    center_region，不含 *_init_region）。评分目标会引用这些站点，但 BDDL 未声明，60 个任务中 10 个因此有一个子目标对规划器不可达
    （x_scan_goal_targets.py；如 Memory_Exploration case5 的"平底锅放上灶"）。r4 起补上（2026-10-21）。"""
    out = list(env.regions)
    for s in getattr(env, "object_sites_dict", {}):
        if not s.endswith("_init_region") and s not in out:
            out.append(s)
    return out


def make_env(case: Case, camera_names=("agentview", "robot0_eye_in_hand"), img_res: int = 256,
             use_camera_obs: bool = True, control_freq: int = 20, scene_seed: int = 0):
    """与官方 evaluation/task_runner.py::setup_task_environment 相同的环境配置。
    scene_seed：LIBERO 在建环境和 reset 时用 np.random 采样固定装置（无关节的盒子、柜子等）的位置，初始状态文件只恢复关节状态，
    恢复不了这些位置（实测储物盒中心在不同实例间相差 1–2 cm）。固定种子使同一任务的每个 episode 场景几何完全一致（2026-10-17 起）。
    之后紧接着调用的 env.reset() 也随之确定。"""
    if scene_seed is not None:
        np.random.seed(scene_seed); random.seed(scene_seed)
    controller_config = load_controller_config(default_controller="OSC_POSE")
    env = TASK_MAPPING[case.problem_name](
        bddl_file_name=str(case.bddl_path),
        robots=["Panda"],
        controller_configs=controller_config,
        has_renderer=False,
        has_offscreen_renderer=use_camera_obs,
        camera_names=list(camera_names),
        ignore_done=True,
        use_camera_obs=use_camera_obs,
        reward_shaping=True,
        camera_heights=img_res,
        camera_widths=img_res,
        control_freq=control_freq,
    )
    return env


def apply_state(env, state: np.ndarray):
    """把扁平化 MuJoCo 状态写入仿真并刷新观测（与官方代码一致）。"""
    env.sim.set_state_from_flattened(state)
    env.sim.forward()
    env._post_process()
    env._update_observables(force=True)
    return env._get_observations()


def check_success(env, goal) -> Tuple[Dict[str, float], int, bool]:
    """官方成功监控器：返回 (每对象完成百分比, 已完成子目标数, 是否全部完成)。有副作用：进度只增不减。"""
    return env._check_success(goal)


def to_image(obs_img: np.ndarray) -> np.ndarray:
    """LIBERO 相机图像是上下颠倒的，保存前翻转。"""
    return obs_img[::-1].copy()


def log(msg: str, fh=None):
    print(msg, flush=True)
    if fh is not None:
        fh.write(msg + "\n")
        fh.flush()
