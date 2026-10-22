# robocerebra-realtime：RoboCerebra 实时快慢思考基准

在 RoboCerebra（NeurIPS 2025 Datasets & Benchmarks）的长程操作任务上，研究实时条件下的快慢思考调度。最终方法是同一模型、共享前缀 KV 缓存的快慢双分支。计划文档：`realtime_robot_reasoning_benchmark_plan-2.md`。

项目分两条路线：
- **路线 A：学习策略直接控制。** 公开视觉-语言-动作策略（OpenVLA-OFT、SmolVLA）直接输出机械臂动作，代码在 `vla_policy_eval/`，待推送。
- **路线 B：语言模型实时调度。** 语言模型选择技能与参数，动作由基于仿真真值的脚本技能执行器完成，仿真按墙钟实时推进，代码在 `exp/`。

阶段汇总见 `notes/RoboCerebra_阶段汇总_合并版_2026-10-22.md`。

## 目录

| 目录 | 内容 |
|---|---|
| `exp/` | 路线 B 代码：任务加载与动态条件、技能执行器、计分器（官方 / 修复版）、实时异步环境、快慢双分支规划器、统计与出图 |
| `vla_policy_eval/` | 路线 A 代码（待推送，见该目录 README） |
| `notes/` | 实验记录、报告与图；论文精读笔记；RoboCerebra 代码与协议解析、任务清单、演示回放诊断 |
| `server/` | GPU 服务器上的 vLLM 部署脚本与说明 |

以下内容不入库，需要自行准备：

| 本地目录 | 内容与获取方式 |
|---|---|
| `repos/` | 第三方仓库的浅克隆：RoboCerebra（含捆绑 LIBERO）、LIBERO 上游、openvla-oft 等 |
| `data/RoboCerebra_Bench/` | Hugging Face 数据集 `qiukingballball/RoboCerebraBench`，共 60 个 case |
| `papers/` | 参考文献 PDF |
| `exp/.venv/` | uv 虚拟环境（Python 3.10） |
| `exp/runs/` | 实验输出：每局的 `episode.json`、`timeline.json`、`states.npz` |
| `exp/.env` | 模型服务地址与密钥，按 `exp/.env.example` 填写 |

环境搭建见 `server/setup_robocerebra_env.sh`（服务器）和 `notes/Phase0_实验记录_2026-10-16.md` 第 0 节（本机 macOS）。

## 主要结果（路线 B，2026-10-22）

RoboCerebra 全部 60 个任务，5 种推理模式，3 批共 900 局，全部满足实时性判据。详见 `notes/排行榜_完整版_2026-10-22.md`。
- 给满 300 s 时，前四名得分 0.707–0.724，彼此不可区分。
- 时间预算 60 s 时，以 Jev 为快分支的三种模式（0.611–0.617）显著高于仅快·文本（0.563）和每步开思考（0.316）。
- 参考线：不用语言模型、按演示步骤执行，得分 0.832。

## 复现排行榜

```bash
cd exp
# 一局 = 任务 × 模式 × 种子；需要 exp/.env 中的 LLM_EXP_* 指向自部署 vLLM
LLM_PROFILE=exp RUNS_SUBDIR=llm_l20_r4lb .venv/bin/python run_dual_shared_episode.py Ideal/case1 \
    --slow=off --fast=jev --max_sim=300 --max_skills=40 --seed=1 --skip_existing
# 五种模式的参数：
#   仅快·文本            --slow=off --fast=text
#   仅快·Jev             --slow=off --fast=jev
#   仅慢（每步开思考）    --slow=off --fast=think
#   双分支·完整计划·Jev   --slow=on --fast=jev
#   双分支·建议注入·Jev   --slow=advice --fast=jev --done_verify_wait=0
# 统计与出图（输出到 notes/figs_lb/）
.venv/bin/python analyze_leaderboard.py --root=llm_l20_r4lb      # 加 --seeds=1 只统计指定批次
.venv/bin/python plot_leaderboard.py --root=llm_l20_r4lb
```

注意事项：
- 实时运行对 CPU 敏感。M1 Pro 上最多同时跑 2 局，且不要和其他重负载任务同时运行。
- 不满足实时性判据（开局 3 s 后最大滞后 ≤ 0.25 s、p95 ≤ 50 ms）的局会被统计脚本剔除，需要删除后重跑。
- 不用语言模型的参考线：`run_gt_plan.py`，统计用 `analyze_gt60.py`。

## 其他实验入口

```bash
cd exp
.venv/bin/python e01_smoke_and_speed.py Ideal case1        # 环境冒烟 + 仿真吞吐
.venv/bin/python e02_inventory.py                           # 任务清单 → notes/RoboCerebra_任务清单.md
.venv/bin/python e03_demo_replay.py Ideal case1 --video     # 演示状态/动作回放诊断
.venv/bin/python e05_oracle_replay_all.py 1                 # 全任务演示回放（官方 / 修复版计分）
.venv/bin/python run_gt_plan.py Ideal/case1 --video --tag=gtplan_test   # 标准计划，完成即切换
.venv/bin/python run_original.py Ideal/case6 --switch=150 --resume --video  # 官方协议：150 步时间片 + resume
.venv/bin/python x_skill_test.py Ideal case3 pick wine_bottle_1             # 单技能测试
.venv/bin/python llm_client.py --probe                       # 模型服务延迟 / 图像支持探测
.venv/bin/python e12_prefix_cache_probe.py --n=5 --words=3000  # 前缀缓存是否可用
.venv/bin/python rescore.py --all                           # 基于 states.npz 离线重算计分
python3 md_to_docx.py ../notes/<文件>.md                     # Markdown 报告转 Word（导入飞书用，需 pip install python-docx）
```

## 核心模块

| 文件 | 作用 |
|---|---|
| `exp/rc_env.py` | 任务加载、建环境、提供给规划器的区域列表（含评分目标用到的功能性站点） |
| `exp/rc_dynamics.py` | RoboCerebra 动态条件：随机扰动、描述错位，以及与官方协议的差异说明 |
| `exp/skills.py` | 技能执行器：pick / place / pour / turnon 为物理执行，抽屉开关与抽屉内取物为抽象运动学 |
| `exp/scoring.py` | 官方计分与修复版计分（v6，规则 R1–R11） |
| `exp/realtime_env.py` | 实时异步仿真、命令队列、时间戳与滞后记录 |
| `exp/run_dual_shared_episode.py` | 快慢双分支规划器（同模型、共享前缀）；五种模式都由它运行 |
| `exp/jev_fast.py`、`exp/shared_prompt.py`、`exp/llm_client.py` | Jev 候选打分、共享前缀提示布局、模型客户端（支持请求级 `cache_salt`） |
| `exp/analyze_leaderboard.py`、`exp/plot_leaderboard.py` | 排行榜统计（含批间标准差、时间预算得分、逐任务配对比较）与出图 |

## 协作约定

- 每人在自己的分支开发，通过合并请求合入 `main`。
- 不提交密钥：所有 `.env` 已被 `.gitignore` 排除。
- 不提交原始实验输出、视频、权重等大文件。
