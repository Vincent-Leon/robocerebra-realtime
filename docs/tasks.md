# Public tasks (v0.1)

60 tasks in 6 categories. *Subgoals*: scored subgoals (excluding those completed at the start under Observation Mismatch). *Reference*: the scripted executor following the demonstration plan, no language model.

## Ideal

| Task | Instruction | Subgoals | Reference |
|---|---|---|---|
| case1 | Organize all the food boxes into the white storage box. | 6 | 1.00 |
| case2 | Place the cream cheese into the white storage box and place the frypan onto the rack | 4 | 0.50 |
| case3 | Place the plates neatly between the knife and fork, and pour all the snacks and drinks into the plates. | 10 | 0.80 |
| case4 | Clean up the desk by putting the two boxes in the bowl and place the frying pan onto the cabinet. | 6 | 0.67 |
| case5 | Prepare a snack tray with chocolate pudding and wine in the plate. | 6 | 1.00 |
| case6 | Place the butter into the short cabinet and pour the tomato sauce into the plate. | 6 | 1.00 |
| case7 | Place the boxes of chocolate pudding and butter into a bowl and heat the pan. | 7 | 0.86 |
| case8 | Place the cream cheese into the short cabinet, the chocolate pudding into the bowl, and pour a glass of wine. | 7 | 1.00 |
| case9 | Place the chocolate pudding and cookies into a bowl and microwave it. | 11 | 0.18 |
| case10 | Place the cookies into the basket, pour the tomato sauce and BBQ sauce into the frying pan, pour the wine into the red coffee mug, and place the white-yellow mug into the wooden tray. | 13 | 0.85 |

## Memory · Execution

| Task | Instruction | Subgoals | Reference |
|---|---|---|---|
| case1 | After putting the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 7 | 0.86 |
| case2 | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 7 | 1.00 |
| case3 | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 9 | 0.89 |
| case4 | Pour the butter into the red coffee mug, then pick up the plate and store it on the top side of the wooden shelf, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 8 | 0.38 |
| case5 | Prepare a snack tray with chocolate pudding and wine in the plate, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 7 | 1.00 |
| case6 | Pour the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 12 | 0.67 |
| case7 | Place the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 12 | 0.75 |
| case8 | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. | 14 | 0.93 |
| case9 | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. placing them on the table if found. | 14 | 0.93 |
| case10 | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. | 14 | 0.93 |

## Memory · Exploration

| Task | Instruction | Subgoals | Reference |
|---|---|---|---|
| case1 | Find and pick the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate onto the top side of the wooden shelf. | 12 | 0.58 |
| case2 | Find and pick up the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate from the kitchen table onto the top side of the wooden shelf. | 10 | 0.50 |
| case3 | Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 12 | 0.92 |
| case4 | Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 10 | 1.00 |
| case5 | Find the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 14 | 0.93 |
| case6 | Find the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice. | 12 | 1.00 |
| case7 | Take the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice. | 10 | 1.00 |
| case8 | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 15 | 1.00 |
| case9 | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 13 | 1.00 |
| case10 | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 11 | 1.00 |

## Mix

| Task | Instruction | Subgoals | Reference |
|---|---|---|---|
| case1 | Find and pick the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate onto the top side of the wooden shelf. | 11 | 0.55 |
| case2 | Take the butter from the wooden cabinet, melt it in a Chefmate frypan, and serve wine in a white-and-yellow mug. | 9 | 0.89 |
| case3 | Find the butter from the white cabinet, pour it and the barbecue sauce into the frying pan, and prepare a mug of orange juice. | 11 | 1.00 |
| case4 | Pour the chocolate pudding and cookies into a bowl and microwave it,and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 11 | 0.73 |
| case5 | Heat the alphabet soup in a bowl using the microwave，pour a cup of milk into a mug,reposition the popcorn and check the white cabinet top region for any previously handled objects, placing them on the table if found. | 13 | 0.46 |
| case6 | Find and pick up the butter from the wooden cabinet, pour the cream cheese from the kitchen table into the red coffee mug, and put the plate from the kitchen table onto the top side of the wooden shelf. | 9 | 0.44 |
| case7 | After putting the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 6 | 0.83 |
| case8 | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 6 | 1.00 |
| case9 | After placing the butter and mug on the rack, pour in the milk, and check the wooden cabinet top region for any previously handled objects, placing them on the table if found. | 8 | 1.00 |
| case10 | Take the white bowl from the wooden cabinet, pour in the chocolate pudding and cookies, and put it on top of the wooden cabinet. | 12 | 0.92 |

## Observation Mismatch

| Task | Instruction | Subgoals | Reference |
|---|---|---|---|
| case1 | Organize all the food boxes into the white storage box. | 5 | 1.00 |
| case2 | Place the cream cheese into the white storage box and place the frypan onto the rack | 3 | 0.33 |
| case3 | Place the plates neatly between the knife and fork, and pour all the snacks and drinks into the plates. | 9 | 0.78 |
| case4 | Clean up the desk by putting the two boxes in the bowl and place the frying pan onto the cabinet. | 5 | 0.80 |
| case5 | Prepare a snack tray with chocolate pudding and wine in the plate. | 5 | 1.00 |
| case6 | Place the butter into the short cabinet and pour the tomato sauce into the plate. | 5 | 1.00 |
| case7 | Place the boxes of chocolate pudding and butter into a bowl and heat the pan. | 6 | 0.83 |
| case8 | Place the cream cheese into the short cabinet, the chocolate pudding into the bowl, and pour a glass of wine. | 6 | 1.00 |
| case9 | Place the chocolate pudding and cookies into a bowl and microwave it. | 10 | 0.70 |
| case10 | Place the cookies into the basket, pour the tomato sauce and BBQ sauce into the frying pan, pour the wine into the red coffee mug, and place the white-yellow mug into the wooden tray. | 12 | 0.83 |

## Random Disturbance

| Task | Instruction | Subgoals | Reference |
|---|---|---|---|
| case1 | Organize all the food boxes into the white storage box. | 6 | 1.00 |
| case2 | Place the cream cheese into the white storage box and place the frypan onto the rack | 4 | 0.50 |
| case3 | Place the plates neatly between the knife and fork, and pour all the snacks and drinks into the plates. | 10 | 1.00 |
| case4 | Clean up the desk by putting the two boxes in the bowl and place the frying pan onto the cabinet. | 6 | 0.83 |
| case5 | Prepare a snack tray with chocolate pudding and wine in the plate. | 6 | 1.00 |
| case6 | Place the butter into the short cabinet and pour the tomato sauce into the plate. | 6 | 1.00 |
| case7 | Place the boxes of chocolate pudding and butter into a bowl and heat the pan. | 7 | 0.86 |
| case8 | Place the cream cheese into the short cabinet, the chocolate pudding into the bowl, and pour a glass of wine. | 7 | 1.00 |
| case9 | Place the chocolate pudding and cookies into a bowl and microwave it. | 11 | 0.18 |
| case10 | Place the cookies into the basket, pour the tomato sauce and BBQ sauce into the frying pan, pour the wine into the red coffee mug, and place the white-yellow mug into the wooden tray. | 13 | 0.92 |

