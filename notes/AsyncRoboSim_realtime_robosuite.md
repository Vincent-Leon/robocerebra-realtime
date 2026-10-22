# Simulation for Evaluating Robot Policies Should Be *Asynchronous* and *Real-Time*（AsyncRoboSim）

> 研究笔记 · 2026-10-16 · 面向"实时机器人快慢思考基准与同模型共享上下文研究"计划（`realtime_robot_reasoning_benchmark_plan-2.md`）
> 页码约定：正文 PDF 印刷页码 p.1–11；附录 PDF 印刷页码 p.12–18（附录 PDF 第 1 页 = p.12）。行号 L 指论文左侧行号。

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 标题 | Simulation for Evaluating Robot Policies Should Be Asynchronous and Real-Time |
| 项目名 | AsyncRoboSim（代码包名 `realtime-robosuite`） |
| 作者 | 匿名（"Anonymous Author(s)"，p.1） |
| 状态 | 页脚 "Submitted to the 10th Conference on Robot Learning (CoRL 2026). Do not distribute."（p.1）。**投稿审稿中，未录用**，引用时不得写成已发表/已录用论文 |
| 论文内网站 | https://anonymous.4open.science/w/async-robosim （p.1、p.12） |
| 项目页（用户提供） | https://corl26-async-robosim.dgrnd8pzg9mss.amplifyapp.com/ |
| 匿名代码 | https://anonymous.4open.science/r/realtime-robosuite ；本地解压：`repos/AsyncRoboSim_realtime-robosuite/` |
| 代码性质 | robosuite 1.5.1 的 fork（`robosuite/__init__.py` 中 `__version__ = "1.5.1"`），`pyproject.toml` 包名 `realtime-robosuite`，版本 `0.1.0` |
| 篇幅 | 正文 8 页 + 参考文献 3 页（p.9–11）；附录 7 页：A Robomimic full results（p.12–13）、B LIBERO full results（p.14）、C Real-World Evaluation Details（p.14–15）、D Simulation Demos（p.15–17）、E Real-world Demos（p.18） |
| 定位 | "meta-benchmark"/"protocol"：把任何基于同步 Gym API 的 benchmark 改造成异步实时评测；实例化在 robosuite 上，使 Robomimic、LIBERO、RoboCasa 等可自动继承（p.2 L43–46） |
| 实验平台 | Robomimic 五任务（Lift/Can/Square/Transport/ToolHang）+ LIBERO 四 suite（Spatial/Object/Goal/Long）+ 真机 Franka Research 3（Can/Square） |

## 一句话总结

论文主张把"仿真暂停等策略推理"的同步评测改成"仿真进程按 wall-clock 实时推进、策略进程通过共享观测/动作队列异步交互、无新动作时保持上一动作"的协议，并引入可调的 Real-Time Rate（RTR）；在 Robomimic 上异步仿真成功率与真机成功率的相关性显著高于同步仿真（Can 的 Pearson r 从 0.477 升到 0.735，Square 从 0.831 升到 0.894，p.5 Table 1），高延迟策略（diffusion policy、部分 VLA）在异步下掉分最多，且 RTR 越大掉分越大（p.7 Fig. 5）。

## 问题设定与动机

- **同步 API 的问题**：主流机器人仿真 benchmark 继承 OpenAI Gym API，交替执行 `obs = env.step(action)` 与 `action = policy.step(obs)`，推理期间仿真被暂停（p.2 L22–26）。作者称所有他们知道的公开 benchmark 都遵守这一同步 API（p.2 L26–27）。
- **"sync-to-async gap"**：真实世界物理不等待推理。同步评测给带大 VLM backbone 或多步去噪的慢策略以不公平优势——它们可以花任意长时间产生下一动作（p.2 L27–33）。作者把这一人为引入的差距命名为 "sync-to-async" gap，与传统 sim-to-real gap（渲染真实感、传感器、物理精度）正交（p.2 L57–61）。
- **四点主张**（p.2–3）：
  1. *Parallel simulator and policy inference*：策略与仿真运行在独立进程，经 IPC 共享 control queue 与 observation queue 通信；仿真以固定控制率（文中举例 500 Hz）拉动作、以固定相机率（举例 30 Hz）推观测；策略若来不及更新，仿真沿用最近一次动作（p.2 L34–43）。
  2. *Unifies latency and performance metrics*：同步评测需要分别报告"性能"和"延迟"两个指标，而延迟的重要性只体现在它对性能的影响上（动态任务受影响更大）；异步仿真自然把延迟折算进任务指标（p.2 L67–75）。特别适合评测 Real-Time Chunking、VLASH、streaming policy 等降延迟方法（p.3 L72–74）。
  3. *Useful for debugging*：diffusion policy 在 action chunk 边界"抖动"（jitter）的现象在 AsyncRoboSim 中清晰可见且与真机一致，同步仿真下运动"看起来平滑得具有欺骗性"（p.3 L76–81）。
  4. *Realtime rate control and monitoring*：可控的 RTR（仿真速度/wall-clock 速度），默认 1；RTR>1 模拟更弱算力或资源竞争，RTR<1 模拟更强算力；带 realized-RTR 监视器，低于目标则报错（p.3 L82–95）。
- **与真机 benchmark 的关系**：RoboArena、AutoEval、ManipulationNet 等真机评测天然异步，但昂贵、难扩展、难复现；异步仿真是"idealized synchronous simulation"与"costly real-world evaluation"之间的中间地带（p.2 L49–66；p.8 L279–283）。
- **三个研究问题**（p.4 L147–151）：RQ1 异步仿真是否更能预测真机表现；RQ2 延迟如何影响 sync-to-async gap；RQ3 RTR 如何影响同步评测高估的严重程度。

## 核心设计

### 1. 进程结构与队列

