#!/usr/bin/env bash
# 用 vLLM 以 OpenAI 兼容接口部署 Qwen 27B，并开启自动前缀缓存（Phase 3 共享上下文实验的基础）。
# 用法: MODEL=/path/or/hf-id TP=1 PORT=8000 bash serve_qwen_vllm.sh
set -euo pipefail
MODEL=${MODEL:-Qwen/Qwen3.5-27B}
TP=${TP:-1}
PORT=${PORT:-8000}
MAXLEN=${MAXLEN:-32768}
python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" --served-model-name qwen27b \
  --tensor-parallel-size "$TP" --max-model-len "$MAXLEN" \
  --enable-prefix-caching \
  --enable-prompt-tokens-details \
  --gpu-memory-utilization 0.92 \
  --port "$PORT" \
  --enable-chunked-prefill \
  --limit-mm-per-prompt '{"image": 4}'
# 说明：
# - 共享前缀实验需要同一进程内两类请求（快分支短问题 / 慢分支长推理）命中同一前缀缓存块；
#   vLLM 的 automatic prefix caching 以 block 为粒度，前缀必须逐 token 一致（含图像 token）。
# - 记录每个请求的 prompt_tokens / cached_tokens（响应 usage.prompt_tokens_details.cached_tokens，若服务端支持）。
# - 若用 SGLang：python -m sglang.launch_server --model-path $MODEL --tp $TP --port $PORT（RadixAttention 默认开启前缀复用）。
