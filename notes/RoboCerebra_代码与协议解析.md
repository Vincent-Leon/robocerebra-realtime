# RoboCerebra 评测栈：代码与协议解析（Phase 0 调研笔记）

> 来源：`repos/RoboCerebra/`（commit 2573426，2026-04-29）、HF 数据集 `qiukingballball/RoboCerebraBench`（2025-10-17）、论文 arXiv 2506.06677v2（NeurIPS 2025 D&B）。本笔记记录**代码实际做了什么**，用于和计划文档第 5 节的改造方案对齐。

## 1. 仓库组成

| 目录 | 内容 | 对我们的意义 |
|---|---|---|
| `evaluation/` | OpenVLA-OFT 评测入口（`eval_openvla.py` 741 行）、episode 逻辑、任务加载、日志 | **Original 协议的权威实现**，我们的 Original 版本以此为准 |
| `LIBERO/` | 捆绑版 LIBERO（基于 robosuite 1.4，内含 RoboCerebra 专属问题类与资产改动） | 必须用这一份，不能用上游 LIBERO |
| `rlds_dataset_builder/` | 训练数据转 RLDS | 本阶段不用 |

捆绑 LIBERO 相对上游的差异（`diff -rq`）：
- 新增 `envs/problems/base_table_manipulation.py`（473 行）：RoboCerebra 的**顺序状态监控器** `_check_success(monitor_dict)` 与 `pick`/`pour` 特殊谓词。
- 改写 `libero_coffee_table_manipulation.py`（继承 BaseTableManipulation）、`libero_kitchen_tabletop_manipulation.py`、`libero_study_tabletop_manipulation.py`、`libero_living_room_tabletop_manipulation.py`（各自内嵌一份同样逻辑的 `_check_success`）。
- `bddl_base_domain.py`：注释掉默认 `_check_success()` 作为 reward/done 的调用；`env_wrapper.py`：支持自定义控制器配置路径。
- 若干物体/场景 XML（alphabet_soup、cookies、milk、popcorn、plate、white_bowl、coffee table 场景）与新增纹理。
- 没有新增 bddl_files 子目录：**RoboCerebra 的任务 BDDL 全部随数据集下发**（每个 case 目录一个 .bddl），不在 LIBERO 包内。

## 2. 数据集结构（60 个 case）

```
RoboCerebra_Bench/
  Ideal/ Memory_Execution/ Memory_Exploration/ Mix/ Observation_Mismatching/ Random_Disturbance/   各 case1..case10
    caseK/
      <SCENE>_<task>.bddl        场景与初始区域、固定装置、物体（含干扰物）
      demo.hdf5                  data/demo_1/actions (T,7)  states (T,71)；attrs 含 env_info（OSC_POSE 参数）、model_file
      goal.json                  {object: [{state_pair:[Pred, obj(, region)], task_step:k}, ...]}
      task_description.txt       Task 行 + 每个 Step 的描述、演示帧区间 [start,end]、Related Objects
      task_description.json      每步的 step 文本与主物体名（用于动态扰动找"相关物体"）
      distractor_name.txt        干扰物名
      caseK.mp4 / caseK.png      演示视频与截图
  init_files/{Ideal,Memory_Execution,Memory_Exploration,Mix,Observation_Mismatching}/caseK.init   pickle 的扁平 MuJoCo 状态
  test.parquet
```

要点：
- **Ideal / Observation_Mismatching / Random_Disturbance 三类共用 Ideal 目录的 10 个任务与 init 文件**（`utils.get_task_directories`、`load_init_state`），差别只在运行配置（是否 `dynamic`、是否换描述）。因此"60 个任务"实际是 40 个不同任务文件 × 不同运行条件。
- 场景：55 个 COFFEE_TABLESCENE，5 个 KITCHEN_TABLESCENE（无 STUDY）。
- 演示 `actions` 是 OSC_POSE 增量 + 夹爪（第 7 维 ±1），数值范围超出 [-1,1]（遥操作原始值），robosuite 控制器会裁剪。`states` 可直接 `sim.set_state_from_flattened`。
- 以 Ideal/case1 为例：6 个子步、3 个物体 × (Pick, In) = 6 个子目标；演示 2554 步（20 Hz ≈ 128 s），每子步 242–490 步。**官方评测每子步只给 150 步（7.5 s）**，远小于人类演示时长，说明微调后的 OpenVLA 动作快于遥操作，也说明时间预算是协议的隐含变量。