- **两个并行进程**（摘要用词是 "parallel threads"，p.1；方法节与代码实际为 Python `multiprocessing` 的 spawn **进程**，p.3 L97–105；代码 `AsyncSimulation.__init__` 用 `mp.get_context("spawn")`）。策略进程与仿真进程互不等待，各自循环直到收到 shutdown 信号（p.3 L104–105）。
- **两条共享队列**（p.2 L36–38；Fig. 1(b) p.1）：
  - *Observation queue*：仿真进程以相机频率 push 观测；策略进程 pull。
  - *Action/Control queue*：策略进程以任意频率 push 动作；仿真进程在每次控制事件 pull。
  - 代码中另有 `request_queue`/`reply_queue`（maxsize 1）用于 `reset`/`shutdown`/`get_action_dim` 等阻塞式控制命令（`SimulationWorker.handle_request`）。
- **队列语义（代码）**：自定义 `Queue(MPQueue)` 提供 `publish()`（队满时丢最旧元素再放入，drop-oldest）和 `drain()`（取空队列并只返回最新一项）。`control_queue` maxsize=8，`observation_queue` maxsize=`history`（默认 1）。仿真进程每个循环迭代 `drain()` 控制队列——**一个控制周期内 push 的多个动作只有最后一个生效，中间动作被丢弃**。因此 action chunk 必须由策略侧按时间节奏逐个 push（论文的 policy-side 默认循环未包含在代码快照中，见下）。
- Fig. 1(b) 伪代码（p.1）：仿真进程 `act = act_queue.pull(); obs = env.step(act); time.sleep(sync_sec); obs_queue.push(obs)`；策略进程 `obs = obs_queue.pull(); act = policy.step(obs); act_queue.push(act)`。

### 2. 仿真进程循环（p.4 L111–124；代码 `SimulationWorker.main_loop`，`async_env.py` L343–410）

每次迭代：
1. 非阻塞检查 request 队列（reset/shutdown 等）；
2. `drain()` 控制队列，若有新动作则 `latest_action` 更新并置 `is_action_new=True`；**若没有新动作，则沿用上一次执行的动作**（"mirroring how a real robot continues actuating under its last command"，p.4 L116–118）；episode 开始时 `latest_action` 初始化为全零 `default_action`（代码 L154–155、L185）；
3. `take_sim_step()`：**一次** MuJoCo 物理步（`model_timestep = macros.SIMULATION_TIMESTEP = 0.002 s`，与论文 "defaults to 2ms" 一致，p.4 L119），调用 `env._pre_action(action, policy_step=is_action_new)` 后 `sim.step2()`（lite_physics）或 `sim.step()`，再 `env._update_observables()`；`policy_step` 只在动作刚更新的那一步为 True，与同步 `MujocoEnv.step()` 中"每个控制步的第一个子步 policy_step=True"语义一致（`base.py` L448–465），从而控制器（OSC 插值器等）行为与同步模式对齐；
4. 若观测事件或同步事件到期（以仿真 tick 计数）→ `sync_time()` 与 wall-clock 对齐（见 §3）；
5. 观测事件到期 → `get_observations()` 并 `publish()`（含渲染，在仿真进程内完成）；
6. 奖励事件到期 → `compute_reward()`（调用 `env._post_action`）——**注意：代码中 reward 计算后既不发布也不记录**（L388–390），`done`/成功判定亦未传回策略进程；
7. wall-clock 事件：按 `real_time_rate_freq`（默认 5 Hz）更新 RTR 计量器、按 `visualization_freq`（默认 30 Hz）刷新 viewer 并在画面叠加 "Async. simulation time" 与 "Real-time rate"；
8. 若 `sim_time >= env.horizon` 置 `done_event`。**async 模式下 `horizon` 的单位是仿真秒**（L351、L407；demo 中 `horizon=100.0  # seconds of simulation time`），而原 robosuite 同步模式 `horizon` 是控制步数；`make_async` 强制 `ignore_done=True`。
- 论文表述："All actions and observations are timestamped in simulation time"（p.4 L123–124）。代码中 `Observation(data, time, action)`：`time` = `env.sim.data.time`（仿真时间），`action` = 该时刻正在执行的动作副本；动作本身入队时不附带时间戳。

### 3. 仿真时钟与 wall-clock 的对齐、RTR 定义（p.4 L125–141；代码 `sync_time` L315–323）

- 定义：设自上次同步事件以来仿真时间流逝 Δsim、真实时间流逝 Δreal。给定 r>0，若 Δsim = r·Δreal 则称仿真以 real-time rate r 与 wall-clock 完美同步（例 r=2：1 秒 wall-clock 对应 2 秒仿真时间）。MuJoCo 通常远快于实时（Δsim ≫ r·Δreal），因此每次同步事件 `time.sleep(Δsleep)`，**Δsleep = max(0, Δsim/r − Δreal)**（p.4 L129–135）。
- 同步事件触发点：每个控制事件（论文默认 500 Hz）或观测事件（相机频率）（p.4 L126–128）。
- 漂移保证："simulated time never drifts from wall-clock (real) time by more than 1/control_frequency (default: 2ms)"（p.4 L135–137）。
- **代码实现是"绝对锚点"而非"增量"**：`reset()` 时记录 `anchor_sim_time`/`anchor_real_time`（`time.perf_counter()`），每次 `sync_time()` 计算 `target_real_elapsed = (sim_time − anchor_sim)/target_rtr`，若领先则 sleep 到目标时刻。因此不会累积漂移（与论文 "pacing remains accurate over long horizons without accumulating drift" 一致，p.4 L137–138）。
- **运行节奏**：两次同步之间仿真以 CPU 全速"突发"推进若干 2 ms 物理步，然后 sleep。同步周期 = 控制周期（按 tick 取整）。代码 docstring（L570–576）明确："the control period (= 1.0 / control_freq) is the maximum time interval between sending a new control command and when that control command will be executed in the simulation"，即**动作被执行的最坏延迟 = 1/control_freq**。
- **频率吸附**：所有以仿真 tick 计的频率被 `snap_frequency_to_sim_timestep()` 取整到 2 ms 的整数倍并打印 warning。例如 30 Hz → 17 tick → 实际 29.41 Hz；50/500/20/10 Hz 均可整除。
- **RTR 的含义**（p.3 L82–95；p.4 L138–141）：r>1 模拟边缘设备/高负载工作站的稀缺算力（等价于让策略"更慢"），r<1 模拟硬件进步；**同步仿真是 RTR→0 的极限**（p.8 L249–251）。默认 r=1。
- **RTR 监视**（p.3 L88–91；p.4 L142–145）：论文称监视器测量 realized RTR，低于目标则 "raise an error"，保证报告的实时率真实。代码 `RealTimeRateMeter.update()` 以 wall-clock 窗口计算 `rate = sim_elapsed/real_elapsed`（默认 5 Hz 更新），但**只在开启可视化（`viz_peg` 非空）时才更新，且仅叠加显示在 viewer 上，没有任何报错/告警/落盘逻辑**（L396–398、L336–341）。论文所述的报错在此代码快照中未实现。
- 仿真跟不上实时时：`sync_time()` 只在领先时 sleep，落后时不做任何补偿，仿真继续全速推进，realized RTR 低于目标；论文称所有测试过的硬件在异步 MuJoCo 下都能支持 RTR≥3（p.3 L92–94；p.8 L269–271）。

