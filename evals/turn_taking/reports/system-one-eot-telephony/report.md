# FDB evaluation: system-one-eot-telephony

- evaluated at: 2026-11-10T12:38:11+00:00
- eval metrics mode: `all`; device: `auto`
- judge: {"enabled": true, "provider": "anthropic", "model": "claude-sonnet-5-5"}
- upstream: Full-Duplex-Bench @ `3e799c45a045256f47d5f1c9cda90157e2d2ec9e` + evals/turn_taking/scoring/patches/fdb.patch

## agent_resolved

```json
{
  "stt_provider": "assemblyai",
  "tts_provider": "assemblyai",
  "anthropic_model": "claude-haiku-5-5",
  "language": "en",
  "voice_id": "(pipecat default)",
  "audio_profile": "telephony",
  "variant": "system_one_eot",
  "bench_agent_version": "1",
  "bench_agent_fingerprint": "c05110edaeed",
  "tools": "control_device,manage_timers,calendar,send_message,read_messages,play_media,add_note,lookup_info",
  "variant_extra_instructions": "",
  "variant_params": "{\"classification_timeout\": 1.5, \"hedge_after_secs\": 0.45, \"long_timeout\": 10.0, \"model\": \"clef-flash\", \"short_timeout\": 5.0}"
}
```

## v1/candor_pause_handling  (upstream task: `pause_handling`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.000 | 0.000 | 0.000 |
| n_words | 10 | 0.000 | 0.000 | 0.000 |
| premature_turn_end | 10 | 0.200 | 0.000 | 1.000 |
| premature_llm_start | 10 | 0.200 | 0.000 | 1.000 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `n_words`: Number of ASR words in the agent's output.
- `premature_turn_end`: Pause handling: 1 if the design tried to take the turn during the pause even if no audio came out (a user_turn.stopped event in [pause start - 0.3 s, pause end + 0.5 s]).
- `premature_llm_start`: Pause handling: 1 if an llm.text event followed that premature stop (up to pause end + 2.5 s), i.e. the LLM actually started answering.

System one:

- samples with system1 events: 10/10; judgments: 50; outcomes: cancelled 28, ok 22
- latency over ok calls (ms): p50 364, p90 811; hedged share: 42.4%

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.00000 | 0.00000 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | n_words | premature_turn_end | premature_llm_start |
|---|---|---|---|---|
| 123 | 0 | 0 | 0 | 0 |
| 139 | 0 | 0 | 0 | 0 |
| 141 | 0 | 0 | 0 | 0 |
| 154 | 0 | 0 | 0 | 0 |
| 172 | 0 | 0 | 0 | 0 |
| 200 | 0 | 0 | 0 | 0 |
| 37 | 0 | 0 | 0 | 0 |
| 44 | 0 | 0 | 1 | 1 |
| 6 | 0 | 0 | 1 | 1 |
| 68 | 0 | 0 | 0 | 0 |

Timing: {"total_s": 18.0, "asr": [{"model_load_s": 2.74, "transcribe_s": 10.57, "audio_s": 115.04, "files": 10, "wall_s": 17.67, "audio_name": "output.wav"}], "eval_s": {"pause_handling": 0.3}}

## v1/candor_turn_taking  (upstream task: `smooth_turn_taking`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.800 | 1.000 | 1.000 |
| latency_raw | 8 | 3.646 | 4.025 | 4.375 |
| latency | 8 | 3.646 | 4.025 | 4.375 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `latency_raw`: Same as latency but unclamped (negative = agent started before the user finished).
- `latency`: Seconds from the user turn/interruption end to the agent's first word, clamped at 0; only samples with TOR=1.

System one:

- samples with system1 events: 10/10; judgments: 29; outcomes: cancelled 14, ok 15
- latency over ok calls (ms): p50 496, p90 916; hedged share: 40.0%

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.80000 | 0.80000 | yes |
| latency | 3.64625 | 3.64625 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | latency_raw | latency |
|---|---|---|---|
| 1 | 1 | 2.290 | 2.290 |
| 10 | 1 | 4.010 | 4.010 |
| 105 | 1 | 4.300 | 4.300 |
| 113 | 1 | 4.550 | 4.550 |
| 115 | 0 | - | - |
| 17 | 1 | 4.040 | 4.040 |
| 18 | 1 | 1.800 | 1.800 |
| 32 | 0 | - | - |
| 53 | 1 | 4.210 | 4.210 |
| 69 | 1 | 3.970 | 3.970 |

Timing: {"total_s": 17.3, "asr": [{"model_load_s": 2.59, "transcribe_s": 10.71, "audio_s": 125.0, "files": 10, "wall_s": 17.03, "audio_name": "output.wav"}], "eval_s": {"smooth_turn_taking": 0.3}}

