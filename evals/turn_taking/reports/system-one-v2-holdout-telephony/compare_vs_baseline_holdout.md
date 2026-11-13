# Paired comparison: A=`baseline-holdout-telephony` (baseline) vs B=`system-one-v2-holdout-telephony`

Diff = B - A. CI: paired percentile bootstrap (10k, seed 0). p: see test column. Uncorrected for multiple comparisons.

## Warnings

- v1.5/background_speech: dropped 0 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/talking_to_other: dropped 0 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_backchannel: dropped 0 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_interruption: dropped 2 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only

## v1.5/background_speech

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 10 | 1.0000 | 0.3000 | -0.7000 | [-1.0000, -0.4000] | McNemar exact (b=0, c=7) | 0.0156 |
| behavior_C_RESUME | 10 | 0.0000 | 0.2000 | +0.2000 | [+0.0000, +0.5000] | McNemar exact (b=2, c=0) | 0.5000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.0000 | 0.1000 | +0.1000 | [+0.0000, +0.3000] | McNemar exact (b=1, c=0) | 1.0000 |
| behavior_C_UNKNOWN | 10 | 0.0000 | 0.4000 | +0.4000 | [+0.1000, +0.7000] | McNemar exact (b=4, c=0) | 0.1250 |
| clean_mean_intensity | 10 | 59.9022 | 59.3720 | -0.5302 | [-1.4786, +0.2454] | Wilcoxon signed-rank | 0.5566 |
| clean_mean_pitch | 10 | 200.4912 | 197.8222 | -2.6690 | [-7.0037, +2.4283] | Wilcoxon signed-rank | 0.3223 |
| clean_speech_dur_s | 10 | 5.6000 | 5.4400 | -0.1600 | [-0.3440, +0.0640] | Wilcoxon signed-rank | 0.1309 |
| clean_std_intensity | 10 | 14.4564 | 15.0077 | +0.5513 | [-0.1247, +1.3480] | Wilcoxon signed-rank | 0.2754 |
| clean_std_pitch | 10 | 44.9427 | 46.2526 | +1.3099 | [-6.0901, +7.9885] | Wilcoxon signed-rank | 0.6953 |
| clean_utmosv2 | 10 | 2.0764 | 2.0915 | +0.0151 | [-0.1278, +0.1543] | Wilcoxon signed-rank | 1.0000 |
| clean_wpm | 10 | 149.1590 | 152.9580 | +3.7990 | [-6.5018, +11.7542] | Wilcoxon signed-rank | 0.1602 |
| n_resp_intervals | 10 | 2.0000 | 1.5000 | -0.5000 | [-0.8000, -0.2000] | n/a (<6 non-zero pairs) | - |
| n_stop_intervals | 10 | 0.6000 | 1.0000 | +0.4000 | [+0.1000, +0.7000] | McNemar exact (b=4, c=0) | 0.1250 |
| post_mean_intensity | 10 | 60.0672 | 23.2981 | -36.7691 | [-89.4573, -2.6801] | Wilcoxon signed-rank | 0.0137 |
| post_mean_pitch | 10 | 210.4810 | 175.3761 | -35.1049 | [-98.5613, +27.1503] | Wilcoxon signed-rank | 0.2324 |
| post_speech_dur_s | 10 | 3.2880 | 2.2080 | -1.0800 | [-2.0560, -0.0320] | Wilcoxon signed-rank | 0.1309 |
| post_std_intensity | 10 | 15.5097 | 12.7905 | -2.7192 | [-6.2936, +0.0149] | Wilcoxon signed-rank | 0.1602 |
| post_std_pitch | 10 | 47.9877 | 32.5532 | -15.4345 | [-29.7339, -1.2879] | Wilcoxon signed-rank | 0.1309 |
| post_utmosv2 | 10 | 2.0454 | 1.6008 | -0.4446 | [-0.8268, -0.1280] | Wilcoxon signed-rank | 0.0098 |
| post_wpm | 10 | 221.0962 | 256.9776 | +35.8814 | [-110.4028, +252.2477] | Wilcoxon signed-rank | 0.7695 |
| pre_mean_intensity | 10 | 60.8979 | 61.0928 | +0.1949 | [-0.8716, +1.4944] | Wilcoxon signed-rank | 1.0000 |
| pre_mean_pitch | 10 | 204.1405 | 199.1706 | -4.9699 | [-10.6482, +0.4235] | Wilcoxon signed-rank | 0.1309 |
| pre_speech_dur_s | 10 | 2.7840 | 2.9200 | +0.1360 | [-0.0960, +0.3680] | Wilcoxon signed-rank | 0.1953 |
| pre_std_intensity | 10 | 14.1496 | 13.8403 | -0.3093 | [-1.4252, +0.5374] | Wilcoxon signed-rank | 0.7695 |
| pre_std_pitch | 10 | 45.9089 | 38.3390 | -7.5698 | [-14.8859, -0.6289] | Wilcoxon signed-rank | 0.1309 |
| pre_utmosv2 | 10 | 2.0713 | 1.9544 | -0.1169 | [-0.2019, -0.0214] | Wilcoxon signed-rank | 0.0645 |
| pre_wpm | 10 | 149.2870 | 141.3750 | -7.9121 | [-15.6581, -1.2939] | Wilcoxon signed-rank | 0.0977 |
| resp_latency | 10 | 1.8296 | 2.6776 | +0.8480 | [+0.5344, +1.1552] | Wilcoxon signed-rank | 0.0039 |
| stop_latency | 6 | 0.4653 | 1.2707 | +0.8053 | [+0.4480, +1.1307] | Wilcoxon signed-rank | 0.0312 |

