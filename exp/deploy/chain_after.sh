#!/bin/bash
# H20 本机：等前一条线（h20_lane.sh）的日志出现"本条线全部完成"后，在同一张卡上接着启动下一条线；前一条线以"停止"结束则不启动。
# 10-29：GPU1 上他人的服务白天间歇性占满（2B 决策延迟 p95 从 0.09 s 涨到 7 s），真实时钟实验改为全部排在 GPU0 上依次跑。
# 用法（环境变量 LANE_RENDER_GPU / LANE_SNAP 照常传给 h20_lane.sh）：
#   LANE_RENDER_GPU=3 LANE_SNAP=../exp_r5d_snap setsid nohup bash chain_after.sh <前一条线的日志> <h20_lane.sh 的参数...> > <新日志> 2>&1 < /dev/null &
set -u
PREV=$1; shift
echo "[$(date '+%m-%d %H:%M:%S')] 等待 ${PREV} 结束"
until grep -q "本条线全部完成\|停止" "$PREV" 2>/dev/null; do sleep 60; done
grep -q "本条线全部完成" "$PREV" || { echo "[$(date '+%m-%d %H:%M:%S')] 前一条线没有正常完成，不启动"; exit 1; }
echo "[$(date '+%m-%d %H:%M:%S')] 前一条线已完成，启动: h20_lane.sh $*"
cd "$(dirname "$0")" && exec bash h20_lane.sh "$@"
