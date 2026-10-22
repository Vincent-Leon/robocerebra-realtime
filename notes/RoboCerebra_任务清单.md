# RoboCerebra 基准任务清单（自动生成，E0.2）

- 任务目录总数：60（6 类 × 10 case）；其中 Ideal / Observation_Mismatching / Random_Disturbance 共用 Ideal 的 10 个任务文件，故不同任务文件实际为 40 个。
- 场景分布：{'COFFEE_TABLESCENE': 55, 'KITCHEN_TABLESCENE': 5}
- goal.json 谓词分布（全部 60 个目录）：{'pick': 199, 'in': 163, 'on': 15, 'pour': 97, 'open': 61, 'turnon': 7, 'close': 15}
- 每个任务子步数：min=4 max=15 mean=9.4
- 人类演示长度（控制步，20 Hz）：min=1086 max=10117 mean=3177；官方评测每子步固定 150 步。

| 类型 | case | 场景 | 任务 | 子步数 | 目标数 | 演示步数 | 子步时长 min/mean/max | 谓词 | 干扰物 |
|---|---|---|---|---|---|---|---|---|---|
| Ideal | case1 | COFFEE | Organize all the food boxes into the white storage box. | 6 | 6 | 2554 | 242/425.7/490 | pick in pick in pick in | black_book |
| Ideal | case2 | COFFEE | Place the cream cheese into the white storage box and place the frypan onto the rack | 4 | 4 | 2780 | 256/694.8/1363 | pick in pick on | moka_pot |
| Ideal | case3 | COFFEE | Place the plates neatly between the knife and fork, and pour all the snacks and drinks into the plates. | 10 | 10 | 2273 | 127/227.3/430 | pick in pick pour in pick pour in pick pour | moka_pot |
| Ideal | case4 | COFFEE | Clean up the desk by putting the two boxes in the bowl and place the frying pan onto the cabinet. | 6 | 6 | 1086 | 146/181.0/233 | pick pour pick pour pick in | moka_pot |
| Ideal | case5 | COFFEE | Prepare a snack tray with chocolate pudding and wine in the plate. | 6 | 6 | 2284 | 145/380.7/797 | pick pour in pick pour in | ketchup |
| Ideal | case6 | COFFEE | Place the butter into the short cabinet and pour the tomato sauce into the plate. | 6 | 6 | 2203 | 196/367.2/786 | open pick in pick pour in | chocolate_pudding |
| Ideal | case7 | COFFEE | Place the boxes of chocolate pudding and butter into a bowl and heat the pan. | 7 | 7 | 2028 | 148/289.7/526 | pick pour pick pour turnon pick in | cookies |
| Ideal | case8 | COFFEE | Place the cream cheese into the short cabinet, the chocolate pudding into the bowl, and pour a glass of wine. | 7 | 7 | 2283 | 123/326.1/573 | open pick in pick pour pick pour | black_book |
| Ideal | case9 | COFFEE | Place the chocolate pudding and cookies into a bowl and microwave it. | 11 | 11 | 3850 | 124/350.0/791 | pick in open pick in pick pour in pick pour in | butter |
| Ideal | case10 | COFFEE | Place the cookies into the basket, pour the tomato sauce and BBQ sauce into the frying pan, pour the wine into the red coffee mug, and place the white-yellow mug into the wooden tray. | 13 | 13 | 3710 | 106/285.4/505 | pick in pick pour in pick pour in pick pour in pick in | glazed_rim_porcelain_ramekin |
| Memory_Execution | case1 | COFFEE | After putting the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 8 | 7 | 2046 | 115/255.8/421 | pick on pick on pick in open | bbq_sauce |
| Memory_Execution | case2 | COFFEE | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 8 | 7 | 2030 | 105/253.8/436 | pick on pick on pick in open | bbq_sauce |
| Memory_Execution | case3 | COFFEE | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 10 | 9 | 2907 | 145/290.7/699 | pick on pick in pick on pick in open | bbq_sauce |
| Memory_Execution | case4 | KITCHEN | Pour the butter into the red coffee mug, then pick up the plate and store it on the top side of the wooden shelf, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 8 | 8 | 4352 | 134/541.0/1100 | pick pour in pick in pick in open | red_coffee_mug |
| Memory_Execution | case5 | COFFEE | Prepare a snack tray with chocolate pudding and wine in the plate, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 7 | 7 | 1684 | 167/240.6/410 | pick pour in pick pour in open | ketchup |
| Memory_Execution | case6 | COFFEE | Pour the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 12 | 12 | 3256 | 74/271.3/703 | pick in pick in pick pour in pick pour in open open | butter |
| Memory_Execution | case7 | COFFEE | Place the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 12 | 12 | 2944 | 66/245.3/628 | pick in open pick in pick pour in pick pour in open | butter |
| Memory_Execution | case8 | COFFEE | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. | 14 | 14 | 3143 | 68/224.5/499 | pick in pick in pick in pick pour in open pick pour in open | moka_pot |
| Memory_Execution | case9 | COFFEE | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. placing them on the table if found. | 14 | 14 | 3319 | 64/237.1/617 | pick in pick in pick in pick pour in open pick pour in open | moka_pot |
| Memory_Execution | case10 | COFFEE | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. | 14 | 14 | 5427 | 120/387.8/1017 | pick in pick in pick pour in open pick pour in open pick in | moka_pot |
| Memory_Exploration | case1 | KITCHEN | Find and pick the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate onto the top side of the wooden shelf. | 12 | 12 | 6881 | 56/573.5/1351 | open close open close open pick in pick in pick pour in | red_coffee_mug |
| Memory_Exploration | case2 | KITCHEN | Find and pick up the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate from the kitchen table onto the top side of the wooden shelf. | 10 | 10 | 4205 | 95/417.7/872 | open close open pick in pick in pick pour in | red_coffee_mug |
| Memory_Exploration | case3 | COFFEE | Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 12 | 12 | 2854 | 52/237.8/422 | open close open pick pour in pick in turnon pick pour in | macaroni_and_cheese |
| Memory_Exploration | case4 | COFFEE | Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 10 | 10 | 3020 | 102/301.8/612 | open pick pour in pick in turnon pick pour in | macaroni_and_cheese |
| Memory_Exploration | case5 | COFFEE | Find the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 14 | 14 | 4273 | 43/305.2/1107 | open close open close open pick pour in pick in turnon pick pour in | macaroni_and_cheese |
| Memory_Exploration | case6 | COFFEE | Find the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice. | 12 | 12 | 2788 | 104/232.3/436 | open close open pick pour in pick pour in pick pour in | black_book |
| Memory_Exploration | case7 | COFFEE | Take the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice. | 10 | 10 | 10117 | 645/1011.7/1385 | open pick pour in pick pour in pick pour in | black_book |
| Memory_Exploration | case8 | COFFEE | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 15 | 15 | 5124 | 71/341.7/1375 | open close open close open pick in pick in pick pour in pick pour in | butter |
| Memory_Exploration | case9 | COFFEE | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 13 | 13 | 4140 | 140/326.3/751 | open close open pick in pick in pick pour in pick pour in | butter |
| Memory_Exploration | case10 | COFFEE | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 11 | 11 | 4247 | 133/431.4/867 | open pick in pick in pick pour in pick pour in | butter |
| Mix | case1 | KITCHEN | Find and pick the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate onto the top side of the wooden shelf. | 12 | 12 | 6881 | 56/573.5/1351 | open close open close open pick in pick in pick pour in | red_coffee_mug |
| Mix | case2 | COFFEE | Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 10 | 10 | 3020 | 102/301.8/612 | open pick pour in pick in turnon pick pour in | macaroni_and_cheese |
| Mix | case3 | COFFEE | Find the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice. | 12 | 12 | 2788 | 104/232.3/436 | open close open pick pour in pick pour in pick pour in | black_book |
| Mix | case4 | COFFEE | Pour the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 12 | 12 | 3256 | 74/271.3/703 | pick in pick in pick pour in pick pour in open open | butter |
| Mix | case5 | COFFEE | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. | 14 | 14 | 5427 | 120/387.8/1017 | pick in pick in pick pour in open pick pour in open pick in | moka_pot |
| Mix | case6 | KITCHEN | Find and pick up the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate from the kitchen table onto the top side of the wooden shelf. | 10 | 10 | 4205 | 95/417.7/872 | open close open pick in pick in pick pour in | red_coffee_mug |
| Mix | case7 | COFFEE | After putting the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 8 | 7 | 2046 | 115/255.8/421 | pick on pick on pick in open | bbq_sauce |
| Mix | case8 | COFFEE | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 8 | 7 | 2030 | 105/253.8/436 | pick on pick on pick in open | bbq_sauce |
| Mix | case9 | COFFEE | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 10 | 9 | 2907 | 145/290.7/699 | pick on pick in pick on pick in open | bbq_sauce |
| Mix | case10 | COFFEE | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 13 | 13 | 4140 | 140/326.3/751 | open close open pick in pick in pick pour in pick pour in | butter |
| Observation_Mismatching | case1 | COFFEE | Organize all the food boxes into the white storage box. | 6 | 6 | 2554 | 242/425.7/490 | pick in pick in pick in | black_book |
| Observation_Mismatching | case2 | COFFEE | Place the cream cheese into the white storage box and place the frypan onto the rack | 4 | 4 | 2780 | 256/694.8/1363 | pick in pick on | moka_pot |
| Observation_Mismatching | case3 | COFFEE | Place the plates neatly between the knife and fork, and pour all the snacks and drinks into the plates. | 10 | 10 | 2273 | 127/227.3/430 | pick in pick pour in pick pour in pick pour | moka_pot |
| Observation_Mismatching | case4 | COFFEE | Clean up the desk by putting the two boxes in the bowl and place the frying pan onto the cabinet. | 6 | 6 | 1086 | 146/181.0/233 | pick pour pick pour pick in | moka_pot |
| Observation_Mismatching | case5 | COFFEE | Prepare a snack tray with chocolate pudding and wine in the plate. | 6 | 6 | 2284 | 145/380.7/797 | pick pour in pick pour in | ketchup |
| Observation_Mismatching | case6 | COFFEE | Place the butter into the short cabinet and pour the tomato sauce into the plate. | 6 | 6 | 2203 | 196/367.2/786 | open pick in pick pour in | chocolate_pudding |
| Observation_Mismatching | case7 | COFFEE | Place the boxes of chocolate pudding and butter into a bowl and heat the pan. | 7 | 7 | 2028 | 148/289.7/526 | pick pour pick pour turnon pick in | cookies |
| Observation_Mismatching | case8 | COFFEE | Place the cream cheese into the short cabinet, the chocolate pudding into the bowl, and pour a glass of wine. | 7 | 7 | 2283 | 123/326.1/573 | open pick in pick pour pick pour | black_book |
| Observation_Mismatching | case9 | COFFEE | Place the chocolate pudding and cookies into a bowl and microwave it. | 11 | 11 | 3850 | 124/350.0/791 | pick in open pick in pick pour in pick pour in | butter |
| Observation_Mismatching | case10 | COFFEE | Place the cookies into the basket, pour the tomato sauce and BBQ sauce into the frying pan, pour the wine into the red coffee mug, and place the white-yellow mug into the wooden tray. | 13 | 13 | 3710 | 106/285.4/505 | pick in pick pour in pick pour in pick pour in pick in | glazed_rim_porcelain_ramekin |
| Random_Disturbance | case1 | COFFEE | Organize all the food boxes into the white storage box. | 6 | 6 | 2554 | 242/425.7/490 | pick in pick in pick in | black_book |
| Random_Disturbance | case2 | COFFEE | Place the cream cheese into the white storage box and place the frypan onto the rack | 4 | 4 | 2780 | 256/694.8/1363 | pick in pick on | moka_pot |
| Random_Disturbance | case3 | COFFEE | Place the plates neatly between the knife and fork, and pour all the snacks and drinks into the plates. | 10 | 10 | 2273 | 127/227.3/430 | pick in pick pour in pick pour in pick pour | moka_pot |
| Random_Disturbance | case4 | COFFEE | Clean up the desk by putting the two boxes in the bowl and place the frying pan onto the cabinet. | 6 | 6 | 1086 | 146/181.0/233 | pick pour pick pour pick in | moka_pot |
| Random_Disturbance | case5 | COFFEE | Prepare a snack tray with chocolate pudding and wine in the plate. | 6 | 6 | 2284 | 145/380.7/797 | pick pour in pick pour in | ketchup |
| Random_Disturbance | case6 | COFFEE | Place the butter into the short cabinet and pour the tomato sauce into the plate. | 6 | 6 | 2203 | 196/367.2/786 | open pick in pick pour in | chocolate_pudding |
| Random_Disturbance | case7 | COFFEE | Place the boxes of chocolate pudding and butter into a bowl and heat the pan. | 7 | 7 | 2028 | 148/289.7/526 | pick pour pick pour turnon pick in | cookies |
| Random_Disturbance | case8 | COFFEE | Place the cream cheese into the short cabinet, the chocolate pudding into the bowl, and pour a glass of wine. | 7 | 7 | 2283 | 123/326.1/573 | open pick in pick pour pick pour | black_book |
| Random_Disturbance | case9 | COFFEE | Place the chocolate pudding and cookies into a bowl and microwave it. | 11 | 11 | 3850 | 124/350.0/791 | pick in open pick in pick pour in pick pour in | butter |
| Random_Disturbance | case10 | COFFEE | Place the cookies into the basket, pour the tomato sauce and BBQ sauce into the frying pan, pour the wine into the red coffee mug, and place the white-yellow mug into the wooden tray. | 13 | 13 | 3710 | 106/285.4/505 | pick in pick pour in pick pour in pick pour in pick in | glazed_rim_porcelain_ramekin |

