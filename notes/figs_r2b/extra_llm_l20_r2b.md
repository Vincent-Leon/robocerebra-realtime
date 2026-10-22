# 第二轮补充统计（llm_l20_r2b，剔除实时性违规 0 个 episode）

| 任务 | 事件 | 方法 | n | 成功 | 完成时间 s | 技能数 | 来自慢计划 | 计划发布 / 拒绝 | 前置失败 | 无效回复 | 开关抽屉 | 失败技能 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ideal/case6 | case6_E3_w6 | dual_shared_jev | 5 | 5/5 | 26.7 | 6.0 | 10% | 0.8 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w6 | dual_shared_text | 5 | 5/5 | 47.0 | 7.4 | 22% | 1.2 / 0.0 | 0.0 | 0.0 | 1.4 | 0.4 |
| Ideal/case6 | case6_E3_w6 | dual_shared_text_monsync | 5 | 0/5 | 70.6 | 10.0 | 0% | 0.4 / 1.0 | 0.0 | 0.0 | 2.0 | 2.4 |
| Ideal/case6 | case6_E3_w6 | fast_shared_jev | 5 | 5/5 | 26.7 | 6.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| Ideal/case6 | case6_E3_w6 | fast_shared_text | 5 | 5/5 | 44.1 | 6.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.2 |
| Ideal/case6 | case6_E3_w6 | fast_shared_text_monsync | 5 | 0/5 | 90.6 | 13.2 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 2.6 | 3.6 |
| Ideal/case6 | case6_E3_w6 | fast_shared_think | 5 | 0/5 | 205.8 | 11.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 2.6 | 2.0 |
| Ideal/case6 | case6_E3_w6 | fast_shared_think_monsync | 5 | 0/5 | 181.3 | 11.2 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 2.6 | 1.6 |
| Memory_Exploration/case10 | noevent | dual_shared_jev | 5 | 5/5 | 60.0 | 12.2 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 1.2 |
| Memory_Exploration/case10 | noevent | dual_shared_jev_bust | 5 | 2/5 | 103.7 | 30.4 | 2% | 0.6 / 0.2 | 0.4 | 0.0 | 1.0 | 24.4 |
| Memory_Exploration/case10 | noevent | dual_shared_text | 5 | 3/5 | 173.1 | 22.4 | 12% | 1.0 / 0.0 | 0.0 | 0.2 | 5.6 | 8.6 |
| Memory_Exploration/case10 | noevent | fast_shared_jev | 5 | 5/5 | 58.5 | 11.8 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 1.0 | 0.8 |
| Memory_Exploration/case10 | noevent | fast_shared_jev_bust | 5 | 2/5 | 208.9 | 24.2 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 3.2 | 17.0 |
| Memory_Exploration/case10 | noevent | fast_shared_text | 5 | 1/5 | 246.5 | 34.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 7.6 | 15.0 |
| Memory_Exploration/case10 | noevent | fast_shared_think | 5 | 1/5 | 292.2 | 10.4 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 3.4 | 4.6 |
| Memory_Exploration/case5 | noevent | dual_shared_jev | 5 | 0/5 | 230.3 | 40.0 | 0% | 0.2 / 0.8 | 0.0 | 0.0 | 16.6 | 21.6 |
| Memory_Exploration/case5 | noevent | dual_shared_jev_bust | 5 | 0/5 | 181.1 | 40.0 | 0% | 0.0 / 0.8 | 0.0 | 0.0 | 14.4 | 24.6 |
| Memory_Exploration/case5 | noevent | dual_shared_text | 5 | 0/5 | 268.3 | 35.0 | 2% | 0.8 / 0.6 | 0.0 | 0.6 | 9.2 | 12.8 |
| Memory_Exploration/case5 | noevent | fast_shared_jev | 5 | 0/5 | 211.7 | 40.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 33.2 | 6.8 |
| Memory_Exploration/case5 | noevent | fast_shared_jev_bust | 5 | 0/5 | 186.6 | 38.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 17.4 | 20.2 |
| Memory_Exploration/case5 | noevent | fast_shared_text | 5 | 0/5 | 235.1 | 28.4 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 10.6 | 8.2 |
| Memory_Exploration/case5 | noevent | fast_shared_think | 5 | 0/5 | 300.8 | 10.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 4.6 | 5.0 |
| Memory_Exploration/case6 | noevent | dual_shared_jev | 5 | 0/5 | 236.2 | 40.0 | 0% | 0.2 / 1.0 | 0.0 | 0.0 | 18.8 | 16.2 |
| Memory_Exploration/case6 | noevent | dual_shared_jev_bust | 5 | 0/5 | 245.1 | 40.0 | 2% | 0.2 / 1.2 | 0.0 | 0.0 | 13.2 | 20.0 |
| Memory_Exploration/case6 | noevent | dual_shared_text | 5 | 1/5 | 258.9 | 28.8 | 4% | 0.8 / 1.0 | 0.0 | 0.0 | 9.4 | 15.6 |
| Memory_Exploration/case6 | noevent | fast_shared_jev | 5 | 0/5 | 229.4 | 40.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 19.6 | 19.0 |
| Memory_Exploration/case6 | noevent | fast_shared_jev_bust | 5 | 0/5 | 229.8 | 40.0 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 14.8 | 21.4 |
| Memory_Exploration/case6 | noevent | fast_shared_text | 5 | 0/5 | 283.2 | 34.6 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 12.4 | 20.0 |
| Memory_Exploration/case6 | noevent | fast_shared_think | 5 | 0/5 | 300.0 | 7.8 | 0% | 0.0 / 0.0 | 0.0 | 0.0 | 3.6 | 3.2 |

