#!/usr/bin/env bash
# RoboCerebra 官方评测栈（OpenVLA-OFT + 捆绑 LIBERO）在 Linux + CUDA 上的环境搭建。
# 按 repos/RoboCerebra/README.md 的步骤整理，并修正了捆绑 LIBERO 缺 __init__.py 的问题。
set -euo pipefail
ROOT=${ROOT:-$HOME/embodied}
ENV_NAME=${ENV_NAME:-openvla-oft}
mkdir -p "$ROOT/repos" && cd "$ROOT/repos"
[ -d RoboCerebra ] || git clone https://github.com/buaa-colalab/RoboCerebra
[ -d openvla-oft ] || git clone https://github.com/moojink/openvla-oft

conda create -n "$ENV_NAME" python=3.10 -y
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate "$ENV_NAME"
pip install torch torchvision torchaudio            # 按服务器 CUDA 版本选择 index-url
cd openvla-oft && pip install -e . && cd ..
pip install packaging ninja && pip install "flash-attn==2.5.5" --no-build-isolation
# 捆绑 LIBERO：顶层缺 libero/__init__.py，用 .pth 把仓库根目录加入 sys.path（不改第三方代码）
SITE=$(python -c "import site; print(site.getsitepackages()[0])")
echo "$ROOT/repos/RoboCerebra/LIBERO" > "$SITE/_robocerebra_libero.pth"
pip install -r openvla-oft/experiments/robot/libero/libero_requirements.txt
pip install "numpy>=1.23.5,<2.0.0" "peft>=0.17.0" "mujoco>=3.1.2" h5py imageio[ffmpeg] huggingface_hub
# 避免 LIBERO 首次导入的交互式提示
mkdir -p "$ROOT/.libero"; export LIBERO_CONFIG_PATH="$ROOT/.libero"
python - <<PY
import os, yaml
pkg = "$ROOT/repos/RoboCerebra/LIBERO/libero/libero"
cfg = {"benchmark_root": pkg, "bddl_files": f"{pkg}/bddl_files", "init_states": f"{pkg}/init_files", "datasets": "$ROOT/data/libero_datasets", "assets": f"{pkg}/assets"}
open(os.path.join(os.environ["LIBERO_CONFIG_PATH"], "config.yaml"), "w").write(yaml.safe_dump(cfg))
PY
# 数据
mkdir -p "$ROOT/data" && hf download qiukingballball/RoboCerebraBench --repo-type dataset --local-dir "$ROOT/data/RoboCerebra_Bench"
# 公开的 OpenVLA-OFT LIBERO 权重（仅作流程验证；RoboCerebra 微调权重未公开）
# hf download moojink/openvla-7b-oft-finetuned-libero-spatial --local-dir "$ROOT/ckpt/openvla-oft-libero-spatial"
echo "完成。运行示例："
echo "  export ROBOCEREBRA_BENCH_ROOT=$ROOT/data/RoboCerebra_Bench ROBOCEREBRA_PRETRAINED_CHECKPOINT=$ROOT/ckpt/<ckpt> MUJOCO_GL=egl LIBERO_CONFIG_PATH=$ROOT/.libero"
echo "  cd $ROOT/repos/RoboCerebra/evaluation && python eval_openvla.py --task_types '[\"Ideal\"]' --num_trials_per_task 1"