## v1.5/background_speech  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.396 | 0.444 | 0.508 | 10 | 0.396 | 0.444 | 0.508 |
| resp_latency | 10 | 2.415 | 2.292 | 2.935 | 10 | 2.415 | 2.292 | 2.935 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.600 | 2.000 | 2.000 | 10 | 1.600 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 1.884 | 1.952 | 2.102 | 10 | 1.884 | 1.952 | 2.102 |
| pre_wpm | 10 | 168.768 | 190.637 | 223.125 | 10 | 168.768 | 190.637 | 223.125 |
| pre_speech_dur_s | 10 | 2.008 | 1.920 | 2.960 | 10 | 2.008 | 1.920 | 2.960 |
| pre_mean_pitch | 10 | 207.710 | 208.108 | 219.706 | 10 | 207.710 | 208.108 | 219.706 |
| pre_std_pitch | 10 | 35.282 | 39.850 | 47.961 | 10 | 35.282 | 39.850 | 47.961 |
| pre_mean_intensity | 10 | 61.517 | 60.966 | 64.351 | 10 | 61.517 | 60.966 | 64.351 |
| pre_std_intensity | 10 | 13.908 | 14.351 | 15.540 | 10 | 13.908 | 14.351 | 15.540 |
| post_utmosv2 | 10 | 1.608 | 1.896 | 2.129 | 10 | 1.608 | 1.896 | 2.129 |
| post_wpm | 10 | 114.802 | 105.769 | 238.399 | 10 | 114.802 | 105.769 | 238.399 |
| post_speech_dur_s | 10 | 1.672 | 1.560 | 3.528 | 10 | 1.672 | 1.560 | 3.528 |
| post_mean_pitch | 10 | 148.521 | 206.018 | 217.616 | 10 | 148.521 | 206.018 | 217.616 |
| post_std_pitch | 10 | 32.077 | 42.361 | 59.187 | 10 | 32.077 | 42.361 | 59.187 |
| post_mean_intensity | 10 | -16.814 | 58.281 | 65.165 | 10 | -16.814 | 58.281 | 65.165 |
| post_std_intensity | 10 | 10.026 | 13.128 | 15.729 | 10 | 10.026 | 13.128 | 15.729 |
| clean_utmosv2 | 10 | 2.141 | 2.179 | 2.361 | 10 | 2.141 | 2.179 | 2.361 |
| clean_wpm | 10 | 156.763 | 163.043 | 188.105 | 10 | 156.763 | 163.043 | 188.105 |
| clean_speech_dur_s | 10 | 6.528 | 7.720 | 9.240 | 10 | 6.528 | 7.720 | 9.240 |
| clean_mean_pitch | 10 | 196.392 | 197.760 | 203.647 | 10 | 196.392 | 197.760 | 203.647 |
| clean_std_pitch | 10 | 34.790 | 34.769 | 41.836 | 10 | 34.790 | 34.769 | 41.836 |
| clean_mean_intensity | 10 | 59.763 | 60.132 | 60.993 | 10 | 59.763 | 60.132 | 60.993 |
| clean_std_intensity | 10 | 14.883 | 15.076 | 16.028 | 10 | 14.883 | 15.076 | 16.028 |
| split_t | 10 | 7.616 | 7.760 | 9.088 | 10 | 7.616 | 7.760 | 9.088 |
| behavior_C_RESPOND | 10 | 0.500 | 0.500 | 1.000 | 10 | 0.500 | 0.500 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.500 | 0.500 | 1.000 | 10 | 0.500 | 0.500 | 1.000 |

