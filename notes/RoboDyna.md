# Benchmarking Robotic Manipulation under Physically Realistic Dynamics（RoboDyna）

## 基本信息

- **作者 / 单位**：Zhiyuan Li (Huawei Technologies Canada, University of Toronto)、Ruiheng Yang、Xuan Zhao、Amir Rasouli (通讯, Huawei Technologies Canada)（p.1）。
- **发表**：p.1 脚注 "Accepted at the NeurIPS 2026 Workshop on Robot Learning with World Models: Capabilities, Frontiers, and Challenges"。**Workshop 论文**，非主会论文；arXiv 编号未在论文中找到。
- **篇幅**：PDF 共 9 页：正文 pp.1–7（含参考文献 pp.7–8）、附录 A 任务列表 p.9。
- **链接**：项目页 https://robodyna.github.io/robodyna/ ；代码 https://github.com/robodyna/robodyna （Apache-2.0）；数据与资产 https://huggingface.co/RoboDyna （运行时资产包 `RoboDyna/RoboDyna-assets`，`robodyna-assets-v1.tar.gz` 约 1.2 GiB；X-VLA 权重 `RoboDyna/X-VLA-RoboDyna`）。
- **本地文件**：PDF `papers/RoboDyna_neurips2026_workshop.pdf`；仓库克隆 `repos/RoboDyna/`（最近提交 `6422e62`，2026-10-01）。本次只浏览代码，未运行任何脚本。
- **仿真栈来源**：论文正文只引用 SAPIEN（p.3）；"RoboTwin 2.0" 一词**未在论文中出现**。仓库 README 致谢 "RoboDyna builds on RoboTwin 2.0, DOMINO, and SAPIEN"，`assets/asset_manifest.json` 标明物体网格与 UR5-WSG 本体网格来自 `TianxingChen/RoboTwin2.0`（MIT）。

## 一句话总结

RoboDyna 是一个基于 SAPIEN 的双臂动态操作基准：20 个概念任务（五类物理理解能力 × 4 种难度条件）+ 10 个家居任务，3,500 条专家演示，并提出**配对的同步（推理时世界冻结）/ 异步（把每次前向的真实耗时折算成仿真步数计入世界）评测协议**；对 π0.5、X-VLA 和 FastWAM 的 5,400 个 episode 评测显示：所有策略成功率低于 20%，延迟计费使平均成功率变化至多 0.03，但重新"洗牌"了三分之一到一半的成功样本，在"世界掌握时钟"的 state-transition 任务上系统性掉分（p.5, p.7）。

## 问题设定与动机

- **两种能力、现有基准都不测**："Physical competence has two components: knowing how the scene will evolve, and how to respond to it. Current benchmarks score neither."（p.1）预测型世界模型基准（Cosmos、Genie Envisioner）只测预测不测动作；机器人基准（ManiSkill2、LIBERO、RoboCasa）没有动态元素，或（Fang et al. 2026）用脚本化、物理上不可信的运动，且"the world halts while the policy infers"（p.2）。
- **冻结世界评测的三个后果**（p.2）：(1) 测得的物理能力不能迁移到真实世界；(2) 物理预判永远不必要——"If the world waits, acting on the current observation is always correct"；(3) 推理成本免费——"A policy taking seconds per chunk ... scores like one running at tens of Hz"。
- **针对 WAM 的动机**：world-action model 的卖点是"act on where things will be"，但目前只用视频质量等生成代理或静态同步世界的成功率评估，"Neither tests whether imagination improves control under time pressure."（p.2）
- **与并行工作的区别**：DynamicVLA (Xie et al. 2026)、Reflex (Chen et al. 2026) 放松了同步约定，"but none scores the same episode under both a synchronized and an asynchronous setting"（p.3）。RoboDyna 的三点定位：物理驱动的动态（滚动、弹跳、滑动、旋转）、按策略自身测得的延迟计费并在两协议下重放同一种子、提供人类基线（p.3）。
- **贡献声明**（p.2）：五类能力、可组合难度因子的物理驱动动态任务集 + 延迟计费的异步协议；对 SOTA VLA 与 WAM 的评测；两种控制方式下的人类基线。

## 核心设计

### 仿真器与机器人

- 每个任务是 "a language-conditioned dual-arm manipulation problem in SAPIEN whose scene evolves under its own dynamics"（p.3）。论文未给出机器人型号。
- 仓库事实：`task_config/demo_dynamic.yml` 设 `embodiment: [ur5-wsg, ur5-wsg, 0.6]`，即两台 UR5 + WSG 夹爪、基座间距 0.6 m（`assets/embodiments/ur5-wsg/config.yml`，6 关节 + 1 夹爪/臂，规划器 `curobo`）。相机：`head_camera` D435 320×240（`fovy 37`）+ 左右腕相机（`_camera_config.yml`、`_run_*_base.yml`）。另有 `aloha-agilex` 本体配置但默认不使用。
- 物理步频 250 Hz（p.4；代码 `TOPP(..., 1/250)`）。