## 各任务的子步描述

### Ideal/case1 — Organize all the food boxes into the white storage box.
1. Pick up cream cheese from coffee table
2. Place down cream cheese into white storage box placed at bottom side
3. Pick up popcorn from coffee table
4. Place down popcorn into white storage box placed at right side
5. Pick up butter from coffee table
6. Place down butter into white storage box placed at left side

### Ideal/case2 — Place the cream cheese into the white storage box and place the frypan onto the rack
1. Pick up the cream cheese from the coffee table.
2. Place the cream cheese into the white storage box at top side
3. Pick the frypan from the coffee table
4. Place the frypan onto the rack

### Ideal/case3 — Place the plates neatly between the knife and fork, and pour all the snacks and drinks into the plates.
1. Pick up the plate from coffee table
2. Place the plate on dining set group
3. Pick up the popcorn from dining set group
4. Place the popcorn on the plate
5. Place the popcorn on dining set group
6. Pick up the cookies from dining set group
7. Place the cookies on the plate
8. Place the cookies on the dining set group
9. Pick up the wine bottle from dining set group
10. Pour out the wine bottle onto the plate

### Ideal/case4 — Clean up the desk by putting the two boxes in the bowl and place the frying pan onto the cabinet.
1. Pick up cream cheese from coffee table
2. Place cream cheese into white bowl
3. Pick up popcorn from coffee table
4. Place popcorn into white bowl
5. Pick up frypan from coffee table
6. Place frypan on wooden cabinet top side

