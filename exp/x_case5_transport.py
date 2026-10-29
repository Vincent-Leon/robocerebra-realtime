"""诊断：Memory_Execution/case5 拿起巧克力布丁后"搬运失败"。
LLM 各模式都是 pick → place_on_object(plate_1) 反复失败；标准计划是 pick → pour(plate_1) 成功。
直接调用执行器复现三种顺序：A pick→pour（标准计划）；B pick→place_on_object；C pick→place_on_object（失败）→pour。
用法: python x_case5_transport.py [A|B|C ...]
"""
import sys
import numpy as np
import rc_env as R
from skills import ScriptedExecutor

ORDERS = {"A": ["pick", "pour"], "B": ["pick", "place_on_object", "place_on_object"], "C": ["pick", "place_on_object", "pour"]}


def run(order):
    case = R.load_case("Memory_Execution", R.BENCH_ROOT / "Memory_Execution" / "case5")
    env = R.make_env(case, use_camera_obs=False); env.reset()
    ex = ScriptedExecutor(env, case.goal)
    ex.hold(15, -1.0, "settle")
    base = np.array(env.robots[0].base_pos)
    out = []
    for sk in ORDERS[order]:
        if sk == "pick": r = ex.pick("chocolate_pudding_1")
        elif sk == "pour": r = ex.pour("plate_1")
        else: r = ex.place_on_object("plate_1")
        eef = ex.eef(); obj = ex.obj_pos("chocolate_pudding_1"); plate = ex.obj_pos("plate_1")
        out.append(f"{sk}: ok={r.ok} ({r.reason[:70]}) steps={r.steps} | eef={np.round(eef, 3)} 布丁={np.round(obj, 3)} 盘子={np.round(plate, 3)} 盘子距底座={np.linalg.norm((plate - base)[:2]):.3f}")
    env.close()
    return out


if __name__ == "__main__":
    for o in (sys.argv[1:] or ["A", "B", "C"]):
        print(f"== 顺序 {o}: {' → '.join(ORDERS[o])}")
        for line in run(o): print("   " + line)