### 五类概念任务（20 个）与家居任务（10 个）

五类能力定义（p.3–4）与任务（附录 Table 3, p.9）：

| 类别 | 定义（p.3–4） | 任务 |
| --- | --- | --- |
| Trajectory prediction | 物体直线或经弹跳后朝目标运动 | `catch_ramp_ball`, `catch_valley_ball`, `stop_valley_ball`, `save_goal` |
| Periodic pattern | 场景含周期运动（如旋转平台），需理解模式并在正确时刻行动 | `catch_marbles_trapdoors`, `catch_cuboid`, `drop_ball_hole`, `whack_moles` |
| Dynamic avoidance | 与运动物体（如火车）交互，同时避开静态或移动障碍 | `put_cup_belt`, `hit_target`, `load_train`, `place_block_belt` |
| State transition | 物体或环境改变状态（如苹果成熟） | `cook_meat_timer`, `pick_ripe_apple`, `sort_apples_belt`, `pack_fruits` |
| Static to dynamic | 开始时无物运动，机器人须自己产生所需运动（如台球） | `catch_shelf_marble`, `dispense_gummy`, `marble_shelf_maze`, `play_billiard` |
| Household（10） | 办公室/厨房真实场景，日常物理过程（牛奶沸腾溢出、咖啡洒向笔记本、啤酒泡沫） | `boil_milk`, `catch_cup`, `catch_mouse_object_drop`, `clean_table`, `cook_food_timer`, `make_soup`, `measure_ingredient`, `pour_beer`, `stop_ball`, `trap_bug` |

- **四种条件 / 三档难度**（p.4）：`base`（easy）、`var1`、`var2`（各打开一条任务特定扰动轴，medium）、`var1+2`（二者组合，hard，**训练演示中刻意不含**，用于测组合泛化）。仓库中对应名称为 `default / opt1 / opt2 / opt1+2`（README；`task_config/scenario_overrides.py`）。家居任务无变体（`script/evaluation_protocol.py`）。
- 扰动轴是任务特定的（Table 4, p.9），"Some axes change the physics, some add a distractor, some remove an affordance such as a retry or a clear view"。例：`catch_marbles_trapdoors` base 单色弹珠、最多三次机会；var1 活板门只开一次；var2 加一颗不能接的黑弹珠（p.4）。`sort_apples_belt` var1 颜色随机到达，var2 "0.3 of the apples are rotten"；`pick_ripe_apple` var2 "the basket moves"；`place_block_belt` var1 "the receiving bowl moves"、var2 "a blocker"；`hit_target` var1 挡板、var2 挡板移动；`dispense_gummy` var2 "the belt never stops"（p.9）。
- 家居任务示例：`pour_beer` 须读取上升的泡沫并暂停倾倒；`catch_cup` 须把下落的易碎物接到软表面上（p.4）。
- 仓库中还有未进入论文 30 个任务的环境：`cook_meat`, `punch_dual_holes`, `control_quality`, `fill_coffee_jar`, `cook_food`（`interactive/experiment.yml` 注明默认省略）。

### 同步 vs 异步评测协议（精确定义）

论文定义（p.4）：
- "The simulator steps physics at 250 Hz and holds one policy action for 15 steps (60 ms, the demonstration cadence); each policy commits its official chunk length before observing again."
- **sync**："Under sync the world is frozen while the policy computes."
- **async**："Under async the wall-clock time of each forward pass is measured and charged to simulated time before the chunk lands; during the charge the arm holds its last commanded joint target while the scene keeps evolving. A single charge is capped at 1 s, and the first call of each process is discarded so that one-off graph compilation is not billed."
- 平均计费延迟：π0.5 109 ms、X-VLA 156 ms、FastWAM 236 ms（p.4）。两协议在相同种子上重放（p.3）。