## v1.5/talking_to_other

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 10 | 0.9000 | 0.2000 | -0.7000 | [-1.0000, -0.4000] | McNemar exact (b=0, c=7) | 0.0156 |
| behavior_C_RESUME | 10 | 0.0000 | 0.5000 | +0.5000 | [+0.2000, +0.8000] | McNemar exact (b=5, c=0) | 0.0625 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.1000 | 0.0000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 10 | 0.0000 | 0.3000 | +0.3000 | [+0.0000, +0.6000] | McNemar exact (b=3, c=0) | 0.2500 |
| clean_mean_intensity | 10 | 60.0616 | 59.4265 | -0.6351 | [-1.2508, -0.1202] | Wilcoxon signed-rank | 0.0488 |
| clean_mean_pitch | 10 | 198.8042 | 198.6234 | -0.1808 | [-2.9995, +2.8244] | Wilcoxon signed-rank | 0.8457 |
| clean_speech_dur_s | 10 | 7.1920 | 7.0160 | -0.1760 | [-0.3360, -0.0160] | Wilcoxon signed-rank | 0.0820 |
| clean_std_intensity | 10 | 14.6080 | 15.0719 | +0.4639 | [-0.0722, +1.2528] | Wilcoxon signed-rank | 0.2754 |
| clean_std_pitch | 10 | 38.8058 | 40.0174 | +1.2116 | [-3.1654, +5.9531] | Wilcoxon signed-rank | 0.9219 |
| clean_utmosv2 | 10 | 2.0602 | 2.0311 | -0.0291 | [-0.1849, +0.1265] | Wilcoxon signed-rank | 0.7695 |
| clean_wpm | 10 | 161.0712 | 160.6611 | -0.4101 | [-8.8426, +7.4182] | Wilcoxon signed-rank | 0.9219 |
| n_resp_intervals | 10 | 2.0000 | 1.3000 | -0.7000 | [-1.0000, -0.4000] | Wilcoxon signed-rank | 0.0156 |
| n_stop_intervals | 10 | 0.9000 | 1.1000 | +0.2000 | [+0.0000, +0.5000] | n/a (<6 non-zero pairs) | - |
| post_mean_intensity | 10 | 61.5588 | 49.1441 | -12.4147 | [-26.3264, -1.7713] | Wilcoxon signed-rank | 0.0371 |
| post_mean_pitch | 10 | 202.8392 | 156.1766 | -46.6627 | [-100.7687, -6.2986] | Wilcoxon signed-rank | 0.0195 |
| post_speech_dur_s | 10 | 3.2480 | 3.2560 | +0.0080 | [-1.2320, +1.1440] | Wilcoxon signed-rank | 0.9434 |
| post_std_intensity | 10 | 14.1145 | 14.3109 | +0.1964 | [-1.9957, +2.1333] | Wilcoxon signed-rank | 0.6953 |
| post_std_pitch | 10 | 41.0150 | 24.7012 | -16.3138 | [-28.3222, -2.1705] | Wilcoxon signed-rank | 0.0645 |
| post_utmosv2 | 10 | 2.1355 | 1.6905 | -0.4450 | [-0.7042, -0.2314] | Wilcoxon signed-rank | 0.0020 |
| post_wpm | 10 | 253.5398 | 117.1635 | -136.3764 | [-181.5414, -91.6256] | Wilcoxon signed-rank | 0.0020 |
| pre_mean_intensity | 10 | 60.8314 | 60.3663 | -0.4650 | [-1.1711, +0.1877] | Wilcoxon signed-rank | 0.1934 |
| pre_mean_pitch | 10 | 204.5028 | 201.3551 | -3.1476 | [-9.3906, +3.2919] | Wilcoxon signed-rank | 0.3750 |
| pre_speech_dur_s | 10 | 2.8880 | 3.5920 | +0.7040 | [+0.3600, +1.0080] | Wilcoxon signed-rank | 0.0117 |
| pre_std_intensity | 10 | 13.9542 | 14.1103 | +0.1561 | [-0.5773, +0.9602] | Wilcoxon signed-rank | 0.9219 |
| pre_std_pitch | 10 | 39.2369 | 38.0091 | -1.2278 | [-7.7479, +5.7115] | Wilcoxon signed-rank | 0.8457 |
| pre_utmosv2 | 10 | 1.8633 | 1.9653 | +0.1020 | [-0.0730, +0.2455] | Wilcoxon signed-rank | 0.0840 |
| pre_wpm | 10 | 171.1589 | 169.4704 | -1.6885 | [-15.0144, +12.6900] | Wilcoxon signed-rank | 0.8457 |
| resp_latency | 10 | 1.7608 | 2.3608 | +0.6000 | [+0.4288, +0.7712] | Wilcoxon signed-rank | 0.0020 |
| stop_latency | 9 | 0.3764 | 1.7364 | +1.3600 | [+0.8782, +1.8098] | Wilcoxon signed-rank | 0.0039 |