### 4. 默认频率一览（论文 vs 代码）

| 量 | 论文 | 代码（`make_async`/`AsyncSimulation` 默认） |
| --- | --- | --- |
| 物理步长 | 2 ms（p.4 L119） | `macros.SIMULATION_TIMESTEP = 0.002` |
| 控制率（动作拉取/同步率） | **500 Hz**（p.4 L113–114；1/500 = 2 ms 漂移上界） | **`control_freq=50.0`**（20 ms）——与论文默认不一致；可显式传 500 |
| 相机/观测率 | 30 Hz（p.4 L113） | `observation_freq=30.0`（吸附为 29.41 Hz） |
| 奖励计算率 | 未在论文中找到 | `reward_freq=10.0`（结果未发布） |
| RTR 计量更新 | 未在论文中找到 | `real_time_rate_freq=5.0` |
| 可视化 | "periodically updates the interactive viewer"（p.4 L122） | `viz_freq=30.0`（可设 None） |
| 目标 RTR | 1 | `target_real_time_rate=1.0` |
| 观测历史 | 未提及 | `history=1`（`ObservationStream` 用 deque 保存最近 N 条） |

### 5. 与同步评测的差异（归纳）

| 维度 | 同步（Gym API） | AsyncRoboSim |
| --- | --- | --- |
| 推理期间世界 | 冻结 | 按 wall-clock/RTR 持续推进 |
| 动作生效 | 立即、每步一个 | 下一个控制事件（≤1/control_freq），期间保持上一动作 |
| 观测 | 每步一帧，与动作一一对应 | 固定频率发布，策略取最新（可能跳帧、可能重复读到同一帧） |
| 延迟 | 单独统计的辅助指标 | 直接体现在成功率中 |
| 评测速度 | 可远快于实时 | 被 `time.sleep` 约束为 ~RTR 倍实时（p.8 L262–266） |
| horizon | 步数 | 仿真秒 |
| 成功/奖励 | `step()` 返回 | 代码快照中由仿真进程算 reward 但不回传；成功判定需评测端自行实现 |

### 6. 延迟如何测量与记录

- 论文：每个策略报告一个 "Inference Latency"（ms，Table 2–6）。**测量定义（计时起止点、是否含图像预处理、是否取均值）未在论文中找到。** 从数值看，Table 3/5/6 的 DP 延迟为每次推理约 535–660 ms，而 Table 2 的 DP 延迟为 73.36 / 150.05 / 302.40 / 37.73 / 597.80 ms（chunk 8/4/2/16/1），接近"每次推理延迟 ÷ chunk 大小"，即 Table 2 很可能是**每动作均摊延迟**，论文未明说。LIBERO 的 VLA 延迟（9.31–66.73 ms，Table 4）同样低得像均摊值，论文未说明。
- 代码：无任何延迟日志或落盘。可得的时间戳只有 `Observation.time`（仿真秒）、`ControlStream.latest_timestamp()`（策略侧 push 时的 `perf_counter`）、以及仿真进程内部的 anchor；"动作实际生效时间"没有被记录。

## 代码实现要点

### 文件与类（相对 `repos/AsyncRoboSim_realtime-robosuite/`）

| 路径 | 作用 |
| --- | --- |
| `robosuite/environments/async_env.py`（779 行） | **全部异步实现**。论文脚注指向 `#L343`（main loop）与 `#L315-L323`（sync_time），与本地文件行号完全吻合 |
| `robosuite/__init__.py` | 导出 `make_async`、`AsyncSimulation`、`ObservationStream`、`ControlStream` |
| `robosuite/demos/demo_async_env.py`（57 行） | 示例：`suite.make_async("Lift", robots="Panda", horizon=100.0, control_freq=50.0, observation_freq=30.0, target_real_time_rate=...)`，循环 `env.control_stream.push(random_action)` 直到 `env.done()`；`tyro` CLI；`pyproject.toml` 注册 `demo` 脚本入口 |
| `tests/test_environments/test_async_env.py`（81 行） | 3 个 pytest：最新动作被采用且 `obs.time` 单调增、未 start 时查 `action_dim` 抛错、horizon 到达后停止 |
| `robosuite/environments/base.py` | 被复用的同步基类：`initialize_time()`、`_pre_action()`、`_update_observables()`、`_get_observations()`、`_post_action()`、`model_timestep`、`lite_physics`、`horizon`、`viewer`/`renderer` |
| `robosuite/macros.py` | `SIMULATION_TIMESTEP = 0.002` |
| `README.md` | 顶部新增 "Known Issues / TODOs"：RTR 很低（如 0.01）时可视化更新频率不正确（突发-长睡眠模式所致），其余为 robosuite 原 README |
| `pyproject.toml` / `requirements.txt` / `uv.lock` | 包名 `realtime-robosuite 0.1.0`；`requires-python >= 3.10`；`mujoco>=3.3.2`、`numpy==2.2.6`、`tyro>=1.0.3`、`mink`、`robosuite-models`、`gymnasium`、`h5py` 等；构建后端 `uv_build`；dev 组含 pytest/pyright/ruff/ty |