### Ideal/case5 — Prepare a snack tray with chocolate pudding and wine in the plate.
1. Pick up the chocolate pudding from wooden cabinet top side
2. Place the chocolate pudding on the plate
3. Place the chocolate pudding on the coffee table
4. Pick up the wine bottle from coffee table
5. Pour out wine from the wine bottle onto the plate
6. Place the wine bottle on the coffee table

### Ideal/case6 — Place the butter into the short cabinet and pour the tomato sauce into the plate.
1. Open the short cabinet in middle region
2. Pick up the butter from coffee table
3. Place down the butter into the short cabinet in middle region
4. Pick up the tomato sauce from coffee table
5. Pour out the tomato sauce onto the plate
6. Place the tomato sauce on the coffee table

### Ideal/case7 — Place the boxes of chocolate pudding and butter into a bowl and heat the pan.
1. Pick up chocolate pudding from coffee table
2. Place chocolate pudding into akita black bowl
3. Pick up butter from coffee table
4. Place butter into akita black bowl
5. Turn on flat stove in cook region
6. Pick up frypan from coffee table
7. Place frypan on flat stove in cook region

### Ideal/case8 — Place the cream cheese into the short cabinet, the chocolate pudding into the bowl, and pour a glass of wine.
1. Open the short cabinet middle region
2. Pick up the cream cheese from coffee table
3. Place down the cream cheese into short cabinet middle region
4. Pick up the chocolate pudding from coffee table
5. Place down the chocolate pudding into akita black bowl
6. Pick up the wine bottle from coffee table
7. Pour out the contents of wine bottle into white yellow mug

