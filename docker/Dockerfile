# Embodied Real-Time Bench — evaluation image (headless EGL rendering on NVIDIA GPUs; the model server runs elsewhere).
# Build:  docker build -t ertbench -f docker/Dockerfile .
# Run:    docker run --rm --gpus all --network host -v $PWD/exp/runs:/ertbench/exp/runs ertbench \
#           python ertbench.py run --model my-model --base-url http://127.0.0.1:8000/v1 --render-gpu 0 --out my_model_wall
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive MUJOCO_GL=egl PYOPENGL_PLATFORM=egl NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates libegl1 libgl1 libglib2.0-0 libgles2 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
WORKDIR /ertbench
COPY exp/requirements.txt exp/requirements.txt
RUN uv venv exp/.venv --python 3.10 && uv pip install --python exp/.venv/bin/python -r exp/requirements.txt
COPY . .
# RoboCerebra code (LIBERO fork) and benchmark data; the data are downloaded, not redistributed
RUN bash -c 'git clone --depth 1 https://github.com/buaa-colalab/RoboCerebra repos/RoboCerebra \
    && echo /ertbench/repos/RoboCerebra/LIBERO > $(exp/.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()[\"purelib\"])")/_robocerebra_libero.pth \
    && exp/.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download(\"qiukingballball/RoboCerebraBench\", repo_type=\"dataset\", local_dir=\"data/RoboCerebra_Bench\")"'
WORKDIR /ertbench/exp
ENV PATH="/ertbench/exp/.venv/bin:${PATH}"
CMD ["python", "ertbench.py", "--help"]
