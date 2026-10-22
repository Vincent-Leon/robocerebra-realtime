# 第三轮统计（llm_l20_r3；有效 110 局，实时性违规 0 局已剔除；计分器版本：v6 ×110）

| 任务 | 事件 | 方法 | n | 整任务成功 | 子目标完成率 | 用时 s | 技能数 | 失败技能 | 慢分支调用（p50 延迟） | 计划发布/拒绝（来自计划的技能） | 建议次数 | 快分支 p50 s | 快分支缓存命中 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ideal/case6 | case6_E1_midplace | 仅快·Jev | 5 | 5/5 | 1.00 | 36.3 | 10.0 | 2.0 | – | – | – | 0.42 | 53% |
| Ideal/case6 | case6_E1_midplace | 双分支·完整计划·Jev | 5 | 5/5 | 1.00 | 37.2 | 10.0 | 2.0 | 1.0（17.6） | 0.6/0.4（2%） | – | 0.48 | 53% |
| Ideal/case6 | case6_E1_midplace | 双分支·建议注入·Jev | 5 | 5/5 | 1.00 | 40.2 | 10.8 | 2.0 | 4.0（2.5） | – | 4.0 | 0.51 | 50% |
| Ideal/case6 | case6_E3_w6 | 仅快·Jev | 5 | 5/5（余量 1.8 s） | 1.00 | 36.2 | 9.0 | 1.0 | – | – | – | 0.42 | 49% |
| Ideal/case6 | case6_E3_w6 | 双分支·完整计划·Jev | 5 | 5/5（余量 1.8 s） | 1.00 | 36.4 | 9.2 | 1.2 | 1.2（22.8） | 1.2/0.0（22%） | – | 0.42 | 55% |
| Ideal/case6 | case6_E3_w6 | 双分支·建议注入·Jev | 5 | 5/5（余量 1.7 s） | 1.00 | 36.3 | 9.0 | 1.0 | 3.0（2.5） | – | 3.0 | 0.48 | 51% |
| Memory_Exploration/case10 | noevent | 仅快·Jev | 5 | 5/5 | 1.00 | 53.4 | 11.0 | 0.0 | – | – | – | 0.50 | 48% |
| Memory_Exploration/case10 | noevent | 双分支·完整计划·Jev | 5 | 5/5 | 1.00 | 53.4 | 11.0 | 0.0 | 0.2（47.4） | 0.2/0.0（2%） | – | 0.51 | 50% |
| Memory_Exploration/case10 | noevent | 双分支·建议注入·Jev | 5 | 5/5 | 1.00 | 53.9 | 11.0 | 0.0 | 1.0（2.0） | – | 1.0 | 0.51 | 48% |
| Memory_Exploration/case10 | noevent | 双分支·建议注入·Jev（禁缓存） | 5 | 5/5 | 1.00 | 58.1 | 11.4 | 0.0 | 1.2（2.5） | – | 1.2 | 0.74 | 0% |
| Memory_Exploration/case5 | noevent | 仅快·Jev | 5 | 0/5 | 0.79 | 183.0 | 22.8 | 10.0 | – | – | – | 0.56 | 50% |
| Memory_Exploration/case5 | noevent | 双分支·完整计划·Jev | 5 | 0/5 | 0.81 | 183.3 | 30.8 | 18.2 | 1.0（98.5） | 0.2/0.8（0%） | – | 0.55 | 57% |
| Memory_Exploration/case5 | noevent | 双分支·建议注入·Jev | 5 | 0/5 | 0.87 | 102.4 | 15.0 | 2.6 | 4.0（2.9） | – | 4.0 | 0.58 | 48% |
| Memory_Exploration/case5 | noevent | 双分支·建议注入·Jev（禁缓存） | 5 | 0/5 | 0.73 | 205.0 | 29.4 | 15.4 | 17.2（4.0） | – | 17.2 | 1.25 | 0% |
| Memory_Exploration/case6 | noevent | 仅快·Jev | 5 | 5/5 | 1.00 | 67.7 | 12.4 | 1.2 | – | – | – | 0.54 | 43% |
| Memory_Exploration/case6 | noevent | 双分支·完整计划·Jev | 5 | 5/5 | 1.00 | 64.9 | 12.2 | 1.4 | 0.4（54.2） | 0.4/0.0（5%） | – | 0.54 | 47% |
| Memory_Exploration/case6 | noevent | 双分支·建议注入·Jev | 5 | 5/5 | 1.00 | 68.6 | 12.4 | 1.4 | 2.0（2.3） | – | 2.0 | 0.59 | 45% |
| Memory_Exploration/case6 | noevent | 双分支·建议注入·Jev（禁缓存） | 5 | 5/5 | 1.00 | 75.0 | 13.0 | 1.0 | 2.0（2.8） | – | 2.0 | 0.82 | 0% |
| Memory_Exploration/case8 | noevent | 仅快·Jev | 5 | 5/5 | 1.00 | 73.2 | 17.0 | 2.0 | – | – | – | 0.56 | 43% |
| Memory_Exploration/case8 | noevent | 双分支·完整计划·Jev | 5 | 4/5 | 0.89 | 93.2 | 21.2 | 8.0 | 0.6（65.1） | 0.4/0.2（0%） | – | 0.56 | 51% |
| Memory_Exploration/case8 | noevent | 双分支·建议注入·Jev | 5 | 5/5 | 1.00 | 70.9 | 16.0 | 1.0 | 2.0（2.5） | – | 2.0 | 0.58 | 44% |
| Memory_Exploration/case8 | noevent | 双分支·建议注入·Jev（禁缓存） | 5 | 5/5 | 1.00 | 76.5 | 16.2 | 1.2 | 2.2（2.9） | – | 2.2 | 0.81 | 0% |

