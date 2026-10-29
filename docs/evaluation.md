# Evaluation protocol (v0.1)

Embodied Real-Time Bench evaluates language-model agents that control a simulated robot arm on long-horizon household tasks **while the world keeps moving**. This document defines what an episode is, how it is scored, and the three timing protocols (clocks).

## Tasks

- **60 tasks in 6 categories** (10 each), built on the RoboCerebra scenes (LIBERO / robosuite, MuJoCo 3.1.6, Franka Panda):
  - **Ideal**: static scene, multi-step instruction.
  - **Memory · Execution**: objects end up in closed drawers; the agent must remember them and act on them.
  - **Memory · Exploration**: targets start hidden; the agent must search.
  - **Observation Mismatch**: the episode starts part-way through the demonstration (already-completed subgoals are excluded from scoring).
  - **Random Disturbance**: objects are displaced at random times (±15 cm).
  - **Mix**: mismatch and disturbances together.
- Task data come from the RoboCerebra benchmark release and are downloaded from Hugging Face by `scripts/setup_env.sh`; they are not redistributed here.

## Episode

- The simulator runs at **20 Hz in real time** and never waits for the agent. An episode ends when all subgoals are complete, the agent declares the task done (after a completion check), the agent has issued **40 skill calls**, or **300 s** of simulated time have passed.
- **Observation** (a timestamped snapshot, read whenever the agent wants): object positions, drawer openings, gripper state, held object, the skill currently executing, and messages; a third-person camera image when images are enabled. Objects inside closed drawers are hidden.
- **Actions** (skill calls to a scripted executor): `pick(obj)`, `place(region)`, `place_on(obj)`, `pour(obj)`, `open_drawer(region)`, `close_drawer(region)`, `turnon(fixture)`, `wait(n)`, `done`. Skills take seconds of simulated time and can be cancelled at any control step. A failed skill returns a reason (for example *out of reach* or *blocked from above*).

## Scoring

- Each task defines ordered subgoal chains per object (the RoboCerebra goal states, with a repaired scorer that fixes several false positives and negatives of the original).
- **Score** = completed subgoals / total subgoals, excluding subgoals already completed at the start (Observation Mismatch).
- **Success** = all subgoals completed. **pass^3** = success in all three seeds of a task.
- **Time-budget score** = fraction of subgoals completed within the first B seconds (B = 30, 60, 120, 180); the full-episode score uses B = 300 s.
- **Reference**: a scripted executor that replays the demonstration plan without a language model (0.825 on H20; it is not an upper bound, agents beat it on several tasks).

## Clocks

| Clock | Environment time charged for a model call | What it measures |
|---|---|---|
| **Wall** (default) | the measured latency: the world advances during inference | decisions plus serving speed; hardware and concurrency must be reported |
| **Token** | the world is frozen during the call, then advances by `0.145 s + uncached_input / 2821 tok/s + output / 23.6 tok/s` before the result is delivered | temporal cost of deliberation, independent of hardware; rewards short outputs and prefix-cache reuse |
| **Paused** | nothing: the world is frozen while any call is in flight | decision quality without time pressure (an upper reference) |

- The token-clock constants were fitted on Qwen3.8-27B (FP8) served by vLLM on one L20 (7,242 calls, R² = 0.998) and are fixed for all models.
- `uncached_input` uses the server-reported `usage.prompt_tokens_details.cached_tokens` (vLLM: `--enable-prompt-tokens-details`). Do not saturate the KV cache under the token clock (cache evictions inflate charged time).
- Under the paused and token clocks the world pauses at the next control step after a call starts (≤ 50 ms).

## Validity

An episode is valid if, after the first 3 s, the simulator's maximum lag behind its schedule is ≤ 0.25 s and the 95th-percentile lag is ≤ 50 ms (frozen periods are excluded under the paused and token clocks). Invalid episodes must be re-run (`ertbench verify --archive-violations`, then `ertbench run ... --resume`).

## Reference agent frameworks

All reference agents share one prompt layout (static scene block → history → image → current state → mode instruction) so that a fast and a slow branch of the same model can share the KV cache.

| Framework | Description |
|---|---|
| Fast · Jev | all legal actions are listed as lettered options; the model emits one token and the highest-probability legal letter is executed |
| Fast · Text | thinking off; one JSON action per decision |
| Slow · Think | thinking before every action (≤ 4,096 tokens) |
| Dual · Plan | Fast Jev acts continuously; a slow branch thinks in the background and sends full plans |
| Dual · Advice | Fast Jev acts continuously; a slow branch (thinking off) injects one- or two-sentence advice |

The coordinator blocks a call after 3 consecutive failures (until progress or a disturbance), lets the model override a blocked choice by insisting 3 times, and checks completion (thinking off) before accepting `done`.

## Reported metrics

Score ± SD over 3 seeds, success, pass^3, time-budget scores, decision latency charged to the environment (p50 / p95; fast branch for dual frameworks), time per task, tokens per task (uncached input + output), and the number of episodes. Wall-clock entries also list the serving hardware and the number of concurrent episodes per model instance (2 in the reference results).