### Ideal/case9 — Place the chocolate pudding and cookies into a bowl and microwave it.
1. Pick up the white bowl from the wooden cabinet at top side
2. Place down the white bowl on the coffee table
3. Pick up the cookies from the coffee table
4. Place down the cookies into the white bowl
5. Place the cookies on the coffee table
6. Pick up the chocolate pudding from the coffee table
7. Place down the chocolate pudding into the white bowl
8. Place the chocolate pudding on the coffee table
9. Open the microwave
10. Pick up the white bowl from the coffee table
11. Place the white bowl into the microwave

### Ideal/case10 — Place the cookies into the basket, pour the tomato sauce and BBQ sauce into the frying pan, pour the wine into the red coffee mug, and place the white-yellow mug into the wooden tray.
1. Pick up the cookies from the coffee table
2. Place down the cookies into basket in contain region
3. Pick up the tomato sauce from coffee table
4. Pour out the tomato sauce onto frypan
5. Place the tomato sauce on the coffee table
6. Pick up the bbq sauce from the coffee table
7. Pour out the bbq sauce onto frypan
8. Place the bbq sauce sauce on the coffee table
9. Pick up the wine from coffee table
10. Pour out the wine from wine bottle into red coffee mug
11. Place down the wine onto coffee table
12. Pick up the white yellow mug from coffee table
13. Place down the white yellow mug into wooden tray in contain region

