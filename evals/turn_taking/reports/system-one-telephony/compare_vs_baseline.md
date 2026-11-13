# Paired comparison: A=`baseline-env-telephony` (baseline) vs B=`system-one-telephony`

Diff = B - A. CI: paired percentile bootstrap (10k, seed 0). p: see test column. Uncorrected for multiple comparisons.

## Warnings

- v1.5/background_speech: dropped 3 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/talking_to_other: dropped 2 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_backchannel: dropped 2 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_interruption: dropped 3 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only

## v1.5/background_speech

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 7 | 0.7143 | 0.1429 | -0.5714 | [-1.0000, +0.0000] | McNemar exact (b=1, c=5) | 0.2188 |
| behavior_C_RESUME | 7 | 0.0000 | 0.1429 | +0.1429 | [+0.0000, +0.4286] | McNemar exact (b=1, c=0) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 7 | 0.1429 | 0.0000 | -0.1429 | [-0.4286, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 7 | 0.1429 | 0.7143 | +0.5714 | [+0.2857, +0.8571] | McNemar exact (b=4, c=0) | 0.1250 |
| clean_mean_intensity | 7 | 60.8461 | 60.0987 | -0.7474 | [-1.5283, +0.1149] | Wilcoxon signed-rank | 0.1562 |
| clean_mean_pitch | 7 | 196.2949 | 194.2252 | -2.0697 | [-5.3783, +0.8757] | Wilcoxon signed-rank | 0.6875 |
| clean_speech_dur_s | 7 | 6.9829 | 6.3657 | -0.6171 | [-1.1200, -0.1829] | Wilcoxon signed-rank | 0.0469 |
| clean_std_intensity | 7 | 14.1397 | 14.6922 | +0.5525 | [-0.1039, +1.2977] | Wilcoxon signed-rank | 0.1562 |
| clean_std_pitch | 7 | 37.0435 | 34.3262 | -2.7173 | [-9.1295, +3.0455] | Wilcoxon signed-rank | 1.0000 |
| clean_utmosv2 | 7 | 2.1645 | 2.0680 | -0.0965 | [-0.3222, +0.1510] | Wilcoxon signed-rank | 0.9375 |
| clean_wpm | 7 | 158.5049 | 171.0490 | +12.5441 | [-0.6290, +30.7006] | Wilcoxon signed-rank | 0.2969 |
| n_resp_intervals | 7 | 2.0000 | 1.1429 | -0.8571 | [-1.0000, -0.5714] | Wilcoxon signed-rank | 0.0312 |
| n_stop_intervals | 7 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 7 | 61.1981 | 16.7775 | -44.4206 | [-120.3927, +0.9384] | Wilcoxon signed-rank | 0.2969 |
| post_mean_pitch | 7 | 204.1971 | 227.9101 | +23.7130 | [-86.4104, +153.8162] | Wilcoxon signed-rank | 0.9375 |
| post_speech_dur_s | 7 | 2.9943 | 2.8571 | -0.1371 | [-1.5889, +1.1886] | Wilcoxon signed-rank | 0.8906 |
| post_std_intensity | 7 | 14.6004 | 10.5228 | -4.0776 | [-8.3190, -0.2681] | Wilcoxon signed-rank | 0.2188 |
| post_std_pitch | 7 | 45.1978 | 25.6602 | -19.5376 | [-39.8280, -0.7115] | Wilcoxon signed-rank | 0.1094 |
| post_utmosv2 | 7 | 2.1100 | 1.5909 | -0.5191 | [-1.0495, -0.0178] | Wilcoxon signed-rank | 0.2188 |
| post_wpm | 7 | 196.1040 | 142.7771 | -53.3269 | [-138.2210, +26.6763] | Wilcoxon signed-rank | 0.2188 |
| pre_mean_intensity | 7 | 62.5553 | 60.7150 | -1.8403 | [-3.2656, -0.8756] | Wilcoxon signed-rank | 0.0156 |
| pre_mean_pitch | 7 | 203.6643 | 201.4629 | -2.2014 | [-10.7653, +5.6735] | Wilcoxon signed-rank | 0.8125 |
| pre_speech_dur_s | 7 | 2.5371 | 3.0171 | +0.4800 | [-0.1486, +1.2457] | Wilcoxon signed-rank | 0.3125 |
| pre_std_intensity | 7 | 13.5939 | 14.4249 | +0.8311 | [-0.2706, +2.2949] | Wilcoxon signed-rank | 0.2969 |
| pre_std_pitch | 7 | 37.5028 | 37.8927 | +0.3900 | [-1.3704, +2.5034] | Wilcoxon signed-rank | 0.9375 |
| pre_utmosv2 | 7 | 1.9687 | 2.1082 | +0.1395 | [-0.0591, +0.3540] | Wilcoxon signed-rank | 0.3750 |
| pre_wpm | 7 | 177.9178 | 156.6611 | -21.2568 | [-49.5845, +5.3374] | Wilcoxon signed-rank | 0.2188 |
| resp_latency | 7 | 1.9834 | 2.8131 | +0.8297 | [+0.3954, +1.2320] | Wilcoxon signed-rank | 0.0781 |
| stop_latency | 7 | 0.3800 | 1.1754 | +0.7954 | [+0.5029, +1.0789] | Wilcoxon signed-rank | 0.0156 |

## v1.5/talking_to_other

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 8 | 0.6250 | 0.0000 | -0.6250 | [-0.8750, -0.2500] | McNemar exact (b=0, c=5) | 0.0625 |
| behavior_C_RESUME | 8 | 0.0000 | 0.6250 | +0.6250 | [+0.2500, +0.8750] | McNemar exact (b=5, c=0) | 0.0625 |
| behavior_C_UNCERTAIN_HANDLING | 8 | 0.1250 | 0.0000 | -0.1250 | [-0.3750, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 8 | 0.2500 | 0.3750 | +0.1250 | [-0.3750, +0.6250] | McNemar exact (b=3, c=2) | 1.0000 |
| clean_mean_intensity | 8 | 59.7329 | 59.7740 | +0.0411 | [-0.6621, +0.8174] | Wilcoxon signed-rank | 0.9453 |
| clean_mean_pitch | 8 | 199.1219 | 198.5867 | -0.5351 | [-5.0810, +3.4647] | Wilcoxon signed-rank | 1.0000 |
| clean_speech_dur_s | 8 | 7.1000 | 6.4500 | -0.6500 | [-1.1300, -0.1900] | Wilcoxon signed-rank | 0.0781 |
| clean_std_intensity | 8 | 14.6139 | 14.7017 | +0.0878 | [-0.6123, +0.7406] | Wilcoxon signed-rank | 0.8438 |
| clean_std_pitch | 8 | 41.7953 | 39.7314 | -2.0639 | [-6.8971, +3.2942] | Wilcoxon signed-rank | 0.5469 |
| clean_utmosv2 | 8 | 2.0903 | 2.0589 | -0.0314 | [-0.2104, +0.1103] | Wilcoxon signed-rank | 0.9453 |
| clean_wpm | 8 | 147.6677 | 158.5231 | +10.8554 | [-1.1734, +20.7115] | Wilcoxon signed-rank | 0.1094 |
| n_resp_intervals | 8 | 2.0000 | 1.1250 | -0.8750 | [-1.0000, -0.6250] | Wilcoxon signed-rank | 0.0156 |
| n_stop_intervals | 8 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 8 | 59.6631 | 60.1609 | +0.4978 | [-0.5313, +1.6595] | Wilcoxon signed-rank | 0.8438 |
| post_mean_pitch | 8 | 201.9459 | 192.4785 | -9.4674 | [-17.3072, -1.9517] | Wilcoxon signed-rank | 0.0547 |
| post_speech_dur_s | 8 | 3.0200 | 3.8600 | +0.8400 | [-0.5500, +2.2802] | Wilcoxon signed-rank | 0.3125 |
| post_std_intensity | 8 | 15.4444 | 14.7110 | -0.7334 | [-2.3734, +0.7045] | Wilcoxon signed-rank | 0.6406 |
| post_std_pitch | 8 | 40.9418 | 31.2344 | -9.7074 | [-25.1238, +5.7496] | Wilcoxon signed-rank | 0.3828 |
| post_utmosv2 | 8 | 2.0205 | 2.1272 | +0.1067 | [-0.1238, +0.3367] | Wilcoxon signed-rank | 0.5469 |
| post_wpm | 8 | 230.2260 | 154.3187 | -75.9073 | [-111.7096, -37.1162] | Wilcoxon signed-rank | 0.0156 |
| pre_mean_intensity | 8 | 60.5631 | 60.6029 | +0.0399 | [-1.0597, +1.1258] | Wilcoxon signed-rank | 1.0000 |
| pre_mean_pitch | 8 | 205.5824 | 207.8977 | +2.3153 | [-2.9907, +8.3570] | Wilcoxon signed-rank | 0.6406 |
| pre_speech_dur_s | 8 | 2.6000 | 2.9000 | +0.3000 | [-0.0800, +0.6800] | Wilcoxon signed-rank | 0.2500 |
| pre_std_intensity | 8 | 14.4946 | 12.9434 | -1.5512 | [-2.5577, -0.5504] | Wilcoxon signed-rank | 0.0391 |
| pre_std_pitch | 8 | 35.7405 | 42.4346 | +6.6940 | [-1.2296, +15.9182] | Wilcoxon signed-rank | 0.3828 |
| pre_utmosv2 | 8 | 1.8900 | 1.9041 | +0.0141 | [-0.1205, +0.1880] | Wilcoxon signed-rank | 0.7422 |
| pre_wpm | 8 | 142.3290 | 152.1174 | +9.7884 | [-7.6825, +28.3738] | Wilcoxon signed-rank | 0.4609 |
| resp_latency | 8 | 2.0620 | 3.0040 | +0.9420 | [+0.4839, +1.4340] | Wilcoxon signed-rank | 0.0078 |
| stop_latency | 8 | 0.4080 | 1.8120 | +1.4040 | [+1.2560, +1.5720] | Wilcoxon signed-rank | 0.0078 |

## v1.5/user_backchannel

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 8 | 0.1250 | 0.0000 | -0.1250 | [-0.3750, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_RESUME | 8 | 0.1250 | 0.2500 | +0.1250 | [-0.2500, +0.5000] | McNemar exact (b=2, c=1) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 8 | 0.3750 | 0.0000 | -0.3750 | [-0.7500, -0.1250] | McNemar exact (b=0, c=3) | 0.2500 |
| behavior_C_UNKNOWN | 8 | 0.3750 | 0.7500 | +0.3750 | [+0.0000, +0.7500] | McNemar exact (b=3, c=0) | 0.2500 |
| clean_mean_intensity | 8 | 61.1075 | 60.4919 | -0.6156 | [-1.1225, -0.0156] | Wilcoxon signed-rank | 0.0781 |
| clean_mean_pitch | 8 | 204.5569 | 203.3811 | -1.1758 | [-2.5245, +0.3130] | Wilcoxon signed-rank | 0.2500 |
| clean_speech_dur_s | 8 | 8.2800 | 7.3900 | -0.8900 | [-1.2900, -0.5100] | Wilcoxon signed-rank | 0.0078 |
| clean_std_intensity | 8 | 13.7419 | 14.3076 | +0.5657 | [+0.0470, +1.0406] | Wilcoxon signed-rank | 0.1094 |
| clean_std_pitch | 8 | 38.0275 | 37.9063 | -0.1211 | [-1.6208, +1.4868] | Wilcoxon signed-rank | 0.9453 |
| clean_utmosv2 | 8 | 2.0448 | 2.1287 | +0.0839 | [-0.0688, +0.2181] | Wilcoxon signed-rank | 0.3828 |
| clean_wpm | 8 | 169.2108 | 175.7951 | +6.5844 | [-7.4912, +21.7114] | Wilcoxon signed-rank | 0.4609 |
| n_resp_intervals | 8 | 2.0000 | 1.0000 | -1.0000 | [-1.0000, -1.0000] | Wilcoxon signed-rank | 0.0078 |
| n_stop_intervals | 8 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 8 | 59.6521 | 59.2430 | -0.4091 | [-1.0468, +0.2373] | Wilcoxon signed-rank | 0.3125 |
| post_mean_pitch | 8 | 202.7115 | 202.1177 | -0.5938 | [-6.9718, +5.5135] | Wilcoxon signed-rank | 0.9453 |
| post_speech_dur_s | 8 | 3.7000 | 5.0200 | +1.3200 | [+0.4200, +2.2200] | Wilcoxon signed-rank | 0.0312 |
| post_std_intensity | 8 | 14.9363 | 14.8485 | -0.0878 | [-1.1900, +1.0404] | Wilcoxon signed-rank | 0.8438 |
| post_std_pitch | 8 | 40.9111 | 37.4552 | -3.4559 | [-10.9099, +4.1394] | Wilcoxon signed-rank | 0.4609 |
| post_utmosv2 | 8 | 2.0937 | 2.0531 | -0.0406 | [-0.1737, +0.0857] | Wilcoxon signed-rank | 0.5469 |
| post_wpm | 8 | 229.9772 | 189.5118 | -40.4654 | [-68.5282, -9.7609] | Wilcoxon signed-rank | 0.0391 |
| pre_mean_intensity | 8 | 62.5141 | 63.4800 | +0.9659 | [-0.2895, +2.3048] | Wilcoxon signed-rank | 0.1484 |
| pre_mean_pitch | 8 | 211.3943 | 212.0813 | +0.6870 | [-3.5348, +4.6025] | Wilcoxon signed-rank | 0.9453 |
| pre_speech_dur_s | 8 | 2.9900 | 2.4200 | -0.5700 | [-0.9200, -0.2200] | Wilcoxon signed-rank | 0.0391 |
| pre_std_intensity | 8 | 12.4181 | 11.4678 | -0.9503 | [-2.0948, +0.1962] | Wilcoxon signed-rank | 0.1484 |
| pre_std_pitch | 8 | 42.9767 | 40.6937 | -2.2830 | [-6.4023, +2.3504] | Wilcoxon signed-rank | 0.5469 |
| pre_utmosv2 | 8 | 2.0977 | 2.1018 | +0.0041 | [-0.2135, +0.2573] | Wilcoxon signed-rank | 0.7422 |
| pre_wpm | 8 | 172.8048 | 159.3586 | -13.4462 | [-23.7869, -1.1211] | Wilcoxon signed-rank | 0.1094 |
| resp_latency | 8 | 1.6140 | 2.4560 | +0.8420 | [+0.4380, +1.1660] | Wilcoxon signed-rank | 0.0156 |
| stop_latency | 8 | 0.4160 | 0.6400 | +0.2240 | [+0.1280, +0.3200] | Wilcoxon signed-rank | 0.0156 |

## v1.5/user_interruption

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 7 | 0.5714 | 0.0000 | -0.5714 | [-0.8571, -0.1429] | McNemar exact (b=0, c=4) | 0.1250 |
| behavior_C_RESUME | 7 | 0.0000 | 0.5714 | +0.5714 | [+0.1429, +0.8571] | McNemar exact (b=4, c=0) | 0.1250 |
| behavior_C_UNCERTAIN_HANDLING | 7 | 0.1429 | 0.0000 | -0.1429 | [-0.4286, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_UNKNOWN | 7 | 0.2857 | 0.4286 | +0.1429 | [-0.4286, +0.7143] | McNemar exact (b=3, c=2) | 1.0000 |
| clean_mean_intensity | 7 | 59.8362 | 59.7671 | -0.0691 | [-0.8540, +0.7655] | Wilcoxon signed-rank | 0.9375 |
| clean_mean_pitch | 7 | 200.8752 | 202.9847 | +2.1094 | [+0.4682, +4.0362] | Wilcoxon signed-rank | 0.2188 |
| clean_speech_dur_s | 7 | 11.2229 | 10.2286 | -0.9943 | [-1.3829, -0.6514] | Wilcoxon signed-rank | 0.0156 |
| clean_std_intensity | 7 | 15.0419 | 15.2729 | +0.2310 | [-0.4051, +0.8572] | Wilcoxon signed-rank | 0.4688 |
| clean_std_pitch | 7 | 38.9321 | 43.4016 | +4.4695 | [-0.1080, +8.7596] | Wilcoxon signed-rank | 0.1094 |
| clean_utmosv2 | 7 | 2.1069 | 2.1105 | +0.0036 | [-0.2185, +0.1946] | Wilcoxon signed-rank | 0.9375 |
| clean_wpm | 7 | 189.9298 | 188.2174 | -1.7124 | [-12.3513, +10.5813] | Wilcoxon signed-rank | 0.8125 |
| n_resp_intervals | 7 | 2.0000 | 1.1429 | -0.8571 | [-1.0000, -0.5714] | Wilcoxon signed-rank | 0.0312 |
| n_stop_intervals | 7 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 7 | 60.1533 | 60.6984 | +0.5451 | [-3.3636, +4.4747] | Wilcoxon signed-rank | 0.4688 |
| post_mean_pitch | 7 | 215.5753 | 209.2466 | -6.3287 | [-30.8667, +15.9691] | Wilcoxon signed-rank | 0.8125 |
| post_speech_dur_s | 7 | 2.2971 | 2.5829 | +0.2857 | [-1.2686, +2.1029] | Wilcoxon signed-rank | 1.0000 |
| post_std_intensity | 7 | 14.0350 | 13.7943 | -0.2408 | [-4.1963, +4.5876] | Wilcoxon signed-rank | 0.6875 |
| post_std_pitch | 7 | 52.6876 | 37.0423 | -15.6453 | [-50.0900, +18.2745] | Wilcoxon signed-rank | 0.5781 |
| post_utmosv2 | 7 | 1.8256 | 1.9317 | +0.1061 | [-0.1333, +0.3718] | Wilcoxon signed-rank | 0.4688 |
| post_wpm | 7 | 169.3898 | 267.0771 | +97.6873 | [-44.5021, +268.7790] | Wilcoxon signed-rank | 0.4688 |
| pre_mean_intensity | 7 | 61.3272 | 59.4093 | -1.9180 | [-2.8598, -0.9702] | Wilcoxon signed-rank | 0.0156 |
| pre_mean_pitch | 7 | 210.7825 | 205.7810 | -5.0014 | [-12.4372, +1.8410] | Wilcoxon signed-rank | 0.2188 |
| pre_speech_dur_s | 7 | 4.9486 | 5.4514 | +0.5029 | [-1.2114, +1.6574] | Wilcoxon signed-rank | 0.2969 |
| pre_std_intensity | 7 | 13.8050 | 15.1286 | +1.3237 | [+0.5055, +2.0308] | Wilcoxon signed-rank | 0.0469 |
| pre_std_pitch | 7 | 51.9268 | 42.2109 | -9.7158 | [-13.3250, -6.0092] | Wilcoxon signed-rank | 0.0156 |
| pre_utmosv2 | 7 | 2.1480 | 2.1471 | -0.0009 | [-0.2276, +0.2186] | Wilcoxon signed-rank | 1.0000 |
| pre_wpm | 7 | 190.2980 | 186.4236 | -3.8745 | [-32.1122, +30.5176] | Wilcoxon signed-rank | 0.6875 |
| resp_latency | 7 | 2.0086 | 2.5160 | +0.5074 | [-0.3474, +1.2571] | Wilcoxon signed-rank | 0.3750 |
| stop_latency | 7 | 0.3937 | 2.6337 | +2.2400 | [+1.6503, +2.7520] | Wilcoxon signed-rank | 0.0156 |

## v1/candor_pause_handling

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.1000 | 0.1000 | +0.0000 | [-0.3000, +0.3000] | McNemar exact (b=1, c=1) | 1.0000 |
| n_words | 10 | 0.7000 | 1.0000 | +0.3000 | [-2.1000, +3.0000] | n/a (<6 non-zero pairs) | - |
| premature_llm_start | 10 | 0.3000 | 0.1000 | -0.2000 | [-0.5000, +0.0000] | McNemar exact (b=0, c=2) | 0.5000 |
| premature_turn_end | 10 | 0.4000 | 0.1000 | -0.3000 | [-0.6000, +0.0000] | McNemar exact (b=0, c=3) | 0.2500 |

## v1/candor_turn_taking

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.8000 | 0.1000 | -0.7000 | [-1.0000, -0.4000] | McNemar exact (b=0, c=7) | 0.0156 |
| latency | 1 | 0.0000 | 2.0400 | +2.0400 | [+2.0400, +2.0400] | n/a (<6 non-zero pairs) | - |
| latency_raw | 1 | -2.1200 | 2.0400 | +4.1600 | [+4.1600, +4.1600] | n/a (<6 non-zero pairs) | - |

## System one

| task | run | judgments | outcomes | latency p50 / p90 (ms, ok) | hedged | actions |
|---|---|---|---|---|---|---|
| v1.5/background_speech | A | - | - | - | - | - |
| v1.5/background_speech | B | 62 | ok 45, stale 13, timeout 4 | 390 / 844 | 45.2% | drop_backchannel 1, drop_side_talk 8, end_turn 8, fallback 3, hold_backchannel 3, interrupt 2, keep_listening 41 |
| v1.5/talking_to_other | A | - | - | - | - | - |
| v1.5/talking_to_other | B | 50 | ok 43, stale 6, timeout 1 | 343 / 718 | 26.0% | drop_backchannel 5, drop_side_talk 14, end_turn 10, hold_backchannel 7, keep_listening 17 |
| v1.5/user_backchannel | A | - | - | - | - | - |
| v1.5/user_backchannel | B | 50 | ok 36, stale 14 | 308 / 872 | 40.4% | drop_backchannel 9, drop_side_talk 3, end_turn 9, fallback 1, hold_backchannel 1, keep_listening 29 |
| v1.5/user_interruption | A | - | - | - | - | - |
| v1.5/user_interruption | B | 75 | ok 60, stale 14, timeout 1 | 291 / 839 | 32.4% | drop_backchannel 11, drop_side_talk 3, end_turn 12, fallback 3, hold_backchannel 15, interrupt 6, keep_listening 39 |
| v1/candor_pause_handling | A | - | - | - | - | - |
| v1/candor_pause_handling | B | 114 | ok 86, stale 28 | 318 / 715 | 38.6% | drop_backchannel 2, drop_side_talk 24, end_turn 1, hold_backchannel 2, keep_listening 86 |
| v1/candor_turn_taking | A | - | - | - | - | - |
| v1/candor_turn_taking | B | 75 | ok 69, stale 6 | 269 / 605 | 24.0% | drop_side_talk 20, end_turn 1, fallback 3, keep_listening 54 |