## 3. Original 评测协议（`eval_openvla.py::run_episode`）

1. 建环境：`TASK_MAPPING[problem_name](bddl, robots=["Panda"], OSC_POSE, 两相机 256×256, control_freq=20, ignore_done=True)`。
2. `env.reset()` 后 `set_state_from_flattened(init_state)`（官方 init 文件），前 `num_steps_wait=15` 步发空动作让物体稳定。
3. **固定时间片切换子目标**：`step_idx = t // switch_steps`，`switch_steps=150`，`max_steps = 150 × 子步数`。这就是论文所说的 anchor points——**与模型是否完成当前子步无关，纯按时间切换**。
4. 每个子步给 System 1 的文本是 `task_description.txt` 中的 Step 描述（GT 计划），或由 `--task_description_suffix` 指定的另一份文件（例如 VLM 规划器**离线**生成的计划）。**System 2 不在循环内在线运行**；"Hierarchical Framework"的在线监控代码未随仓库发布。
5. `resume=True` 时，每次切换把仿真**重置到演示中下一子步起始帧的状态** `step_states[step_idx]`，并用 `simulate_resume_completion` 把之前子目标标记为已完成（`total_resume_completed`，不计入 agent 得分）。这使子步评测彼此独立（类似"teacher forcing"）。
6. `dynamic=True`（Random_Disturbance）：在切换后第 10 步，以 50% 概率选"当前子步相关物体"，否则选无关可动物体，把其 **y 坐标瞬移 ±0.15 m**（`handle_dynamic_movement`），方向交替。这是离散重置式扰动，不是物理运动。
7. `dynamic_shift_description`（Observation_Mismatching）：从第 2 个子步开始、换一份描述文件，首段不计分。
8. 每步调用 `env._check_success(goal)`：按 goal.json 中每个物体的状态序列**顺序**判定，进度只增不减；统计 `total_agent_subtasks / effective_total_goals`（子目标完成率）与 `all_done`（整任务成功）。
9. 动作：OpenVLA-OFT 每次推理输出 8 步动作块（`num_open_loop_steps=8`），队列逐步执行；没有任何实时时钟，推理时世界冻结。

## 4. 成功监控器语义（`BaseTableManipulation._check_success`）

- `in obj region`：调用 LIBERO 谓词；对多区域容器（microwave/cabinet/fridge/storage box/shelf/drainer）任一子区域满足即算 `In`。
- 目标是桌面区域时要求物体**先离开桌面再回来**（`_has_left_table`）。
- `pick obj`：物体所在区域集合从非空变为空（离开所有已知区域），且最近 40 帧四元数变化 < 0.1（防止"推倒/碰飞"算作拿起）；`skip_pick_quat_once` 用于 resume 后首帧豁免。
- `pour a b`：最近 40 帧内 a、b 最小距离 < 0.3 且 a 的四元数变化 > 0.2。
- 每次调用有副作用（进度推进、位置日志），**一步只能调用一次**，我们的异步版本要注意只在仿真线程中调用。

## 5. 对计划文档的直接影响

- **Original 版本可以精确复现**，但 System 1 需要 OpenVLA-OFT + CUDA；本机（M1 Pro 16 GB）不可行。Phase 0 在本机能做的是：环境/成功判定/数据的复现与诊断、演示回放 oracle、仿真吞吐测量；OpenVLA 跑分需要 GPU 机器。
- 原协议的"anchor 切换"= **固定 150 步时间片 + 可选状态重置**，没有"完成即切换"。计划文档 5.4 的三种切换对照中，"原协议切换"应实现为固定时间片；"模型自主切换"是全新的。
- 原协议的扰动是瞬移式，正好对应计划文档 5.5 对"离散重置应标注为抽象扰动"的要求；E2 的"容器被可见地移动"可以先复用这个机制再做物理化。
- 时间预算：官方 150 步/子步 vs 演示 242–490 步/子步，Real-time 版本的截止时间设计必须先用固定执行器实测各技能耗时（计划 5.6 "用固定控制器和诊断 oracle 验证期限可行"）。
- 60 个目录实际只有 40 个任务文件，选 5–10 个任务做 pilot 时应按**任务文件**去重，并同时覆盖 Ideal 条件与 Memory 类任务。