### Memory_Execution/case1 — After putting the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the butter from coffee table
2. Place the butter onto the rack
3. Pick up the red coffee mug from coffee table
4. Place the red coffee mug onto the rack
5. Pick up the milk from coffee table
6. Pour out the milk from the milk container
7. Place down the milk onto coffee table
8. Open the wooden cabinet top region

### Memory_Execution/case2 — After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the butter from coffee table
2. Place the butter onto the rack
3. Pick up the red coffee mug from coffee table
4. Place the red coffee mug onto the rack
5. Pick up the milk from coffee table
6. Pour out the milk from the milk container
7. Place down the milk onto coffee table
8. Open the wooden cabinet top region

### Memory_Execution/case3 — After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the butter from coffee table
2. Place the butter onto the rack
3. Pick up the red coffee mug from coffee table
4. Place the red coffee mug onto the rack
5. Pick up the milk from coffee table
6. Pour out the milk from the milk container
7. Place down the milk onto coffee table
8. Open the wooden cabinet top region
9. Pick up the butter from the wooden cabinet top region
10. Place the butter on the coffee table

### Memory_Execution/case4 — Pour the butter into the red coffee mug, then pick up the plate and store it on the top side of the wooden shelf, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the butter from the kitchen table
2. Pour the butter into the red coffee mug
3. Place butter on the kitchen table
4. Pick up the plate from the kitchen table
5. Place the plate into the wooden shelf top side
6. Open the wooden cabinet top region
7. Pick up the butter from the wooden cabinet top region
8. Place butter on the kitchen table

### Memory_Execution/case5 — Prepare a snack tray with chocolate pudding and wine in the plate, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the chocolate pudding from wooden cabinet
2. Place the chocolate pudding on the plate
3. Place the chocolate pudding on the coffee table
4. Pick up the wine bottle from coffee table
5. Pour out wine from the wine bottle onto the plate
6. Place the wine bottle on the coffee table
7. Open the wooden cabinet top region

### Memory_Execution/case6 — Pour the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the white bowl from the coffee table
2. Place down the white bowl on the coffee table
3. Pick up the cookies from the coffee table
4. Place down the cookies into the white bowl
5. Place the cookies on the coffee table
6. Pick up the chocolate pudding from the coffee table
7. Place down the chocolate pudding into the white bowl
8. Place the chocolate pudding on the coffee table
9. Open the microwave
10. Pick up the white bowl from the coffee table
11. Place the white bowl into the microwave
12. Open the top region of the wooden cabinet

### Memory_Execution/case7 — Place the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the white bowl from the coffee table
2. Place down the white bowl on the coffee table
3. Pick up the cookies from the coffee table
4. Place down the cookies into the white bowl
5. Place the cookies on the coffee table
6. Pick up the chocolate pudding from the coffee table
7. Place down the chocolate pudding into the white bowl
8. Put the chocolate pudding on the coffee table
9. Open the microwave
10. Pick up the white bowl from the coffee table
11. Place the white bowl into the microwave
12. Open the top region of the wooden cabinet

