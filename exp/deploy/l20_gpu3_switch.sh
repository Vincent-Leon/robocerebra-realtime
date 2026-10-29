#!/bin/bash
# 切换 L20 GPU3 上的实验实例（两套 compose 共用 10.0.2.220:11591，同一时间只开一个），并等待服务就绪。
# 用法（L20 上）: l20_gpu3_switch.sh qwen38 | vl-2b | vl-4b | vl-8b | vl-32b | down
# qwen38 = Qwen3.8-27B FP8（/data/vllm/exp/embodied-rt/compose.yml，模型名 exp-qwen3.8-27b-fp8）
# vl-*   = Qwen3-VL Instruct（qwen3vl/compose.yml，模型名 exp-qwen3-vl-<尺寸>；32B 用官方 FP8 权重）
set -e
BASE=/data/vllm/exp/embodied-rt; W=/data/vllm/weights
down_all() {
  (cd $BASE && docker compose down) >/dev/null 2>&1 || true
  (cd $BASE/qwen3vl && docker compose -p embodied-vl --env-file ../.env down) >/dev/null 2>&1 || true
}
case "$1" in
  qwen38) down_all; (cd $BASE && docker compose up -d) ;;
  vl-2b|vl-4b|vl-8b) down_all; s=${1#vl-}
    (cd $BASE/qwen3vl && VL_DIR=$W/qwen3-vl-$s-instruct VL_NAME=exp-qwen3-vl-$s docker compose -p embodied-vl --env-file ../.env up -d) ;;
  vl-32b) down_all
    (cd $BASE/qwen3vl && VL_DIR=$W/qwen3-vl-32b-instruct-fp8 VL_NAME=exp-qwen3-vl-32b docker compose -p embodied-vl --env-file ../.env up -d) ;;
  down) down_all; echo "GPU3 实验实例已全部停止"; exit 0 ;;
  *) echo "用法: $0 qwen38|vl-2b|vl-4b|vl-8b|vl-32b|down"; exit 1 ;;
esac
echo "[$(date +%T)] 等待 $1 就绪..."
for i in $(seq 1 120); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' http://10.0.2.220:11591/health)" = "200" ]; then
    echo "[$(date +%T)] 就绪"; nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader -i 3; exit 0
  fi
  sleep 5
done
echo "[$(date +%T)] 10 分钟内未就绪，最近日志："; docker logs --tail 30 $( [ "$1" = qwen38 ] && echo vllm-exp-embodied || echo vllm-exp-embodied-vl ) 2>&1 | sed -E 's/(api[-_]key[^ ]*[ =:]+)[^ ]+/\1***/I; s/sk-[A-Za-z0-9_-]+/sk-***/g; s/[A-Za-z0-9_-]{32,}/***/g'
exit 1
