# GPU 服务器端工作（L20 / H20 / A6000 / 3090）

本机 Mac 负责仿真与原型；下列工作需要 Linux + NVIDIA GPU：

| 工作 | 用途 | 推荐卡 | 脚本 |
|---|---|---|---|
| A. OpenVLA-OFT × LIBERO 公开权重参考运行 | 用官方评测栈复现 `eval_openvla.py` 的流程，作为"学习型 System 1"对照（注意：RoboCerebra 微调权重未公开，LIBERO 公开权重不认识 RoboCerebra 的物体，结果只作流程验证与下界参考） | 单卡 24 GB 以上（L20/A6000/3090 均可） | `setup_robocerebra_env.sh` |
| B. 用 vLLM 部署 Qwen 27B（OpenAI 兼容接口，开 prefix caching） | 决策层模型；Phase 3 共享前缀/KV 的实际实验 | H20（显存大，27B bf16 约 54 GB，需 1×H20 或 2×L20 TP） | `serve_qwen_vllm.sh` |
| C. RoboDyna（P1） | 动态物理任务扩展，SAPIEN + CuRobo 需 CUDA | 任意 | 见 `notes/RoboDyna.md` 安装可行性 |

## 同步代码
```bash
rsync -av --exclude .venv --exclude runs 具身智能/exp/  user@server:~/embodied/exp/
rsync -av 具身智能/data/RoboCerebra_Bench/            user@server:~/embodied/data/RoboCerebra_Bench/
```
服务器上 `exp/rc_env.py` 依赖的路径约定不变（`repos/RoboCerebra/LIBERO`、`data/RoboCerebra_Bench`），把 `具身智能/` 整体同步即可（`repos/` 可在服务器重新 `git clone`）。

## 实验室 Qwen 服务接入
`exp/llm_client.py` 读取环境变量：
```bash
export LLM_BASE_URL=http://<host>:<port>/v1   # OpenAI 兼容
export LLM_API_KEY=EMPTY
export LLM_MODEL=<模型名，如 Qwen3.5-27B>
exp/.venv/bin/python exp/llm_client.py --probe   # 探测：模型列表、是否支持图像、首 token 延迟
```
需要确认：模型确切版本、是否多模态（图像输入）、服务栈（vLLM/SGLang）、是否开启 `--enable-prefix-caching`、最大上下文长度、并发限制。

## Phase 3 核心实验：共享前缀 × 并发（E1.3）

实验室网关（https://llm.ustb-sal.com）实测**没有可控的前缀缓存**（E1.2：重复 3.2k token 前缀首 token 时间不变，usage 不报告 cached_tokens），所以共享 KV 的实验需要在服务器上自部署：

```bash
# 1) 在 H20（或 2×L20 张量并行）上部署，开启前缀缓存与缓存命中统计
MODEL=<Qwen3.8-27B 权重路径> TP=1 PORT=8000 bash server/serve_qwen_vllm.sh
# 2) 在任意能访问该端口的机器上运行（含本机 Mac，需 exp/.venv）
exp/.venv/bin/python exp/e13_shared_prefix_concurrency.py --base_url=http://<server>:8000/v1 --model=qwen27b --n=10 --prefix_words=2500
```
输出 `exp/runs/e13/shared_prefix_*.json`：快分支在"单独 / 与慢分支并发"× "冷前缀 / 共享前缀 / 共享前缀但图像换新帧"下的首 token 延迟中位数、cached_tokens、慢分支解码速度。这对应计划文档 RQ3 与 §6.2 的边界条件。

之后把 `exp/.env` 的 `LLM_BASE_URL` 指向自部署服务，即可用同一套运行器（`run_llm_episode.py`、`run_dual_episode.py`）在可控服务上复跑全部 episode。

## 已部署：L20 实验实例（2026-10-17）

| 项 | 值 |
|---|---|
| 位置 | L20（ssh 别名 `L20`），**仅 GPU3**；GPU0/1 = 生产 `sal-pro`，GPU2 = `qchibi-comfyui`（他人服务） |
| compose | `/data/vllm/exp/embodied-rt/compose.yml`，密钥在同目录 `.env`（600） |
| 模型 | Qwen3.8-27B，**FP8 在线量化**（BF16 54 GB 单卡放不下），权重只读复用 `/data/vllm/weights/qwen3.8-27b` |
| 服务 | `http://10.0.2.220:11591/v1`，served name `exp-qwen3.8-27b-fp8`，需 API key；上下文 32768，KV 池 172,714 token |
| 本地使用 | `exp/.env` 中 `LLM_EXP_*`；运行器加环境变量 `LLM_PROFILE=exp`（结果目录用 `RUNS_SUBDIR=llm_l20` 区分） |
| 停用 | `ssh L20 'cd /data/vllm/exp/embodied-rt && docker compose down'`（释放 GPU3） |

**与网关（sal-pro，2×L20 BF16）的差异**：FP8 量化、单卡、专用（无其他用户排队）、推理内容以 `reasoning` 字段单独流式返回、usage 报告 `cached_tokens`。

**前缀缓存要点（E1.3 实测）**：混合架构（含 Mamba 层）使注意力块为 784 token，只有整块对齐的公共前缀能复用；提示布局应"静态文本在前、图像居中、动态状态在后、分支指令最后"。
