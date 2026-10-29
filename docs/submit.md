# Submitting results

1. **Run** the 60 public tasks with 3 seeds under the clock(s) you want to report (see `model_configuration.md`).
2. **Verify** completeness and real-time validity; re-run violators until none remain:
   ```bash
   .venv/bin/python ertbench.py verify --out my_model_wall --archive-violations
   .venv/bin/python ertbench.py run ... --out my_model_wall --resume
   ```
3. **Check** your leaderboard row locally: `.venv/bin/python ertbench.py analyze --out my_model_wall`.
4. **Pack** the results (episode summaries, timelines, manifest and checksums; no simulator states or videos):
   ```bash
   .venv/bin/python ertbench.py pack --out my_model_wall --dest .
   ```
5. **Send** the archive together with: the model and revision, the agent framework (or the code of a new one), the serving stack and settings, the hardware, and the number of concurrent episodes per instance. During the preview, contact the maintainers directly; a submission form will follow.

## Rules

- Do not tune prompts or agents on individual public tasks.
- New agent frameworks are welcome as separate entries if their code is released.
- Wall-clock entries are compared within the hardware they report; token- and paused-clock entries are hardware-independent.
- A held-out task set (unreleased layouts and disturbance seeds) will be evaluated by the maintainers on submitted endpoints.