代码实现（`envs/_base_task.py`，类 `Base_Task`）：
- `configure_async_inference(enabled=False, sim_hz=250.0, max_idle_steps=2000, video_stride=5)`：开关 + 计数器清零。
- `inference_window()`（`contextlib.contextmanager`）：策略适配器用 `with TASK_ENV.inference_window(): actions = model.act(...)` 包住一次前向；关闭时为 no-op；开启时用 `time.perf_counter()` 测 `dt`，累加 `_inference_time_total/_inference_calls`，再调用 `advance_idle_steps(round(dt * sim_hz))`。
- `advance_idle_steps(n)`：**不**重设关节目标（"the drives keep their previous setpoint"），循环 `_tick_kinematic_tasks(); scene.step(); _update_transient_checks(); _update_render()`，每步检查 `check_success()`，成功或超过 episode 截止则提前退出；`n` 上限为 `_async_max_idle_steps`。
- `async_inference_stats()` 返回 `idle_steps_total / inference_time_total_s / inference_calls / inference_latency_mean_s`，由 `script/eval_policy.py` 写入 `_metrics.json` 的 `inference_timing` 字段，并记录 `evaluation_protocol.inference_mode = "async" | "frozen"`。
- **关键性质**：这是"测完再计费"的串行模型——推理期间仿真实际上是停止的，之后一次性补推 `dt·250` 步；推理与动作块执行**不重叠**，补推期间手臂空转保持上一目标。`frozen` 模式下 `scene.step()` 只在 `take_action()` 内运行（`policy/xvla/README.md`）。
- **与论文描述的两处差异（需向作者确认）**：(1) 论文说单次计费上限 1 s，代码默认 `max_idle_steps=2000`（250 Hz 下为 8 s），且 `eval_policy.py` 调用 `configure_async_inference` 时未覆盖该参数；(2) "丢弃每个进程的首次调用"在 `_base_task.py`、`eval_policy.py` 与各 `deploy_policy.py` 中未找到对应代码，可能在离线统计或模型服务端处理。
- "holds one policy action for 15 steps" 与数据采集的 `save_freq: 15` 一致；评测时 `take_action()` 对每个动作做 TOPP 时间参数化（`1/250` s 步长），实际仿真步数随轨迹而变（规划失败时固定 50 步）。

### 观测与动作接口

- `Base_Task.get_obs()` 返回字典：`observation.{head_camera,left_camera,right_camera}.rgb`（可选 depth/分割/点云），`joint_action.{left_arm(6), left_gripper, right_arm(6), right_gripper, vector(14)}`，`endpose.{left_endpose(7), left_gripper, right_endpose(7), right_gripper}`（16 维）。个别任务在 `get_obs()` 中附加特权状态（如 `sort_apples_belt` 的 `obs["sorting"]`：`gate_left`, `correct`, `belt_speed` 等），论文评测的策略只用图像 + 本体感知。
- 动作：`take_action(action, action_type='qpos'|'ee')`。π0.5 输出 14 维关节目标（`qpos`）；X-VLA 输出 20 维绝对 EE6D 块（`ee`，四元数 wxyz、夹爪 [0,1]，见 `policy/xvla/README.md`）。每次推理后按块逐个 `take_action`：π0.5 `pi0_step: 50`（`policy/pi05/deploy_policy.yml`）；FastWAM 每次执行 32 步预测中的 24 步，"RoboDyna runs at 16.7 Hz, so 24 steps commit to 1.44 s of open-loop motion"（`policy/fwam/README.md`）。
- 语言指令：每任务一条固定句子（`task_config/task_instructions.json`），如 `catch_ramp_ball`: "Place the blue cup in front of the ramp to catch the red ball before hitting the table."

### 成功判定与指标

- 每任务重写 `check_success()`，在 `take_action()` 和 `advance_idle_steps()` 的**每个仿真步**检查，一旦为真即 `eval_success=True` 结束 episode。失败：`eval_fail`、动态目标出界 `out_of_bounds`、或 `take_action_cnt` 达 `step_lim`（`eval_step_limit: 15000`，`demo_dynamic.yml`；`envs/utils/household_view.py` 的 `EPISODE_MAX_STEPS = 15000`）。
- 进度分 "PS = b · 2^−m ∈ [0,1], where b credits observable completed milestones and m counts penalty events"（p.4）；`pour_beer` 液位带得 0.25–0.75，溢出得 0。实现：`envs/utils/partial_score.py::completed_action_score`（`factor = 0.5 ** count`），各概念任务里程碑规则在 `envs/utils/base_partial_scores.py`，家居任务各自 `get_score()`。
- 代码还计算 Manipulation Score / Route Completion / 碰撞罚分（出界 0.5、杂物碰撞 0.8，`script/eval_metrics.py`），论文未报告。

### 专家演示数据规模

- "We provide 50 expert demonstrations for each of the 70 configurations excluding var1+2"（20×3 + 10 = 70），共 3,500 条（p.4）。README："3,500 expert demonstrations from task-specific expert controllers"，即各任务 `play_once()` 中的脚本化专家（使用特权状态）。
- 采集：`bash scripts/collect_data.sh <task> demo_dynamic <gpu> [scenario]`，输出 `data/<task>/<scenario>/` HDF5 + `data_lerobot/` 的 LeRobot v2.1 导出（README）。
- 评测规模：每个 task–condition–protocol 槽位同样 10 个保留种子（`task_config/eval_seeds.yml`，"single source of truth" 同时供人类实验使用），每策略每协议 900 episode，共 5,400（p.4）。三策略均在全部 3,500 条演示上微调、单一 checkpoint（π0.5 与 X-VLA 30k 步，FastWAM 13k 步，p.4）。
- 评测流程（`script/eval_policy.py::eval_policy`）：每个固定种子先用专家 `play_once()` 复核（失败即 `RuntimeError`），再以同种子重建场景、恢复 `_saved_dynamic_motion_info`、设指令、`configure_async_inference`，然后 `while take_action_cnt < step_lim: obs = get_obs(); eval(TASK_ENV, model, obs)`。

