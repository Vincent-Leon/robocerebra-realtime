# 第二轮补充统计（llm_l20_r2，剔除实时性违规 0 个 episode）

| 任务 | 事件 | 方法 | n | 成功 | 完成时间 s | 技能数 | 来自慢计划 | 计划发布 / 拒绝 | 前置失败 | 无效回复 | 开关抽屉 | 失败技能 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ideal/case1 | case1_E1_midplace | dual_shared_jev | 5 | 5/5 | 34.1 | 7.0 | 0% | 0.0 / 0.8 | 0.0 | 0.0 | 0.0 | 1.0 |
| Ideal/case1 | case1_E1_midplace | dual_shared_text | 5 | 5/5 | 54.0 | 7.0 | 6% | 1.0 / 0.4 | 0.2 | 0.0 | 0.0 | 1.0 |
| Ideal/case1 | case1_E1_midplace | fast_shared_jev | 5 | 5/5 | 34.0 | 7.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| Ideal/case1 | case1_E1_midplace | fast_shared_text | 5 | 5/5 | 53.2 | 7.0 | 0% | 0.0 / 0.0 | 0.0 | 0.2 | 0.0 | 1.0 |
| Ideal/case1 | case1_E1_midplace | fast_shared_text_nomon | 5 | 5/5 | 59.7 | 7.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Ideal/case1 | case1_E1_midplace | fast_shared_think | 5 | 5/5 | 114.8 | 7.0 | 0% | 0.0 / 0.0 | 0.0 | 0.6 | 0.0 | 1.0 |
| Ideal/case1 | case1_E1_midplace | fast_shared_think_nomon | 5 | 5/5 | 123.4 | 8.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Ideal/case6 | case6_E1_midplace | dual_shared_jev | 5 | 5/5 | 28.0 | 7.0 | 0% | 0.0 / 0.4 | 0.0 | 0.0 | 1.0 | 1.0 |
| Ideal/case6 | case6_E1_midplace | dual_shared_text | 5 | 3/5 | 95.6 | 11.8 | 2% | 1.0 / 1.0 | 0.4 | 0.0 | 2.0 | 3.0 |
| Ideal/case6 | case6_E1_midplace | fast_shared_jev | 5 | 5/5 | 27.8 | 7.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 1.0 |
| Ideal/case6 | case6_E1_midplace | fast_shared_text | 5 | 4/5 | 59.7 | 8.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 1.0 |
| Ideal/case6 | case6_E1_midplace | fast_shared_text_nomon | 5 | 5/5 | 58.3 | 8.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.2 | 0.2 |
| Ideal/case6 | case6_E1_midplace | fast_shared_think | 5 | 5/5 | 175.9 | 9.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 1.8 |
| Ideal/case6 | case6_E1_midplace | fast_shared_think_nomon | 5 | 5/5 | 154.1 | 8.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w12 | dual_shared_jev | 5 | 5/5 | 26.9 | 6.0 | 7% | 0.6 / 0.2 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w12 | dual_shared_text | 5 | 5/5 | 49.2 | 7.6 | 47% | 1.6 / 0.0 | 0.0 | 0.0 | 1.8 | 0.8 |
| Ideal/case6 | case6_E3_w12 | fast_shared_jev | 5 | 5/5 | 26.7 | 6.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w12 | fast_shared_text | 5 | 5/5 | 43.6 | 6.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.2 | 0.2 |
| Ideal/case6 | case6_E3_w12 | fast_shared_think | 5 | 5/5 | 107.0 | 6.4 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.4 |
| Ideal/case6 | case6_E3_w6 | dual_shared_jev | 5 | 5/5 | 26.9 | 6.0 | 7% | 0.4 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w6 | dual_shared_jev_bust | 5 | 5/5 | 29.3 | 6.0 | 7% | 0.4 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w6 | dual_shared_text | 5 | 0/5 | 90.2 | 13.2 | 0% | 0.6 / 1.4 | 0.0 | 0.0 | 2.2 | 3.0 |
| Ideal/case6 | case6_E3_w6 | fast_shared_jev | 5 | 5/5 | 26.9 | 6.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w6 | fast_shared_jev_bust | 5 | 5/5 | 30.4 | 6.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.2 |
| Ideal/case6 | case6_E3_w6 | fast_shared_text | 5 | 0/5 | 72.3 | 10.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 2.4 | 2.8 |
| Ideal/case6 | case6_E3_w6 | fast_shared_text_nomon | 5 | 5/5 | 42.6 | 6.8 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.2 | 0.4 |
| Ideal/case6 | case6_E3_w6 | fast_shared_think | 5 | 0/5 | 201.2 | 10.2 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 2.6 | 1.6 |
| Ideal/case6 | case6_E3_w6 | fast_shared_think_nomon | 5 | 0/5 | 207.8 | 13.8 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 2.4 | 3.8 |
| Ideal/case6 | case6_E3_w9 | dual_shared_jev | 5 | 5/5 | 26.8 | 6.0 | 17% | 0.6 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w9 | dual_shared_text | 5 | 5/5 | 47.2 | 7.4 | 30% | 1.6 / 0.2 | 0.2 | 0.0 | 1.6 | 0.4 |
| Ideal/case6 | case6_E3_w9 | fast_shared_jev | 5 | 5/5 | 26.7 | 6.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w9 | fast_shared_text | 5 | 5/5 | 44.2 | 6.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.2 | 0.2 |
| Ideal/case6 | case6_E3_w9 | fast_shared_think | 5 | 1/5 | 209.5 | 12.4 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 3.0 | 3.4 |
| Ideal/case6 | noevent | dual_shared_jev | 5 | 5/5 | 26.5 | 6.0 | 7% | 0.4 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | noevent | dual_shared_jev_bust | 5 | 5/5 | 28.8 | 6.0 | 3% | 0.6 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | noevent | dual_shared_text | 5 | 5/5 | 38.9 | 7.2 | 33% | 0.6 / 0.4 | 0.0 | 0.0 | 1.8 | 0.2 |
| Ideal/case6 | noevent | fast_shared_jev | 5 | 5/5 | 26.6 | 6.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | noevent | fast_shared_jev_bust | 5 | 5/5 | 28.7 | 6.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | noevent | fast_shared_text | 5 | 5/5 | 43.6 | 7.2 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.4 | 0.4 |
| Ideal/case6 | noevent | fast_shared_think | 5 | 5/5 | 64.3 | 6.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |

