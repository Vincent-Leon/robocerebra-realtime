#!/bin/bash
# Embodied Real-Time Bench — environment setup (Linux, headless EGL rendering; also works on macOS for development).
# 1. Python 3.10 virtual environment with pinned dependencies (exp/requirements.txt, tested with MuJoCo 3.1.6 + robosuite 1.4.1)
# 2. RoboCerebra code (for its LIBERO fork), added to the environment with a .pth file
# 3. RoboCerebra benchmark data downloaded from Hugging Face (not redistributed by this repository)
# 4. A model-free smoke test: the scripted reference plan on one task
# Usage: bash scripts/setup_env.sh            (from the repository root)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
command -v uv >/dev/null || { echo "Install uv first: https://docs.astral.sh/uv/"; exit 1; }

echo "[1/4] Python environment"
uv venv exp/.venv --python 3.10
uv pip install --python exp/.venv/bin/python -r exp/requirements.txt

echo "[2/4] RoboCerebra code (LIBERO fork)"
mkdir -p repos
[ -d repos/RoboCerebra ] || git clone --depth 1 https://github.com/buaa-colalab/RoboCerebra repos/RoboCerebra
SITE=$(exp/.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
echo "$ROOT/repos/RoboCerebra/LIBERO" > "$SITE/_robocerebra_libero.pth"

echo "[3/4] Benchmark data (Hugging Face: qiukingballball/RoboCerebraBench)"
exp/.venv/bin/python -c "
from huggingface_hub import snapshot_download
snapshot_download('qiukingballball/RoboCerebraBench', repo_type='dataset', local_dir='data/RoboCerebra_Bench')"

echo "[4/4] Smoke test (scripted reference plan, no language model)"
if [ "$(uname)" = "Linux" ]; then export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl; fi
(cd exp && .venv/bin/python run_gt_plan.py Ideal/case1 --tag=setup_check | tail -2)
echo "Done. Next: serve a model and run   cd exp && .venv/bin/python ertbench.py run --help"