`async_env.py` 中的关键符号：

- `Observation(data: OrderedDict, time: float, action: np.ndarray)` —— 观测数据、仿真时间、当时执行的动作。
- `Request`/`Response` —— 控制命令。
- `PeriodicEventGenerator(period, start_time)`：`is_ready(ts)`、`register_event(ts)`；用于 `obs_peg`/`sync_peg`/`reward_peg`（以仿真 tick 计）和 `rtr_peg`/`viz_peg`（以 wall-clock 计）。
- `RealTimeRateMeter(real_time, sim_time)`：`update()` → `rate`。
- `Queue(MPQueue)`：`publish()`（drop-oldest）、`drain()`（取最新）。
- `SimulationWorkerConf`（dataclass：`env_factory, control_freq, observation_freq, visualization_freq, real_time_rate_freq, target_real_time_rate, reward_freq, start/stop/done_event, 四条队列`）。
- `SimulationWorker`：`reset()`、`handle_request()`、`compute_reward()`、`get_observations()`、`take_sim_step()`、`sync_time()`、`update_viewer()`、`update_viewer_overlays()`、`main_loop()`、`runner()`、`_run_with_main_thread_viewer()`（macOS 下 GLFW 必须在主线程，仿真改在后台线程跑）。
- `ObservationStream(queue, history)`：`latest()`（非阻塞，空则 None）、`get(timeout)`（阻塞）、`snapshot()`。
- `ControlStream(queue)`：`push(action)`、`latest()`、`latest_timestamp()`。
- `AsyncSimulation(env_factory, control_freq=50, observation_freq=30, visualization_freq=30, real_time_rate_freq=5, target_real_time_rate=1, reward_freq=10, history=1, ctx=None)`：`start()`（等待子进程 `start_event`，10 s 超时）、`stop()`、`reset()`、`action_dim`、`done()`、`is_running()`、`latest_observation()`，支持 `with` 上下文。
- `make_async(env_name, *args, control_freq, observation_freq, viz_freq, real_time_rate_freq, target_real_time_rate, history, **kwargs)` → `AsyncSimulation(env_factory=partial(suite.make, env_name, ..., control_freq=control_freq, ignore_done=True))`。

### 与 robosuite 的接入点

- 不改动任何任务/机器人/控制器代码；只依赖 `MujocoEnv` 的公开/半公开接口：`sim`、`initialize_time`、`reset`、`_pre_action`、`_update_observables`、`_get_observations`、`_post_action`、`model_timestep`、`lite_physics`、`horizon`、`action_spec`/`action_dim`、`viewer`/`renderer`/`viewer_get_obs`/`initialize_renderer`/`close`。任何提供这些接口的 robosuite 子类环境（包括 LIBERO 的任务类，理论上）都可通过 `env_factory` 接入。
- 环境在**子进程内**由 `env_factory()` 构造（避免跨进程传递 MuJoCo 句柄）；因此 `env_factory` 必须可 pickle（`functools.partial(suite.make, ...)`）。

### 是否支持 LIBERO / 是否有评测与策略代码

- **仓库中没有 LIBERO、Robomimic 策略、VLA 推理、评测脚本或成功率统计代码**（全仓 grep `libero` 无结果；`robomimic` 仅出现在原 robosuite 文档）。论文 p.3 L106–110 描述的"将任何同步策略转换为异步的默认 policy-process 循环"**未包含在此代码快照中**；demo 仅为随机动作。
- 论文在 LIBERO 上做了实验（p.4 L151："both of which inherit robosuite"），说明作者有 LIBERO 接入代码，但未公开在此快照中。

### 时间戳与日志

- 有：`Observation.time`（仿真秒）、`Observation.action`、`ControlStream.latest_timestamp()`（wall-clock）、viewer 叠加的 realized RTR。
- 无：动作生效时刻记录、延迟统计、RTR 落盘、episode 日志、成功判定回传。

### 依赖与安装

- Python ≥ 3.10；MuJoCo ≥ 3.3.2（`uv.lock` 锁 3.3.2）；numpy 2.2.6；robosuite 1.5.1 代码内置（fork）；`uv` 构建；CI（`.github/workflows/run-tests.yaml`）在 Ubuntu + OSMesa 无头环境跑 pytest（`MUJOCO_GL=osmesa`）。
- macOS 开 viewer 需 `mjpython`/主线程 workaround（代码已处理）。

### 论文描述与代码快照的差异（需在复用时注意）

1. 默认控制率：论文 500 Hz，代码 50 Hz。
2. RTR 监视报错：论文有，代码只在可视化开启时计算并显示。
3. 奖励/成功：仿真进程计算 reward 但不发布。
4. Policy-side 默认异步循环与评测 harness：论文提及，代码无。
5. 摘要说 "parallel threads"，实现是 processes。
6. `demo_async_env.py` 文档字符串含一条非匿名 GitHub 地址（`uvx --from git+https://github.com/siddancha/realtime-robosuite ...`）；鉴于论文处于匿名评审期，**引用与署名仍按匿名投稿处理，不据此推断作者**。

## 实验与主要结果

### 设置（p.4 L152–p.5 L174）