### 人类基线

- 12 名参与者，在相同种子上玩概念任务的 `var1+2` 与家居任务的 `base`；两种控制：**teleoperation**（键盘驱动机械臂，"like a policy"）与 **scene-interactive**（点选直接作用于物体，去掉底层控制成本）（p.6；项目页）。GUI：`interactive/experiment_gui.py`、协议 `interactive/experiment.yml`，日志 `data/exp_logs/<user>/user.json`。

## 代码实现要点

**安装与依赖**（`README.md`、`script/install_robodyna.sh`）
- 要求："Linux, an NVIDIA GPU with a CUDA-capable driver, Python 3.10, Vulkan, and FFmpeg"。
- 脚本流程：conda 建 `robodyna` 环境（Python 3.10）→ `pip install -r script/requirements.txt`（固定 `torch==2.4.1`, `sapien==3.0.0b1`, `mplib==0.2.1`, `gymnasium==0.29.1`, `open3d==0.18.0`, `huggingface_hub==0.25.0` 等）→ 覆盖安装 **`sapien==3.0.3`**（"RoboDyna standardizes on SAPIEN 3.0.3"）→ Pillow/PyYAML → 可选 pytorch3d（git）→ 用 `sed -i -E` 打补丁 SAPIEN `urdf_loader.py` 与 mplib `planner.py` → `git clone NVlabs/curobo` 到 `envs/curobo` 并 `pip install -e . --no-build-isolation`（需 CUDA 编译）。
- 资产：`bash script/_download_assets.sh` → `assets/_download.py` 从 HF 下载并校验 sha256 后解压（~1.2 GiB）。无头渲染需 `export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json; unset DISPLAY`。
- **macOS：不支持**。仓库无任何 macOS/darwin 说明；CuRobo 依赖 CUDA，渲染依赖 NVIDIA Vulkan ICD，安装脚本的 `sed -i -E` 为 GNU 语法。脚本末尾提到的 `scripts/build_domino_aarch64.sh`（aarch64/GB10）和 `scripts/collect_data.sh` 引用的 `script/.update_path.sh` **均不存在于仓库**。
- 策略各需独立环境：X-VLA 推理服务器单独 venv（transformers 与仿真环境冲突，`policy/xvla/README.md`）；π0.5 通过 `policy/pi05_ws/`（openpi websocket）远程服务（"the sim venv has sapien 3.0.3 + curobo but no openpi"）；FastWAM 与仿真同进程，约 29 GiB 显存（`policy/fwam/README.md`）。`compat/sitecustomize.py` 为 Python 3.10 打 `datetime.UTC` 补丁。

**异步评测核心文件与类名**
- `envs/_base_task.py`：`class Base_Task` — `configure_async_inference`, `inference_window`, `advance_idle_steps`, `async_inference_stats`, `_write_idle_video_frame`, `take_action`, `get_obs`, `check_success`, `get_score`, `_tick_kinematic_tasks`/`_update_kinematic_tasks`（传送带、地鼠、振荡搁板等运动学驱动元素的逐步更新）, `_episode_past_deadline`。
- `script/eval_policy.py`：评测入口（`main`, `eval_policy`, `parse_args_and_config`）；参数 `--async_inference True|False`, `--async_sim_hz`, `--task_name`, `--task_config`, `--scenario`, `--policy_name`, `--ckpt_setting`, `--seed`, `--eval_step_limit`。输出 `eval_result/<task>/<policy>/<task_config>/<ckpt_setting>/<时间>/{_result.txt,_metrics_report.txt,_metrics.json,_episodes_detail.json,episode*.mp4}`。
- `script/evaluation_protocol.py::configure_evaluation(task, args, scenario)` → `(suite, scenario, seeds)`；种子解析在 `interactive/experiment_config.py::evaluation_seeds_for / evaluation_suite`。
- `script/eval_metrics.py`：`EvalMetricsTracker`, `AggregatedMetrics`, `EpisodeMetrics`, `PenaltyEvent`。
- 启动脚本：`policy/<policy>/eval.sh <task> <task_config> <ckpt> <tag> <seed> <gpu_id> [scenario] [frozen|async]`（`frozen` 为默认）。
- 另有基于 TCP/JSON 的通用模型服务 `script/policy_model_server.py`（按 `cmd` 反射调用模型方法）与 `script/eval_policy_client.py`，但二者**未见** `inference_window`/`async_inference` 的使用。