## 调用延迟与前缀缓存（按方法与分支）

| 方法 | 分支 | 调用数 | 延迟 p50 s | 延迟 p90 s | 提示 token p50 | 缓存命中 |
|---|---|---|---|---|---|---|
| dual_shared_jev | check | 21 | 0.48 | 0.65 | 1597 | 57% |
| dual_shared_jev | fast | 487 | 0.53 | 0.65 | 2078 | 59% |
| dual_shared_jev | slow | 15 | 78.55 | 142.51 | 1288 | 55% |
| dual_shared_jev_bust | check | 12 | 1.02 | 1.56 | 2314 | 0% |
| dual_shared_jev_bust | fast | 546 | 1.01 | 1.34 | 2261 | 0% |
| dual_shared_jev_bust | slow | 15 | 73.82 | 165.78 | 1323 | 0% |
| dual_shared_text | check | 33 | 2.38 | 3.25 | 1573 | 53% |
| dual_shared_text | fast | 446 | 2.99 | 4.10 | 1849 | 63% |
| dual_shared_text | slow | 27 | 79.25 | 179.96 | 1288 | 55% |
| dual_shared_text_monsync | check | 8 | 2.45 | 3.44 | 1322 | 56% |
| dual_shared_text_monsync | fast | 60 | 2.96 | 3.76 | 1403 | 56% |
| dual_shared_text_monsync | slow | 8 | 23.41 | 40.13 | 1218 | 61% |
| fast_shared_jev | check | 5 | 0.32 | 0.36 | 1287 | 61% |
| fast_shared_jev | fast | 489 | 0.51 | 0.62 | 2065 | 59% |
| fast_shared_jev_bust | fast | 514 | 0.97 | 1.26 | 2244 | 0% |
| fast_shared_text | check | 5 | 2.35 | 2.74 | 1283 | 61% |
| fast_shared_text | fast | 527 | 2.84 | 3.90 | 1818 | 61% |
| fast_shared_text_monsync | check | 5 | 2.27 | 2.59 | 1283 | 60% |
| fast_shared_text_monsync | fast | 79 | 2.91 | 3.63 | 1451 | 53% |
| fast_shared_think | check | 5 | 2.18 | 2.38 | 1284 | 61% |
| fast_shared_think | fast | 208 | 11.03 | 39.64 | 1466 | 49% |
| fast_shared_think_monsync | check | 5 | 1.90 | 2.18 | 1284 | 61% |
| fast_shared_think_monsync | fast | 67 | 8.57 | 20.29 | 1427 | 55% |

## 缓存命中率随提示长度（历史增长）

| 方法·分支 | <1500 | 1500–2500 | 2500–3500 | ≥3500 token |
|---|---|---|---|---|
| dual_shared_jev·check | 60% (n=8) | 53% (n=10) | 65% (n=3) | – |
| dual_shared_jev·fast | 54% (n=72) | 55% (n=279) | 66% (n=136) | – |
| dual_shared_jev·slow | 57% (n=14) | 40% (n=1) | – | – |
| dual_shared_text·check | 58% (n=16) | 49% (n=16) | 57% (n=1) | – |
| dual_shared_text·fast | 58% (n=131) | 64% (n=271) | 66% (n=44) | – |
| dual_shared_text·slow | 61% (n=20) | 43% (n=7) | – | – |
| dual_shared_text_monsync·check | 60% (n=6) | 48% (n=2) | – | – |
| dual_shared_text_monsync·fast | 58% (n=47) | 49% (n=13) | – | – |
| dual_shared_text_monsync·slow | 61% (n=8) | – | – | – |
| fast_shared_jev·check | 61% (n=5) | – | – | – |
| fast_shared_jev·fast | 55% (n=75) | 55% (n=282) | 66% (n=132) | – |
| fast_shared_text·check | 61% (n=5) | – | – | – |
| fast_shared_text·fast | 50% (n=130) | 62% (n=352) | 69% (n=45) | – |
| fast_shared_text_monsync·check | 60% (n=5) | – | – | – |
| fast_shared_text_monsync·fast | 58% (n=46) | 48% (n=33) | – | – |
| fast_shared_think·check | 61% (n=5) | – | – | – |
| fast_shared_think·fast | 48% (n=123) | 50% (n=85) | – | – |
| fast_shared_think_monsync·check | 61% (n=5) | – | – | – |
| fast_shared_think_monsync·fast | 57% (n=48) | 51% (n=19) | – | – |
