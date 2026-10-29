#!/bin/bash
# H20 上后台启动一个作业文件（run_jobs.py，固定并行度），断开 SSH 后继续运行。
# 仿真渲染默认放在 GPU1（RENDER_GPU 可改）。10-26 晚 GPU2 被他人任务间歇性占满，渲染卡住数分钟：4B/8B 共 41 局被 SIGABRT 终止、2 局滞后约 200–300 s。实验进程不走代理：H20 的 no_proxy 写的是网段（10.0.0.0/8），httpx2 不认这种写法，
# 访问 L20 实验实例会绕道代理（实测 150 ms 对 3 ms）；实验只访问内网模型服务，不需要外网。
# 用法: h20_run.sh <RUNS_SUBDIR> <作业文件（相对 exp/）> [并行度=2] [代码快照=../exp_r5b_snap]
# 模型由调用方的环境变量指定：
#   Qwen3.8 / Qwen3-VL（L20 GPU3 实验实例）：LLM_PROFILE=exp [LLM_EXP_MODEL=exp-qwen3-vl-2b]（密钥在 exp/.env 的 LLM_EXP_API_KEY）
#   DeepSeek V4（H20 本机 sal-max，内网无需密钥）：LLM_BASE_URL=http://10.0.2.221:11589/v1 LLM_API_KEY=EMPTY LLM_MODEL=deepseek-v4-flash
set -e
cd /data/embodied-rt/exp
SUB=$1; JOBS=$2; PAR=${3:-2}; SNAP=${4:-../exp_r5b_snap}
[ -n "$SUB" ] && [ -f "$JOBS" ] || { echo "用法: $0 <RUNS_SUBDIR> <作业文件> [并行度] [快照]"; exit 1; }
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export NO_PROXY="10.0.2.220,10.0.2.221,localhost,127.0.0.1" no_proxy="10.0.2.220,10.0.2.221,localhost,127.0.0.1"
RG=${RENDER_GPU:-1}
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MUJOCO_EGL_DEVICE_ID=$RG CUDA_VISIBLE_DEVICES=$RG RUNS_SUBDIR=$SUB
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1          # 异常退出时日志里留下输出与调用栈
mkdir -p runs/$SUB
setsid nohup .venv/bin/python run_jobs.py "$SNAP" "$JOBS" --parallel=$PAR > runs/$SUB/_launch.log 2>&1 < /dev/null &
echo "已启动 ${SUB}（作业 ${JOBS}，并行 ${PAR}，快照 ${SNAP}，渲染 GPU${RG}），PID $!"
