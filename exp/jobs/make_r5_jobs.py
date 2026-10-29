"""生成第五轮（r5）正式作业文件：60 个任务 × 模式，按类别交错排列（中途停下时各类别进度均衡）。
用法: python make_r5_jobs.py [--done_verify=fast] [--fail_block=3] [--seed=1] [--clock=wall|paused|token]
输出（与本脚本同目录）：
  r5_main_img_s<seed>.txt    5 种模式，带图像（Qwen3.8-27B 主榜）
  r5_core_img_s<seed>.txt    3 种核心模式，带图像（Qwen3-VL 阶梯；模型由启动时的 LLM_EXP_MODEL 指定）
  r5_core_noimg_s<seed>.txt  3 种核心模式，关图像（Qwen3.8 关图像基线、DeepSeek V4 这类纯文本模型）
"""
import sys
from pathlib import Path

opt = {a.split("=")[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
DV, FB, SEED = opt.get("done_verify", "fast"), int(opt.get("fail_block", 3)), int(opt.get("seed", 1))
CLOCK = opt.get("clock", "wall")                                       # 非 wall 时文件名加 _<clock>，参数加 --clock
TYPES = ["Ideal", "Memory_Execution", "Memory_Exploration", "Mix", "Observation_Mismatching", "Random_Disturbance"]
TASKS = [f"{t}/case{c}" for c in range(1, 11) for t in TYPES]          # 按 case 外层、类别内层交错
MODES = {"jev": "--fast=jev --slow=off", "text": "--fast=text --slow=off", "think": "--fast=think --slow=off",
         "plan": "--fast=jev --slow=on", "advice": "--fast=jev --slow=advice --done_verify_wait=0"}
CORE = ["jev", "text", "advice"]
COMMON = f"--max_sim=300 --max_skills=40 --seed={SEED} --fail_block={FB} --done_verify={DV}" + ("" if CLOCK == "wall" else f" --clock={CLOCK}")
CS = "" if CLOCK == "wall" else f"_{CLOCK}"
here = Path(__file__).resolve().parent


def write(name, modes, extra=""):
    head = [f"# r5 正式作业：{len(TASKS)} 个任务 × {len(modes)} 种模式（{', '.join(modes)}），种子 {SEED}，失败屏蔽 {FB}，完成核实 {DV}，时钟 {CLOCK}" + (f"，{extra}" if extra else "")]
    lines = [f"{t} {MODES[m]} {COMMON}" + (f" {extra}" if extra else "") for t in TASKS for m in modes]
    (here / name).write_text("\n".join(head + lines) + "\n")
    print(f"{name}: {len(lines)} 局")


write(f"r5_main_img_s{SEED}{CS}.txt", list(MODES))
write(f"r5_core_img_s{SEED}{CS}.txt", CORE)
write(f"r5_core_noimg_s{SEED}{CS}.txt", CORE, "--image=off")