**任务配置格式**（`task_config/`）
- 运行配置 YAML（`demo_dynamic.yml` 为生产配置；`_run_<task>_<scenario>.yml` 为每任务-场景快照）：`embodiment`, `eval_step_limit`, `domain_randomization.*`, `camera.{head_camera_type,wrist_camera_type,...}`, `data_type.{rgb,depth,pointcloud,endpose,qpos,...}`, `interactive_params`, `task_args.<task>.<连续参数>`（如 `catch_ramp_ball` 的 `ramp_angle`, `ball_radius`, `drop_time`, `roll_speed`, `ramp_friction`, `wall_bounce_enabled`, `enable_distractor`）。
- 离散条件矩阵：`scenario_overrides.py` 的 `SCENARIO_OVERRIDES[task][scenario] -> {flag: value}`（如 `pick_ripe_apple`: `two_apples_enabled`, `basket_move_enabled`）；`BASE_SCENARIOS`, `BASE_TASKS`, `HOUSEHOLD_TASKS`。
- `eval_seeds.yml`（10 个种子/槽位）、`task_instructions.json`（指令）、`_camera_config.yml`、`_embodiment_config.yml`、`manifest_collect.txt`（采集清单）。

**策略接口**（`policy/<name>/deploy_policy.py` + `deploy_policy.yml`）
- 模块需提供 `encode_obs(observation)`, `get_model(usr_args)`, `eval(TASK_ENV, model, observation)`, `reset_model(model)`；`eval` 内用 `TASK_ENV.get_instruction()` 取指令，`with TASK_ENV.inference_window(): actions = model...`，再对块中每个动作 `TASK_ENV.take_action(action[, action_type='ee'])`，`TASK_ENV.eval_success` 为真时返回。参考实现：`policy/pi05/deploy_policy.py`（本地 openpi）、`policy/pi05_ws/deploy_policy.py`（websocket）、`policy/xvla/deploy_policy.py` + `xvla_client.py` + `xvla_codec.py`、`policy/fwam/deploy_policy.py`。
- `deploy_policy.yml` 固定字段：`policy_name, task_name, task_config, ckpt_setting, seed, scenario, instruction_type`，再加策略自定义参数（如 X-VLA 的 `host/port/domain_id: 19`）。

**其他**
- 交互 GUI：`interactive/robodyna_gui.py`（总入口）、`base_task_gui.py`、`household_task_gui.py`、`experiment_gui.py`；人类控制映射见 `interactive/keyboard_control.md`。
- `script/bench_script/`：各任务的烟雾测试、种子录制、成功率扫描、演示录制脚本。
- 与论文的其他差异：`policy/pi05/deploy_policy.yml` 默认 `checkpoint_id: 25000`（注释 "wall-clock truncated at 25k"），论文称 π0.5 用 30k 步 checkpoint（p.4）。

## 实验与主要结果

**策略**（p.4）：两个 VLA——π0.5、X-VLA；一个 WAM——FastWAM（"rolls a video prediction forward and decodes an action chunk from it"）。作者声明 "With a single WAM evaluated, WAM-level statements below are observations about this policy rather than the class."

**Table 1（p.4）成功率，两协议合并**：

| | Conceptual E / M | Household | Overall（含 var1+2） |
| --- | --- | --- | --- |
| π0.5 | 0.23 / 0.18 | 0.07 | **0.17** |
| X-VLA | 0.16 / 0.10 | 0.07 | 0.11 |
| FastWAM | 0.07 / 0.06 | 0.04 | 0.05 |

分类别 E/M：π0.5 traj 0.24/0.20、periodic 0.28/0.14、dyn-avoid 0.36/0.38、state-trans 0.15/0.09、static-to-dyn 0.10/0.09；X-VLA 0.23/0.17、0.06/0.02、0.24/0.11、0.24/0.18、0.05/0.03；FastWAM 0.04/0.08、0.00/0.00、0.00/0.00、0.12/0.12、0.17/0.07（p.4）。（README 表的 Overall 不含 Hard，为 0.18/0.11/0.06，与论文 Table 1 口径不同。）

**Table 2（p.5）SR/PS 按协议**（Avg. 为五类均值）：π0.5 sync 0.22/0.30 → async 0.19/0.28；X-VLA sync 0.12/0.16 → async 0.14/0.19；FastWAM sync 0.07/0.12 → async 0.05/0.11。State transition：π0.5 0.16→0.09、X-VLA 0.21→0.21、FastWAM 0.19→0.06。Household：π0.5 0.06/0.21→0.07/0.22，X-VLA 0.07/0.13→0.06/0.14，FastWAM 0.02/0.08→0.05/0.15。

**R1（p.5）WAM 的预测带来的是"不同"而非"更好"的能力**：FastWAM 总体最差（0.05 vs 0.17、0.11），但在 static-to-dynamic easy 上最高（0.17 vs 0.10、0.05）。回放其预测视频：30 个任务中只有 12 个预测出场景自身运动，其余 18 个 "reproduces a near-frozen input or erases the moving object"；四个 periodic-pattern 任务预测全部错误，对应成功率为 0。"FastWAM never scores above zero on a task where its prediction is actively wrong"。VLA 不预测，靠跟踪与试错成功，"an approach that never predicts the future has an upper bound"。