- Overlap validity: v1.5 assumes the agent is still speaking when the overlap starts (metadata timestamps[0]); if it had already finished or not yet started, the sample tests nothing, so the valid-only rows exclude those (and samples whose events.json is missing).
- `stop_latency`: v1.5 timing: mean duration (s) of user/model speech-overlap intervals in latency_intervals.json (Silero VAD).
- `resp_latency`: v1.5 timing: mean gap (s) from the end of user speech to the next model speech start (Silero VAD).
- `n_stop_intervals`: Number of overlap intervals found by get_timing.py.
- `n_resp_intervals`: Number of response-gap intervals found by get_timing.py.
- `pre_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed before the overlap.
- `pre_wpm`: Words per minute over speech-only time. Computed before the overlap.
- `pre_speech_dur_s`: Speech duration (s) used for wpm. Computed before the overlap.
- `pre_mean_pitch`: Mean F0 (Hz). Computed before the overlap.
- `pre_std_pitch`: Std of F0 (Hz). Computed before the overlap.
- `pre_mean_intensity`: Mean intensity (dB). Computed before the overlap.
- `pre_std_intensity`: Std of intensity (dB). Computed before the overlap.
- `post_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed after the overlap.
- `post_wpm`: Words per minute over speech-only time. Computed after the overlap.
- `post_speech_dur_s`: Speech duration (s) used for wpm. Computed after the overlap.
- `post_mean_pitch`: Mean F0 (Hz). Computed after the overlap.
- `post_std_pitch`: Std of F0 (Hz). Computed after the overlap.
- `post_mean_intensity`: Mean intensity (dB). Computed after the overlap.
- `post_std_intensity`: Std of intensity (dB). Computed after the overlap.
- `clean_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed in the clean (no-overlap) run.
- `clean_wpm`: Words per minute over speech-only time. Computed in the clean (no-overlap) run.
- `clean_speech_dur_s`: Speech duration (s) used for wpm. Computed in the clean (no-overlap) run.
- `clean_mean_pitch`: Mean F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_std_pitch`: Std of F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_mean_intensity`: Mean intensity (dB). Computed in the clean (no-overlap) run.
- `clean_std_intensity`: Std of intensity (dB). Computed in the clean (no-overlap) run.
- `behavior_C_RESPOND`: Judge label: 1 if the first post-overlap segment was tagged C_RESPOND (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_RESUME`: Judge label: 1 if the first post-overlap segment was tagged C_RESUME (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNCERTAIN_HANDLING`: Judge label: 1 if the first post-overlap segment was tagged C_UNCERTAIN_HANDLING (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNKNOWN`: Judge label: 1 if the first post-overlap segment was tagged C_UNKNOWN (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.

System one:

- samples with system1 events: 10/10; judgments: 20; outcomes: ok 20
- latency over ok calls (ms): p50 418, p90 931; hedged share: 45.0%

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "speech_dur_s": 2.2311111111111117,
    "mean_pitch": 205.43829727172852,
    "std_pitch": 35.16489934921265,
    "wpm": 178.14789286563482,
    "mean_intensity": 61.45424270629883,
    "std_intensity": 14.222997069358826,
    "utmosv2": 1.9447620660066605
   },
   "post": {
    "speech_dur_s": 1.4577777777777776,
    "mean_pitch": 140.53951687282986,
    "std_pitch": 27.26030863655938,
    "wpm": 100.47417577905384,
    "mean_intensity": -26.345422956678604,
    "std_intensity": 9.319440629747179,
    "utmosv2": 1.532053656048245
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.5,
   "C_UNKNOWN": 0.5
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 0.508 | 2.420 | 1 | 2 | 8.560 | 1 | 0 | 0 | 0 |
| 100 | yes | 0.508 | 1.892 | 1 | 1 | 5.360 | 0 | 0 | 0 | 1 |
| 11 | yes | 0.060 | 1.828 | 1 | 1 | 6.720 | 0 | 0 | 0 | 1 |
| 21 | yes | 0.476 | 2.036 | 1 | 2 | 9.040 | 1 | 0 | 0 | 0 |
| 49 | yes | 0.444 | 2.772 | 1 | 2 | 7.200 | 0 | 0 | 0 | 1 |
| 54 | yes | 0.348 | 2.852 | 1 | 1 | 6.640 | 0 | 0 | 0 | 1 |
| 61 | yes | 0.348 | 3.108 | 1 | 1 | 6.480 | 0 | 0 | 0 | 1 |
| 76 | yes | 0.444 | 2.916 | 1 | 2 | 8.320 | 1 | 0 | 0 | 0 |
| 80 | yes | 0.316 | 2.164 | 1 | 2 | 9.520 | 1 | 0 | 0 | 0 |
| 98 | yes | 0.508 | 2.164 | 1 | 2 | 8.320 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 100.2, "asr": [{"model_load_s": 2.57, "transcribe_s": 10.68, "audio_s": 125.02, "files": 10, "wall_s": 17.02, "audio_name": "output.wav"}, {"model_load_s": 2.73, "transcribe_s": 10.73, "audio_s": 125.02, "files": 10, "wall_s": 17.24, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.1, "general_before_after": 44.4, "behavior": 20.4}}

## v1.5/talking_to_other  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.406 | 0.412 | 0.447 | 10 | 0.406 | 0.412 | 0.447 |
| resp_latency | 10 | 2.647 | 2.700 | 2.970 | 10 | 2.647 | 2.700 | 2.970 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.800 | 2.000 | 2.000 | 10 | 1.800 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 1.746 | 1.798 | 1.983 | 10 | 1.746 | 1.798 | 1.983 |
| pre_wpm | 10 | 113.587 | 161.458 | 179.464 | 10 | 113.587 | 161.458 | 179.464 |
| pre_speech_dur_s | 10 | 1.376 | 1.800 | 2.232 | 10 | 1.376 | 1.800 | 2.232 |
| pre_mean_pitch | 10 | 213.879 | 208.026 | 234.687 | 10 | 213.879 | 208.026 | 234.687 |
| pre_std_pitch | 10 | 43.194 | 45.354 | 55.525 | 10 | 43.194 | 45.354 | 55.525 |
| pre_mean_intensity | 10 | 61.432 | 61.163 | 64.462 | 10 | 61.432 | 61.163 | 64.462 |
| pre_std_intensity | 10 | 13.296 | 13.482 | 14.634 | 10 | 13.296 | 13.482 | 14.634 |
| post_utmosv2 | 10 | 1.823 | 2.106 | 2.499 | 10 | 1.823 | 2.106 | 2.499 |
| post_wpm | 10 | 174.582 | 224.256 | 276.951 | 10 | 174.582 | 224.256 | 276.951 |
| post_speech_dur_s | 10 | 2.024 | 2.600 | 3.280 | 10 | 2.024 | 2.600 | 3.280 |
| post_mean_pitch | 10 | 163.843 | 198.855 | 217.460 | 10 | 163.843 | 198.855 | 217.460 |
| post_std_pitch | 10 | 44.061 | 51.714 | 68.402 | 10 | 44.061 | 51.714 | 68.402 |
| post_mean_intensity | 10 | 8.094 | 59.448 | 62.980 | 10 | 8.094 | 59.448 | 62.980 |
| post_std_intensity | 10 | 12.076 | 13.834 | 17.318 | 10 | 12.076 | 13.834 | 17.318 |
| clean_utmosv2 | 10 | 2.096 | 2.087 | 2.357 | 10 | 2.096 | 2.087 | 2.357 |
| clean_wpm | 10 | 150.053 | 148.502 | 166.556 | 10 | 150.053 | 148.502 | 166.556 |
| clean_speech_dur_s | 10 | 6.608 | 7.680 | 8.352 | 10 | 6.608 | 7.680 | 8.352 |
| clean_mean_pitch | 10 | 199.467 | 199.758 | 205.472 | 10 | 199.467 | 199.758 | 205.472 |
| clean_std_pitch | 10 | 36.081 | 37.096 | 40.677 | 10 | 36.081 | 37.096 | 40.677 |
| clean_mean_intensity | 10 | 59.972 | 60.185 | 61.125 | 10 | 59.972 | 60.185 | 61.125 |
| clean_std_intensity | 10 | 14.647 | 14.495 | 15.552 | 10 | 14.647 | 14.495 | 15.552 |
| split_t | 10 | 8.973 | 9.440 | 10.144 | 10 | 8.973 | 9.440 | 10.144 |
| behavior_C_RESPOND | 10 | 0.400 | 0.000 | 1.000 | 10 | 0.400 | 0.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNKNOWN | 10 | 0.500 | 0.500 | 1.000 | 10 | 0.500 | 0.500 | 1.000 |

- Overlap validity: v1.5 assumes the agent is still speaking when the overlap starts (metadata timestamps[0]); if it had already finished or not yet started, the sample tests nothing, so the valid-only rows exclude those (and samples whose events.json is missing).
- `stop_latency`: v1.5 timing: mean duration (s) of user/model speech-overlap intervals in latency_intervals.json (Silero VAD).
- `resp_latency`: v1.5 timing: mean gap (s) from the end of user speech to the next model speech start (Silero VAD).
- `n_stop_intervals`: Number of overlap intervals found by get_timing.py.
- `n_resp_intervals`: Number of response-gap intervals found by get_timing.py.
- `pre_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed before the overlap.
- `pre_wpm`: Words per minute over speech-only time. Computed before the overlap.
- `pre_speech_dur_s`: Speech duration (s) used for wpm. Computed before the overlap.
- `pre_mean_pitch`: Mean F0 (Hz). Computed before the overlap.
- `pre_std_pitch`: Std of F0 (Hz). Computed before the overlap.
- `pre_mean_intensity`: Mean intensity (dB). Computed before the overlap.
- `pre_std_intensity`: Std of intensity (dB). Computed before the overlap.
- `post_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed after the overlap.
- `post_wpm`: Words per minute over speech-only time. Computed after the overlap.
- `post_speech_dur_s`: Speech duration (s) used for wpm. Computed after the overlap.
- `post_mean_pitch`: Mean F0 (Hz). Computed after the overlap.
- `post_std_pitch`: Std of F0 (Hz). Computed after the overlap.
- `post_mean_intensity`: Mean intensity (dB). Computed after the overlap.
- `post_std_intensity`: Std of intensity (dB). Computed after the overlap.
- `clean_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed in the clean (no-overlap) run.
- `clean_wpm`: Words per minute over speech-only time. Computed in the clean (no-overlap) run.
- `clean_speech_dur_s`: Speech duration (s) used for wpm. Computed in the clean (no-overlap) run.
- `clean_mean_pitch`: Mean F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_std_pitch`: Std of F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_mean_intensity`: Mean intensity (dB). Computed in the clean (no-overlap) run.
- `clean_std_intensity`: Std of intensity (dB). Computed in the clean (no-overlap) run.
- `behavior_C_RESPOND`: Judge label: 1 if the first post-overlap segment was tagged C_RESPOND (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_RESUME`: Judge label: 1 if the first post-overlap segment was tagged C_RESUME (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNCERTAIN_HANDLING`: Judge label: 1 if the first post-overlap segment was tagged C_UNCERTAIN_HANDLING (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNKNOWN`: Judge label: 1 if the first post-overlap segment was tagged C_UNKNOWN (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.

System one:

- samples with system1 events: 10/10; judgments: 20; outcomes: ok 20
- latency over ok calls (ms): p50 372, p90 879; hedged share: 35.0%

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_pitch": 43.32069373130798,
    "utmosv2": 1.7428323477506638,
    "speech_dur_s": 1.208888888888889,
    "mean_intensity": 61.51472568511963,
    "mean_pitch": 213.480712890625,
    "wpm": 105.37494912494911,
    "std_intensity": 13.391085267066956
   },
   "post": {
    "std_pitch": 40.404277589586044,
    "utmosv2": 1.7314152717590332,
    "speech_dur_s": 1.8844444444444446,
    "mean_intensity": 1.8947274949815538,
    "mean_pitch": 156.5219268798828,
    "wpm": 160.6467850914095,
    "std_intensity": 11.073933389451769
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.4,
   "C_UNCERTAIN_HANDLING": 0.1,
   "C_UNKNOWN": 0.5
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 0.348 | 1.988 | 1 | 1 | 6.480 | 0 | 0 | 0 | 1 |
| 20 | yes | 0.476 | 2.868 | 1 | 2 | 9.760 | 1 | 0 | 0 | 0 |
| 3 | yes | 0.348 | 2.740 | 1 | 2 | 10.720 | 0 | 0 | 0 | 1 |
| 39 | yes | 0.380 | 3.892 | 1 | 2 | 7.808 | 0 | 0 | 0 | 1 |
| 45 | yes | 0.444 | 2.708 | 1 | 2 | 10.080 | 0 | 0 | 0 | 1 |
| 48 | yes | 0.380 | 2.148 | 1 | 2 | 9.760 | 1 | 0 | 0 | 0 |
| 56 | yes | 0.412 | 2.356 | 1 | 2 | 9.360 | 0 | 0 | 1 | 0 |
| 75 | yes | 0.412 | 2.692 | 1 | 2 | 9.520 | 1 | 0 | 0 | 0 |
| 88 | yes | 0.412 | 2.724 | 1 | 1 | 7.040 | 0 | 0 | 0 | 1 |
| 99 | yes | 0.444 | 2.356 | 1 | 2 | 9.200 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 102.0, "asr": [{"model_load_s": 2.58, "transcribe_s": 10.76, "audio_s": 129.8, "files": 10, "wall_s": 17.07, "audio_name": "output.wav"}, {"model_load_s": 2.58, "transcribe_s": 10.72, "audio_s": 129.8, "files": 10, "wall_s": 17.05, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 44.3, "behavior": 22.4}}

## v1.5/user_backchannel  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.409 | 0.396 | 0.511 | 10 | 0.409 | 0.396 | 0.511 |
| resp_latency | 10 | 2.202 | 1.844 | 3.194 | 10 | 2.202 | 1.844 | 3.194 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.200 | 1.000 | 2.000 | 10 | 1.200 | 1.000 | 2.000 |
| pre_utmosv2 | 10 | 1.933 | 1.928 | 2.261 | 10 | 1.933 | 1.928 | 2.261 |
| pre_wpm | 10 | 159.883 | 157.895 | 180.357 | 10 | 159.883 | 157.895 | 180.357 |
| pre_speech_dur_s | 10 | 2.648 | 2.920 | 3.360 | 10 | 2.648 | 2.920 | 3.360 |
| pre_mean_pitch | 10 | 211.648 | 213.513 | 221.551 | 10 | 211.648 | 213.513 | 221.551 |
| pre_std_pitch | 10 | 40.400 | 41.667 | 48.879 | 10 | 40.400 | 41.667 | 48.879 |
| pre_mean_intensity | 10 | 63.103 | 63.174 | 67.022 | 10 | 63.103 | 63.174 | 67.022 |
| pre_std_intensity | 10 | 12.006 | 11.792 | 13.915 | 10 | 12.006 | 11.792 | 13.915 |
| post_utmosv2 | 10 | 0.974 | 0.685 | 2.032 | 10 | 0.974 | 0.685 | 2.032 |
| post_wpm | 10 | 52.238 | 0.000 | 173.601 | 10 | 52.238 | 0.000 | 173.601 |
| post_speech_dur_s | 10 | 0.976 | 0.000 | 2.688 | 10 | 0.976 | 0.000 | 2.688 |
| post_mean_pitch | 10 | 63.738 | 0.000 | 211.787 | 10 | 63.738 | 0.000 | 211.787 |
| post_std_pitch | 10 | 8.058 | 0.000 | 29.622 | 10 | 8.058 | 0.000 | 29.622 |
| post_mean_intensity | 10 | -101.276 | -200.000 | 59.652 | 10 | -101.276 | -200.000 | 59.652 |
| post_std_intensity | 10 | 4.649 | 0.000 | 15.630 | 10 | 4.649 | 0.000 | 15.630 |
| clean_utmosv2 | 10 | 2.070 | 2.123 | 2.269 | 10 | 2.070 | 2.123 | 2.269 |
| clean_wpm | 10 | 186.083 | 176.184 | 212.527 | 10 | 186.083 | 176.184 | 212.527 |
| clean_speech_dur_s | 10 | 7.224 | 7.920 | 8.096 | 10 | 7.224 | 7.920 | 8.096 |
| clean_mean_pitch | 10 | 205.533 | 205.611 | 208.456 | 10 | 205.533 | 205.611 | 208.456 |
| clean_std_pitch | 10 | 41.732 | 41.345 | 48.117 | 10 | 41.732 | 41.345 | 48.117 |
| clean_mean_intensity | 10 | 59.920 | 59.902 | 61.981 | 10 | 59.920 | 59.902 | 61.981 |
| clean_std_intensity | 10 | 14.609 | 14.656 | 15.603 | 10 | 14.609 | 14.656 | 15.603 |
| split_t | 10 | 7.208 | 7.040 | 7.608 | 10 | 7.208 | 7.040 | 7.608 |
| behavior_C_RESPOND | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_RESUME | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNKNOWN | 10 | 0.800 | 1.000 | 1.000 | 10 | 0.800 | 1.000 | 1.000 |

- Overlap validity: v1.5 assumes the agent is still speaking when the overlap starts (metadata timestamps[0]); if it had already finished or not yet started, the sample tests nothing, so the valid-only rows exclude those (and samples whose events.json is missing).
- `stop_latency`: v1.5 timing: mean duration (s) of user/model speech-overlap intervals in latency_intervals.json (Silero VAD).
- `resp_latency`: v1.5 timing: mean gap (s) from the end of user speech to the next model speech start (Silero VAD).
- `n_stop_intervals`: Number of overlap intervals found by get_timing.py.
- `n_resp_intervals`: Number of response-gap intervals found by get_timing.py.
- `pre_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed before the overlap.
- `pre_wpm`: Words per minute over speech-only time. Computed before the overlap.
- `pre_speech_dur_s`: Speech duration (s) used for wpm. Computed before the overlap.
- `pre_mean_pitch`: Mean F0 (Hz). Computed before the overlap.
- `pre_std_pitch`: Std of F0 (Hz). Computed before the overlap.
- `pre_mean_intensity`: Mean intensity (dB). Computed before the overlap.
- `pre_std_intensity`: Std of intensity (dB). Computed before the overlap.
- `post_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed after the overlap.
- `post_wpm`: Words per minute over speech-only time. Computed after the overlap.
- `post_speech_dur_s`: Speech duration (s) used for wpm. Computed after the overlap.
- `post_mean_pitch`: Mean F0 (Hz). Computed after the overlap.
- `post_std_pitch`: Std of F0 (Hz). Computed after the overlap.
- `post_mean_intensity`: Mean intensity (dB). Computed after the overlap.
- `post_std_intensity`: Std of intensity (dB). Computed after the overlap.
- `clean_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed in the clean (no-overlap) run.
- `clean_wpm`: Words per minute over speech-only time. Computed in the clean (no-overlap) run.
- `clean_speech_dur_s`: Speech duration (s) used for wpm. Computed in the clean (no-overlap) run.
- `clean_mean_pitch`: Mean F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_std_pitch`: Std of F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_mean_intensity`: Mean intensity (dB). Computed in the clean (no-overlap) run.
- `clean_std_intensity`: Std of intensity (dB). Computed in the clean (no-overlap) run.
- `behavior_C_RESPOND`: Judge label: 1 if the first post-overlap segment was tagged C_RESPOND (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_RESUME`: Judge label: 1 if the first post-overlap segment was tagged C_RESUME (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNCERTAIN_HANDLING`: Judge label: 1 if the first post-overlap segment was tagged C_UNCERTAIN_HANDLING (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNKNOWN`: Judge label: 1 if the first post-overlap segment was tagged C_UNKNOWN (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.

System one:

- samples with system1 events: 10/10; judgments: 20; outcomes: cancelled 2, ok 18
- latency over ok calls (ms): p50 316, p90 775; hedged share: 31.6%

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "mean_intensity": 62.84354782104492,
    "mean_pitch": 211.3328971862793,
    "utmosv2": 1.9781323075294495,
    "speech_dur_s": 2.8177777777777777,
    "std_pitch": 41.679277420043945,
    "wpm": 159.22843965736527,
    "std_intensity": 12.049418091773987
   },
   "post": {
    "mean_intensity": -119.20746040344238,
    "mean_pitch": 44.37537129720052,
    "utmosv2": 0.832023991478814,
    "speech_dur_s": 0.4977777777777778,
    "std_pitch": 3.504690647125244,
    "wpm": 35.6060606060606,
    "std_intensity": 3.306947708129883
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESUME": 0.1,
   "C_UNCERTAIN_HANDLING": 0.1,
   "C_UNKNOWN": 0.8
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | yes | 0.508 | 1.732 | 1 | 1 | 7.360 | 0 | 0 | 0 | 1 |
| 29 | yes | 0.412 | 1.796 | 1 | 1 | 6.960 | 0 | 0 | 0 | 1 |
| 3 | yes | 0.412 | 1.572 | 1 | 1 | 6.640 | 0 | 0 | 0 | 1 |
| 32 | yes | 0.380 | 2.628 | 1 | 2 | 9.840 | 0 | 0 | 1 | 0 |
| 34 | yes | 0.348 | 3.684 | 1 | 1 | 6.240 | 0 | 0 | 0 | 1 |
| 55 | yes | 0.348 | 3.140 | 1 | 1 | 7.280 | 0 | 0 | 0 | 1 |
| 64 | yes | 0.380 | 1.892 | 1 | 2 | 6.480 | 0 | 1 | 0 | 0 |
| 7 | yes | 0.476 | 1.700 | 1 | 1 | 7.120 | 0 | 0 | 0 | 1 |
| 92 | yes | 0.540 | 1.508 | 1 | 1 | 7.280 | 0 | 0 | 0 | 1 |
| 97 | yes | 0.284 | 2.372 | 1 | 1 | 6.880 | 0 | 0 | 0 | 1 |

Timing: {"total_s": 104.7, "asr": [{"model_load_s": 2.57, "transcribe_s": 10.75, "audio_s": 121.9, "files": 10, "wall_s": 17.15, "audio_name": "output.wav"}, {"model_load_s": 2.57, "transcribe_s": 10.83, "audio_s": 121.91, "files": 10, "wall_s": 17.16, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.1, "general_before_after": 44.1, "behavior": 25.1}}

## v1.5/user_interruption  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 9/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 8 | 0.404 | 0.396 | 0.463 | 8 | 0.404 | 0.396 | 0.463 |
| resp_latency | 9 | 2.349 | 2.052 | 3.287 | 9 | 2.349 | 2.052 | 3.287 |
| n_stop_intervals | 10 | 0.800 | 1.000 | 1.000 | 9 | 0.889 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.700 | 2.000 | 2.000 | 9 | 1.889 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 1.900 | 1.890 | 2.189 | 9 | 1.946 | 1.943 | 2.195 |
| pre_wpm | 10 | 167.829 | 196.898 | 238.393 | 9 | 186.477 | 197.368 | 241.071 |
| pre_speech_dur_s | 10 | 2.592 | 3.000 | 4.432 | 9 | 2.880 | 3.040 | 4.464 |
| pre_mean_pitch | 10 | 187.427 | 207.775 | 216.641 | 9 | 208.252 | 207.845 | 216.724 |
| pre_std_pitch | 10 | 38.433 | 43.123 | 51.944 | 9 | 42.703 | 44.574 | 52.286 |
| pre_mean_intensity | 10 | 57.830 | 60.381 | 62.960 | 9 | 60.680 | 61.113 | 63.238 |
| pre_std_intensity | 10 | 14.428 | 14.370 | 16.639 | 9 | 14.152 | 14.276 | 15.849 |
| post_utmosv2 | 10 | 1.622 | 1.826 | 2.122 | 9 | 1.726 | 1.843 | 2.150 |
| post_wpm | 10 | 331.580 | 214.773 | 632.143 | 9 | 368.422 | 225.000 | 728.571 |
| post_speech_dur_s | 10 | 2.360 | 2.800 | 3.664 | 9 | 2.622 | 2.960 | 4.128 |
| post_mean_pitch | 10 | 174.229 | 209.964 | 233.933 | 9 | 193.588 | 210.050 | 234.198 |
| post_std_pitch | 10 | 44.481 | 50.433 | 61.112 | 9 | 49.424 | 52.068 | 66.015 |
| post_mean_intensity | 10 | 28.002 | 57.896 | 64.063 | 9 | 53.335 | 58.851 | 64.191 |
| post_std_intensity | 10 | 12.256 | 14.370 | 17.074 | 9 | 13.618 | 14.720 | 17.535 |
| clean_utmosv2 | 10 | 2.024 | 2.046 | 2.344 | 9 | 2.015 | 1.994 | 2.353 |
| clean_wpm | 10 | 200.076 | 196.081 | 220.870 | 9 | 197.484 | 194.245 | 214.330 |
| clean_speech_dur_s | 10 | 10.304 | 10.720 | 11.304 | 9 | 10.613 | 10.880 | 11.328 |
| clean_mean_pitch | 10 | 206.474 | 204.146 | 219.763 | 9 | 206.885 | 205.514 | 220.446 |
| clean_std_pitch | 10 | 41.813 | 41.490 | 49.557 | 9 | 41.748 | 40.587 | 49.951 |
| clean_mean_intensity | 10 | 59.989 | 60.032 | 60.597 | 9 | 59.927 | 59.992 | 60.483 |
| clean_std_intensity | 10 | 15.003 | 14.941 | 15.779 | 9 | 15.173 | 15.288 | 15.806 |
| split_t | 10 | 10.974 | 11.480 | 13.440 | 9 | 11.004 | 11.520 | 13.520 |
| behavior_C_RESPOND | 10 | 0.600 | 1.000 | 1.000 | 9 | 0.667 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 9 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 9 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.400 | 0.000 | 1.000 | 9 | 0.333 | 0.000 | 1.000 |

- Overlap validity: v1.5 assumes the agent is still speaking when the overlap starts (metadata timestamps[0]); if it had already finished or not yet started, the sample tests nothing, so the valid-only rows exclude those (and samples whose events.json is missing).
- `stop_latency`: v1.5 timing: mean duration (s) of user/model speech-overlap intervals in latency_intervals.json (Silero VAD).
- `resp_latency`: v1.5 timing: mean gap (s) from the end of user speech to the next model speech start (Silero VAD).
- `n_stop_intervals`: Number of overlap intervals found by get_timing.py.
- `n_resp_intervals`: Number of response-gap intervals found by get_timing.py.
- `pre_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed before the overlap.
- `pre_wpm`: Words per minute over speech-only time. Computed before the overlap.
- `pre_speech_dur_s`: Speech duration (s) used for wpm. Computed before the overlap.
- `pre_mean_pitch`: Mean F0 (Hz). Computed before the overlap.
- `pre_std_pitch`: Std of F0 (Hz). Computed before the overlap.
- `pre_mean_intensity`: Mean intensity (dB). Computed before the overlap.
- `pre_std_intensity`: Std of intensity (dB). Computed before the overlap.
- `post_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed after the overlap.
- `post_wpm`: Words per minute over speech-only time. Computed after the overlap.
- `post_speech_dur_s`: Speech duration (s) used for wpm. Computed after the overlap.
- `post_mean_pitch`: Mean F0 (Hz). Computed after the overlap.
- `post_std_pitch`: Std of F0 (Hz). Computed after the overlap.
- `post_mean_intensity`: Mean intensity (dB). Computed after the overlap.
- `post_std_intensity`: Std of intensity (dB). Computed after the overlap.
- `clean_utmosv2`: UTMOSv2 speech-quality MOS (1-5) of the segment. Computed in the clean (no-overlap) run.
- `clean_wpm`: Words per minute over speech-only time. Computed in the clean (no-overlap) run.
- `clean_speech_dur_s`: Speech duration (s) used for wpm. Computed in the clean (no-overlap) run.
- `clean_mean_pitch`: Mean F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_std_pitch`: Std of F0 (Hz). Computed in the clean (no-overlap) run.
- `clean_mean_intensity`: Mean intensity (dB). Computed in the clean (no-overlap) run.
- `clean_std_intensity`: Std of intensity (dB). Computed in the clean (no-overlap) run.
- `behavior_C_RESPOND`: Judge label: 1 if the first post-overlap segment was tagged C_RESPOND (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_RESUME`: Judge label: 1 if the first post-overlap segment was tagged C_RESUME (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNCERTAIN_HANDLING`: Judge label: 1 if the first post-overlap segment was tagged C_UNCERTAIN_HANDLING (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.
- `behavior_C_UNKNOWN`: Judge label: 1 if the first post-overlap segment was tagged C_UNKNOWN (C-axis: RESPOND/RESUME/UNCERTAIN_HANDLING/UNKNOWN), else 0.

System one:

- samples with system1 events: 10/10; judgments: 30; outcomes: cancelled 10, ok 20
- latency over ok calls (ms): p50 414, p90 680; hedged share: 41.4%

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "mean_pitch": 207.11099815368652,
    "utmosv2": 1.9090912491083145,
    "std_intensity": 14.47251033782959,
    "mean_intensity": 60.082622051239014,
    "speech_dur_s": 2.355555555555556,
    "wpm": 157.30994325998785,
    "std_pitch": 41.163991928100586
   },
   "post": {
    "mean_pitch": 167.3300526936849,
    "utmosv2": 1.5393652386135526,
    "std_intensity": 11.259700563218859,
    "mean_intensity": 51.85084753856063,
    "speech_dur_s": 1.7511111111111115,
    "wpm": 201.75581068438206,
    "std_pitch": 37.72998809814453
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.6,
   "C_UNKNOWN": 0.4
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | yes | 0.380 | 3.220 | 1 | 2 | 14.160 | 0 | 0 | 0 | 1 |
| 12 | yes | 0.380 | 3.012 | 1 | 1 | 6.000 | 0 | 0 | 0 | 1 |
| 13 | yes | 0.348 | 2.052 | 1 | 2 | 10.720 | 1 | 0 | 0 | 0 |
| 32 | no | - | - | 0 | 0 | 10.699 | 0 | 0 | 0 | 1 |
| 45 | yes | - | 3.556 | 0 | 2 | 13.360 | 0 | 0 | 0 | 1 |
| 59 | yes | 0.316 | 1.860 | 1 | 2 | 11.680 | 1 | 0 | 0 | 0 |
| 62 | yes | 0.444 | 1.844 | 1 | 2 | 7.120 | 1 | 0 | 0 | 0 |
| 65 | yes | 0.444 | 1.604 | 1 | 2 | 13.040 | 1 | 0 | 0 | 0 |
| 85 | yes | 0.412 | 2.116 | 1 | 2 | 11.440 | 1 | 0 | 0 | 0 |
| 9 | yes | 0.508 | 1.876 | 1 | 2 | 11.520 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 103.7, "asr": [{"model_load_s": 2.58, "transcribe_s": 10.9, "audio_s": 150.14, "files": 10, "wall_s": 17.2, "audio_name": "output.wav"}, {"model_load_s": 2.59, "transcribe_s": 11.0, "audio_s": 150.14, "files": 10, "wall_s": 17.35, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.3, "general_before_after": 44.5, "behavior": 23.4}}
