# Paired comparison: A=`system-one-telephony` (baseline) vs B=`system-one-v2-telephony`

Diff = B - A. CI: paired percentile bootstrap (10k, seed 0). p: see test column. Uncorrected for multiple comparisons.

## Warnings

- **Same variant `system_one` in A and B**: this is not a design comparison (only run-to-run noise or non-variant config changes).
- v1.5/background_speech: dropped 4 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/talking_to_other: dropped 2 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_backchannel: dropped 2 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only
- v1.5/user_interruption: dropped 1 of 10 shared pairs (overlap invalid or unknown in A or B); pairing valid-in-both only

## v1.5/background_speech

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 6 | 0.1667 | 0.0000 | -0.1667 | [-0.5000, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| behavior_C_RESUME | 6 | 0.1667 | 0.5000 | +0.3333 | [+0.0000, +0.6667] | McNemar exact (b=2, c=0) | 0.5000 |
| behavior_C_UNCERTAIN_HANDLING | 6 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNKNOWN | 6 | 0.6667 | 0.5000 | -0.1667 | [-0.6667, +0.3333] | McNemar exact (b=1, c=2) | 1.0000 |
| clean_mean_intensity | 6 | 59.9289 | 59.8037 | -0.1252 | [-0.7422, +0.6275] | Wilcoxon signed-rank | 0.4375 |
| clean_mean_pitch | 6 | 193.2256 | 199.7950 | +6.5694 | [+1.3169, +14.1397] | Wilcoxon signed-rank | 0.0625 |
| clean_speech_dur_s | 6 | 6.9867 | 7.1200 | +0.1333 | [-0.2933, +0.4667] | Wilcoxon signed-rank | 0.4375 |
| clean_std_intensity | 6 | 14.8290 | 14.8202 | -0.0088 | [-0.6047, +0.6927] | Wilcoxon signed-rank | 1.0000 |
| clean_std_pitch | 6 | 33.9915 | 39.9650 | +5.9735 | [+0.7311, +12.8608] | Wilcoxon signed-rank | 0.1562 |
| clean_utmosv2 | 6 | 2.0537 | 2.0533 | -0.0004 | [-0.1300, +0.1312] | Wilcoxon signed-rank | 0.8438 |
| clean_wpm | 6 | 173.0421 | 167.2161 | -5.8260 | [-24.1551, +12.0861] | Wilcoxon signed-rank | 0.4375 |
| n_resp_intervals | 6 | 1.1667 | 1.1667 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| n_stop_intervals | 6 | 1.0000 | 1.1667 | +0.1667 | [+0.0000, +0.5000] | n/a (<6 non-zero pairs) | - |
| post_mean_intensity | 6 | 17.8292 | 48.7345 | +30.9052 | [-1.8170, +94.9779] | Wilcoxon signed-rank | 0.6875 |
| post_mean_pitch | 6 | 171.1881 | 243.0418 | +71.8538 | [-23.2962, +234.5946] | Wilcoxon signed-rank | 0.5625 |
| post_speech_dur_s | 6 | 3.2800 | 4.0667 | +0.7867 | [-0.1600, +2.4400] | n/a (<6 non-zero pairs) | - |
| post_std_intensity | 6 | 11.4641 | 14.9886 | +3.5246 | [+0.5234, +8.9366] | Wilcoxon signed-rank | 0.0625 |
| post_std_pitch | 6 | 29.9255 | 28.9072 | -1.0182 | [-5.1830, +3.7757] | n/a (<6 non-zero pairs) | - |
| post_utmosv2 | 6 | 1.7418 | 1.8034 | +0.0615 | [-0.1916, +0.3351] | n/a (<6 non-zero pairs) | - |
| post_wpm | 6 | 135.3232 | 150.8675 | +15.5442 | [+0.8986, +32.0046] | n/a (<6 non-zero pairs) | - |
| pre_mean_intensity | 6 | 60.2794 | 61.1452 | +0.8657 | [-0.5369, +2.2992] | Wilcoxon signed-rank | 0.5625 |
| pre_mean_pitch | 6 | 202.5288 | 201.6601 | -0.8687 | [-5.1798, +3.4583] | Wilcoxon signed-rank | 0.6875 |
| pre_speech_dur_s | 6 | 3.1067 | 2.7333 | -0.3733 | [-0.6800, -0.1333] | Wilcoxon signed-rank | 0.0625 |
| pre_std_intensity | 6 | 14.9218 | 14.2895 | -0.6323 | [-2.0745, +0.6760] | Wilcoxon signed-rank | 0.6875 |
| pre_std_pitch | 6 | 38.0197 | 31.9843 | -6.0354 | [-9.1609, -2.4773] | Wilcoxon signed-rank | 0.0625 |
| pre_utmosv2 | 6 | 2.1282 | 2.0355 | -0.0928 | [-0.1927, +0.0409] | Wilcoxon signed-rank | 0.4375 |
| pre_wpm | 6 | 158.5777 | 167.2489 | +8.6712 | [-8.5650, +28.8233] | Wilcoxon signed-rank | 0.4375 |
| resp_latency | 6 | 2.7587 | 2.7373 | -0.0213 | [-0.2827, +0.2720] | Wilcoxon signed-rank | 0.8438 |
| stop_latency | 6 | 1.1320 | 0.9693 | -0.1627 | [-0.3335, +0.0000] | n/a (<6 non-zero pairs) | - |

## v1.5/talking_to_other

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 8 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_RESUME | 8 | 0.6250 | 0.2500 | -0.3750 | [-0.7500, -0.1250] | McNemar exact (b=0, c=3) | 0.2500 |
| behavior_C_UNCERTAIN_HANDLING | 8 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNKNOWN | 8 | 0.3750 | 0.7500 | +0.3750 | [+0.1250, +0.7500] | McNemar exact (b=3, c=0) | 0.2500 |
| clean_mean_intensity | 8 | 59.7740 | 59.7057 | -0.0683 | [-1.0611, +0.8701] | Wilcoxon signed-rank | 0.9453 |
| clean_mean_pitch | 8 | 198.5867 | 200.2777 | +1.6909 | [-2.7280, +7.2648] | Wilcoxon signed-rank | 0.8438 |
| clean_speech_dur_s | 8 | 6.4500 | 6.7600 | +0.3100 | [-0.2100, +0.7800] | Wilcoxon signed-rank | 0.3672 |
| clean_std_intensity | 8 | 14.7017 | 14.9483 | +0.2466 | [-0.6490, +1.0814] | Wilcoxon signed-rank | 0.6406 |
| clean_std_pitch | 8 | 39.7314 | 39.7266 | -0.0048 | [-5.8643, +5.2109] | Wilcoxon signed-rank | 0.8438 |
| clean_utmosv2 | 8 | 2.0589 | 2.0498 | -0.0091 | [-0.1746, +0.1459] | Wilcoxon signed-rank | 0.9453 |
| clean_wpm | 8 | 158.5231 | 149.8465 | -8.6766 | [-19.1567, +4.0895] | Wilcoxon signed-rank | 0.2500 |
| n_resp_intervals | 8 | 1.1250 | 1.0000 | -0.1250 | [-0.3750, +0.0000] | n/a (<6 non-zero pairs) | - |
| n_stop_intervals | 8 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 8 | 60.1609 | 28.4570 | -31.7039 | [-96.6296, +1.6624] | Wilcoxon signed-rank | 1.0000 |
| post_mean_pitch | 8 | 192.4785 | 170.0416 | -22.4369 | [-65.7795, +2.3377] | Wilcoxon signed-rank | 0.3125 |
| post_speech_dur_s | 8 | 3.8600 | 3.6000 | -0.2600 | [-0.6103, +0.0800] | Wilcoxon signed-rank | 0.2188 |
| post_std_intensity | 8 | 14.7110 | 12.0911 | -2.6199 | [-6.6207, +0.1943] | Wilcoxon signed-rank | 0.1953 |
| post_std_pitch | 8 | 31.2344 | 32.2370 | +1.0026 | [-8.6164, +9.7224] | Wilcoxon signed-rank | 0.9453 |
| post_utmosv2 | 8 | 2.1272 | 1.9515 | -0.1757 | [-0.5311, +0.1182] | Wilcoxon signed-rank | 0.4609 |
| post_wpm | 8 | 154.3187 | 134.5493 | -19.7694 | [-60.5750, +10.6018] | Wilcoxon signed-rank | 0.5625 |
| pre_mean_intensity | 8 | 60.6029 | 60.0490 | -0.5539 | [-1.5653, +0.3889] | Wilcoxon signed-rank | 0.5469 |
| pre_mean_pitch | 8 | 207.8977 | 201.4920 | -6.4057 | [-13.4583, +0.0695] | Wilcoxon signed-rank | 0.1953 |
| pre_speech_dur_s | 8 | 2.9000 | 3.1200 | +0.2200 | [-0.2600, +0.6900] | Wilcoxon signed-rank | 0.6172 |
| pre_std_intensity | 8 | 12.9434 | 14.1998 | +1.2563 | [+0.2486, +2.2286] | Wilcoxon signed-rank | 0.0781 |
| pre_std_pitch | 8 | 42.4346 | 38.3253 | -4.1092 | [-13.8143, +5.0164] | Wilcoxon signed-rank | 0.6406 |
| pre_utmosv2 | 8 | 1.9041 | 1.8120 | -0.0921 | [-0.2037, +0.0148] | Wilcoxon signed-rank | 0.1953 |
| pre_wpm | 8 | 152.1174 | 150.2254 | -1.8920 | [-14.3372, +12.2097] | Wilcoxon signed-rank | 0.9453 |
| resp_latency | 8 | 3.0040 | 2.9840 | -0.0200 | [-0.4120, +0.3801] | Wilcoxon signed-rank | 0.7422 |
| stop_latency | 8 | 1.8120 | 1.7880 | -0.0240 | [-0.0720, +0.0000] | n/a (<6 non-zero pairs) | - |

## v1.5/user_backchannel

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 8 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_RESUME | 8 | 0.2500 | 0.3750 | +0.1250 | [-0.2500, +0.5000] | McNemar exact (b=2, c=1) | 1.0000 |
| behavior_C_UNCERTAIN_HANDLING | 8 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNKNOWN | 8 | 0.7500 | 0.6250 | -0.1250 | [-0.5000, +0.2500] | McNemar exact (b=1, c=2) | 1.0000 |
| clean_mean_intensity | 8 | 60.4919 | 60.1287 | -0.3632 | [-1.6003, +0.8323] | Wilcoxon signed-rank | 0.7422 |
| clean_mean_pitch | 8 | 203.3811 | 204.0545 | +0.6734 | [-2.5153, +4.1079] | Wilcoxon signed-rank | 0.8438 |
| clean_speech_dur_s | 8 | 7.3900 | 7.4900 | +0.1000 | [-0.4100, +0.6200] | Wilcoxon signed-rank | 0.6406 |
| clean_std_intensity | 8 | 14.3076 | 14.3708 | +0.0632 | [-0.8703, +1.1454] | Wilcoxon signed-rank | 0.8438 |
| clean_std_pitch | 8 | 37.9063 | 39.5313 | +1.6250 | [-2.3740, +5.4239] | Wilcoxon signed-rank | 0.5469 |
| clean_utmosv2 | 8 | 2.1287 | 2.0965 | -0.0322 | [-0.2086, +0.1135] | Wilcoxon signed-rank | 0.8438 |
| clean_wpm | 8 | 175.7951 | 167.6998 | -8.0954 | [-26.4547, +8.8810] | Wilcoxon signed-rank | 0.5469 |
| n_resp_intervals | 8 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| n_stop_intervals | 8 | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 8 | 59.2430 | 59.9853 | +0.7422 | [+0.0425, +1.3758] | Wilcoxon signed-rank | 0.0781 |
| post_mean_pitch | 8 | 202.1177 | 200.5387 | -1.5789 | [-5.2961, +2.7240] | Wilcoxon signed-rank | 0.4609 |
| post_speech_dur_s | 8 | 5.0200 | 5.0600 | +0.0400 | [-0.1700, +0.2400] | Wilcoxon signed-rank | 0.8750 |
| post_std_intensity | 8 | 14.8485 | 14.6665 | -0.1820 | [-1.2952, +0.9517] | Wilcoxon signed-rank | 0.7422 |
| post_std_pitch | 8 | 37.4552 | 35.6712 | -1.7840 | [-5.7843, +1.9554] | Wilcoxon signed-rank | 0.5469 |
| post_utmosv2 | 8 | 2.0531 | 2.0241 | -0.0290 | [-0.1594, +0.1172] | Wilcoxon signed-rank | 0.7422 |
| post_wpm | 8 | 189.5118 | 184.8711 | -4.6408 | [-21.5955, +11.2831] | Wilcoxon signed-rank | 0.7422 |
| pre_mean_intensity | 8 | 63.4800 | 63.6808 | +0.2008 | [-0.3412, +0.7410] | Wilcoxon signed-rank | 0.6406 |
| pre_mean_pitch | 8 | 212.0813 | 210.3904 | -1.6909 | [-5.6914, +2.6729] | Wilcoxon signed-rank | 0.4609 |
| pre_speech_dur_s | 8 | 2.4200 | 2.1700 | -0.2500 | [-0.6000, +0.1400] | Wilcoxon signed-rank | 0.3438 |
| pre_std_intensity | 8 | 11.4678 | 11.7759 | +0.3081 | [-0.1299, +0.7081] | Wilcoxon signed-rank | 0.2500 |
| pre_std_pitch | 8 | 40.6937 | 38.5918 | -2.1019 | [-7.7637, +2.7379] | Wilcoxon signed-rank | 0.7422 |
| pre_utmosv2 | 8 | 2.1018 | 2.0222 | -0.0796 | [-0.2659, +0.1104] | Wilcoxon signed-rank | 0.3828 |
| pre_wpm | 8 | 159.3586 | 161.5507 | +2.1921 | [-19.5720, +20.6919] | Wilcoxon signed-rank | 0.8125 |
| resp_latency | 8 | 2.4560 | 2.6800 | +0.2240 | [-0.1800, +0.5840] | Wilcoxon signed-rank | 0.3125 |
| stop_latency | 8 | 0.6400 | 0.6400 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |

## v1.5/user_interruption

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| behavior_C_RESPOND | 9 | 0.1111 | 0.5556 | +0.4444 | [+0.1111, +0.7778] | McNemar exact (b=4, c=0) | 0.1250 |
| behavior_C_RESUME | 9 | 0.4444 | 0.1111 | -0.3333 | [-0.6667, -0.1111] | McNemar exact (b=0, c=3) | 0.2500 |
| behavior_C_UNCERTAIN_HANDLING | 9 | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| behavior_C_UNKNOWN | 9 | 0.4444 | 0.3333 | -0.1111 | [-0.3333, +0.0000] | McNemar exact (b=0, c=1) | 1.0000 |
| clean_mean_intensity | 9 | 59.6883 | 59.9329 | +0.2447 | [-0.4679, +0.9371] | Wilcoxon signed-rank | 0.5703 |
| clean_mean_pitch | 9 | 203.2147 | 202.2411 | -0.9735 | [-4.3119, +1.8631] | Wilcoxon signed-rank | 0.8203 |
| clean_speech_dur_s | 9 | 9.6444 | 10.7022 | +1.0578 | [+0.1687, +2.1867] | Wilcoxon signed-rank | 0.0547 |
| clean_std_intensity | 9 | 15.3055 | 14.8305 | -0.4750 | [-1.0710, +0.1295] | Wilcoxon signed-rank | 0.3008 |
| clean_std_pitch | 9 | 42.8312 | 42.1427 | -0.6884 | [-4.7550, +3.0620] | Wilcoxon signed-rank | 0.6523 |
| clean_utmosv2 | 9 | 2.0798 | 2.0794 | -0.0005 | [-0.2004, +0.2388] | Wilcoxon signed-rank | 0.6523 |
| clean_wpm | 9 | 191.1771 | 196.3105 | +5.1334 | [-2.7484, +14.1413] | Wilcoxon signed-rank | 0.6523 |
| n_resp_intervals | 9 | 1.2222 | 2.0000 | +0.7778 | [+0.4444, +1.0000] | Wilcoxon signed-rank | 0.0156 |
| n_stop_intervals | 9 | 1.1111 | 1.1111 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| post_mean_intensity | 9 | 59.7453 | 58.4827 | -1.2626 | [-4.2730, +1.7900] | Wilcoxon signed-rank | 0.6523 |
| post_mean_pitch | 9 | 204.5044 | 219.7984 | +15.2941 | [-12.2964, +44.1671] | Wilcoxon signed-rank | 0.4258 |
| post_speech_dur_s | 9 | 2.6133 | 1.8667 | -0.7467 | [-2.0000, +0.4000] | Wilcoxon signed-rank | 0.3594 |
| post_std_intensity | 9 | 14.5806 | 16.2686 | +1.6880 | [-0.9607, +4.6883] | Wilcoxon signed-rank | 0.4258 |
| post_std_pitch | 9 | 39.0340 | 43.9202 | +4.8861 | [-18.4030, +26.2762] | Wilcoxon signed-rank | 0.7344 |
| post_utmosv2 | 9 | 1.8709 | 1.8898 | +0.0190 | [-0.2497, +0.2542] | Wilcoxon signed-rank | 0.7344 |
| post_wpm | 9 | 261.1989 | 153.9589 | -107.2400 | [-254.7115, +15.5258] | Wilcoxon signed-rank | 0.3008 |
| pre_mean_intensity | 9 | 59.7548 | 59.6573 | -0.0974 | [-1.2378, +0.7149] | Wilcoxon signed-rank | 0.8203 |
| pre_mean_pitch | 9 | 206.4341 | 206.8333 | +0.3992 | [-7.4126, +9.1914] | Wilcoxon signed-rank | 1.0000 |
| pre_speech_dur_s | 9 | 5.3511 | 5.2267 | -0.1244 | [-1.5911, +1.6444] | Wilcoxon signed-rank | 0.7344 |
| pre_std_intensity | 9 | 15.1327 | 14.9217 | -0.2110 | [-1.1517, +0.9572] | Wilcoxon signed-rank | 0.3008 |
| pre_std_pitch | 9 | 41.6176 | 44.7687 | +3.1511 | [-2.4792, +9.4071] | Wilcoxon signed-rank | 0.3594 |
| pre_utmosv2 | 9 | 2.1126 | 2.0507 | -0.0619 | [-0.1981, +0.0724] | Wilcoxon signed-rank | 0.3008 |
| pre_wpm | 9 | 187.2183 | 187.3221 | +0.1038 | [-25.3923, +21.7159] | Wilcoxon signed-rank | 0.7344 |
| resp_latency | 9 | 2.5089 | 2.5978 | +0.0889 | [-0.4818, +0.6507] | Wilcoxon signed-rank | 0.9102 |
| stop_latency | 9 | 2.5293 | 1.5373 | -0.9920 | [-1.6604, -0.1956] | Wilcoxon signed-rank | 0.0781 |

## v1/candor_pause_handling

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.1000 | 0.2000 | +0.1000 | [+0.0000, +0.3000] | McNemar exact (b=1, c=0) | 1.0000 |
| n_words | 10 | 1.0000 | 2.5000 | +1.5000 | [-0.3000, +4.8000] | n/a (<6 non-zero pairs) | - |
| premature_llm_start | 10 | 0.1000 | 0.1000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |
| premature_turn_end | 10 | 0.1000 | 0.1000 | +0.0000 | [+0.0000, +0.0000] | n/a (identical) | 1.0000 |

## v1/candor_turn_taking

| metric | n pairs | mean A | mean B | diff (B-A) | 95% CI | test | p |
|---|---|---|---|---|---|---|---|
| TOR | 10 | 0.1000 | 0.8000 | +0.7000 | [+0.4000, +1.0000] | McNemar exact (b=7, c=0) | 0.0156 |
| latency | 1 | 2.0400 | 1.8800 | -0.1600 | [-0.1600, -0.1600] | n/a (<6 non-zero pairs) | - |
| latency_raw | 1 | 2.0400 | 1.8800 | -0.1600 | [-0.1600, -0.1600] | n/a (<6 non-zero pairs) | - |

## System one

| task | run | judgments | outcomes | latency p50 / p90 (ms, ok) | hedged | actions |
|---|---|---|---|---|---|---|
| v1.5/background_speech | A | 62 | ok 45, stale 13, timeout 4 | 390 / 844 | 45.2% | drop_backchannel 1, drop_side_talk 8, end_turn 8, fallback 3, hold_backchannel 3, interrupt 2, keep_listening 41 |
| v1.5/background_speech | B | 46 | ok 39, stale 7 | 171 / 628 | 26.7% | drop_backchannel 7, drop_side_talk 4, end_turn 14, hold_backchannel 10, interrupt 4, keep_listening 17, open_turn 1 |
| v1.5/talking_to_other | A | 50 | ok 43, stale 6, timeout 1 | 343 / 718 | 26.0% | drop_backchannel 5, drop_side_talk 14, end_turn 10, hold_backchannel 7, keep_listening 17 |
| v1.5/talking_to_other | B | 51 | ok 45, stale 6 | 210 / 638 | 23.5% | drop_backchannel 1, drop_side_talk 10, end_turn 10, hold_backchannel 16, keep_listening 15 |
| v1.5/user_backchannel | A | 50 | ok 36, stale 14 | 308 / 872 | 40.4% | drop_backchannel 9, drop_side_talk 3, end_turn 9, fallback 1, hold_backchannel 1, keep_listening 29 |
| v1.5/user_backchannel | B | 51 | ok 39, stale 10, timeout 2 | 192 / 604 | 31.4% | drop_backchannel 13, drop_side_talk 1, end_turn 9, fallback 1, hold_backchannel 3, keep_listening 28 |
| v1.5/user_interruption | A | 75 | ok 60, stale 14, timeout 1 | 291 / 839 | 32.4% | drop_backchannel 11, drop_side_talk 3, end_turn 12, fallback 3, hold_backchannel 15, interrupt 6, keep_listening 39 |
| v1.5/user_interruption | B | 71 | ok 63, stale 6, timeout 2 | 203 / 590 | 16.9% | drop_backchannel 5, end_turn 18, fallback 3, hold_backchannel 8, interrupt 11, keep_listening 36 |
| v1/candor_pause_handling | A | 114 | ok 86, stale 28 | 318 / 715 | 38.6% | drop_backchannel 2, drop_side_talk 24, end_turn 1, hold_backchannel 2, keep_listening 86 |
| v1/candor_pause_handling | B | 113 | ok 95, stale 18 | 197 / 615 | 25.0% | drop_backchannel 4, drop_side_talk 4, end_turn 5, fallback 1, hold_backchannel 6, interrupt 1, keep_listening 97 |
| v1/candor_turn_taking | A | 75 | ok 69, stale 6 | 269 / 605 | 24.0% | drop_side_talk 20, end_turn 1, fallback 3, keep_listening 54 |
| v1/candor_turn_taking | B | 74 | ok 69, stale 5 | 164 / 440 | 13.5% | drop_backchannel 1, drop_side_talk 6, end_turn 7, fallback 2, hold_backchannel 5, keep_listening 59 |
