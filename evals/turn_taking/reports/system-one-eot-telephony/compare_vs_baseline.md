# Paired comparison: A=`baseline-env-telephony` (baseline) vs B=`system-one-eot-telephony`

Diff = B - A. CI: paired percentile bootstrap (10k, seed 0). p: see test column. Uncorrected for multiple comparisons.

## Warnings

- v1.5/background_speech: dropped 0 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/talking_to_other: dropped 0 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_backchannel: dropped 0 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_interruption: dropped 2 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only

## v1.5/background_speech

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 10 | 0.8000 | 0.5000 | -0.3000 | [-0.6000, +0.0000] | McNemar exact (b=0, c=3) | 0.2500 |
| behavior_C_RESUME | 10 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.1000 | 0.0000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 10 | 0.1000 | 0.5000 | +0.4000 | [+0.1000, +0.7000] | McNemar exact (b=4, c=0) | 0.1250 |
| clean_mean_intensity | 10 | 60.2386 | 59.7632 | -0.4754 | [-1.3196, +0.3688] | Wilcoxon signed-rank | 0.4316 |
| clean_mean_pitch | 10 | 194.8553 | 196.3922 | +1.5369 | [-2.9316, +7.3798] | Wilcoxon signed-rank | 1.0000 |
| clean_speech_dur_s | 10 | 6.7840 | 6.5280 | -0.2560 | [-0.3840, -0.1440] | Wilcoxon signed-rank | 0.0020 |
| clean_std_intensity | 10 | 14.3332 | 14.8834 | +0.5502 | [+0.0592, +1.1167] | Wilcoxon signed-rank | 0.0840 |
| clean_std_pitch | 10 | 39.4298 | 34.7895 | -4.6403 | [-9.6695, +0.3788] | Wilcoxon signed-rank | 0.0840 |
| clean_utmosv2 | 10 | 2.1481 | 2.1415 | -0.0066 | [-0.2612, +0.2451] | Wilcoxon signed-rank | 0.9219 |
| clean_wpm | 10 | 159.8935 | 156.7635 | -3.1300 | [-11.2409, +4.5613] | Wilcoxon signed-rank | 0.6953 |
| n_resp_intervals | 10 | 2.0000 | 1.6000 | -0.4000 | [-0.7000, -0.1000] | n/a (<6 non-zero pairs) | - |
| n_stop_intervals | 10 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 10 | 60.3988 | -16.8136 | -77.2124 | [-156.2168, +0.1232] | Wilcoxon signed-rank | 0.2754 |
| post_mean_pitch | 10 | 203.6278 | 148.5206 | -55.1071 | [-119.7312, +4.9461] | Wilcoxon signed-rank | 0.6250 |
| post_speech_dur_s | 10 | 3.1120 | 1.6720 | -1.4400 | [-2.5600, -0.3680] | Wilcoxon signed-rank | 0.0898 |
| post_std_intensity | 10 | 14.8251 | 10.0263 | -4.7988 | [-8.8503, -1.1532] | Wilcoxon signed-rank | 0.0840 |
| post_std_pitch | 10 | 47.2471 | 32.0765 | -15.1706 | [-29.0992, -2.4204] | Wilcoxon signed-rank | 0.1602 |
| post_utmosv2 | 10 | 2.0910 | 1.6078 | -0.4832 | [-0.9606, -0.0534] | Wilcoxon signed-rank | 0.1309 |
| post_wpm | 10 | 203.3598 | 114.8018 | -88.5580 | [-172.0685, -8.5836] | Wilcoxon signed-rank | 0.2500 |
| pre_mean_intensity | 10 | 62.1026 | 61.5173 | -0.5852 | [-2.3824, +0.6734] | Wilcoxon signed-rank | 1.0000 |
| pre_mean_pitch | 10 | 203.8913 | 207.7105 | +3.8192 | [-5.5129, +15.9467] | Wilcoxon signed-rank | 1.0000 |
| pre_speech_dur_s | 10 | 2.4960 | 2.0080 | -0.4880 | [-0.9682, -0.0480] | Wilcoxon signed-rank | 0.0742 |
| pre_std_intensity | 10 | 13.5233 | 13.9085 | +0.3852 | [-0.9706, +1.9448] | Wilcoxon signed-rank | 1.0000 |
| pre_std_pitch | 10 | 40.9147 | 35.2824 | -5.6323 | [-13.8391, +2.2670] | Wilcoxon signed-rank | 0.1934 |
| pre_utmosv2 | 10 | 1.9403 | 1.8837 | -0.0566 | [-0.2164, +0.0833] | Wilcoxon signed-rank | 1.0000 |
| pre_wpm | 10 | 182.1972 | 168.7683 | -13.4289 | [-48.1037, +24.4160] | Wilcoxon signed-rank | 0.6953 |
| resp_latency | 10 | 1.9816 | 2.4152 | +0.4336 | [+0.2320, +0.6368] | Wilcoxon signed-rank | 0.0059 |
| stop_latency | 10 | 0.4088 | 0.3960 | -0.0128 | [-0.0480, +0.0256] | Wilcoxon signed-rank | 0.6133 |

