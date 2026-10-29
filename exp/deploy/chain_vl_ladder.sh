#!/bin/bash
# 本机执行（只有本机能同时登录 L20 与 H20）：等 H20 上 Qwen3.8 主榜跑完，依次把 L20 GPU3 切到 Qwen3-VL 2B / 4B / 8B / 32B，
# 每个尺寸在 H20 上跑 r5 核心模式（jobs/r5_core_img_s1.txt，180 局，2 局并行），全部串行。任一步失败即停止，不再切换。
# 用法: nohup caffeinate -i bash chain_vl_ladder.sh > /tmp/chain_vl_ladder.log 2>&1 &
set -u
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*"; }
wait_done() {   # $1 = RUNS_SUBDIR，$2 = 作业文件名：等该作业文件对应的批次写出"全部结束"
  until ssh -o ConnectTimeout=10 H20-lan "awk '/作业文件 $2/{f=1} f' /data/embodied-rt/exp/runs/$1/_logs/progress.txt 2>/dev/null | grep -q 全部结束" < /dev/null; do sleep 120; done
}
log "等待 Qwen3.8 主榜（llm_h20_r5_q38）结束"
wait_done llm_h20_r5_q38 r5_main_img_s1.txt
log "Qwen3.8 主榜结束：$(ssh -o ConnectTimeout=10 H20-lan 'tail -1 /data/embodied-rt/exp/runs/llm_h20_r5_q38/_logs/progress.txt' < /dev/null)"
for s in 2b 4b 8b 32b; do
  log "切换 GPU3 到 vl-$s"
  ssh -o ConnectTimeout=10 L20 "/data/vllm/exp/embodied-rt/l20_gpu3_switch.sh vl-$s" < /dev/null || { log "切换失败，停止"; exit 1; }
  log "在 H20 上启动 vl-$s"
  ssh -o ConnectTimeout=10 H20-lan "cd /data/embodied-rt/exp && LLM_PROFILE=exp LLM_EXP_MODEL=exp-qwen3-vl-$s deploy/h20_run.sh llm_h20_r5_vl$s jobs/r5_core_img_s1.txt 2" < /dev/null || { log "启动失败，停止"; exit 1; }
  sleep 120
  wait_done llm_h20_r5_vl$s r5_core_img_s1.txt
  log "vl-$s 结束：$(ssh -o ConnectTimeout=10 H20-lan "tail -1 /data/embodied-rt/exp/runs/llm_h20_r5_vl$s/_logs/progress.txt" < /dev/null)"
done
log "Qwen3-VL 阶梯全部完成；GPU3 停在 vl-32b"
