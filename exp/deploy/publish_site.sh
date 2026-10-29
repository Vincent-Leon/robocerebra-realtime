#!/bin/bash
# 一键更新预览站 https://bench.vincentleon.cn ：从 H20 同步结果（不含 states.npz / 视频 / 单局日志）→ make_site.py 生成 → 上传到 ali-vincent:/var/www/bench。
# 用法: bash deploy/publish_site.sh [preview|final]
#   preview（默认）：真实时钟同时放 L20 上的第 1 批（标 1× L20）与 H20 上已完成的批次，便于在 H20 跑完前展示；
#   final：真实时钟只用 H20（llm_r5w_*）。
set -eu
cd "$(dirname "$0")/.."
MODE=${1:-preview}
WALL_H20=llm_r5w_ds41,llm_r5w_q38,llm_r5w_vl32b,llm_r5w_vl8b,llm_r5w_vl4b,llm_r5w_vl2b
WALL_L20=llm_h20_r5_q38,llm_h20_r5_vl32b,llm_h20_r5_vl8b,llm_h20_r5_vl4b,llm_h20_r5_vl2b
TOKEN=llm_r5t_ds41,llm_h20_r5_q38_token,llm_r5t_vl32b,llm_r5t_vl8b,llm_r5t_vl4b,llm_r5t_vl2b
PAUSED=llm_r5p_ds41,llm_h20_r5_q38_paused,llm_r5p_vl32b,llm_r5p_vl8b,llm_r5p_vl4b,llm_r5p_vl2b
WALL=$WALL_H20; [ "$MODE" = "preview" ] && WALL=$WALL_L20,$WALL_H20
for s in $(echo "$WALL,$TOKEN,$PAUSED" | tr ',' ' '); do
  ssh -o ConnectTimeout=10 H20-lan "test -d /data/embodied-rt/exp/runs/$s" < /dev/null || continue
  rsync -az --exclude='states.npz' --exclude='*.mp4' --exclude='_logs/' H20-lan:/data/embodied-rt/exp/runs/$s ./runs/
done
.venv/bin/python make_site.py --wall=$WALL --token=$TOKEN --paused=$PAUSED 2>&1 | tail -1
scp -q ../site/index.html ali-vincent:/var/www/bench/index.html
ssh -o ConnectTimeout=10 ali-vincent 'chmod 644 /var/www/bench/index.html' < /dev/null
# 示例视频与封面（render_demo.py 生成；页面按 videos/<id>.mp4 引用）
if [ -d ../site/videos ]; then   # 本机 rsync 不支持 --chmod，传完再统一设权限
  rsync -az --include='*.mp4' --include='*.jpg' --exclude='*' ../site/videos/ ali-vincent:/var/www/bench/videos/
  ssh -o ConnectTimeout=10 ali-vincent 'chmod 755 /var/www/bench/videos && chmod 644 /var/www/bench/videos/*' < /dev/null
fi
echo "已上传：https://bench.vincentleon.cn （模式 ${MODE}）"