### Memory_Execution/case8 — Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the akita black bowl from coffee table.
2. Place the akita black bowl on table surface.
3. Pick up the popcorn from coffee table.
4. Place the popcorn on coffee table.
5. Pick up the alphabet soup from coffee table.
6. Pour out the alphabet soup into the akita black bowl.
7. Place the empty alphabet soup on table surface.
8. Open the microwave at top side.
9. Pick up the akita black bowl with soup from table surface.
10. Place the akita black bowl with soup into the microwave heating region.
11. Pick up the milk from its storage.
12. Pour out the milk into the white yellow mug.
13. Place the milk on table surface.
14. Open the top region of the white cabinet

### Memory_Execution/case9 — Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. placing them on the table if found.
1. Pick up the akita black bowl from coffee table.
2. Place the akita black bowl on table surface.
3. Pick up the popcorn from coffee table.
4. Place the popcorn on coffee table.
5. Pick up the alphabet soup from coffee table.
6. Pour out the alphabet soup into the akita black bowl.
7. Place the empty alphabet soup on table surface.
8. Open the microwave at top side.
9. Pick up the akita black bowl with soup from table surface.
10. Place the akita black bowl with soup into the microwave heating region.
11. Pick up the milk from its storage.
12. Pour out the milk into the white yellow mug.
13. Place the milk on table surface.
14. Open the top region of the white cabinet

### Memory_Execution/case10 — Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the akita black bowl from coffee table.
2. Place the akita black bowl on table surface.
3. Pick up the popcorn from coffee table.
4. Place the popcorn on coffee table.
5. Pick up the alphabet soup from coffee table.
6. Pour out the alphabet soup into the akita black bowl.
7. Place the empty alphabet soup on table surface.
8. Open the microwave.
9. Pick up the milk from its storage.
10. Pour out the milk into the white yellow mug.
11. Place the milk on table surface.
12. Open the top region of the white cabinet
13. Pick up the popcorn from coffee table.
14. Place the popcorn on coffee table.

### Memory_Exploration/case1 — Find and pick the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate onto the top side of the wooden shelf.
1. Open the wooden cabinet top region
2. Close the wooden cabinet top region
3. Open the wooden cabinet middle region
4. Close the wooden cabinet middle region
5. Open the wooden cabinet bottom region
6. Pick up the butter from the wooden cabinet bottom region
7. Place the butter on the kitchen table
8. Pick up the cream cheese from the kitchen table
9. Pour the cream cheese into the red coffee mug
10. Place cream cheese on the kitchen table
11. Pick up the plate from the kitchen table
12. Place the plate into the wooden shelf top side

### Memory_Exploration/case2 — Find and pick up the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate from the kitchen table onto the top side of the wooden shelf.
1. Open the wooden cabinet top region
2. Close the wooden cabinet top region
3. Open the wooden cabinet middle region
4. Pick up the butter from the wooden cabinet middle region
5. Place the butter on the kitchen table
6. Pick up the cream cheese from the kitchen table
7. Pour the cream cheese into the red coffee mug
8. Place cream cheese on the kitchen table
9. Pick up the plate from the kitchen table
10. Place the plate on the wooden shelf top side

### Memory_Exploration/case3 — Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug.
1. Open the wooden cabinet top region.
2. Close the wooden cabinet top region.
3. Open the wooden cabinet middle region.
4. Pick up the frypan pan from the coffee table
5. Place frypan on flat stove cook region.
6. Pick up butter from wooden cabinet.
7. Place butter into frypan.
8. Put butter on the coffee table
9. Turn on the flat stove cook region.
10. Pick up wine bottle from coffee table.
11. Pour wine from wine bottle into white yellow mug.
12. Place the wine bottle on the coffee table

### Memory_Exploration/case4 — Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug.
1. Open the wooden cabinet top region.
2. Pick up the frypan on the table.
3. Place frypan on flat stove cook region.
4. Pick up butter from wooden cabinet.
5. Place butter into frypan.
6. Put the butter on the coffee table.
7. Turn on the flat stove cook region.
8. Pick up wine bottle from coffee table.
9. Pour wine from wine bottle into white yellow mug.
10. Place the wine bottle on the coffee table