- Robomimic：RTX 4060 工作站；每任务每策略 400 trials，同步与异步各一遍；95% Wilson score CI。五任务 Lift、Can、Square、Transport、ToolHang。
- LIBERO：RTX 4090；每 suite 100 trials，"following the standard LIBERO evaluation protocol"。四 suite Spatial、Object、Goal、Long。
- 真机：Franka Research 3，复现 Robomimic 的 Can 与 Square（3D 打印同样物体），多视角 RGB（静态前视 + 腕部），84×84×3，每策略 20 trials。训练：Can 63 条演示/200 epoch，Square 120 条/400 epoch。
- 策略族（robosuite/robomimic 基准策略）：MLP-BC 变体（BC、BC-Gaussian、BC-GMM、BC-VAE）、Transformer-BC 变体（BC-TF、BC-TF-GMM）、Diffusion Policy（预测 16 步，执行 chunk Ta ∈ {1,2,4,8,16}，只执行前 Ta 步）。延迟范围 ~7 ms（BC on Square）到 ~660 ms（DP on Transport）。
- 相关性指标（p.6）：Pearson r、Spearman ρ、Pairwise Ranking Accuracy（PRA = 所有策略对中仿真排序与真机排序一致的比例）。

### RQ1：与真机的相关性（p.5 Fig. 3、Table 1；附录 p.14–15 Fig. 6、Table 5–6）

| 任务 | 条件 | Pearson r | Spearman ρ | PRA |
| --- | --- | --- | --- | --- |
| Can | 同步 | 0.477 | 0.485 | 0.724 |
| Can | 异步 | **0.735** | **0.664** | **0.812** |
| Can | 提升 | +0.258 | +0.179 | +0.088 |
| Square | 同步 | 0.831 | 0.782 | 0.824 |
| Square | 异步 | **0.894** | **0.975** | **0.971** |
| Square | 提升 | +0.063 | +0.193 | +0.147 |

- 代表性例子（p.6 L206–211）：Square 上同步评测 DP(chunk=8) 86% > BC-TF-GMM 83%，但异步与真机下排序反转（异步 52% vs 62%，真机 30% vs 40%，Table 6 p.15）；DP 延迟 587 ms vs 12 ms。
- Table 5（Can，Sync/Async/Real，p.15）：BC-TF 98/88/75；BC-TF-GMM 98/90/80；BC-Gaussian 38/54/35；BC 31/28/5；BC-GMM 94/93/30；BC-VAE 87/72/–；DP16 98/42/25；DP8 96/61/30；DP4 97/69/35；DP2 97/10/–；DP1 95/32/30。
- Table 6（Square，p.15）：BC-TF 90/72/75；BC-TF-GMM 83/62/40；BC-Gaussian 23/19/0；BC 19/14/0；BC-GMM 54/46/15；BC-VAE 28/24/–；DP16 84/54/35；DP8 86/52/30；DP4 78/68/40；DP2 83/30/–；DP1 81/33/25。
- 注意：真机仅 20 trials、每任务 9 个有真机数据的策略，CI 很宽（Fig. 6 p.14）；且 Can 上 BC-GMM 94/93/30 这类"仿真（同步和异步）都高、真机低"的情形异步仿真也没能解释——异步只修正延迟相关的那部分 gap。
- p.6 L200 把 0.477→0.735 写成 "squared Pearson linear correlation" 的提升，但表中数值是 r 而非 r²（措辞小瑕疵）。

### RQ2：Robomimic 延迟—掉分（p.6 L213–p.7 L230；Fig. 4 左 p.7；Table 2 p.12、Table 3 p.12–13）

Table 2（五任务平均成功率 Sync/Async，绝对掉分，相对掉分，延迟）：

| 策略 | Avg Sync/Async | 掉分 | 相对掉分 % | 延迟 |
| --- | --- | --- | --- | --- |
| BC | 27.2 / 24.4 | −2.8 | 10.29 | 11.5 ms |
| BC-VAE | 39.4 / 34.6 | −4.8 | 12.18 | 11.7 ms |
| BC-Gaussian | 24.2 / 24.6 | +0.4 | −1.65 | 12.4 ms |
| BC-GMM | 60.0 / 48.6 | −11.4 | 19.00 | 13.0 ms |
| BC-TF | 64.2 / 52.4 | −11.8 | 18.38 | 21.9 ms |
| BC-TF-GMM | 71.8 / 51.0 | −20.8 | 28.97 | 22.1 ms |
| DP (chunk=16) | 82.2 / 46.6 | −35.6 | 43.31 | 37.73 ms（均摊，见上） |
| DP (chunk=8) | 78.6 / 49.6 | −29.0 | 36.90 | 73.36 ms |
| DP (chunk=4) | 78.4 / 52.6 | −25.8 | 32.91 | 150.05 ms |
| DP (chunk=2) | 79.0 / 22.8 | −56.2 | 71.14 | 302.40 ms |
| DP (chunk=1) | 76.6 / 22.0 | −54.6 | 71.28 | 597.80 ms |

- 低延迟 MLP/GMM 策略（11–22 ms，与仿真控制环时间尺度相当）对异步化不敏感，Can 上同步/异步接近（p.7 L218–223）。DP 变体差距大得多：Can 上 DP(chunk=16) 从 98% 掉到 42%（p.7 L229–230）；Can 上 DP(chunk=2) 97→10（Table 3）。
- 逐任务（Table 3 p.12–13）要点：Lift 几乎所有策略 100/100，仅 DP(chunk=2) 100→72、DP(chunk=1) 100→45；**Transport 异步下几乎全部归零**（BC-TF 33→2、BC-TF-GMM 78→3、BC-GMM 52→4、DP 76–83→0–6），即使延迟只有 ~14–18 ms——论文未解释，提示掉分不只由延迟决定（双臂协调、hold-last 语义等可能有关）；ToolHang 只有 DP 非零（DP16 46→32、DP8 30→29、DP4 35→26、DP2 33→2、DP1 31→0）。
- Fig. 4 左（掉分 vs 推理延迟，按任务 log-linear 拟合，图例给出相关系数）：Lift r=0.729、Can r=0.841、Square r=0.831、Transport r=0.741、Tool Hang r=0.879。

### RQ2：LIBERO VLA（p.7 L231–p.8 L245；Fig. 4 右 p.7；Table 4 p.14）