**R2（p.5）延迟决定"哪些"成功而非"多少"成功**：sync→async，π0.5 与 FastWAM 平均成功率仅降 0.03 与 0.02，X-VLA 反升 0.02；但逐种子配对后 "a third to a half of every policy's successes are protocol-contingent (π0.5 loses 0.38 of its sync successes and gains 49 new ones)"。State transition 损失最大（π0.5 −0.07、FastWAM −0.13、X-VLA 持平），因为 "A state-transition task evolves in one direction and runs a deadline the robot did not start and cannot pause—the apple ripens and does not turn green again"。最大单项效应：FastWAM 在 `sort_apples_belt` 上 sync 0.65 vs async 0.17。
- **关于"延迟翻转 5–12% episode 结果但平均成功率变化至多 3%"**：这句话出自仓库 README（"Moving from synchronous to asynchronous evaluation changes average success by at most 0.03 but flips 5–12% of episode outcomes"）和项目页摘要（"inference latency flips 5–12% of episode outcomes while changing average success rates by at most 3%"），**PDF 正文中没有 "5–12%" 这一数字**；论文中对应的表述是 "at most 0.03"（p.5、p.7）与 "re-deals a third to a half of every policy's successes"（p.7）。含义：以全部 episode 为分母，约 5–12% 的 episode 在两协议下结果不同（成功↔失败），而净变化相互抵消，所以只看平均成功率会掩盖延迟的因果影响。引用时建议注明来源为项目页/README。

**R3（p.5–6）组合泛化**：easy/medium/hard 成功率 π0.5 0.23/0.18/0.14、X-VLA 0.16/0.10/0.09、FastWAM 0.07/0.06/0.04，hard 保留 easy 的 0.56–0.61；崩溃集中在 periodic pattern（变体多为加入干扰物或移除重试/清晰视野等 affordance）；trajectory prediction 受影响最小，"a combination of dynamics is not difficult, but an unseen dynamic can be catastrophic"。

**人类基线（p.6–7）**：在 var1+2 条件下，teleoperation 50.2% vs 最佳策略 14%；interactive 77.1%。两种控制的差距在时间关键类别最大（trajectory prediction 0.67→0.27，periodic 0.75→0.42），static-to-dynamic 最小（0.62→0.53）。interactive 下 state transitions 0.88、household 0.84 最容易。VLA 在人类最难处相对最强（π0.5 dynamic avoidance 0.29，trajectory 0.23；X-VLA trajectory 0.20），但在 periodic pattern 上崩溃（0.07、0.00 vs 人类 0.75）。

**未发布内容**：p.9 "Full per-task, per-condition, per-protocol results will be published with the benchmark upon acceptance."（项目页任务画廊提供按条件、两协议平均的每任务成功率。）

## 与本项目的关系

对照 `realtime_robot_reasoning_benchmark_plan-2.md` 第 2、5.1、5.5、7.1 节：

**1. 哪些动态任务天然具有"等待会改变可执行动作/约束/结果"的性质（可作 E2/E3 的物理版本）**

| 我们的事件类型 | RoboDyna 中的天然对应 | 说明 |
| --- | --- | --- |
| E3 有期限的机会/约束 | `pick_ripe_apple`（成熟窗口 `RED_WINDOW 0.78–0.82`、不可逆变黑，`RIPEN_STEPS_DEFAULT=3600` 步 ≈ 14.4 s）、`cook_meat_timer`（绿→黄→红饼图计时，过熟不可逆）、`sort_apples_belt`（每个苹果被传送带带走前必须分流）、`boil_milk`/`pour_beer`（溢出截止）、`catch_*`/`stop_valley_ball`/`save_goal`（一次性接球窗口）、`catch_marbles_trapdoors var1`（"the door opens once, no retry"）、`load_train`/`whack_moles`（周期性到达窗口） | 期限由物理/状态过程给出，不是人为计时器，正是论文 R2 所说 "the world owns the clock"。这些任务是验证我们"延迟干预"条件（计划 §7.1）最直接的物理载体 |
| E2 场景状态变化（容器移动、放置区被占） | `pick_ripe_apple var2`（篮子移动）、`place_block_belt var1/var2`（接收碗移动 / 挡板）、`marble_shelf_maze var2`（接收碗振荡）、`hit_target var1/var2`（挡板出现/移动）、`put_cup_belt var1/var2`（帘子遮挡/移动）、`save_goal var2`（球门部分遮挡） | 已有 `SCENARIO_OVERRIDES` 开关，可直接作为"有/无事件"的配对对照（计划 §5.3 要求保留无事件对照） |
| 条件规则 / 任务依赖（P1 新增项） | `sort_apples_belt`（颜色→篮子映射；var2 腐烂苹果须进垃圾箱，否则失败）、`pack_fruits`（两色 / 干扰物）、`catch_marbles_trapdoors var2`（黑弹珠不能接）、`dispense_gummy`（只收目标色）、`play_billiard var1`（指定球袋）、`load_train var1`（指定车厢） | 已含"条件规则"雏形；但规则是**固定在任务里、写进单句指令**的，没有运行中更新 |
| E1 明确目标更新 | **无** | 指令为每任务一条固定字符串（`task_instructions.json`），需自行加入运行中指令变更与可观测提示 |
| E4/E5 依赖重排 / 争取时间 | `sort_apples_belt`、`pack_fruits` 的多物序列可改造为 E4；无暂存区机制 | 需新增 |