## 调用延迟与前缀缓存（按方法与分支）

| 方法 | 分支 | 调用数 | 延迟 p50 s | 延迟 p90 s | 提示 token p50 | 缓存命中 |
|---|---|---|---|---|---|---|
| dual_shared_jev | check | 48 | 0.39 | 0.49 | 1309 | 56% |
| dual_shared_jev | fast | 179 | 0.42 | 0.49 | 1400 | 56% |
| dual_shared_jev | slow | 18 | 19.92 | 24.95 | 1218 | 65% |
| dual_shared_jev_bust | check | 11 | 0.71 | 0.76 | 1393 | 0% |
| dual_shared_jev_bust | fast | 57 | 0.70 | 1.02 | 1426 | 0% |
| dual_shared_jev_bust | slow | 6 | 22.93 | 27.50 | 1252 | 0% |
| dual_shared_text | check | 89 | 2.37 | 3.52 | 1371 | 56% |
| dual_shared_text | fast | 240 | 2.77 | 3.77 | 1298 | 60% |
| dual_shared_text | slow | 49 | 20.84 | 40.39 | 1218 | 61% |
| fast_shared_jev | check | 25 | 0.32 | 0.38 | 1287 | 61% |
| fast_shared_jev | fast | 190 | 0.40 | 0.45 | 1401 | 56% |
| fast_shared_jev_bust | check | 5 | 0.67 | 0.69 | 1322 | 0% |
| fast_shared_jev_bust | fast | 63 | 0.68 | 0.88 | 1428 | 0% |
| fast_shared_text | check | 25 | 2.01 | 2.26 | 1283 | 61% |
| fast_shared_text | fast | 246 | 2.58 | 3.28 | 1298 | 58% |
| fast_shared_text_nomon | fast | 115 | 2.58 | 3.10 | 1287 | 62% |
| fast_shared_think | check | 25 | 1.93 | 2.14 | 1284 | 61% |
| fast_shared_think | fast | 271 | 8.83 | 24.61 | 1352 | 56% |
| fast_shared_think_nomon | fast | 155 | 9.35 | 21.79 | 1372 | 56% |

## 缓存命中率随提示长度（历史增长）

| 方法·分支 | <1500 | 1500–2500 | 2500–3500 | ≥3500 token |
|---|---|---|---|---|
| dual_shared_jev·check | 60% (n=34) | 49% (n=14) | – | – |
| dual_shared_jev·fast | 57% (n=174) | 52% (n=5) | – | – |
| dual_shared_jev·slow | 65% (n=18) | – | – | – |
| dual_shared_text·check | 58% (n=77) | 48% (n=12) | – | – |
| dual_shared_text·fast | 61% (n=192) | 54% (n=48) | – | – |
| dual_shared_text·slow | 62% (n=45) | 48% (n=4) | – | – |
| fast_shared_jev·check | 61% (n=25) | – | – | – |
| fast_shared_jev·fast | 56% (n=185) | 52% (n=5) | – | – |
| fast_shared_text·check | 61% (n=25) | – | – | – |
| fast_shared_text·fast | 59% (n=227) | 49% (n=19) | – | – |
| fast_shared_text_nomon·fast | 62% (n=115) | – | – | – |
| fast_shared_think·check | 61% (n=25) | – | – | – |
| fast_shared_think·fast | 57% (n=229) | 49% (n=42) | – | – |
| fast_shared_think_nomon·fast | 59% (n=119) | 48% (n=36) | – | – |