| 模型 | 参数 | Spatial | Object | Goal | Long | Avg Sync/Async | 掉分 | 相对掉分 % | IAR↑ | 延迟 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SmolVLA | 450M | 90/56 | 96/52 | 92/67 | 71/50 | 87.2/56.2 | −31.0 | 35.6 | 64.5 | 9.31 ms |
| X-VLA | 0.9B | 93/83 | 98/95 | 99/94 | 98/92 | 97.0/91.0 | −6.0 | 6.2 | 93.8 | 14.32 ms |
| MolmoAct2 | 5B | 98/96 | 100/98 | 98/96 | 97/93 | 98.2/95.8 | −2.5 | 2.4 | 97.6 | 16.14 ms |
| π0 | 4B | 90/52 | 86/68 | 95/72 | 73/44 | 86.0/59.0 | −27.0 | 31.4 | 68.6 | 44.46 ms |
| π0.5 | 4B | 97/68 | 99/65 | 98/74 | 96/77 | 97.5/71.0 | −26.5 | 27.2 | 72.8 | 66.73 ms |

- "IAR" 列缩写未在论文中展开；数值等于 Async/Sync×100（保留率），正文用 "retains 93.8% / 97.6% / 68.6%" 表述（p.8 L240–242）。
- LIBERO 上延迟与掉分的相关性为正但弱于 Robomimic：Spatial r=0.383、Object r=0.103、Goal r=0.406、Long r=0.464（Fig. 4 右）。作者归因于策略级属性：时间稳定性、动作纠正、从过时指令恢复的能力（p.8 L238–240）。SmolVLA 延迟最低（9.31 ms）却掉分最多（−31.0），说明**低延迟不等于异步鲁棒**。
- 定性发现：MolmoAct2 在异步仿真中表现出自我纠正（self-correction）行为，同步仿真下看不到（p.8 L242–245）。
- 注意：Table 4 的延迟数值对 4–5B 模型而言明显偏低，推测为每动作均摊或特定硬件/实现下的值，论文未说明测量方式。

### RQ3：RTR 扫描（p.8 L246–260；Fig. 5 p.7）

- 仅在 Robomimic **Square** 上做；RTR ∈ {0 (Sync), 0.33, 0.67, 1, 2, 3}；策略分三组：Diffusion Policy、BC-Transformer variants、BC variants。
- 结论：RTR 越大（仿真相对策略越快）掉分越大，且与延迟强耦合——低延迟 BC（~10 ms）在 RTR 增大时基本稳定，高延迟 DP 急剧退化（p.8 L251–255）。右图：按延迟分档（10 ms+、20 ms+、600 ms+）的掉分在 RTR 越高时越大。
- 读图近似值（**非表格数据，仅供参考**）：DP 组成功率约 86%(Sync) → ~80%(0.33–0.67) → ~53%(RTR 1) → ~42%(2) → ~38%(3)；BC-Transformer 组约 88% → ~80% → ~70% → ~60% → ~55%；BC 组约 41% → ~35% → ~35% → ~33% → ~31%。右图 600 ms+ 档掉分约 8%(RTR 0.33–0.67)、~30%(RTR 1)、~41%(RTR 2)、~45%(RTR 3)。
- 作者的总结性原则（p.8 L255–258）："latency is not merely an auxiliary runtime statistic but directly affects task success when the asynchronous nature of the world is properly accounted for."

### 局限（论文自述，p.8 §4）

- 评测速度：异步评测被 `time.sleep` 约束，不能比实时快（RTR=1 时 400 trials 需真实时间）；可无人值守长时间运行。
- 硬件约束：老旧/边缘设备可能达不到实时；靠 RTR 监视器检测；他们测过的设备都支持 ≥3× 实时。

## 与本项目的关系

### 协议层面的对应（计划 §5.3、§7.1）

- 计划 §5.3 的 **Real-time 版本**（"仿真独立推进，推理与当前技能可重叠，计入真实延迟"）与计划 §7.1 的**真实时间闭环**（"环境按 wall-clock 持续推进，推理与技能执行异步"）在仿真侧正是 AsyncRoboSim 的协议：独立仿真进程 + 实时时钟 + 共享观测/动作队列 + hold-last。
- 计划 §7.1 **暂停环境参考** = AsyncRoboSim 的同步评测 = RTR→0 极限（p.8 L249–251）。这给了我们一个统一视角：暂停参考与实时闭环只是 RTR 的两个取值，可以在同一代码路径上实现（RTR 很小时注意 README 所述的可视化问题，且仿真仍会 sleep，只是极慢）。
- 计划 §7.1 "主实时赛道固定仿真时间与真实时间比例为 1:1，记录仿真是否跟得上；其他比例仅作为明确标记的压力实验" ↔ AsyncRoboSim 的 `target_real_time_rate=1` + realized-RTR 监视 + RTR 扫描。**术语可直接对齐：我们的"仿真/真实时间比例" = 他们的 RTR**。但其代码未实现"跟不上则报错/标记"，我们需要自行加 realized-RTR 落盘与阈值判定（计划要求"该运行需标记或重跑"）。
- 计划 §7.1 **延迟干预**（在请求或动作生效环节注入已知延迟）：AsyncRoboSim 没有延迟注入，但 RTR=r 等价于把所有策略延迟按比例放大 r 倍（乘性）；我们的注入是加性常量，两者互补，可在策略进程 push 前 sleep 实现，不需改仿真侧。
- 计划 §7.1 "明确动作队列是否覆盖、技能何时结束、超时后怎样处理"：AsyncRoboSim 的回答是**覆盖（drain 取最新、drop-oldest）+ 无新动作则保持上一动作 + horizon 以仿真秒计**。这对低层连续动作合理，但对我们的高层决策（子目标/技能选择）不够：保持"上一动作"在我们这里应解释为"底层技能继续执行当前子目标"，而非重复一个 7 维向量。

### 层级差异：他们测低层策略延迟，我们测高层语义推理延迟

