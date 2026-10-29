#!/bin/bash
# H20 本机执行的真实时钟串联（10-27 起真实时钟参考硬件改为 H20；每张卡一条线，后台独立运行，不依赖本机 Mac 在线）。
# 每一步：起该卡上的模型实例（可用显存 43.2 GiB，与 L20 相同）→ 依次跑若干作业文件（每实例 2 局并行，渲染在 GPU3）→ 停实例。任一步失败即停止。
# 用法: nohup bash h20_lane.sh <GPU> <步骤>... > /data/embodied-rt/exp/runs/_lane_gpu<GPU>.log 2>&1 &
#   步骤 = "<模型>:<RUNS_SUBDIR>:<作业文件1>[,<作业文件2>...]"，模型取 q38 | vl-2b | vl-4b | vl-8b | vl-32b | ds41
#   ds41 = 实验室部署的 DeepSeek-V4.1-Flash（H20 GPU4–7，10.0.2.221:11592），不启停容器，GPU 参数仅用作日志标识。
#   q38 只能在 GPU0（使用 /data/embodied-rt/deploy/qwen38-h20 的现有实例，端口 11593）。
#   渲染默认在 GPU3，可用环境变量 LANE_RENDER_GPU 改（10-29 起 GPU3 被他人训练任务占用，补跑改用 GPU0/GPU1）。
set -u
GPU=$1; shift
EXP=/data/embodied-rt/exp; DEP=/data/embodied-rt/deploy; W=/data/embodied-rt/weights; RG=${LANE_RENDER_GPU:-3}; SNAP=${LANE_SNAP:-../exp_r5c_snap}   # 代码快照可用 LANE_SNAP 改（r5d 起）
log() { echo "[$(date '+%m-%d %H:%M:%S')] GPU${GPU} $*"; }
wait_health() {   # $1 = 端口，$2 = 地址（默认 127.0.0.1）
  for i in $(seq 1 120); do
    [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://${2:-127.0.0.1}:$1/health)" = "200" ] && return 0
    sleep 5
  done
  return 1
}
vl_dir() { case $1 in 32b) echo $W/qwen3-vl-32b-instruct-fp8 ;; *) echo $W/qwen3-vl-$1-instruct ;; esac; }
vl_repo() { case $1 in 32b) echo Qwen3-VL-32B-Instruct-FP8 ;; *) echo Qwen3-VL-${1^^}-Instruct ;; esac; }
start_inst() {    # $1 = 模型；设置 PORT / SERVED / HOST
  HOST=127.0.0.1
  case $1 in
    ds41) HOST=10.0.2.221; PORT=11592; SERVED=deepseek-v4.1-flash ;;
    q38)
      [ "$GPU" = "0" ] || { log "q38 只能在 GPU0"; return 1; }
      PORT=11593; SERVED=exp-qwen3.8-27b-fp8
      (cd $DEP/qwen38-h20 && docker compose -p embodied-q38h20 up -d) >/dev/null 2>&1 ;;
    vl-*)
      s=${1#vl-}; PORT=$((11594 + GPU)); SERVED=exp-qwen3-vl-$s; d=$(vl_dir $s)
      if [ "$s" = "8b" ] || [ "$s" = "32b" ]; then   # H20 上的 8B / 32B 由 /tmp/dl_vl_h20.sh 下载，等它完成
        until grep -q "done $(vl_repo $s) rc=0" /tmp/dl_vl_h20.log 2>/dev/null; do sleep 60; done
      fi
      (cd $DEP/vl-h20 && VL_GPU=$GPU VL_PORT=$PORT VL_DIR=$d VL_NAME=$SERVED docker compose -p embodied-vl-h20-gpu$GPU up -d) >/dev/null 2>&1 ;;
    *) log "未知模型 $1"; return 1 ;;
  esac
  wait_health $PORT $HOST || { log "$1 未就绪"; return 1; }
  log "$1 就绪（端口 ${PORT}，$(nvidia-smi --query-gpu=memory.used --format=csv,noheader -i $GPU)）"
}
stop_inst() {
  case $1 in
    q38) (cd $DEP/qwen38-h20 && docker compose -p embodied-q38h20 down) >/dev/null 2>&1 ;;
    ds41) : ;;                                   # 外部实例，不停
    vl-*) (cd $DEP/vl-h20 && VL_GPU=$GPU VL_PORT=$PORT VL_DIR=x VL_NAME=x docker compose -p embodied-vl-h20-gpu$GPU down) >/dev/null 2>&1 ;;
  esac
}
run_batch() {     # $1 = RUNS_SUBDIR，$2 = 作业文件（相对 exp/，可写成 文件@并行数，默认 2）
  local f=${2%@*} par=2 name
  [ "$f" != "$2" ] && par=${2##*@}
  name=$(basename "$f")
  (cd $EXP && LLM_PROFILE=exp LLM_EXP_BASE_URL=http://${HOST}:$PORT/v1 LLM_EXP_MODEL=$SERVED RENDER_GPU=$RG deploy/h20_run.sh "$1" "$f" $par $SNAP) || return 1
  sleep 60
  until awk "/作业文件 ${name}/{f=1} f" $EXP/runs/$1/_logs/progress.txt 2>/dev/null | grep -q 全部结束; do sleep 60; done
  log "$1 / ${name} 结束：$(awk "/作业文件 ${name}/{f=1} f" $EXP/runs/$1/_logs/progress.txt | tail -1)"
}
cur=""   # 相邻步骤模型相同时沿用同一实例（例如同一模型分别写入真实 / token / 暂停时钟的目录）
for step in "$@"; do
  IFS=: read -r model sub jobs <<< "$step"
  if [ "$model" != "$cur" ]; then
    [ -n "$cur" ] && { stop_inst "$cur"; log "$cur 全部批次完成，实例已停"; }
    start_inst "$model" || { log "启动失败，停止"; exit 1; }
    cur=$model
  fi
  IFS=, read -ra files <<< "$jobs"
  for f in "${files[@]}"; do run_batch "$sub" "$f" || { log "批量启动失败，停止"; exit 1; }; done
done
[ -n "$cur" ] && { stop_inst "$cur"; log "$cur 全部批次完成，实例已停"; }
log "本条线全部完成"