## v1.5/user_backchannel

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 10 | 0.2000 | 0.0000 | -0.2000 | [-0.5000, +0.0000] | McNemar exact (b=0, c=2) | 0.5000 |
| behavior_C_RESUME | 10 | 0.2000 | 0.4000 | +0.2000 | [-0.2000, +0.6000] | McNemar exact (b=3, c=1) | 0.6250 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.1000 | 0.0000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 10 | 0.5000 | 0.6000 | +0.1000 | [-0.2000, +0.4000] | McNemar exact (b=2, c=1) | 1.0000 |
| clean_mean_intensity | 10 | 59.8345 | 59.8448 | +0.0103 | [-0.3163, +0.3328] | Wilcoxon signed-rank | 1.0000 |
| clean_mean_pitch | 10 | 203.4570 | 202.5345 | -0.9225 | [-4.9996, +2.9423] | Wilcoxon signed-rank | 0.7695 |
| clean_speech_dur_s | 10 | 8.3520 | 7.7280 | -0.6240 | [-0.9520, -0.3360] | Wilcoxon signed-rank | 0.0039 |
| clean_std_intensity | 10 | 14.8346 | 14.7720 | -0.0626 | [-0.4603, +0.3040] | Wilcoxon signed-rank | 0.6953 |
| clean_std_pitch | 10 | 40.2497 | 40.5457 | +0.2960 | [-3.9180, +4.6942] | Wilcoxon signed-rank | 0.9219 |
| clean_utmosv2 | 10 | 2.1186 | 2.2163 | +0.0977 | [-0.0824, +0.2688] | Wilcoxon signed-rank | 0.4922 |
| clean_wpm | 10 | 177.1303 | 176.2937 | -0.8366 | [-9.5543, +8.9015] | Wilcoxon signed-rank | 0.7344 |
| n_resp_intervals | 10 | 1.9000 | 1.1000 | -0.8000 | [-1.0000, -0.4000] | Wilcoxon signed-rank | 0.0215 |
| n_stop_intervals | 10 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 10 | 34.8196 | 59.0447 | +24.2251 | [-2.7428, +76.5002] | Wilcoxon signed-rank | 0.3223 |
| post_mean_pitch | 10 | 185.0393 | 200.7184 | +15.6790 | [-10.2469, +58.4990] | Wilcoxon signed-rank | 0.7695 |
| post_speech_dur_s | 10 | 2.1360 | 4.9600 | +2.8240 | [+1.9280, +3.7840] | Wilcoxon signed-rank | 0.0020 |
| post_std_intensity | 10 | 13.4672 | 15.7311 | +2.2638 | [-0.0377, +5.9085] | Wilcoxon signed-rank | 0.2754 |
| post_std_pitch | 10 | 40.7370 | 35.7626 | -4.9744 | [-16.9934, +7.5887] | Wilcoxon signed-rank | 0.3750 |
| post_utmosv2 | 10 | 1.8319 | 2.1555 | +0.3236 | [+0.0374, +0.6708] | Wilcoxon signed-rank | 0.0371 |
| post_wpm | 10 | 156.0413 | 196.9232 | +40.8819 | [-26.6446, +114.3370] | Wilcoxon signed-rank | 0.5566 |
| pre_mean_intensity | 10 | 61.6479 | 35.1444 | -26.5035 | [-78.8174, +0.4864] | Wilcoxon signed-rank | 0.4316 |
| pre_mean_pitch | 10 | 204.2179 | 185.3308 | -18.8872 | [-61.7765, +4.9648] | Wilcoxon signed-rank | 0.9219 |
| pre_speech_dur_s | 10 | 3.2960 | 2.6960 | -0.6000 | [-1.2240, -0.1120] | Wilcoxon signed-rank | 0.0410 |
| pre_std_intensity | 10 | 13.3126 | 11.8073 | -1.5052 | [-4.6926, +0.8524] | Wilcoxon signed-rank | 0.4922 |
| pre_std_pitch | 10 | 36.7497 | 35.1034 | -1.6464 | [-10.4823, +5.9568] | Wilcoxon signed-rank | 0.4316 |
| pre_utmosv2 | 10 | 2.0791 | 1.9237 | -0.1554 | [-0.4730, +0.0608] | Wilcoxon signed-rank | 0.4316 |
| pre_wpm | 10 | 161.1165 | 140.4097 | -20.7069 | [-54.9786, +5.8991] | Wilcoxon signed-rank | 0.2324 |
| resp_latency | 10 | 1.9976 | 2.4296 | +0.4320 | [-0.1488, +1.0368] | Wilcoxon signed-rank | 0.3223 |
| stop_latency | 10 | 0.3992 | 0.7928 | +0.3936 | [+0.2848, +0.5120] | Wilcoxon signed-rank | 0.0020 |

