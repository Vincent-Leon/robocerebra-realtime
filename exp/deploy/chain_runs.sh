#!/bin/bash
# 本机执行（只有本机能同时登录 L20 与 H20）：依次把 L20 GPU3 切到某个模型，在 H20 上跑一个作业文件，等它结束再进行下一步。任一步失败即停止。
# 每一步写成 "GPU3实例:RUNS_SUBDIR:作业文件:模型名"，GPU3实例取 qwen38 | vl-2b | vl-4b | vl-8b | vl-32b（见 l20_gpu3_switch.sh）。
# 可选最后一个参数 "final=<实例>"：全部结束后把 GPU3 切到该实例。
# 用法: nohup caffeinate -i bash chain_runs.sh vl-8b:llm_h20_r5_vl8b:jobs/r5_core_img_s1.txt:exp-qwen3-vl-8b ... final=qwen38 > /tmp/chain_runs.log 2>&1 &
set -u
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*"; }
wait_done() {   # $1 = RUNS_SUBDIR，$2 = 作业文件名：等该作业文件对应的批次写出"全部结束"
  until ssh -o ConnectTimeout=10 H20-lan "awk '/作业文件 $2/{f=1} f' /data/embodied-rt/exp/runs/$1/_logs/progress.txt 2>/dev/null | grep -q 全部结束" < /dev/null; do sleep 120; done
}
final=""
for step in "$@"; do
  case "$step" in final=*) final=${step#final=}; continue ;; esac
  IFS=: read -r inst sub jobs model <<< "$step"
  log "切换 GPU3 到 $inst"
  ssh -o ConnectTimeout=10 L20 "/data/vllm/exp/embodied-rt/l20_gpu3_switch.sh $inst" < /dev/null || { log "切换失败，停止"; exit 1; }
  log "在 H20 上启动 ${sub}（${jobs}，模型 ${model}）"
  ssh -o ConnectTimeout=10 H20-lan "cd /data/embodied-rt/exp && LLM_PROFILE=exp LLM_EXP_MODEL=$model deploy/h20_run.sh $sub $jobs 2" < /dev/null || { log "启动失败，停止"; exit 1; }
  sleep 120
  wait_done "$sub" "$(basename "$jobs")"
  log "$sub 结束：$(ssh -o ConnectTimeout=10 H20-lan "awk '/作业文件 $(basename "$jobs")/{f=1} f' /data/embodied-rt/exp/runs/$sub/_logs/progress.txt | tail -1" < /dev/null)"
done
if [ -n "$final" ]; then
  log "全部结束，GPU3 切到 $final"
  ssh -o ConnectTimeout=10 L20 "/data/vllm/exp/embodied-rt/l20_gpu3_switch.sh $final" < /dev/null || log "最后切换失败"
fi
log "串联完成"