### Memory_Exploration/case5 — Find the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug.
1. Open the wooden cabinet top region.
2. Close the wooden cabinet top region.
3. Open the wooden cabinet middle region.
4. Close the wooden cabinet middle region.
5. Open the wooden cabinet bottom region.
6. Pick up frypan from coffee table.
7. Place frypan on flat stove cook region.
8. Pick up butter from wooden cabinet.
9. Place butter into frypan.
10. Put the butter on the coffee table.
11. Turn on the flat stove cook region.
12. Pick up wine bottle from coffee table.
13. Pour wine from wine bottle into white yellow mug.
14. Place the wine bottle on the coffee table

### Memory_Exploration/case6 — Find the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice.
1. Open the white cabinet top region
2. Close the white cabinet top region
3. Open the white cabinet middle region
4. Pick up the butter from the white cabinet
5. Pour the butter into the frypan
6. Place the butter on the coffee table.
7. Pick up the bbq sauce from the coffee table
8. Pour the bbq sauce into the frypan
9. Place the barbecue sauce on the coffee table.
10. Pick up the orange juice from the coffee table
11. Pour the orange juice into the red coffee mug
12. Place the orange juice back on the coffee table.

### Memory_Exploration/case7 — Take the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice.
1. Open the white cabinet top region
2. Pick up the butter from the white cabinet
3. Pour the butter into the frypan
4. Place the butter on the coffee table.
5. Pick up the bbq sauce from the coffee table
6. Pour the bbq sauce into the frypan
7. Place the barbecue sauce on the coffee table.
8. Pick up the orange juice from the coffee table
9. Pour the orange juice into the red coffee mug
10. Place the orange juice back on the coffee table.

### Memory_Exploration/case8 — Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet.
1. Open the wooden cabinet top region.
2. Close the wooden cabinet top region.
3. Open the wooden cabinet middle region.
4. Close the wooden cabinet middle region.
5. Open the wooden cabinet bottom region.
6. Pick up the white bowl from the wooden cabinet
7. Place down the white bowl on the coffee table
8. Pick up the cookies from the coffee table
9. Place down the cookies into the white bowl
10. Place the cookies on the coffee table
11. Pick up the chocolate pudding from the coffee table
12. Pour the chocolate pudding into the white bowl
13. Place the chocolate pudding on the coffee table
14. Pick up the white bowl from the coffee table
15. Place the white bowl onto the wooden cabinet at top side

### Memory_Exploration/case9 — Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet.
1. Open the wooden cabinet top region.
2. Close the wooden cabinet top region.
3. Open the wooden cabinet middle region.
4. Pick up the white bowl from the wooden cabinet
5. Place down the white bowl on the coffee table
6. Pick up the cookies from the coffee table
7. Place down the cookies into the white bowl
8. Place the cookies on the coffee table
9. Pick up the chocolate pudding from the coffee table
10. Place down the chocolate pudding into the white bowl
11. Place the chocolate pudding on the coffee table
12. Pick up the white bowl from the coffee table
13. Place the white bowl into the wooden cabinet at top side

### Memory_Exploration/case10 — Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet.
1. Open the wooden cabinet top region.
2. Pick up the white bowl from the wooden cabinet
3. Place down the white bowl on the coffee table
4. Pick up the cookies from the coffee table
5. Place down the cookies into the white bowl
6. Place the cookies on the coffee table
7. Pick up the chocolate pudding from the coffee table
8. Place down the chocolate pudding into the white bowl
9. Place the  chocolate pudding  on the coffee table
10. Pick up the white bowl from the coffee table
11. Place the white bowl onto the top side of wooden cabinet

### Mix/case1 — Find and pick the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate onto the top side of the wooden shelf.
1. Open the wooden cabinet top region
2. Close the wooden cabinet top region
3. Open the wooden cabinet middle region
4. Close the wooden cabinet middle region
5. Open the wooden cabinet bottom region
6. Pick up the butter from the wooden cabinet bottom region
7. Place the butter on the kitchen table
8. Pick up the cream cheese from the kitchen table
9. Pour the cream cheese into the red coffee mug
10. Place cream cheese on the kitchen table
11. Pick up the plate from the kitchen table
12. Place the plate into the wooden shelf top side

