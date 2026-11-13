# Paired comparison: A=`baseline-env-telephony` (baseline) vs B=`system-one-v2-telephony`

Diff = B - A. CI: paired percentile bootstrap (10k, seed 0). p: see test column. Uncorrected for multiple comparisons.

## Warnings

- v1.5/background_speech: dropped 1 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/talking_to_other: dropped 0 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_backchannel: dropped 1 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_interruption: dropped 2 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only

## v1.5/background_speech

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 9 | 0.7778 | 0.3333 | -0.4444 | [-0.7778, -0.1111] | McNemar exact (b=0, c=4) | 0.1250 |
| behavior_C_RESUME | 9 | 0.0000 | 0.3333 | +0.3333 | [+0.0000, +0.6667] | McNemar exact (b=3, c=0) | 0.2500 |
| behavior_C_UNCERTAIN_HANDLING | 9 | 0.1111 | 0.0000 | -0.1111 | [-0.3333, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 9 | 0.1111 | 0.3333 | +0.2222 | [+0.0000, +0.5556] | McNemar exact (b=2, c=0) | 0.5000 |
| clean_mean_intensity | 9 | 59.9374 | 59.7140 | -0.2234 | [-1.2064, +0.6362] | Wilcoxon signed-rank | 0.9102 |
| clean_mean_pitch | 9 | 194.2897 | 198.7116 | +4.4219 | [-0.7467, +9.9626] | Wilcoxon signed-rank | 0.2500 |
| clean_speech_dur_s | 9 | 7.2444 | 6.7733 | -0.4711 | [-0.7822, -0.1689] | Wilcoxon signed-rank | 0.0234 |
| clean_std_intensity | 9 | 14.5052 | 14.9556 | +0.4504 | [-0.1292, +1.1613] | Wilcoxon signed-rank | 0.2031 |
| clean_std_pitch | 9 | 38.0570 | 38.5052 | +0.4482 | [-6.6209, +7.5230] | Wilcoxon signed-rank | 0.9102 |
| clean_utmosv2 | 9 | 2.1169 | 2.0287 | -0.0883 | [-0.3383, +0.1479] | Wilcoxon signed-rank | 0.6523 |
| clean_wpm | 9 | 159.9827 | 172.3477 | +12.3650 | [+1.7643, +23.8342] | Wilcoxon signed-rank | 0.0547 |
| n_resp_intervals | 9 | 2.0000 | 1.4444 | -0.5556 | [-0.8889, -0.2222] | n/a (<6 non-zero pairs) | - |
| n_stop_intervals | 9 | 1.0000 | 1.1111 | +0.1111 | [+0.0000, +0.3333] | n/a (<6 non-zero pairs) | - |
| post_mean_intensity | 9 | 60.6495 | 52.0333 | -8.6162 | [-25.2358, +0.4713] | Wilcoxon signed-rank | 0.4258 |
| post_mean_pitch | 9 | 203.9908 | 230.4351 | +26.4443 | [-7.0954, +86.2413] | Wilcoxon signed-rank | 0.5703 |
| post_speech_dur_s | 9 | 3.1111 | 4.0622 | +0.9511 | [-0.6222, +2.5333] | Wilcoxon signed-rank | 0.3438 |
| post_std_intensity | 9 | 14.6941 | 15.3412 | +0.6471 | [-0.1069, +1.3694] | Wilcoxon signed-rank | 0.2031 |
| post_std_pitch | 9 | 44.7697 | 33.7318 | -11.0379 | [-22.2851, -0.8117] | Wilcoxon signed-rank | 0.1289 |
| post_utmosv2 | 9 | 2.0995 | 1.8453 | -0.2541 | [-0.6332, +0.0332] | Wilcoxon signed-rank | 0.2031 |
| post_wpm | 9 | 206.7245 | 153.0839 | -53.6406 | [-117.1769, +9.1741] | Wilcoxon signed-rank | 0.0977 |
| pre_mean_intensity | 9 | 61.8476 | 60.8894 | -0.9583 | [-2.8650, +0.6849] | Wilcoxon signed-rank | 0.2500 |
| pre_mean_pitch | 9 | 204.3668 | 200.6453 | -3.7215 | [-8.6198, +1.2364] | Wilcoxon signed-rank | 0.1641 |
| pre_speech_dur_s | 9 | 2.4889 | 2.7644 | +0.2756 | [-0.3289, +0.8800] | Wilcoxon signed-rank | 0.4609 |
| pre_std_intensity | 9 | 13.6986 | 13.9415 | +0.2430 | [-1.0702, +1.9547] | Wilcoxon signed-rank | 0.9102 |
| pre_std_pitch | 9 | 42.0055 | 32.1974 | -9.8080 | [-16.5379, -4.5813] | Wilcoxon signed-rank | 0.0078 |
| pre_utmosv2 | 9 | 1.9340 | 2.0446 | +0.1106 | [-0.0916, +0.2864] | Wilcoxon signed-rank | 0.4258 |
| pre_wpm | 9 | 184.2122 | 171.5838 | -12.6284 | [-31.8280, +2.5887] | Wilcoxon signed-rank | 0.2500 |
| resp_latency | 9 | 1.9809 | 2.6440 | +0.6631 | [+0.3947, +0.9120] | Wilcoxon signed-rank | 0.0039 |
| stop_latency | 9 | 0.4013 | 1.1000 | +0.6987 | [+0.3182, +1.0560] | Wilcoxon signed-rank | 0.0117 |

## v1.5/talking_to_other

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 10 | 0.7000 | 0.0000 | -0.7000 | [-1.0000, -0.4000] | McNemar exact (b=0, c=7) | 0.0156 |
| behavior_C_RESUME | 10 | 0.0000 | 0.3000 | +0.3000 | [+0.0000, +0.6000] | McNemar exact (b=3, c=0) | 0.2500 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.1000 | 0.0000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 10 | 0.2000 | 0.7000 | +0.5000 | [+0.1000, +0.9000] | McNemar exact (b=6, c=1) | 0.1250 |
| clean_mean_intensity | 10 | 59.7123 | 59.5259 | -0.1864 | [-0.6481, +0.3024] | Wilcoxon signed-rank | 0.3750 |
| clean_mean_pitch | 10 | 198.9018 | 198.9618 | +0.0600 | [-2.0345, +1.9747] | Wilcoxon signed-rank | 0.9219 |
| clean_speech_dur_s | 10 | 6.9280 | 6.6480 | -0.2800 | [-0.5200, -0.0400] | Wilcoxon signed-rank | 0.0742 |
| clean_std_intensity | 10 | 14.7836 | 14.9319 | +0.1483 | [-0.4060, +0.7486] | Wilcoxon signed-rank | 0.7695 |
| clean_std_pitch | 10 | 40.2487 | 39.6059 | -0.6428 | [-3.6480, +3.1278] | Wilcoxon signed-rank | 0.4316 |
| clean_utmosv2 | 10 | 2.1058 | 2.0724 | -0.0334 | [-0.1782, +0.1079] | Wilcoxon signed-rank | 0.7695 |
| clean_wpm | 10 | 148.0271 | 149.1792 | +1.1521 | [-4.6886, +7.2931] | Wilcoxon signed-rank | 0.9102 |
| n_resp_intervals | 10 | 2.0000 | 1.0000 | -1.0000 | [-1.0000, -1.0000] | Wilcoxon signed-rank | 0.0020 |
| n_stop_intervals | 10 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 10 | 59.1722 | 29.0147 | -30.1575 | [-83.0472, +1.9290] | Wilcoxon signed-rank | 0.8457 |
| post_mean_pitch | 10 | 203.7039 | 207.7735 | +4.0696 | [-65.8237, +88.3666] | Wilcoxon signed-rank | 0.1934 |
| post_speech_dur_s | 10 | 3.0560 | 3.3360 | +0.2800 | [-1.2080, +1.7520] | Wilcoxon signed-rank | 0.9766 |
| post_std_intensity | 10 | 15.6108 | 11.8240 | -3.7869 | [-7.5054, -0.8520] | Wilcoxon signed-rank | 0.0488 |
| post_std_pitch | 10 | 42.8321 | 29.6353 | -13.1968 | [-25.3477, -1.2706] | Wilcoxon signed-rank | 0.0840 |
| post_utmosv2 | 10 | 2.0428 | 1.8479 | -0.1949 | [-0.6239, +0.1820] | Wilcoxon signed-rank | 0.6250 |
| post_wpm | 10 | 225.3462 | 126.0605 | -99.2857 | [-144.7355, -55.2669] | Wilcoxon signed-rank | 0.0059 |
| pre_mean_intensity | 10 | 60.5384 | 59.8560 | -0.6824 | [-1.3051, -0.1031] | Wilcoxon signed-rank | 0.0840 |
| pre_mean_pitch | 10 | 206.0138 | 201.0475 | -4.9663 | [-9.2117, -1.1686] | Wilcoxon signed-rank | 0.0488 |
| pre_speech_dur_s | 10 | 2.5360 | 3.0400 | +0.5040 | [+0.1920, +0.8400] | Wilcoxon signed-rank | 0.0273 |
| pre_std_intensity | 10 | 14.7050 | 14.4643 | -0.2408 | [-1.2335, +0.7447] | Wilcoxon signed-rank | 0.6953 |
| pre_std_pitch | 10 | 37.4367 | 39.1351 | +1.6985 | [-2.1812, +5.6969] | Wilcoxon signed-rank | 0.5566 |
| pre_utmosv2 | 10 | 1.9424 | 1.8914 | -0.0510 | [-0.1577, +0.0431] | Wilcoxon signed-rank | 0.5566 |
| pre_wpm | 10 | 143.1245 | 148.8261 | +5.7016 | [-10.4366, +24.9749] | Wilcoxon signed-rank | 0.8457 |
| resp_latency | 10 | 2.0552 | 2.9928 | +0.9376 | [+0.6176, +1.1760] | Wilcoxon signed-rank | 0.0039 |
| stop_latency | 10 | 0.4152 | 1.7208 | +1.3056 | [+1.1200, +1.4848] | Wilcoxon signed-rank | 0.0020 |

## v1.5/user_backchannel

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 9 | 0.1111 | 0.0000 | -0.1111 | [-0.3333, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_RESUME | 9 | 0.2222 | 0.4444 | +0.2222 | [+0.0000, +0.5556] | McNemar exact (b=2, c=0) | 0.5000 |
| behavior_C_UNCERTAIN_HANDLING | 9 | 0.3333 | 0.0000 | -0.3333 | [-0.6667, +0.0000] | McNemar exact (b=0, c=3) | 0.2500 |
| behavior_C_UNKNOWN | 9 | 0.3333 | 0.5556 | +0.2222 | [-0.2222, +0.6667] | McNemar exact (b=3, c=1) | 0.6250 |
| clean_mean_intensity | 9 | 60.8663 | 59.9790 | -0.8872 | [-2.0294, +0.3189] | Wilcoxon signed-rank | 0.2500 |
| clean_mean_pitch | 9 | 204.1258 | 203.5428 | -0.5830 | [-2.7232, +2.1338] | Wilcoxon signed-rank | 0.3594 |
| clean_speech_dur_s | 9 | 8.2133 | 7.2622 | -0.9511 | [-1.4044, -0.5600] | Wilcoxon signed-rank | 0.0039 |
| clean_std_intensity | 9 | 13.8598 | 14.4296 | +0.5698 | [-0.1359, +1.3295] | Wilcoxon signed-rank | 0.4258 |
| clean_std_pitch | 9 | 38.1277 | 40.7773 | +2.6496 | [-2.1511, +7.0289] | Wilcoxon signed-rank | 0.3008 |
| clean_utmosv2 | 9 | 2.0822 | 2.1106 | +0.0284 | [-0.1417, +0.1943] | Wilcoxon signed-rank | 0.8203 |
| clean_wpm | 9 | 171.2429 | 172.3508 | +1.1079 | [-6.6357, +9.0670] | Wilcoxon signed-rank | 0.8203 |
| n_resp_intervals | 9 | 2.0000 | 1.1111 | -0.8889 | [-1.0000, -0.6667] | Wilcoxon signed-rank | 0.0078 |
| n_stop_intervals | 9 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 9 | 58.9664 | 59.9403 | +0.9739 | [+0.0152, +2.3778] | Wilcoxon signed-rank | 0.1641 |
| post_mean_pitch | 9 | 201.6446 | 200.9286 | -0.7160 | [-6.9325, +5.0280] | Wilcoxon signed-rank | 0.9102 |
| post_speech_dur_s | 9 | 3.2889 | 5.0311 | +1.7422 | [+0.6931, +2.8178] | Wilcoxon signed-rank | 0.0195 |
| post_std_intensity | 9 | 15.5776 | 14.8002 | -0.7774 | [-2.3532, +0.6768] | Wilcoxon signed-rank | 0.7344 |
| post_std_pitch | 9 | 38.8048 | 36.8858 | -1.9190 | [-12.1626, +8.3358] | Wilcoxon signed-rank | 0.8203 |
| post_utmosv2 | 9 | 2.0101 | 2.0383 | +0.0282 | [-0.2189, +0.2941] | Wilcoxon signed-rank | 0.9102 |
| post_wpm | 9 | 204.4242 | 189.3298 | -15.0944 | [-61.1042, +51.6557] | Wilcoxon signed-rank | 0.1641 |
| pre_mean_intensity | 9 | 62.0611 | 63.4942 | +1.4331 | [-0.0675, +2.8520] | Wilcoxon signed-rank | 0.1289 |
| pre_mean_pitch | 9 | 211.3497 | 222.1486 | +10.7988 | [-3.8834, +35.5686] | Wilcoxon signed-rank | 0.7344 |
| pre_speech_dur_s | 9 | 3.0133 | 2.0089 | -1.0044 | [-1.4489, -0.6400] | Wilcoxon signed-rank | 0.0039 |
| pre_std_intensity | 9 | 12.6282 | 11.9465 | -0.6817 | [-1.8172, +0.3307] | Wilcoxon signed-rank | 0.5703 |
| pre_std_pitch | 9 | 45.0924 | 36.5445 | -8.5479 | [-18.0471, -2.0969] | Wilcoxon signed-rank | 0.0547 |
| pre_utmosv2 | 9 | 2.0759 | 1.9923 | -0.0836 | [-0.2377, +0.1020] | Wilcoxon signed-rank | 0.2500 |
| pre_wpm | 9 | 176.5210 | 152.8599 | -23.6611 | [-55.0266, +2.4585] | Wilcoxon signed-rank | 0.1289 |
| resp_latency | 9 | 1.7604 | 2.8342 | +1.0738 | [+0.8071, +1.3564] | Wilcoxon signed-rank | 0.0039 |
| stop_latency | 9 | 0.4084 | 0.5969 | +0.1884 | [+0.0818, +0.2951] | Wilcoxon signed-rank | 0.0156 |

## v1.5/user_interruption

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 8 | 0.6250 | 0.6250 | +0.0000 | [-0.5000, +0.5000] | McNemar exact (b=2, c=2) | 1.0000 |
| behavior_C_RESUME | 8 | 0.0000 | 0.1250 | +0.1250 | [+0.0000, +0.3750] | McNemar exact (b=1, c=0) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 8 | 0.1250 | 0.0000 | -0.1250 | [-0.3750, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 8 | 0.2500 | 0.2500 | +0.0000 | [-0.5000, +0.5000] | McNemar exact (b=2, c=2) | 1.0000 |
| clean_mean_intensity | 8 | 59.8037 | 59.7913 | -0.0124 | [-0.2722, +0.2440] | Wilcoxon signed-rank | 0.8438 |
| clean_mean_pitch | 8 | 200.6361 | 203.0341 | +2.3980 | [+0.1911, +4.7671] | Wilcoxon signed-rank | 0.1484 |
| clean_speech_dur_s | 8 | 11.2000 | 10.6600 | -0.5400 | [-0.9100, -0.2700] | Wilcoxon signed-rank | 0.0156 |
| clean_std_intensity | 8 | 15.0206 | 14.9551 | -0.0656 | [-0.3899, +0.2760] | Wilcoxon signed-rank | 0.8438 |
| clean_std_pitch | 8 | 39.6503 | 42.5059 | +2.8556 | [+0.0952, +6.3144] | Wilcoxon signed-rank | 0.1094 |
| clean_utmosv2 | 8 | 2.1172 | 2.1070 | -0.0102 | [-0.2171, +0.1548] | Wilcoxon signed-rank | 0.7422 |
| clean_wpm | 8 | 192.0038 | 194.2271 | +2.2233 | [-5.6263, +11.0147] | Wilcoxon signed-rank | 0.6406 |
| n_resp_intervals | 8 | 2.0000 | 2.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| n_stop_intervals | 8 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 8 | 60.2926 | 58.4084 | -1.8842 | [-4.3308, +0.3348] | Wilcoxon signed-rank | 0.3828 |
| post_mean_pitch | 8 | 213.6641 | 219.2667 | +5.6026 | [-12.0212, +30.0708] | Wilcoxon signed-rank | 0.9453 |
| post_speech_dur_s | 8 | 2.3600 | 1.7800 | -0.5800 | [-1.7500, +0.3900] | Wilcoxon signed-rank | 0.4688 |
| post_std_intensity | 8 | 13.7213 | 16.0621 | +2.3408 | [+0.3780, +4.8668] | Wilcoxon signed-rank | 0.1094 |
| post_std_pitch | 8 | 50.8581 | 44.0323 | -6.8258 | [-23.6146, +8.8410] | Wilcoxon signed-rank | 0.7422 |
| post_utmosv2 | 8 | 1.9001 | 1.9760 | +0.0759 | [-0.1454, +0.2665] | Wilcoxon signed-rank | 0.4609 |
| post_wpm | 8 | 172.3232 | 172.4517 | +0.1285 | [-77.8453, +80.5424] | Wilcoxon signed-rank | 0.9375 |
| pre_mean_intensity | 8 | 60.8290 | 59.2104 | -1.6186 | [-2.9557, -0.1920] | Wilcoxon signed-rank | 0.1094 |
| pre_mean_pitch | 8 | 210.9431 | 207.2490 | -3.6940 | [-7.3771, -0.1091] | Wilcoxon signed-rank | 0.0781 |
| pre_speech_dur_s | 8 | 4.7800 | 5.4400 | +0.6600 | [-1.7400, +3.2102] | Wilcoxon signed-rank | 0.3984 |
| pre_std_intensity | 8 | 14.3316 | 14.9839 | +0.6523 | [-0.9042, +2.0790] | Wilcoxon signed-rank | 0.3828 |
| pre_std_pitch | 8 | 52.2067 | 46.6459 | -5.5609 | [-11.2592, -0.3781] | Wilcoxon signed-rank | 0.1953 |
| pre_utmosv2 | 8 | 2.1303 | 2.0280 | -0.1023 | [-0.2632, +0.0327] | Wilcoxon signed-rank | 0.5469 |
| pre_wpm | 8 | 189.4275 | 185.1130 | -4.3144 | [-35.5241, +32.0594] | Wilcoxon signed-rank | 0.5469 |
| resp_latency | 8 | 1.9600 | 2.5000 | +0.5400 | [+0.1360, +0.9460] | Wilcoxon signed-rank | 0.0547 |
| stop_latency | 8 | 0.3880 | 1.7560 | +1.3680 | [+1.0000, +1.7080] | Wilcoxon signed-rank | 0.0078 |

## v1/candor_pause_handling

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.1000 | 0.2000 | +0.1000 | [-0.2000, +0.4000] | McNemar exact (b=2, c=1) | 1.0000 |
| n_words | 10 | 0.7000 | 2.5000 | +1.8000 | [-1.4000, +5.9000] | n/a (<6 non-zero pairs) | - |
| premature_llm_start | 10 | 0.3000 | 0.1000 | -0.2000 | [-0.5000, +0.0000] | McNemar exact (b=0, c=2) | 0.5000 |
| premature_turn_end | 10 | 0.4000 | 0.1000 | -0.3000 | [-0.6000, +0.0000] | McNemar exact (b=0, c=3) | 0.2500 |

## v1/candor_turn_taking

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.8000 | 0.8000 | +0.0000 | [-0.4000, +0.4000] | McNemar exact (b=2, c=2) | 1.0000 |
| latency | 6 | 2.4517 | 2.1000 | -0.3517 | [-2.5583, +1.7133] | n/a (<6 non-zero pairs) | - |
| latency_raw | 6 | 2.0983 | 0.3117 | -1.7867 | [-7.3867, +2.4533] | n/a (<6 non-zero pairs) | - |

## System one

| task | run | judgments | outcomes | latency p50 / p90 (ms, ok) | hedged | actions |
|---|---|---|---|---|---|---|
| v1.5/background_speech | A | - | - | - | - | - |
| v1.5/background_speech | B | 46 | ok 39, stale 7 | 171 / 628 | 26.7% | drop_backchannel 7, drop_side_talk 4, end_turn 14, hold_backchannel 10, interrupt 4, keep_listening 17, open_turn 1 |
| v1.5/talking_to_other | A | - | - | - | - | - |
| v1.5/talking_to_other | B | 51 | ok 45, stale 6 | 210 / 638 | 23.5% | drop_backchannel 1, drop_side_talk 10, end_turn 10, hold_backchannel 16, keep_listening 15 |
| v1.5/user_backchannel | A | - | - | - | - | - |
| v1.5/user_backchannel | B | 51 | ok 39, stale 10, timeout 2 | 192 / 604 | 31.4% | drop_backchannel 13, drop_side_talk 1, end_turn 9, fallback 1, hold_backchannel 3, keep_listening 28 |
| v1.5/user_interruption | A | - | - | - | - | - |
| v1.5/user_interruption | B | 71 | ok 63, stale 6, timeout 2 | 203 / 590 | 16.9% | drop_backchannel 5, end_turn 18, fallback 3, hold_backchannel 8, interrupt 11, keep_listening 36 |
| v1/candor_pause_handling | A | - | - | - | - | - |
| v1/candor_pause_handling | B | 113 | ok 95, stale 18 | 197 / 615 | 25.0% | drop_backchannel 4, drop_side_talk 4, end_turn 5, fallback 1, hold_backchannel 6, interrupt 1, keep_listening 97 |
| v1/candor_turn_taking | A | - | - | - | - | - |
| v1/candor_turn_taking | B | 74 | ok 69, stale 5 | 164 / 440 | 13.5% | drop_backchannel 1, drop_side_talk 6, end_turn 7, fallback 2, hold_backchannel 5, keep_listening 59 |
