# Observed-facts guide

- elapsed: 14400.873 s
- maps: [1, 2, 6, 494, 495, 607]
- transitions: 32
- battles completed: 20
- deaths: 2
- checkpoint recoveries: 2

## Observed transitions
- t=479.064s map 2 [8, 0] -> map 6 [10, 9]
- t=480.661s map 6 None -> map 2 [8, 0]
- t=488.229s map 2 [8, 14] -> map 1 [76, 76]
- t=490.695s map 1 None -> map 2 [8, 11]
- t=493.052s map 2 None -> map 1 [76, 76]
- t=501.085s map 1 [85, 73] -> map 607 [1, 4]
- t=530.377s map 607 [10, 12] -> map 1 [85, 74]
- t=592.173s map 2 [9, 14] -> map 1 [76, 76]
- t=600.285s map 1 [85, 73] -> map 607 [1, 4]
- t=619.61s map 607 [0, 4] -> map 1 [84, 73]
- t=677.005s map 1 [76, 75] -> map 2 [8, 11]
- t=683.339s map 2 None -> map 6 [10, 9]
- t=869.728s map 2 None -> map 1 [76, 76]
- t=877.962s map 1 [85, 73] -> map 607 [1, 4]
- t=889.068s map 607 [10, 12] -> map 1 [85, 74]
- t=920.225s map 1 [76, 75] -> map 2 [8, 11]
- t=926.497s map 2 None -> map 6 [10, 9]
- t=1001.763s map 6 None -> map 2 [8, 0]
- t=1043.998s map 2 None -> map 1 [76, 76]
- t=1071.515s map 6 [10, 9] -> map 2 [8, 0]
- t=1078.87s map 2 [8, 14] -> map 1 [76, 76]
- t=1087.011s map 1 [85, 73] -> map 607 [1, 4]
- t=1090.629s map 607 [0, 4] -> map 1 [84, 73]
- t=1253.565s map 1 [76, 75] -> map 2 [8, 11]
- t=1259.822s map 2 None -> map 6 [10, 9]
- t=1268.411s map 6 [10, 9] -> map 2 [8, 0]
- t=1275.779s map 2 [8, 14] -> map 1 [76, 76]
- t=1283.996s map 1 [85, 73] -> map 607 [1, 4]
- t=1376.213s map 607 [0, 3] -> map 1 [84, 73]
- t=1409.795s map 1 [81, 67] -> map 494 [17, 18]
- t=1413.941s map 494 [17, 15] -> map 495 [33, 12]
- t=1415.447s map 495 None -> map 494 [17, 16]

## Observed deaths/recoveries
- party_member_casualty t=586.063s fallen=Kappa recovery=checkpoint_load_after_party_casualty battle_strategy->1
- death #1 t=862.001s recovery=checkpoint_load battle_strategy->2
- party_member_casualty t=994.895s fallen=Vargas recovery=checkpoint_load_after_party_casualty battle_strategy->3
- death #2 t=1068.084s recovery=checkpoint_load battle_strategy->3
- party_member_casualty t=1193.784s fallen=Vargas recovery=checkpoint_load_after_party_casualty battle_strategy->3
- party_member_casualty t=1218.153s fallen=Kappa recovery=checkpoint_load_after_party_casualty battle_strategy->3

## Learned avoidance heuristic
- event 6/2/0 risk=37
- event 1/134/0 risk=16
- event 1/3/0 risk=10
- event 2/14/0 risk=4
- event 1/69/0 risk=4