- AsyncRoboSim 评的是 BC/DP/VLA 这类**低层视觉运动策略**，延迟 7–660 ms，与 20–50 ms 控制周期同量级；掉分机制是"旧动作继续执行导致闭环反应变慢/chunk 边界抖动"。
- 我们评的是**高层决策模型**（VLM/LLM 语义推理、计划刷新），延迟秒级到数十秒；核心问题是"推理结果返回时是否仍适用"。这不是 AsyncRoboSim 两层结构能直接表达的，需要**三层结构**：仿真进程（可直接用 AsyncRoboSim）↔ 低层执行器进程（OpenVLA 等以固定频率消费 `ObservationStream`、生产 `ControlStream`）↔ 高层推理（异步、按计划 §6.3 的 `plan_id`/`observation_version` 版本化）。AsyncRoboSim 只解决第一个边界；第二个边界（计划版本检查、接受/修订/丢弃、子目标切换）是我们的新增内容。
- 衔接点：AsyncRoboSim 的实验给出了"低层执行器自身在异步下会掉多少分"的参考（如 LIBERO 上 ~10–16 ms 的 VLA 保留率 64.5–97.6%）。我们必须先把 Original→Real-time 的**执行器自身掉分**（无事件、无高层推理变化）作为对照测出来（计划 §5.3 "静态任务未必明显掉分"），否则高层方法的收益会与执行器掉分混淆。
- 可借鉴的论证方式：他们用"同步评测下排序被颠倒"（DP vs BC-TF-GMM）证明协议的必要性；我们可以用"暂停参考下慢推理方法领先、实时闭环下排序反转"的同类证据。

### Phase 1 实时化能否直接复用其实现接入 RoboCerebra/LIBERO

- **可复用的部分**：`async_env.py` 几乎自包含（依赖 robosuite `MujocoEnv` 接口 + mujoco + numpy），可整体 vendoring 进我们的栈，作为仿真进程与实时时钟的实现；`make_async` 的 `env_factory` 机制允许传入任何构造 robosuite 子类环境的可 pickle 工厂。
- **需要解决的问题**：
  1. LIBERO 的任务环境是 robosuite 子类（BDDL 任务 + `OffScreenRenderEnv` 包装），但 LIBERO 官方依赖的 robosuite 版本与此 fork（1.5.1，含 composite controller 重构）**可能不兼容，需核实**；可选路径是把 `async_env.py` 的逻辑移植到 LIBERO 所用的 robosuite 版本上，而不是反过来。
  2. 成功判定：worker 不回传 `done`/成功；需在 `get_observations()` 或独立事件中调用 LIBERO 的成功检查（如 `env.check_success()`/`_check_success()`），并把结果带时间戳发布。
  3. 控制频率：LIBERO 环境默认 `control_freq=20`（同步模式 50 ms/步）、RoboCerebra/OpenVLA 栈以约 20 Hz 出动作——这两点是背景知识，**未在本论文或本代码中读到，需在 Phase 0 复现时核实**；异步化后应把 AsyncRoboSim 的 `control_freq` 设得足够高（论文用 500 Hz）以把动作生效量化误差压到 2 ms，而策略进程自行按执行器频率节奏 push。
  4. 策略侧循环与日志完全需要自建（见下）。
  5. 观测渲染在仿真进程内完成：LIBERO 多相机 128×128/256×256 渲染会占用仿真进程时间，影响 realized RTR，需实测。
  6. RoboCerebra 的 anchor-point 子目标切换协议（计划 §5.4）在异步化后需要重新定义触发时刻（按仿真时间还是按高层决策），AsyncRoboSim 对此没有现成支持。

### 可直接对齐的时间戳与指标

- 对齐：`Observation.time`（仿真秒）↔ 我们的"观测采样时间戳"；`ControlStream.latest_timestamp()` ↔ "动作接受时间"（wall-clock）；"动作实际生效" = 下一次 `drain()` 后的那一步仿真时间，需在 worker 中补记（`is_action_new` 为 True 的那一步的 `sim_time`，并回填到 `Observation`）。还需加：wall-clock 观测时间（`perf_counter`）、仿真时间↔wall-clock 映射（锚点）、请求发送/结果返回（策略侧）。
- 指标对齐：他们的 "performance drop (sync→async)"（绝对百分点）、"Rel. drop %"、"IAR/保留率" ↔ 我们的"暂停参考 vs 实时闭环"差值；他们的 "Inference Latency"（均值）↔ 我们的"观测到动作生效延迟"（计划要求 P50/P95 并拆分编码/排队/推理/解析/执行接口，比他们细）；他们的 RTR 扫描 ↔ 我们的"成功率—时间压力曲线"的一种实现（但我们的时间压力主要来自事件响应窗口，不只是 RTR）。
- 不对齐/需补：事件响应延迟、计划过时率、误拒绝率、恢复时间（计划 §7.2）在 AsyncRoboSim 中无对应物。

### 引用时的措辞

- 写作 "AsyncRoboSim (anonymous CoRL 2026 submission, under review; project page …)"，不写作者、不写"accepted"、不写 "published at CoRL 2026"；计划文档 §2 已有同样提醒。
- 可以说"我们采用与 AsyncRoboSim 相同的异步实时协议（独立仿真进程、实时时钟、hold-last 动作、RTR）"并注明"其论文投稿中、代码为匿名快照、我们复现/移植了其仿真侧实现"。
- 不要把"异步实时仿真"本身宣称为我们的贡献；我们的增量是**在该协议上加入需要语义推理、计划刷新与主动争取时间的任务、三层结构与相应指标**。

## 可复用资产