## 建议注入：触发原因、延迟与采纳

| 方法 | 触发原因 | 次数 | 延迟 p50 s | 延迟 p90 s | 输出 token p50 | 下一步与建议一致 |
|---|---|---|---|---|---|---|
| 双分支·建议注入·Jev | 开局 | 30 | 2.23 | 2.69 | 42 | 10/30 |
| 双分支·建议注入·Jev | 循环 | 2 | 2.85 | 2.95 | 54 | 2/2 |
| 双分支·建议注入·Jev | 技能失败 | 38 | 2.64 | 3.81 | 48 | 21/38 |
| 双分支·建议注入·Jev | 新消息 | 10 | 2.68 | 3.20 | 44 | 1/10 |
| 双分支·建议注入·Jev（禁缓存） | 开局 | 20 | 2.75 | 3.18 | 38 | 0/20 |
| 双分支·建议注入·Jev（禁缓存） | 循环 | 7 | 3.60 | 4.68 | 45 | 4/7 |
| 双分支·建议注入·Jev（禁缓存） | 技能失败 | 86 | 3.91 | 5.20 | 53 | 42/84 |

## 结束方式（planner_done 的来源；空 = 到达时间或技能上限）

- Ideal/case6 case6_E1_midplace 双分支·建议注入·Jev：None ×5
- Ideal/case6 case6_E1_midplace 双分支·完整计划·Jev：None ×5
- Ideal/case6 case6_E1_midplace 仅快·Jev：None ×5
- Ideal/case6 case6_E3_w6 双分支·建议注入·Jev：None ×5
- Ideal/case6 case6_E3_w6 双分支·完整计划·Jev：None ×5
- Ideal/case6 case6_E3_w6 仅快·Jev：None ×5
- Memory_Exploration/case10 noevent 双分支·建议注入·Jev：None ×5
- Memory_Exploration/case10 noevent 双分支·建议注入·Jev（禁缓存）：None ×5
- Memory_Exploration/case10 noevent 双分支·完整计划·Jev：None ×5
- Memory_Exploration/case10 noevent 仅快·Jev：None ×5
- Memory_Exploration/case5 noevent 双分支·建议注入·Jev：fast branch (2 consecutive) ×5
- Memory_Exploration/case5 noevent 双分支·建议注入·Jev（禁缓存）：fast branch (2 consecutive) ×2，None ×3
- Memory_Exploration/case5 noevent 双分支·完整计划·Jev：fast branch (2 consecutive) ×2，None ×3
- Memory_Exploration/case5 noevent 仅快·Jev：None ×2，fast branch (2 consecutive) ×3
- Memory_Exploration/case6 noevent 双分支·建议注入·Jev：None ×5
- Memory_Exploration/case6 noevent 双分支·建议注入·Jev（禁缓存）：None ×5
- Memory_Exploration/case6 noevent 双分支·完整计划·Jev：None ×5
- Memory_Exploration/case6 noevent 仅快·Jev：None ×5
- Memory_Exploration/case8 noevent 双分支·建议注入·Jev：fast branch (2 consecutive) ×5
- Memory_Exploration/case8 noevent 双分支·建议注入·Jev（禁缓存）：fast branch (2 consecutive) ×4，None ×1
- Memory_Exploration/case8 noevent 双分支·完整计划·Jev：fast branch (2 consecutive) ×4，None ×1
- Memory_Exploration/case8 noevent 仅快·Jev：fast branch (2 consecutive) ×5

## 实时性违规（需重跑）

- 无