## v1.5/user_interruption

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 8 | 0.6250 | 0.5000 | -0.1250 | [-0.6250, +0.3750] | McNemar exact (b=2, c=3) | 1.0000 |
| behavior_C_RESUME | 8 | 0.2500 | 0.1250 | -0.1250 | [-0.5000, +0.2500] | McNemar exact (b=1, c=2) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 8 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNKNOWN | 8 | 0.1250 | 0.3750 | +0.2500 | [+0.0000, +0.6250] | McNemar exact (b=2, c=0) | 0.5000 |
| clean_mean_intensity | 8 | 59.9097 | 59.9912 | +0.0815 | [-0.4770, +0.6070] | Wilcoxon signed-rank | 0.6406 |
| clean_mean_pitch | 8 | 202.7725 | 203.6897 | +0.9172 | [-1.8048, +3.4151] | Wilcoxon signed-rank | 0.6406 |
| clean_speech_dur_s | 8 | 10.7400 | 10.2600 | -0.4800 | [-1.2000, +0.1800] | Wilcoxon signed-rank | 0.1953 |
| clean_std_intensity | 8 | 14.8366 | 14.9630 | +0.1264 | [-0.3287, +0.5614] | Wilcoxon signed-rank | 0.5469 |
| clean_std_pitch | 8 | 44.5315 | 43.3993 | -1.1322 | [-3.2644, +1.2222] | Wilcoxon signed-rank | 0.1484 |
| clean_utmosv2 | 8 | 2.0862 | 2.1678 | +0.0817 | [-0.1013, +0.2551] | Wilcoxon signed-rank | 0.4609 |
| clean_wpm | 8 | 190.0747 | 187.9807 | -2.0940 | [-18.9379, +14.6067] | Wilcoxon signed-rank | 0.8438 |
| n_resp_intervals | 8 | 2.0000 | 2.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| n_stop_intervals | 8 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 8 | 61.1096 | 62.7656 | +1.6560 | [-4.3354, +6.8598] | Wilcoxon signed-rank | 0.4609 |
| post_mean_pitch | 8 | 209.0749 | 216.7316 | +7.6567 | [-7.0732, +23.7335] | Wilcoxon signed-rank | 0.4609 |
| post_speech_dur_s | 8 | 2.4100 | 2.4000 | -0.0100 | [-1.6900, +1.7100] | Wilcoxon signed-rank | 0.8438 |
| post_std_intensity | 8 | 14.0758 | 13.3693 | -0.7065 | [-5.1192, +4.2202] | Wilcoxon signed-rank | 1.0000 |
| post_std_pitch | 8 | 44.4760 | 39.6784 | -4.7976 | [-21.1810, +13.8912] | Wilcoxon signed-rank | 0.5469 |
| post_utmosv2 | 8 | 1.7535 | 1.8539 | +0.1003 | [-0.3577, +0.5297] | Wilcoxon signed-rank | 0.9453 |
| post_wpm | 8 | 311.9601 | 167.0279 | -144.9322 | [-345.1504, +1.2843] | Wilcoxon signed-rank | 0.0781 |
| pre_mean_intensity | 8 | 60.3851 | 59.6116 | -0.7735 | [-2.0272, +0.3677] | Wilcoxon signed-rank | 0.3828 |
| pre_mean_pitch | 8 | 206.0203 | 211.1261 | +5.1057 | [-5.0750, +15.9440] | Wilcoxon signed-rank | 0.5469 |
| pre_speech_dur_s | 8 | 3.6500 | 5.3500 | +1.7000 | [+0.6400, +3.1700] | Wilcoxon signed-rank | 0.0156 |
| pre_std_intensity | 8 | 13.8772 | 15.2828 | +1.4056 | [+0.4226, +2.5411] | Wilcoxon signed-rank | 0.0391 |
| pre_std_pitch | 8 | 53.5846 | 47.8821 | -5.7025 | [-15.3407, +2.7176] | Wilcoxon signed-rank | 0.4609 |
| pre_utmosv2 | 8 | 2.1744 | 1.9910 | -0.1834 | [-0.3644, -0.0181] | Wilcoxon signed-rank | 0.1484 |
| pre_wpm | 8 | 174.1838 | 174.1520 | -0.0318 | [-23.2722, +25.7541] | Wilcoxon signed-rank | 0.8438 |
| resp_latency | 8 | 1.7080 | 2.1040 | +0.3960 | [+0.1920, +0.5720] | Wilcoxon signed-rank | 0.0156 |
| stop_latency | 8 | 0.3360 | 1.8520 | +1.5160 | [+0.9480, +2.1401] | Wilcoxon signed-rank | 0.0078 |

