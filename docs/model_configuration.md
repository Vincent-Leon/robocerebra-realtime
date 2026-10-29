# Configuring a model

Any model behind an **OpenAI-compatible Chat Completions endpoint** can be evaluated. Features a framework needs:

| Feature | Needed by | Notes |
|---|---|---|
| image inputs (`image_url` data URLs) | all frameworks with `--image on` (default) | use `--image off` for text-only models |
| `logprobs` with `top_logprobs = 20` | Fast · Jev, Dual · Plan, Dual · Advice | Jev reads the probabilities of the option letters at the first output position |
| thinking switch `chat_template_kwargs.enable_thinking` | Slow · Think (on), every other call (off) | supported by the Qwen and DeepSeek chat templates in vLLM / SGLang |
| `usage.prompt_tokens_details.cached_tokens` | token clock | vLLM: `--enable-prompt-tokens-details`; without it all input is charged as uncached |

## Serving with vLLM (reference settings)

```bash
vllm serve Qwen/Qwen3-VL-8B-Instruct --served-model-name my-model \
  --max-model-len 16384 --max-num-seqs 16 --enable-prefix-caching --enable-prompt-tokens-details \
  --limit-mm-per-prompt '{"image":2,"video":0}' --host 127.0.0.1 --port 8000
```

Reference results use one dedicated instance per model, prefix caching on, and **two concurrent episodes per instance** under the wall clock.

## Running

```bash
cd exp
# wall clock (default), 3 core frameworks, 3 seeds, all 60 tasks
.venv/bin/python ertbench.py run --model my-model --base-url http://127.0.0.1:8000/v1 --out my_model_wall --hardware "1x H20"
# token clock (hardware-independent) and paused clock
.venv/bin/python ertbench.py run --model my-model --base-url http://127.0.0.1:8000/v1 --clock token --out my_model_token
.venv/bin/python ertbench.py run --model my-model --base-url http://127.0.0.1:8000/v1 --clock paused --seeds 1 --out my_model_paused
```

- `--modes jev,text,think,plan,advice` selects frameworks (default `jev,text,advice`).
- `--api-key-env NAME` reads the API key from an environment variable (default `OPENAI_API_KEY`).
- `--render-gpu N` selects the GPU for headless EGL rendering on Linux.
- `--resume` skips episodes that already have results.

Hosted APIs that do not accept the extra request fields used for the thinking switch will be supported through provider adapters in a later release.
