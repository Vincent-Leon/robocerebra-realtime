#!/bin/bash
# 本机执行（只有本机能切换 L20 GPU3）：等 Qwen3.8 的暂停 / token 时钟批量跑完，依次把 L20 GPU3 切到 Qwen3-VL 2B / 4B / 8B / 32B，
# 每个尺寸跑 token 时钟 3 批（540 局）与暂停时钟 1 批（180 局），两批同时跑，都结束后切下一个；最后切回 Qwen3.8。任一步失败即停止。
# 暂停 / token 时钟的结果与硬件无关，但 token 时钟按"未命中缓存的输入 token"计时，KV 缓存不能被挤满：32B 在 L20 上 KV 只有约 2.76 万 token，并发降到 4 + 2。
# 用法: nohup caffeinate -i bash chain_l20_virtual.sh > /tmp/chain_l20_virtual.log 2>&1 &
set -u -o pipefail
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*"; }
done_in() {   # $1 = RUNS_SUBDIR，$2 = 作业文件名：该作业文件对应的批次是否已写出"全部结束"
  ssh -o ConnectTimeout=10 H20-lan "awk '/作业文件 $2/{f=1} f' /data/embodied-rt/exp/runs/$1/_logs/progress.txt 2>/dev/null | grep -q 全部结束" < /dev/null
}
log "等待 Qwen3.8 的 token / 暂停时钟批量结束"
until done_in llm_h20_r5_q38_token q38_token_all.txt && done_in llm_h20_r5_q38_paused rest_q38_s1_paused.txt; do sleep 120; done
log "Qwen3.8 新时钟批量结束"
for s in 2b 4b 8b 32b; do
  if [ "$s" = "32b" ]; then PT=4; PP=2; else PT=12; PP=4; fi
  log "切换 L20 GPU3 到 vl-${s}"
  ssh -o ConnectTimeout=10 L20 "/data/vllm/exp/embodied-rt/l20_gpu3_switch.sh vl-${s}" < /dev/null | tail -2 || { log "切换失败，停止"; exit 1; }
  ssh -o ConnectTimeout=10 H20-lan "cd /data/embodied-rt/exp && { echo '# Qwen3-VL-${s} token 时钟 3 批（L20 GPU3，r5c）'; cat jobs/r5_core_img_s1_token.txt jobs/r5_core_img_s2_token.txt jobs/r5_core_img_s3_token.txt | grep -v '^#'; } > jobs/vl${s}_token_all.txt \
    && LLM_PROFILE=exp LLM_EXP_MODEL=exp-qwen3-vl-${s} RENDER_GPU=3 deploy/h20_run.sh llm_r5t_vl${s} jobs/vl${s}_token_all.txt ${PT} ../exp_r5c_snap \
    && LLM_PROFILE=exp LLM_EXP_MODEL=exp-qwen3-vl-${s} RENDER_GPU=3 deploy/h20_run.sh llm_r5p_vl${s} jobs/r5_core_img_s1_paused.txt ${PP} ../exp_r5c_snap" < /dev/null || { log "启动失败，停止"; exit 1; }
  sleep 120
  until done_in llm_r5t_vl${s} vl${s}_token_all.txt && done_in llm_r5p_vl${s} r5_core_img_s1_paused.txt; do sleep 120; done
  log "vl-${s} 新时钟批量结束"
done
log "全部结束，L20 GPU3 切回 qwen38"
ssh -o ConnectTimeout=10 L20 "/data/vllm/exp/embodied-rt/l20_gpu3_switch.sh qwen38" < /dev/null | tail -2
log "串联完成"
