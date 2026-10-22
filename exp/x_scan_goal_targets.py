"""扫描全部任务：评分目标（in/on/pour 的目标、open/close 的对象）是否出现在提供给模型的 id 列表（env.regions、物体、装置）中。
用法: python x_scan_goal_targets.py"""
import collections
import rc_env as R
rows = []; types = ("Ideal", "Memory_Execution", "Memory_Exploration", "Mix", "Observation_Mismatching", "Random_Disturbance")
for tt in types:
    for cd in sorted((R.BENCH_ROOT / tt).glob("case*"), key=lambda p: int(p.name[4:])):
        c = R.load_case(tt, R.BENCH_ROOT / ("Ideal" if tt in R.USE_IDEAL_FILES else tt) / cd.name, load_demo=False)
        env = R.make_env(c, use_camera_obs=False); env.reset()
        visible = set(env.regions) | set(env.objects_dict) | set(env.fixtures_dict)
        missing = collections.Counter()
        for obj, acts in c.goal.items():
            for a in acts:
                tgt = a[2] if a[0] in ("in", "on", "pour") and len(a) > 2 else (a[1] if a[0] in ("open", "close", "turnon") else None)
                if tgt and tgt not in visible: missing[f"{a[0]}:{tgt}"] += 1
        extra = [s for s in env.object_sites_dict if not s.endswith("_init_region") and s not in env.regions]
        rows.append((tt, cd.name, c.n_goals, dict(missing), extra)); env.close()
        if missing: print(f"{tt}/{cd.name}: n_goals={c.n_goals} 缺失目标 {dict(missing)}  可补充站点 {extra}", flush=True)
aff = [r for r in rows if r[3]]
print(f"\n受影响任务 {len(aff)}/{len(rows)}；涉及子目标 {sum(sum(r[3].values()) for r in aff)} 个")
print("所有缺失目标类型:", collections.Counter(k.split(':', 1)[1] for r in aff for k in r[3]))