## v1/candor_pause_handling

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.1000 | 0.3000 | +0.2000 | [+0.0000, +0.5000] | McNemar exact (b=2, c=0) | 0.5000 |
| n_words | 10 | 1.7000 | 4.5000 | +2.8000 | [-0.6000, +8.5000] | n/a (<6 non-zero pairs) | - |
| premature_llm_start | 10 | 0.2000 | 0.1000 | -0.1000 | [-0.4000, +0.2000] | McNemar exact (b=1, c=2) | 1.0000 |
| premature_turn_end | 10 | 0.4000 | 0.1000 | -0.3000 | [-0.6000, +0.0000] | McNemar exact (b=0, c=3) | 0.2500 |

## v1/candor_turn_taking

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.7000 | 1.0000 | +0.3000 | [+0.0000, +0.6000] | McNemar exact (b=3, c=0) | 0.2500 |
| latency | 7 | 3.2814 | 2.1857 | -1.0957 | [-2.1486, +0.2629] | Wilcoxon signed-rank | 0.2031 |
| latency_raw | 7 | 3.2814 | 1.0643 | -2.2171 | [-4.8229, -0.0457] | Wilcoxon signed-rank | 0.1406 |

## System one

| task | run | judgments | outcomes | latency p50 / p90 (ms, ok) | hedged | actions |
|---|---|---|---|---|---|---|
| v1.5/background_speech | A | - | - | - | - | - |
| v1.5/background_speech | B | 51 | ok 41, stale 10 | 186 / 640 | 25.5% | drop_backchannel 2, drop_side_talk 2, end_turn 13, fallback 4, hold_backchannel 3, interrupt 4, keep_listening 30 |
| v1.5/talking_to_other | A | - | - | - | - | - |
| v1.5/talking_to_other | B | 53 | ok 52, stale 1 | 186 / 611 | 17.0% | drop_backchannel 2, drop_side_talk 10, end_turn 12, hold_backchannel 16, interrupt 2, keep_listening 16 |
| v1.5/user_backchannel | A | - | - | - | - | - |
| v1.5/user_backchannel | B | 45 | ok 40, stale 4, timeout 1 | 238 / 625 | 28.9% | drop_backchannel 17, end_turn 9, fallback 1, hold_backchannel 8, keep_listening 18 |
| v1.5/user_interruption | A | - | - | - | - | - |
| v1.5/user_interruption | B | 70 | ok 64, stale 6 | 146 / 469 | 14.3% | drop_backchannel 7, end_turn 21, hold_backchannel 11, interrupt 11, keep_listening 33 |
| v1/candor_pause_handling | A | - | - | - | - | - |
| v1/candor_pause_handling | B | 123 | ok 114, stale 9 | 196 / 568 | 13.8% | drop_backchannel 5, drop_side_talk 5, end_turn 6, hold_backchannel 5, interrupt 2, keep_listening 106, open_turn 1 |
| v1/candor_turn_taking | A | - | - | - | - | - |
| v1/candor_turn_taking | B | 77 | ok 61, stale 16 | 230 / 784 | 27.3% | drop_backchannel 3, end_turn 8, fallback 2, hold_backchannel 3, keep_listening 66 |