注意：论文强调 "physics-governed"，但代码里驱动元素（传送带、地鼠、振荡搁板、活板门）由 `active_kinematic_tasks` **运动学脚本**逐步推进，被操作物体（球、苹果、弹珠）才是 PhysX 刚体；另有源自 RoboTwin 的 `init_dynamic_motion_for_eval`/`stop_dynamic_object_motion`（目标物体按保存的轨迹运动、接触即停）。对应计划 §5.5 "物理可解释的移动方式 vs 离散重置"，应在报告中区分这两类运动来源。

**2. 他们评测低层策略，我们要加高层决策接口——衔接点**
- 接入点是 `policy/<ours>/deploy_policy.py` 的 `eval(TASK_ENV, model, observation)`：可在此放"高层决策模型 + 固定底层执行器"的组合，底层执行器可复用各任务 `play_once()` 的脚本化专家（有特权状态、需拆成可中断原语）或微调好的 π0.5/X-VLA；高层与低层的推理耗时都可用 `TASK_ENV.inference_window()` 计费，天然对应计划 §4.1 "固定底层控制，评估决策层"。
- `script/eval_policy.py` 的 episode 循环、`evaluation_protocol.py` 的固定种子与 `_metrics.json`（含 `inference_timing`）可直接作为我们 Original/Real-time 版本的日志基础；`get_score()` 的里程碑分可对应计划 §7.2 的"任务进度"。
- **必须改造的地方**：(a) RoboDyna 的 async 是"推理阻塞 + 事后补推"，推理与技能执行不重叠、手臂空转，无法直接测计划 §6.3 的"推理与当前技能重叠"与"计划有效性检查"——需把 `inference_window` 改成非阻塞（后台推理线程 + 前台继续执行旧块，再按剩余 `dt` 补推），并明确计划 §7.1 要求的各时间戳（观测采样、请求、返回、生效）；(b) 成功在每个仿真步即时锁定、失败只有 `eval_fail`/出界/步数上限，需增加"响应窗口内完成""约束违反类型"等判定；(c) 部分任务 `get_obs()` 暴露特权字段，公平性（计划 §4.2）要求对决策模型屏蔽；(d) 指令与规则的运行中更新（E1）需新增可观测通道。
- 可直接复用的协议思想：同一种子在 sync/async 下配对比较、报告"翻转"而非只报平均——这正是计划 §7.1"延迟干预"与 §7.2"成功率–时间压力曲线"所需的分析方式。

**3. 安装可行性对扩展阶段的影响**
- 需要 Linux + NVIDIA GPU（CUDA 编译 CuRobo、Vulkan 渲染）+ conda/Python 3.10 + SAPIEN 3.0.3 + ~1.2 GiB 资产；三种策略各需独立环境或服务器，FastWAM 约 29 GiB 显存。**无法在 macOS 开发机上运行**。与计划 §5.1 "不同时维护所有仿真栈" 一致：P1 应安排在 P0（RoboCerebra/LIBERO）跑通之后、在 Linux GPU 服务器上进行；安装脚本有两处引用缺失文件，预期需要手工修补。

**4. 引用时的措辞注意**
- 这是 **NeurIPS 2026 Workshop (Robot Learning with World Models)** 论文，README 与 PDF 脚注均写 "Accepted"，引用写 workshop paper，不写主会；arXiv 编号未知。
- "5–12% flips" 来自 README/项目页而非 PDF，引用时注明；论文自身表述为 "at most 0.03" 与 "a third to a half ... protocol-contingent"。
- 作者自己限定：只评测了一个 WAM，WAM 级结论仅针对 FastWAM（p.4）；每策略单一 checkpoint；完整分任务结果尚未发布（p.9）。
- 论文称其动态为物理驱动，但按代码应说明驱动元素为运动学脚本；描述 RoboTwin 2.0 来源时引用 README 而非论文。

## 可复用资产