### Mix/case2 — Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug.
1. Open the wooden cabinet top region.
2. Pick up frypan from the table.
3. Place frypan on flat stove cook region.
4. Pick up butter from wooden cabinet.
5. Place butter into frypan.
6. Put the butter on the coffee table.
7. Turn on the flat stove cook region.
8. Pick up wine bottle from coffee table.
9. Pour wine from wine bottle into white yellow mug.
10. Place the wine bottle on the coffee table

### Mix/case3 — Find the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice.
1. Open the white cabinet top region
2. Close the white cabinet top region
3. Open the white cabinet middle region
4. Pick up the butter from the white cabinet
5. Pour the butter into the frypan
6. Place the butter on the coffee table.
7. Pick up the bbq sauce from the coffee table
8. Pour the bbq sauce into the frypan
9. Place the barbecue sauce on the coffee table.
10. Pick up the orange juice from the coffee table
11. Pour the orange juice into the red coffee mug
12. Place the orange juice back on the coffee table.

### Mix/case4 — Pour the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the white bowl from the coffee table
2. Place down the white bowl on the coffee table
3. Pick up the cookies from the coffee table
4. Place down the cookies into the white bowl
5. Place the cookies on the coffee table
6. Pick up the chocolate pudding from the coffee table
7. Place down the chocolate pudding into the white bowl
8. Place the chocolate pudding on the coffee table
9. Open the microwave
10. Pick up the white bowl from the coffee table
11. Place the white bowl into the microwave
12. Open the top region of the wooden cabinet

### Mix/case5 — Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the akita black bowl from coffee table.
2. Place the akita black bowl on table surface.
3. Pick up the popcorn from coffee table.
4. Place the popcorn on coffee table.
5. Pick up the alphabet soup from coffee table.
6. Pour out the alphabet soup into the akita black bowl.
7. Place the empty alphabet soup on table surface.
8. Open the microwave.
9. Pick up the milk from its storage.
10. Pour out the milk into the white yellow mug.
11. Place the milk on table surface.
12. Open the top region of the white cabinet
13. Pick up the popcorn from coffee table.
14. Place the popcorn on coffee table.

### Mix/case6 — Find and pick up the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate from the kitchen table onto the top side of the wooden shelf.
1. Open the wooden cabinet top region
2. Close the wooden cabinet top region
3. Open the wooden cabinet middle region
4. Pick up the butter from the wooden cabinet middle region
5. Place the butter on the kitchen table
6. Pick up the cream cheese from the kitchen table
7. Pour the cream cheese into the red coffee mug
8. Place cream cheese on the kitchen table
9. Pick up the plate from the kitchen table
10. Place the plate on the wooden shelf top side

### Mix/case7 — After putting the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the butter from coffee table
2. Place the butter onto the rack
3. Pick up the red coffee mug from coffee table
4. Place the red coffee mug onto the rack
5. Pick up the milk from coffee table
6. Pour out the milk from the milk container
7. Place down the milk onto coffee table
8. Open the wooden cabinet top region

### Mix/case8 — After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the butter from coffee table
2. Place the butter onto the rack
3. Pick up the red coffee mug from coffee table
4. Place the red coffee mug onto the rack
5. Pick up the milk from coffee table
6. Pour out the milk from the milk container
7. Place down the milk onto coffee table
8. Open the wooden cabinet top region

### Mix/case9 — After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found.
1. Pick up the butter from coffee table
2. Place the butter onto the rack
3. Pick up the red coffee mug from coffee table
4. Place the red coffee mug onto the rack
5. Pick up the milk from coffee table
6. Pour out the milk from the milk container
7. Place down the milk onto coffee table
8. Open the wooden cabinet top region
9. Pick up the butter from the wooden cabinet top region
10. Place the butter on the coffee table

### Mix/case10 — Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet.
1. Open the wooden cabinet top region.
2. Close the wooden cabinet top region.
3. Open the wooden cabinet middle region.
4. Pick up the white bowl from the wooden cabinet
5. Place down the white bowl on the coffee table
6. Pick up the cookies from the coffee table
7. Place down the cookies into the white bowl
8. Place the cookies on the coffee table
9. Pick up the chocolate pudding from the coffee table
10. Place down the chocolate pudding into the white bowl
11. Place the chocolate pudding on the coffee table
12. Pick up the white bowl from the coffee table
13. Place the white bowl into the wooden cabinet at top side