## v1.5/talking_to_other

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 10 | 0.7000 | 0.4000 | -0.3000 | [-0.6000, +0.0000] | McNemar exact (b=0, c=3) | 0.2500 |
| behavior_C_RESUME | 10 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.1000 | 0.1000 | +0.0000 | [-0.3000, +0.3000] | McNemar exact (b=1, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 10 | 0.2000 | 0.5000 | +0.3000 | [+0.0000, +0.6000] | McNemar exact (b=3, c=0) | 0.2500 |
| clean_mean_intensity | 10 | 59.7123 | 59.9715 | +0.2593 | [-0.2915, +0.8353] | Wilcoxon signed-rank | 0.3750 |
| clean_mean_pitch | 10 | 198.9018 | 199.4672 | +0.5654 | [-1.5237, +2.5528] | Wilcoxon signed-rank | 0.6250 |
| clean_speech_dur_s | 10 | 6.9280 | 6.6080 | -0.3200 | [-0.6160, -0.1040] | Wilcoxon signed-rank | 0.0156 |
| clean_std_intensity | 10 | 14.7836 | 14.6469 | -0.1368 | [-0.5385, +0.4024] | Wilcoxon signed-rank | 0.1309 |
| clean_std_pitch | 10 | 40.2487 | 36.0806 | -4.1681 | [-6.6474, -1.7080] | Wilcoxon signed-rank | 0.0195 |
| clean_utmosv2 | 10 | 2.1058 | 2.0956 | -0.0103 | [-0.1454, +0.1472] | Wilcoxon signed-rank | 0.6953 |
| clean_wpm | 10 | 148.0271 | 150.0534 | +2.0263 | [-1.7271, +5.5392] | Wilcoxon signed-rank | 0.2500 |
| n_resp_intervals | 10 | 2.0000 | 1.8000 | -0.2000 | [-0.5000, +0.0000] | n/a (<6 non-zero pairs) | - |
| n_stop_intervals | 10 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 10 | 59.1722 | 8.0941 | -51.0781 | [-129.4806, +2.0933] | Wilcoxon signed-rank | 0.9219 |
| post_mean_pitch | 10 | 203.7039 | 163.8429 | -39.8610 | [-102.8885, +5.3310] | Wilcoxon signed-rank | 0.5566 |
| post_speech_dur_s | 10 | 3.0560 | 2.0240 | -1.0320 | [-1.8642, -0.3358] | Wilcoxon signed-rank | 0.0156 |
| post_std_intensity | 10 | 15.6108 | 12.0760 | -3.5348 | [-7.2374, -0.4535] | Wilcoxon signed-rank | 0.1055 |
| post_std_pitch | 10 | 42.8321 | 44.0613 | +1.2292 | [-21.5365, +20.5054] | Wilcoxon signed-rank | 0.6953 |
| post_utmosv2 | 10 | 2.0428 | 1.8227 | -0.2200 | [-0.6442, +0.1551] | Wilcoxon signed-rank | 0.6953 |
| post_wpm | 10 | 225.3462 | 174.5821 | -50.7641 | [-127.7137, +17.2526] | Wilcoxon signed-rank | 0.6250 |
| pre_mean_intensity | 10 | 60.5384 | 61.4319 | +0.8935 | [+0.0603, +1.8068] | Wilcoxon signed-rank | 0.1055 |
| pre_mean_pitch | 10 | 206.0138 | 213.8794 | +7.8657 | [-0.7322, +17.0073] | Wilcoxon signed-rank | 0.0840 |
| pre_speech_dur_s | 10 | 2.5360 | 1.3760 | -1.1600 | [-1.7682, -0.6000] | Wilcoxon signed-rank | 0.0039 |
| pre_std_intensity | 10 | 14.7050 | 13.2959 | -1.4091 | [-1.9633, -0.7921] | Wilcoxon signed-rank | 0.0098 |
| pre_std_pitch | 10 | 37.4367 | 43.1938 | +5.7571 | [-3.2450, +14.5483] | Wilcoxon signed-rank | 0.2324 |
| pre_utmosv2 | 10 | 1.9424 | 1.7458 | -0.1966 | [-0.3629, -0.0302] | Wilcoxon signed-rank | 0.0488 |
| pre_wpm | 10 | 143.1245 | 113.5875 | -29.5371 | [-76.3136, +11.5035] | Wilcoxon signed-rank | 0.5566 |
| resp_latency | 10 | 2.0552 | 2.6472 | +0.5920 | [+0.4128, +0.7744] | Wilcoxon signed-rank | 0.0020 |
| stop_latency | 10 | 0.4152 | 0.4056 | -0.0096 | [-0.0416, +0.0288] | Wilcoxon signed-rank | 0.5781 |

## v1.5/user_backchannel

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 10 | 0.1000 | 0.0000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_RESUME | 10 | 0.2000 | 0.1000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.3000 | 0.1000 | -0.2000 | [-0.5000, +0.0000] | McNemar exact (b=0, c=2) | 0.5000 |
| behavior_C_UNKNOWN | 10 | 0.4000 | 0.8000 | +0.4000 | [+0.1000, +0.7000] | McNemar exact (b=4, c=0) | 0.1250 |
| clean_mean_intensity | 10 | 60.7713 | 59.9204 | -0.8510 | [-1.4927, -0.1766] | Wilcoxon signed-rank | 0.0645 |
| clean_mean_pitch | 10 | 204.8378 | 205.5325 | +0.6947 | [-3.2630, +4.2263] | Wilcoxon signed-rank | 0.6250 |
| clean_speech_dur_s | 10 | 8.2240 | 7.2240 | -1.0000 | [-2.0160, -0.3680] | Wilcoxon signed-rank | 0.0020 |
| clean_std_intensity | 10 | 14.0057 | 14.6092 | +0.6035 | [+0.1533, +0.9784] | Wilcoxon signed-rank | 0.0488 |
| clean_std_pitch | 10 | 37.4174 | 41.7315 | +4.3141 | [+1.7936, +6.8836] | Wilcoxon signed-rank | 0.0137 |
| clean_utmosv2 | 10 | 2.1097 | 2.0705 | -0.0392 | [-0.2525, +0.1493] | Wilcoxon signed-rank | 1.0000 |
| clean_wpm | 10 | 168.5417 | 186.0834 | +17.5416 | [+1.7788, +39.3737] | Wilcoxon signed-rank | 0.1055 |
| n_resp_intervals | 10 | 2.0000 | 1.2000 | -0.8000 | [-1.0000, -0.5000] | Wilcoxon signed-rank | 0.0078 |
| n_stop_intervals | 10 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 10 | 59.8811 | -101.2758 | -161.1569 | [-235.2854, -84.2620] | Wilcoxon signed-rank | 0.0059 |
| post_mean_pitch | 10 | 202.5107 | 63.7383 | -138.7723 | [-200.3008, -73.2092] | Wilcoxon signed-rank | 0.0137 |
| post_speech_dur_s | 10 | 3.0240 | 0.9760 | -2.0480 | [-2.9360, -1.1200] | Wilcoxon signed-rank | 0.0039 |
| post_std_intensity | 10 | 14.9041 | 4.6488 | -10.2553 | [-14.7207, -5.4471] | Wilcoxon signed-rank | 0.0137 |
| post_std_pitch | 10 | 36.5853 | 8.0584 | -28.5269 | [-37.9241, -20.2474] | Wilcoxon signed-rank | 0.0020 |
| post_utmosv2 | 10 | 1.9295 | 0.9741 | -0.9554 | [-1.3458, -0.5335] | Wilcoxon signed-rank | 0.0059 |
| post_wpm | 10 | 193.3568 | 52.2378 | -141.1190 | [-212.5575, -67.6744] | Wilcoxon signed-rank | 0.0117 |
| pre_mean_intensity | 10 | 62.0974 | 63.1032 | +1.0058 | [-0.2600, +2.3035] | Wilcoxon signed-rank | 0.2754 |
| pre_mean_pitch | 10 | 212.1739 | 211.6477 | -0.5262 | [-5.3959, +4.1768] | Wilcoxon signed-rank | 0.8457 |
| pre_speech_dur_s | 10 | 2.9920 | 2.6480 | -0.3440 | [-0.8480, +0.0880] | Wilcoxon signed-rank | 0.3008 |
| pre_std_intensity | 10 | 12.5789 | 12.0065 | -0.5724 | [-1.6324, +0.4530] | Wilcoxon signed-rank | 0.3223 |
| pre_std_pitch | 10 | 44.1753 | 40.4000 | -3.7753 | [-8.4748, +1.2220] | Wilcoxon signed-rank | 0.2324 |
| pre_utmosv2 | 10 | 2.0812 | 1.9327 | -0.1485 | [-0.3253, +0.0173] | Wilcoxon signed-rank | 0.2324 |
| pre_wpm | 10 | 173.8689 | 159.8828 | -13.9861 | [-24.3959, -1.7845] | Wilcoxon signed-rank | 0.0645 |
| resp_latency | 10 | 1.8968 | 2.2024 | +0.3056 | [-0.0944, +0.7088] | Wilcoxon signed-rank | 0.1309 |
| stop_latency | 10 | 0.3960 | 0.4088 | +0.0128 | [-0.0128, +0.0384] | Wilcoxon signed-rank | 0.5312 |

## v1.5/user_interruption

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 8 | 0.6250 | 0.7500 | +0.1250 | [+0.0000, +0.3750] | McNemar exact (b=1, c=0) | 1.0000 |
| behavior_C_RESUME | 8 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 8 | 0.1250 | 0.0000 | -0.1250 | [-0.3750, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 8 | 0.2500 | 0.2500 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| clean_mean_intensity | 8 | 59.8037 | 59.7914 | -0.0123 | [-0.7048, +0.7204] | Wilcoxon signed-rank | 0.8438 |
| clean_mean_pitch | 8 | 200.6361 | 204.5062 | +3.8701 | [-0.2144, +9.1053] | Wilcoxon signed-rank | 0.1953 |
| clean_speech_dur_s | 8 | 11.2000 | 10.8400 | -0.3600 | [-0.6400, -0.1000] | Wilcoxon signed-rank | 0.0469 |
| clean_std_intensity | 8 | 15.0206 | 15.0662 | +0.0455 | [-0.3953, +0.4845] | Wilcoxon signed-rank | 0.9453 |
| clean_std_pitch | 8 | 39.6503 | 40.3286 | +0.6783 | [-2.7343, +4.4212] | Wilcoxon signed-rank | 0.9453 |
| clean_utmosv2 | 8 | 2.1172 | 2.0462 | -0.0710 | [-0.2281, +0.1354] | Wilcoxon signed-rank | 0.3125 |
| clean_wpm | 8 | 192.0038 | 199.1587 | +7.1549 | [-1.5113, +18.6391] | Wilcoxon signed-rank | 0.2500 |
| n_resp_intervals | 8 | 2.0000 | 2.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| n_stop_intervals | 8 | 1.0000 | 0.8750 | -0.1250 | [-0.3750, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| post_mean_intensity | 8 | 60.2926 | 59.9523 | -0.3403 | [-2.0714, +1.4358] | Wilcoxon signed-rank | 0.8438 |
| post_mean_pitch | 8 | 213.6641 | 217.7861 | +4.1221 | [-5.5856, +13.6175] | Wilcoxon signed-rank | 0.6406 |
| post_speech_dur_s | 8 | 2.3600 | 2.9500 | +0.5900 | [-0.1400, +1.6500] | Wilcoxon signed-rank | 0.2969 |
| post_std_intensity | 8 | 13.7213 | 15.3198 | +1.5986 | [-0.2623, +4.2011] | Wilcoxon signed-rank | 0.3828 |
| post_std_pitch | 8 | 50.8581 | 55.6019 | +4.7437 | [-3.2864, +13.5556] | Wilcoxon signed-rank | 0.5469 |
| post_utmosv2 | 8 | 1.9001 | 1.8566 | -0.0436 | [-0.2525, +0.1788] | Wilcoxon signed-rank | 0.6406 |
| post_wpm | 8 | 172.3232 | 414.4753 | +242.1520 | [-28.0405, +631.6858] | Wilcoxon signed-rank | 0.7422 |
| pre_mean_intensity | 8 | 60.8290 | 60.0826 | -0.7464 | [-2.1355, +0.3706] | Wilcoxon signed-rank | 0.5469 |
| pre_mean_pitch | 8 | 210.9431 | 208.3206 | -2.6225 | [-9.5833, +3.8155] | Wilcoxon signed-rank | 0.8438 |
| pre_speech_dur_s | 8 | 4.7800 | 3.0400 | -1.7400 | [-3.5300, -0.4100] | Wilcoxon signed-rank | 0.0391 |
| pre_std_intensity | 8 | 14.3316 | 14.4725 | +0.1409 | [-1.1165, +1.3385] | Wilcoxon signed-rank | 0.6406 |
| pre_std_pitch | 8 | 52.2067 | 42.3798 | -9.8270 | [-19.2636, +0.3742] | Wilcoxon signed-rank | 0.1484 |
| pre_utmosv2 | 8 | 2.1303 | 1.9834 | -0.1469 | [-0.2848, -0.0109] | Wilcoxon signed-rank | 0.1953 |
| pre_wpm | 8 | 189.4275 | 176.9737 | -12.4538 | [-91.6489, +47.8348] | Wilcoxon signed-rank | 0.7422 |
| resp_latency | 8 | 1.9600 | 2.2660 | +0.3060 | [+0.2060, +0.4060] | Wilcoxon signed-rank | 0.0078 |
| stop_latency | 7 | 0.3800 | 0.4074 | +0.0274 | [+0.0046, +0.0503] | Wilcoxon signed-rank | 0.1562 |

## v1/candor_pause_handling

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.1000 | 0.0000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| n_words | 10 | 0.7000 | 0.0000 | -0.7000 | [-2.1000, +0.0000] | n/a (<6 non-zero pairs) | - |
| premature_llm_start | 10 | 0.3000 | 0.2000 | -0.1000 | [-0.3000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| premature_turn_end | 10 | 0.4000 | 0.2000 | -0.2000 | [-0.5000, +0.0000] | McNemar exact (b=0, c=2) | 0.5000 |

## v1/candor_turn_taking

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.8000 | 0.8000 | +0.0000 | [-0.3000, +0.3000] | McNemar exact (b=1, c=1) | 1.0000 |
| latency | 7 | 2.7029 | 3.5657 | +0.8629 | [+0.1143, +1.9829] | Wilcoxon signed-rank | 0.0938 |
| latency_raw | 7 | 2.4000 | 3.5657 | +1.1657 | [+0.1143, +2.8914] | Wilcoxon signed-rank | 0.0938 |

## System one

| task | run | judgments | outcomes | latency p50 / p90 (ms, ok) | hedged | actions |
|---|---|---|---|---|---|---|
| v1.5/background_speech | A | - | - | - | - | - |
| v1.5/background_speech | B | 20 | ok 20 | 418 / 931 | 45.0% | - |
| v1.5/talking_to_other | A | - | - | - | - | - |
| v1.5/talking_to_other | B | 20 | ok 20 | 372 / 879 | 35.0% | - |
| v1.5/user_backchannel | A | - | - | - | - | - |
| v1.5/user_backchannel | B | 20 | cancelled 2, ok 18 | 316 / 775 | 31.6% | - |
| v1.5/user_interruption | A | - | - | - | - | - |
| v1.5/user_interruption | B | 30 | cancelled 10, ok 20 | 414 / 680 | 41.4% | - |
| v1/candor_pause_handling | A | - | - | - | - | - |
| v1/candor_pause_handling | B | 50 | cancelled 28, ok 22 | 364 / 811 | 42.4% | - |
| v1/candor_turn_taking | A | - | - | - | - | - |
| v1/candor_turn_taking | B | 29 | cancelled 14, ok 15 | 496 / 916 | 40.0% | - |