- **环境代码**：30+ 个 SAPIEN 双臂动态任务（`envs/*.py`）、`Base_Task` 基类、运动学任务调度（`_update_kinematic_tasks`）、专家控制器（`play_once`）。
- **异步评测机制**：`configure_async_inference` / `inference_window` / `advance_idle_steps` / `async_inference_stats`（`envs/_base_task.py`）；`script/eval_policy.py` + `evaluation_protocol.py` + `eval_metrics.py`。
- **配置与协议**：`task_config/scenario_overrides.py`（条件矩阵）、`eval_seeds.yml`（10 种子/槽位，人机共用）、`task_instructions.json`、`demo_dynamic.yml`。
- **数据与模型**：3,500 条演示（HDF5 + LeRobot v2.1 导出；HF 组织 `RoboDyna`）、`RoboDyna/X-VLA-RoboDyna` 权重、`RoboDyna/RoboDyna-assets` 资产包；π0.5/FastWAM 权重获取方式未在仓库中明确写出。
- **人类实验工具**：`interactive/experiment_gui.py`、`experiment.yml`、`robodyna_gui.py`、浏览器版 Arcade（`docs/arcade.html`，简化 2D 物理，非 SAPIEN）。
- **策略适配器模板**：`policy/pi05_ws`（websocket）、`policy/xvla`（TCP client + codec）、`policy/fwam`。

## 局限与注意点

1. **异步 ≠ 实时并发**：延迟是测后补推的串行计费，推理期间手臂空转、不执行上一块；无推理-执行重叠，不测计划失效检查；也不存在"仿真跟不上实时"的问题（与计划 §7.1 的 wall-clock 1:1 赛道不同）。
2. **分数依赖硬件**："Scores therefore depend on GPU and model speed, so both policies must be run on the same hardware"（`policy/xvla/README.md`）；论文未写明评测 GPU 型号（FastWAM README 提到 H200 上约 2.5 s/块，但论文平均计费 236 ms，二者口径可能不同——未在论文中找到说明）。
3. **论文与代码差异**：单次计费上限（1 s vs 默认 2000 步 = 8 s）、首次调用丢弃未见实现、π0.5 checkpoint 步数（30k vs yml 默认 25000）、"15 步/动作"在评测中实际由 TOPP 决定。
4. **单一 checkpoint、单一 WAM、10 种子/槽位**：统计功效有限，作者未报告置信区间；完整分任务结果待发布（p.9）。
5. **人类基线口径不同**：人类按真实时间、只计成功率，不区分协议（项目页）；teleoperation 用键盘而非真实遥操作设备。
6. **特权观测**：某些任务 `get_obs()` 附带真值状态字段；专家演示基于特权信息。
7. **可运行性**：仅 Linux + NVIDIA；多环境依赖（openpi、X-VLA、Fast-WAM 需各自 checkout）；安装脚本引用了缺失脚本；`requirements.txt` 含与评测无关的依赖（azure、openai、wandb）。
8. **任务指令固定**，无运行中目标更新；成功判定为即时锁定，无"按时且无违规"的组合判定。

## 关键引用句（原文英文，附页码）

1. "Dynamic robotic manipulation benchmarks contain only basic, physically implausible object motions and evaluate policies synchronously, so physical anticipation is never necessary and inference cost is free." (p.1, Abstract)
2. "Second, physical anticipation is never necessary–If the world waits, acting on the current observation is always correct. Third, inference cost is free– A policy taking seconds per chunk ... scores like one running at tens of Hz." (p.2)
3. "RoboDyna makes physical prediction necessary, charges its cost, and lets any advantage register as task success." (p.2)
4. "Concurrent work relaxes parts of this convention with asynchronous evaluation ..., but none scores the same episode under both a synchronized and an asynchronous setting." (p.3)
5. "Under async the wall-clock time of each forward pass is measured and charged to simulated time before the chunk lands; during the charge the arm holds its last commanded joint target while the scene keeps evolving. A single charge is capped at 1 s, and the first call of each process is discarded so that one-off graph compilation is not billed. The mean charge is 109 ms for π0.5, 156 ms for X-VLA and 236 ms for FastWAM." (p.4)
6. "The averages move little, but the successes underneath are not the same successes: pairing protocols seed by seed, a third to a half of every policy's successes are protocol-contingent (π0.5 loses 0.38 of its sync successes and gains 49 new ones)." (p.5)
7. "A state-transition task evolves in one direction and runs a deadline the robot did not start and cannot pause—the apple ripens and does not turn green again—so the seconds charged during inference are subtracted directly from the window to act in." (p.5)
8. "This further supports that a combination of dynamics is not difficult, but an unseen dynamic can be catastrophic." (p.6)
9. "Under teleoperation humans solve 50.2% where the best policy solves 14% at the same condition; under interactive control, which removes the cost of acting through the arms, they solve 77.1%." (p.6)
10. "We showed that charging latency moves average success by at most 0.03 yet re-deals a third to a half of every policy's successes, with systematic losses exactly where the world owns the clock." (p.7)
11. "for prediction to do so, it must attend to the objects that move, arrive within the task's action window, and outrun its own inference cost. RoboDyna measures all three." (p.7)