1. **代码**：`robosuite/environments/async_env.py` 整文件（`SimulationWorker`、`AsyncSimulation`、`ObservationStream`、`ControlStream`、drop-oldest `Queue`、`PeriodicEventGenerator`、`RealTimeRateMeter`）；绝对锚点式 `sync_time()`；频率吸附逻辑；macOS 主线程 viewer workaround；`tests/test_environments/test_async_env.py` 的测试思路（验证最新动作被采用、`obs.time` 单调、horizon 以秒终止）。
2. **协议定义**：Δsleep = max(0, Δsim/r − Δreal)；漂移上界 1/control_freq；同步 = RTR→0；hold-last 语义；horizon 以仿真秒计。
3. **指标与统计**：Pearson/Spearman/PRA 三指标评估仿真→真机预测力；Wilson 95% CI；绝对掉分 + 相对掉分 + 保留率三种表达；掉分 vs 延迟的按任务 log-linear 拟合图（Fig. 4）；RTR 扫描图（Fig. 5）。
4. **参考数据**：Table 2–6 可作为"低层策略在异步下掉分"的外部基线；Table 4 可作为 LIBERO 上 VLA 异步保留率的参照（我们若用 OpenVLA 作底层执行器，可与之对比量级）。
5. **论证模板**："同步评测颠倒策略排序"（p.6 L206–211）与"异步才暴露的行为"（MolmoAct2 自纠正，p.8 L242–245）两类定性/定量证据。
6. **已知坑**：README 的低 RTR 可视化问题；观测频率吸附；中间动作被丢弃；成功判定不回传。

## 局限与注意点

- **代码与论文不完全一致**：默认控制率 50 vs 500 Hz；RTR 监视只显示不报错且只在可视化开启时计算；无 policy-side 异步循环、评测 harness、LIBERO 接入、延迟日志。复用前应按论文设置显式传参，并自行补齐监视/日志。
- **延迟测量定义缺失**：Table 2 与 Table 3 的 DP 延迟相差约 chunk 倍，LIBERO VLA 延迟偏低，论文未说明是否均摊、是否含预处理与数据搬运；与我们的 P50/P95 端到端延迟不可直接比较。
- **掉分不只来自延迟**：Transport 上 ~14–18 ms 延迟的 BC 策略也从 33–78% 掉到 2–4%，论文未解释；LIBERO 上延迟与掉分相关性弱（r=0.10–0.46）。说明"异步掉分"同时反映策略的时间稳定性、hold-last 语义与任务动态，归因需谨慎（对应计划 §5.5 "明确区分控制恢复与语义决策收益"）。
- **真机证据规模小**：仅 Can/Square 两任务、每策略 20 trials、每任务约 9 个策略点；相关系数的置信区间未报告；Can 上异步仿真仍有解释不了的 sim-real 差（BC-GMM 93 vs 30）。
- **RTR 扫描只在 Square 一个任务上做**；Fig. 5 的具体数值未列表，本文的读图值为近似。
- **动作队列丢中间动作**：策略若一次 push 整个 chunk，只有最后一个被执行；chunk 的时序必须由策略进程维护。对我们的高层/低层三层结构，低层执行器进程须负责节拍。
- **评测时间成本**：RTR=1 时 400 trials × 任务 horizon 的真实时间；LIBERO 长程任务 + 多种子会很慢；需规划并行多进程/多机（每个 `AsyncSimulation` 是独立进程，理论上可并行，但要监控各自 realized RTR）。
- **`time.sleep` 精度与渲染开销**：OS 调度抖动约毫秒级，相机渲染在仿真进程内串行执行；"漂移 ≤ 2 ms" 的保证是软保证，应以 realized RTR 日志为准。
- **匿名性**：demo 文档字符串泄露了一个非匿名仓库地址；为尊重匿名评审，我们的文稿只引用论文给出的匿名链接与项目页。
- **版本漂移风险**：anonymous.4open.science 快照可能与后续公开版本不同；记录本次读取的快照（本地解压目录）与日期。

## 关键引用句（原文英文，附页码）

1. p.1（Abstract）："However, current simulation benchmarks introduce an artificial sim-to-real gap by running robot policies synchronously i.e. pausing the simulation to let the policy "think" for as long as it needs before executing actions. But real world physics does not wait for policy inference."
2. p.2 L40–43："If the policy fails to update the control queue in time for the next control step, the simulator uses the most recent action. The asynchronous design decouples the speed of the policy from the simulation rate, which is run in realtime."
3. p.2 L45–47："To the best of our knowledge, AsyncRoboSim is the first public asynchronous and realtime simulation meta-benchmark for evaluating robot policies."
4. p.3 L84–86："Modifying the RTR allows the user to evaluate policies under different hardware conditions and resource constraints by speeding up or slowing down physics (equivalently, slowing down or speeding up policy inference)."
5. p.4 L115–118："At the beginning of the main loop, the simulator pulls the last action from the action queue. If no action is available (for e.g. a slow policy) the simulator uses the previously executed action, mirroring how a real robot continues actuating under its last command."
6. p.4 L130–137："Given r > 0, simulation is considered perfectly synchronized with wall-clock time at real-time rate r if Δsim = r · Δreal. [...] at every synchronization event, the simulator sleeps for Δsleep = max(0, Δsim/r − Δreal) seconds via a Python time.sleep() call [...] We are able to guarantee that simulated time never drifts from wall-clock (real) time by more than 1/control_frequency (default: 2ms)."
7. p.6 L206–211："Under conventional synchronous simulation, diffusion policy with chunk size 8 outperforms BC-Transformer-GMM, with success rates of 86% and 83%, respectively. However, this ordering is reversed under both asynchronous simulation and real-world deployment. Note that diffusion policy has substantially higher inference latency than BC-Transformer-GMM (587 ms compared with 12 ms)."
8. p.8 L242–245："We observe self-correction behavior from MolmoAct2 in our asynchronous simulator. Importantly, this behavior is not visible under synchronous simulation, and is only visible when accounting for the asynchronous interaction between the policy and the environment."
9. p.8 L249–251："Note that synchronous simulation is the limiting case of asynchronous simulation when RTR → 0 i.e. the simulation runs infinitely slowly and waits arbitrarily long for policy inference to complete."
10. p.8 L255–258："This reveals a key principle for robot evaluation: latency is not merely an auxiliary runtime statistic but directly affects task success when the asynchronous nature of the world is properly accounted for. Asynchronous simulation exposes a latency-reactivity tradeoff that synchronous evaluation systematically hides."
