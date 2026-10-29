#!/bin/bash
# 本机执行：等 H20 上 Qwen3.8 权重下载完成 → 核对非权重文件与 L20 副本一致 → 启动 H20 GPU0 校准实例 → 接口测试 → 启动校准运行。任一步失败即停止。
set -u
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*"; }
until ssh -o ConnectTimeout=10 H20-lan 'grep -q "done rc=" /tmp/dl_q38_h20.log' < /dev/null; do sleep 60; done
log "下载结束：$(ssh -o ConnectTimeout=10 H20-lan 'tail -1 /tmp/dl_q38_h20.log' < /dev/null)"
FILES="config.json generation_config.json chat_template.jinja tokenizer.json tokenizer_config.json vocab.json merges.txt preprocessor_config.json video_preprocessor_config.json model.safetensors.index.json"
A=$(ssh -o ConnectTimeout=10 L20 "cd /data/vllm/weights/qwen3.8-27b && md5sum $FILES 2>&1" < /dev/null)
B=$(ssh -o ConnectTimeout=10 H20-lan "cd /data/embodied-rt/weights/qwen3.8-27b && md5sum $FILES 2>&1" < /dev/null)
if [ "$A" != "$B" ]; then log "非权重文件与 L20 不一致，停止"; echo "L20:"; echo "$A"; echo "H20:"; echo "$B"; exit 1; fi
log "非权重文件与 L20 一致（$(echo "$A" | wc -l | tr -d ' ') 个）"
N=$(ssh -o ConnectTimeout=10 H20-lan 'ls /data/embodied-rt/weights/qwen3.8-27b/model-*.safetensors | wc -l' < /dev/null)
[ "$N" = "18" ] || { log "权重分片数为 ${N}，不是 18，停止"; exit 1; }
log "启动 H20 GPU0 校准实例"
ssh -o ConnectTimeout=10 H20-lan 'cd /data/embodied-rt/deploy/qwen38-h20 && docker compose -p embodied-q38h20 up -d 2>&1 | tail -2' < /dev/null
for i in $(seq 1 120); do
  [ "$(ssh -o ConnectTimeout=10 H20-lan 'curl -s --noproxy "*" -o /dev/null -w "%{http_code}" http://127.0.0.1:11593/health' < /dev/null)" = "200" ] && break
  sleep 10
done
ssh -o ConnectTimeout=10 H20-lan 'docker logs vllm-exp-q38-h20 2>&1 | grep -E "Available KV cache memory|GPU KV cache size|Model loading took" | cut -c1-160' < /dev/null
R=$(ssh -o ConnectTimeout=10 H20-lan 'curl -s --noproxy "*" --max-time 60 http://127.0.0.1:11593/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"exp-qwen3.8-27b-fp8\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: ready\"}],\"max_tokens\":8,\"chat_template_kwargs\":{\"enable_thinking\":false}}"' < /dev/null)
echo "$R" | grep -q '"content"' || { log "接口测试失败：${R:0:300}"; exit 1; }
log "接口测试通过：$(echo "$R" | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])')"
ssh -o ConnectTimeout=10 H20-lan 'cd /data/embodied-rt/exp && LLM_PROFILE=exp LLM_EXP_BASE_URL=http://127.0.0.1:11593/v1 deploy/h20_run.sh llm_h20_r5_q38_h20gpu jobs/r5_core_img_s1.txt 2' < /dev/null
log "校准运行已启动"
