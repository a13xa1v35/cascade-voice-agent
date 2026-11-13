# FDB evaluation: system-one-telephony

- evaluated at: 2026-11-10T12:45:37+00:00
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
  "variant": "system_one",
  "bench_agent_version": "1",
  "bench_agent_fingerprint": "c05110edaeed",
  "tools": "control_device,manage_timers,calendar,send_message,read_messages,play_media,add_note,lookup_info",
  "variant_extra_instructions": "",
  "variant_params": "{\"addressed_threshold\": 0.5, \"classification_timeout\": 1.5, \"provider\": \"cloudflare-workers-ai\", \"complete_floor\": 0.55, \"complete_start\": 0.72, \"debounce_secs\": 0.15, \"fallback_secs\": 5.0, \"hedge_after_secs\": 0.45, \"holding_fallback_secs\": 12.0, \"holding_threshold\": 0.5, \"interrupt_requires_addressed\": true, \"model\": \"clef-flash\", \"pipecat_user_turn_stop_timeout\": 3600.0, \"quiet_confirm_secs\": 0.3, \"relax_secs\": 3.0, \"taking_threshold\": 0.5}"
}
```

## v1/candor_pause_handling  (upstream task: `pause_handling`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.100 | 0.000 | 0.100 |
| n_words | 10 | 1.000 | 0.000 | 1.000 |
| premature_turn_end | 10 | 0.100 | 0.000 | 0.100 |
| premature_llm_start | 10 | 0.100 | 0.000 | 0.100 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `n_words`: Number of ASR words in the agent's output.
- `premature_turn_end`: Pause handling: 1 if the design tried to take the turn during the pause even if no audio came out (a user_turn.stopped event in [pause start - 0.3 s, pause end + 0.5 s]).
- `premature_llm_start`: Pause handling: 1 if an llm.text event followed that premature stop (up to pause end + 2.5 s), i.e. the LLM actually started answering.

System one:

- samples with system1 events: 10/10; judgments: 114; outcomes: ok 86, stale 28
- latency over ok calls (ms): p50 318, p90 715; hedged share: 38.6%
- actions: drop_backchannel 2, drop_side_talk 24, end_turn 1, hold_backchannel 2, keep_listening 86

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.10000 | 0.10000 | yes |

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
| 44 | 0 | 0 | 0 | 0 |
| 6 | 1 | 10 | 1 | 1 |
| 68 | 0 | 0 | 0 | 0 |

Timing: {"total_s": 17.3, "asr": [{"model_load_s": 2.59, "transcribe_s": 10.66, "audio_s": 115.04, "files": 10, "wall_s": 17.0, "audio_name": "output.wav"}], "eval_s": {"pause_handling": 0.3}}

## v1/candor_turn_taking  (upstream task: `smooth_turn_taking`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.100 | 0.000 | 0.100 |
| latency_raw | 1 | 2.040 | 2.040 | 2.040 |
| latency | 1 | 2.040 | 2.040 | 2.040 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `latency_raw`: Same as latency but unclamped (negative = agent started before the user finished).
- `latency`: Seconds from the user turn/interruption end to the agent's first word, clamped at 0; only samples with TOR=1.

System one:

- samples with system1 events: 10/10; judgments: 75; outcomes: ok 69, stale 6
- latency over ok calls (ms): p50 269, p90 605; hedged share: 24.0%
- actions: drop_side_talk 20, end_turn 1, fallback 3, keep_listening 54

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.10000 | 0.10000 | yes |
| latency | 2.04000 | 2.04000 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | latency_raw | latency |
|---|---|---|---|
| 1 | 0 | - | - |
| 10 | 0 | - | - |
| 105 | 0 | - | - |
| 113 | 0 | - | - |
| 115 | 0 | - | - |
| 17 | 1 | 2.040 | 2.040 |
| 18 | 0 | - | - |
| 32 | 0 | - | - |
| 53 | 0 | - | - |
| 69 | 0 | - | - |

Timing: {"total_s": 17.3, "asr": [{"model_load_s": 2.65, "transcribe_s": 10.58, "audio_s": 125.0, "files": 10, "wall_s": 17.02, "audio_name": "output.wav"}], "eval_s": {"smooth_turn_taking": 0.3}}

## v1.5/background_speech  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 7/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 7 | 1.175 | 1.276 | 1.609 | 7 | 1.175 | 1.276 | 1.609 |
| resp_latency | 7 | 2.813 | 3.140 | 3.402 | 7 | 2.813 | 3.140 | 3.402 |
| n_stop_intervals | 10 | 0.700 | 1.000 | 1.000 | 7 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 0.800 | 1.000 | 1.100 | 7 | 1.143 | 1.000 | 1.400 |
| pre_utmosv2 | 10 | 1.681 | 2.011 | 2.250 | 7 | 2.108 | 2.082 | 2.267 |
| pre_wpm | 10 | 109.663 | 146.110 | 163.452 | 7 | 156.661 | 150.000 | 176.536 |
| pre_speech_dur_s | 10 | 2.112 | 2.560 | 4.112 | 7 | 3.017 | 2.640 | 4.208 |
| pre_mean_pitch | 10 | 141.024 | 197.317 | 208.490 | 7 | 201.463 | 201.018 | 209.777 |
| pre_std_pitch | 10 | 26.525 | 35.053 | 41.220 | 7 | 37.893 | 37.131 | 42.185 |
| pre_mean_intensity | 10 | -17.500 | 59.451 | 63.363 | 7 | 60.715 | 60.525 | 63.466 |
| pre_std_intensity | 10 | 10.097 | 12.995 | 16.050 | 7 | 14.425 | 14.690 | 16.822 |
| post_utmosv2 | 10 | 1.319 | 0.968 | 2.154 | 7 | 1.591 | 2.060 | 2.172 |
| post_wpm | 10 | 99.944 | 132.635 | 195.133 | 7 | 142.777 | 147.059 | 198.637 |
| post_speech_dur_s | 10 | 2.000 | 0.600 | 4.976 | 7 | 2.857 | 4.080 | 5.024 |
| post_mean_pitch | 10 | 159.537 | 191.793 | 277.488 | 7 | 227.910 | 195.552 | 374.406 |
| post_std_pitch | 10 | 17.962 | 14.354 | 40.413 | 7 | 25.660 | 30.342 | 42.488 |
| post_mean_intensity | 10 | -48.256 | 35.300 | 61.692 | 7 | 16.777 | 61.073 | 62.013 |
| post_std_intensity | 10 | 7.366 | 8.848 | 14.083 | 7 | 10.523 | 13.565 | 14.172 |
| clean_utmosv2 | 10 | 2.109 | 2.151 | 2.232 | 7 | 2.068 | 2.148 | 2.173 |
| clean_wpm | 10 | 177.957 | 177.896 | 204.076 | 7 | 171.049 | 174.757 | 184.115 |
| clean_speech_dur_s | 10 | 6.432 | 6.880 | 9.000 | 7 | 6.366 | 6.960 | 9.024 |
| clean_mean_pitch | 10 | 194.964 | 194.314 | 202.364 | 7 | 194.225 | 194.595 | 202.358 |
| clean_std_pitch | 10 | 34.145 | 35.988 | 39.214 | 7 | 34.326 | 36.674 | 40.020 |
| clean_mean_intensity | 10 | 60.074 | 60.610 | 61.140 | 7 | 60.099 | 60.614 | 60.990 |
| clean_std_intensity | 10 | 14.749 | 14.536 | 16.493 | 7 | 14.692 | 14.593 | 15.845 |
| split_t | 10 | 7.393 | 7.761 | 8.144 | 7 | 7.314 | 7.760 | 8.096 |
| behavior_C_RESPOND | 10 | 0.100 | 0.000 | 0.100 | 7 | 0.143 | 0.000 | 0.400 |
| behavior_C_RESUME | 10 | 0.100 | 0.000 | 0.100 | 7 | 0.143 | 0.000 | 0.400 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 7 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.800 | 1.000 | 1.000 | 7 | 0.714 | 1.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 62; outcomes: ok 45, stale 13, timeout 4
- latency over ok calls (ms): p50 390, p90 844; hedged share: 45.2%
- actions: drop_backchannel 1, drop_side_talk 8, end_turn 8, fallback 3, hold_backchannel 3, interrupt 2, keep_listening 41

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "mean_pitch": 133.0989023844401,
    "std_intensity": 9.178641107347277,
    "utmosv2": 1.6123963461981878,
    "speech_dur_s": 1.857777777777778,
    "wpm": 99.32496214517089,
    "mean_intensity": -26.518756866455078,
    "std_pitch": 24.57026375664605
   },
   "post": {
    "mean_pitch": 114.12538316514757,
    "std_intensity": 6.590037663777669,
    "utmosv2": 1.2202630970213149,
    "speech_dur_s": 1.6533333333333335,
    "wpm": 88.1993585704919,
    "mean_intensity": -60.579087257385254,
    "std_pitch": 14.776044045885405
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.1,
   "C_RESUME": 0.1,
   "C_UNKNOWN": 0.8
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 0.700 | 3.300 | 1 | 1 | 6.080 | 0 | 0 | 0 | 1 |
| 100 | yes | 0.764 | 2.612 | 1 | 2 | 6.320 | 1 | 0 | 0 | 0 |
| 11 | yes | 1.276 | 1.924 | 1 | 1 | 7.760 | 0 | 0 | 0 | 1 |
| 21 | no | - | - | 0 | 0 | 7.761 | 0 | 0 | 0 | 1 |
| 49 | no | - | - | 0 | 0 | 8.133 | 0 | 0 | 0 | 1 |
| 54 | yes | 1.596 | 3.140 | 1 | 1 | 8.240 | 0 | 0 | 0 | 1 |
| 61 | yes | 1.628 | 3.556 | 1 | 1 | 8.000 | 0 | 0 | 0 | 1 |
| 76 | no | - | - | 0 | 0 | 6.833 | 0 | 0 | 0 | 1 |
| 80 | yes | 0.828 | 2.020 | 1 | 1 | 7.840 | 0 | 1 | 0 | 0 |
| 98 | yes | 1.436 | 3.140 | 1 | 1 | 6.960 | 0 | 0 | 0 | 1 |

Timing: {"total_s": 100.3, "asr": [{"model_load_s": 2.58, "transcribe_s": 10.65, "audio_s": 125.02, "files": 10, "wall_s": 16.97, "audio_name": "output.wav"}, {"model_load_s": 2.6, "transcribe_s": 10.63, "audio_s": 125.02, "files": 10, "wall_s": 16.98, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.1, "general_before_after": 44.4, "behavior": 20.8}}

## v1.5/talking_to_other  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 8/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 1.686 | 1.740 | 2.038 | 8 | 1.812 | 1.788 | 2.089 |
| resp_latency | 10 | 3.380 | 3.300 | 4.820 | 8 | 3.004 | 3.268 | 3.722 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 8 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.100 | 1.000 | 1.100 | 8 | 1.125 | 1.000 | 1.300 |
| pre_utmosv2 | 10 | 1.886 | 1.923 | 2.072 | 8 | 1.904 | 1.923 | 2.076 |
| pre_wpm | 10 | 152.286 | 145.988 | 189.205 | 8 | 152.117 | 145.988 | 183.864 |
| pre_speech_dur_s | 10 | 2.504 | 2.320 | 4.008 | 8 | 2.900 | 2.720 | 4.024 |
| pre_mean_pitch | 10 | 205.184 | 201.361 | 216.577 | 8 | 207.898 | 205.927 | 219.099 |
| pre_std_pitch | 10 | 40.899 | 37.441 | 58.324 | 8 | 42.435 | 38.777 | 59.252 |
| pre_mean_intensity | 10 | 60.597 | 60.573 | 62.346 | 8 | 60.603 | 60.791 | 62.487 |
| pre_std_intensity | 10 | 13.678 | 13.270 | 15.859 | 8 | 12.943 | 13.233 | 13.966 |
| post_utmosv2 | 10 | 2.151 | 2.090 | 2.400 | 8 | 2.127 | 2.090 | 2.363 |
| post_wpm | 10 | 159.783 | 157.031 | 196.460 | 8 | 154.319 | 150.000 | 179.338 |
| post_speech_dur_s | 10 | 3.856 | 4.840 | 5.208 | 8 | 3.860 | 4.840 | 5.224 |
| post_mean_pitch | 10 | 190.546 | 194.292 | 200.088 | 8 | 192.478 | 196.977 | 200.599 |
| post_std_pitch | 10 | 31.083 | 34.380 | 40.467 | 8 | 31.234 | 34.380 | 42.590 |
| post_mean_intensity | 10 | 59.913 | 60.024 | 61.078 | 8 | 60.161 | 60.588 | 61.272 |
| post_std_intensity | 10 | 14.797 | 14.830 | 16.006 | 8 | 14.711 | 14.830 | 15.710 |
| clean_utmosv2 | 10 | 2.106 | 2.117 | 2.397 | 8 | 2.059 | 2.071 | 2.243 |
| clean_wpm | 10 | 157.875 | 157.065 | 187.546 | 8 | 158.523 | 157.065 | 185.949 |
| clean_speech_dur_s | 10 | 6.416 | 6.760 | 8.968 | 8 | 6.450 | 6.760 | 8.984 |
| clean_mean_pitch | 10 | 198.667 | 198.277 | 204.115 | 8 | 198.587 | 198.218 | 205.120 |
| clean_std_pitch | 10 | 38.838 | 37.139 | 52.942 | 8 | 39.731 | 37.139 | 53.077 |
| clean_mean_intensity | 10 | 59.764 | 59.352 | 61.251 | 8 | 59.774 | 59.352 | 61.434 |
| clean_std_intensity | 10 | 14.668 | 14.832 | 15.580 | 8 | 14.702 | 14.832 | 15.535 |
| split_t | 10 | 7.696 | 7.720 | 8.032 | 8 | 7.720 | 7.720 | 8.096 |
| behavior_C_RESPOND | 10 | 0.000 | 0.000 | 0.000 | 8 | 0.000 | 0.000 | 0.000 |
| behavior_C_RESUME | 10 | 0.700 | 1.000 | 1.000 | 8 | 0.625 | 1.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 8 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.300 | 0.000 | 1.000 | 8 | 0.375 | 0.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 50; outcomes: ok 43, stale 6, timeout 1
- latency over ok calls (ms): p50 343, p90 718; hedged share: 26.0%
- actions: drop_backchannel 5, drop_side_talk 14, end_turn 10, hold_backchannel 7, keep_listening 17

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_intensity": 13.620793461799622,
    "std_pitch": 39.67382550239563,
    "mean_pitch": 204.50212287902832,
    "wpm": 149.9866993921192,
    "mean_intensity": 60.60434913635254,
    "speech_dur_s": 2.5799999999999996,
    "utmosv2": 1.8967604786157608
   },
   "post": {
    "std_intensity": 14.831095814704895,
    "std_pitch": 31.863463401794434,
    "mean_pitch": 191.70065116882324,
    "wpm": 160.4034073863405,
    "mean_intensity": 59.923473834991455,
    "speech_dur_s": 4.01,
    "utmosv2": 2.136177733540535
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESUME": 0.7,
   "C_UNKNOWN": 0.3
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 1.500 | 2.052 | 1 | 1 | 7.520 | 0 | 0 | 0 | 1 |
| 20 | yes | 1.756 | 4.260 | 1 | 1 | 7.840 | 0 | 1 | 0 | 0 |
| 3 | yes | 1.820 | 2.052 | 1 | 1 | 7.840 | 0 | 1 | 0 | 0 |
| 39 | yes | 1.532 | 3.332 | 1 | 1 | 7.600 | 0 | 1 | 0 | 0 |
| 45 | yes | 2.268 | 3.492 | 1 | 1 | 8.320 | 0 | 0 | 0 | 1 |
| 48 | no | 1.468 | 4.804 | 1 | 1 | 7.920 | 0 | 1 | 0 | 0 |
| 56 | yes | 1.724 | 3.268 | 1 | 1 | 7.360 | 0 | 0 | 0 | 1 |
| 75 | yes | 2.012 | 2.308 | 1 | 2 | 7.280 | 0 | 1 | 0 | 0 |
| 88 | yes | 1.884 | 3.268 | 1 | 1 | 8.000 | 0 | 1 | 0 | 0 |
| 99 | no | 0.892 | 4.964 | 1 | 1 | 7.280 | 0 | 1 | 0 | 0 |

Timing: {"total_s": 108.3, "asr": [{"model_load_s": 2.55, "transcribe_s": 10.73, "audio_s": 129.8, "files": 10, "wall_s": 16.95, "audio_name": "output.wav"}, {"model_load_s": 2.56, "transcribe_s": 10.83, "audio_s": 129.8, "files": 10, "wall_s": 17.14, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 44.9, "behavior": 28.2}}

## v1.5/user_backchannel  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 8/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 8 | 0.640 | 0.636 | 0.780 | 8 | 0.640 | 0.636 | 0.780 |
| resp_latency | 9 | 2.539 | 2.692 | 3.127 | 8 | 2.456 | 2.596 | 2.929 |
| n_stop_intervals | 10 | 0.800 | 1.000 | 1.000 | 8 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 0.900 | 1.000 | 1.000 | 8 | 1.000 | 1.000 | 1.000 |
| pre_utmosv2 | 10 | 1.818 | 1.953 | 2.402 | 8 | 2.102 | 2.010 | 2.459 |
| pre_wpm | 10 | 127.487 | 147.581 | 181.737 | 8 | 159.359 | 153.947 | 185.211 |
| pre_speech_dur_s | 10 | 1.936 | 2.160 | 3.040 | 8 | 2.420 | 2.320 | 3.040 |
| pre_mean_pitch | 10 | 169.665 | 207.293 | 219.724 | 8 | 212.081 | 208.998 | 221.142 |
| pre_std_pitch | 10 | 32.555 | 39.464 | 48.490 | 8 | 40.694 | 42.260 | 48.696 |
| pre_mean_intensity | 10 | 10.784 | 63.064 | 66.089 | 8 | 63.480 | 64.099 | 66.383 |
| pre_std_intensity | 10 | 9.174 | 10.877 | 13.563 | 8 | 11.468 | 11.656 | 13.692 |
| post_utmosv2 | 10 | 1.881 | 2.035 | 2.172 | 8 | 2.053 | 2.057 | 2.173 |
| post_wpm | 10 | 170.359 | 178.409 | 218.203 | 8 | 189.512 | 178.409 | 229.609 |
| post_speech_dur_s | 10 | 4.144 | 4.800 | 5.296 | 8 | 5.020 | 4.960 | 5.328 |
| post_mean_pitch | 10 | 183.612 | 201.385 | 214.450 | 8 | 202.118 | 201.385 | 205.656 |
| post_std_pitch | 10 | 35.586 | 35.189 | 54.389 | 8 | 37.455 | 35.189 | 48.553 |
| post_mean_intensity | 10 | 33.623 | 59.251 | 61.500 | 8 | 59.243 | 59.251 | 60.694 |
| post_std_intensity | 10 | 13.453 | 15.021 | 15.905 | 8 | 14.849 | 15.021 | 16.127 |
| clean_utmosv2 | 10 | 1.840 | 2.042 | 2.297 | 8 | 2.129 | 2.109 | 2.363 |
| clean_wpm | 10 | 140.636 | 179.674 | 184.272 | 8 | 175.795 | 180.517 | 185.468 |
| clean_speech_dur_s | 10 | 5.912 | 7.160 | 7.928 | 8 | 7.390 | 7.600 | 7.944 |
| clean_mean_pitch | 10 | 162.705 | 199.610 | 213.076 | 8 | 203.381 | 200.751 | 213.709 |
| clean_std_pitch | 10 | 30.325 | 36.934 | 43.037 | 8 | 37.906 | 39.853 | 43.146 |
| clean_mean_intensity | 10 | 8.394 | 59.084 | 62.384 | 8 | 60.492 | 60.394 | 62.411 |
| clean_std_intensity | 10 | 11.446 | 14.078 | 15.070 | 8 | 14.308 | 14.564 | 15.248 |
| split_t | 10 | 7.320 | 7.120 | 7.848 | 8 | 7.100 | 7.120 | 7.376 |
| behavior_C_RESPOND | 10 | 0.100 | 0.000 | 0.100 | 8 | 0.000 | 0.000 | 0.000 |
| behavior_C_RESUME | 10 | 0.200 | 0.000 | 1.000 | 8 | 0.250 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 8 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.700 | 1.000 | 1.000 | 8 | 0.750 | 1.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 50; outcomes: ok 36, stale 14
- latency over ok calls (ms): p50 308, p90 872; hedged share: 40.4%
- actions: drop_backchannel 9, drop_side_talk 3, end_turn 9, fallback 1, hold_backchannel 1, keep_listening 29

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_pitch": 30.681370205349392,
    "mean_pitch": 163.39411417643228,
    "speech_dur_s": 1.936,
    "utmosv2": 1.7251178688473172,
    "std_intensity": 8.62219344245063,
    "mean_intensity": 4.492048051622179,
    "wpm": 119.7222746232367
   },
   "post": {
    "std_pitch": 37.455209255218506,
    "mean_pitch": 202.11769676208496,
    "speech_dur_s": 4.5,
    "utmosv2": 1.9934466928243637,
    "std_intensity": 14.641758799552917,
    "mean_intensity": 59.24303722381592,
    "wpm": 179.2579211665702
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.1,
   "C_RESUME": 0.2,
   "C_UNKNOWN": 0.7
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | yes | 0.892 | 2.692 | 1 | 1 | 7.600 | 0 | 1 | 0 | 0 |
| 29 | yes | 0.604 | 2.852 | 1 | 1 | 7.200 | 0 | 1 | 0 | 0 |
| 3 | yes | 0.476 | 1.956 | 1 | 1 | 7.040 | 0 | 0 | 0 | 1 |
| 32 | yes | 0.444 | 2.500 | 1 | 1 | 6.880 | 0 | 0 | 0 | 1 |
| 34 | no | - | - | 0 | 0 | 6.322 | 0 | 0 | 0 | 1 |
| 55 | yes | 0.636 | 3.108 | 1 | 1 | 7.200 | 0 | 0 | 0 | 1 |
| 64 | yes | 0.732 | 1.892 | 1 | 1 | 6.720 | 0 | 0 | 0 | 1 |
| 7 | yes | 0.636 | 1.860 | 1 | 1 | 6.880 | 0 | 0 | 0 | 1 |
| 92 | yes | 0.700 | 2.788 | 1 | 1 | 7.280 | 0 | 0 | 0 | 1 |
| 97 | no | - | 3.204 | 0 | 1 | 10.080 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 102.6, "asr": [{"model_load_s": 2.58, "transcribe_s": 10.75, "audio_s": 121.9, "files": 10, "wall_s": 17.02, "audio_name": "output.wav"}, {"model_load_s": 2.62, "transcribe_s": 10.73, "audio_s": 121.91, "files": 10, "wall_s": 17.06, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.1, "general_before_after": 43.2, "behavior": 24.2}}

## v1.5/user_interruption  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 9/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 9 | 2.529 | 2.972 | 3.337 | 9 | 2.529 | 2.972 | 3.337 |
| resp_latency | 10 | 2.518 | 2.596 | 2.822 | 9 | 2.509 | 2.596 | 2.871 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.100 | 9 | 1.111 | 1.000 | 1.200 |
| n_resp_intervals | 10 | 1.200 | 1.000 | 2.000 | 9 | 1.222 | 1.000 | 2.000 |
| pre_utmosv2 | 10 | 1.970 | 2.088 | 2.284 | 9 | 2.113 | 2.091 | 2.289 |
| pre_wpm | 10 | 168.497 | 180.190 | 210.687 | 9 | 187.218 | 180.380 | 211.373 |
| pre_speech_dur_s | 10 | 4.816 | 5.400 | 6.352 | 9 | 5.351 | 5.600 | 6.384 |
| pre_mean_pitch | 10 | 185.791 | 202.682 | 219.721 | 9 | 206.434 | 205.377 | 219.798 |
| pre_std_pitch | 10 | 37.456 | 39.541 | 48.324 | 9 | 41.618 | 40.211 | 49.927 |
| pre_mean_intensity | 10 | 33.779 | 59.287 | 62.221 | 9 | 59.755 | 59.602 | 62.227 |
| pre_std_intensity | 10 | 13.619 | 15.047 | 16.461 | 9 | 15.133 | 15.847 | 16.549 |
| post_utmosv2 | 10 | 1.842 | 1.792 | 2.137 | 9 | 1.871 | 1.812 | 2.165 |
| post_wpm | 10 | 260.079 | 202.823 | 328.125 | 9 | 261.199 | 200.000 | 375.000 |
| post_speech_dur_s | 10 | 2.568 | 1.840 | 4.816 | 9 | 2.613 | 1.520 | 4.832 |
| post_mean_pitch | 10 | 208.054 | 200.313 | 241.076 | 9 | 204.504 | 199.502 | 235.833 |
| post_std_pitch | 10 | 42.423 | 40.293 | 75.210 | 9 | 39.034 | 37.780 | 58.517 |
| post_mean_intensity | 10 | 60.041 | 59.887 | 63.221 | 9 | 59.745 | 59.478 | 63.239 |
| post_std_intensity | 10 | 14.685 | 15.256 | 17.909 | 9 | 14.581 | 15.195 | 17.962 |
| clean_utmosv2 | 10 | 2.048 | 2.038 | 2.231 | 9 | 2.080 | 2.045 | 2.235 |
| clean_wpm | 10 | 193.862 | 188.161 | 218.096 | 9 | 191.177 | 184.322 | 215.809 |
| clean_speech_dur_s | 10 | 9.368 | 9.920 | 10.936 | 9 | 9.644 | 10.000 | 10.992 |
| clean_mean_pitch | 10 | 202.283 | 202.633 | 207.265 | 9 | 203.215 | 203.446 | 207.284 |
| clean_std_pitch | 10 | 43.366 | 43.608 | 51.781 | 9 | 42.831 | 42.790 | 52.273 |
| clean_mean_intensity | 10 | 59.580 | 59.508 | 60.399 | 9 | 59.688 | 59.525 | 60.444 |
| clean_std_intensity | 10 | 15.440 | 15.439 | 16.451 | 9 | 15.306 | 15.273 | 16.237 |
| split_t | 10 | 10.640 | 10.400 | 12.368 | 9 | 10.471 | 10.160 | 12.000 |
| behavior_C_RESPOND | 10 | 0.200 | 0.000 | 1.000 | 9 | 0.111 | 0.000 | 0.200 |
| behavior_C_RESUME | 10 | 0.400 | 0.000 | 1.000 | 9 | 0.444 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 9 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.400 | 0.000 | 1.000 | 9 | 0.444 | 0.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 75; outcomes: ok 60, stale 14, timeout 1
- latency over ok calls (ms): p50 291, p90 839; hedged share: 32.4%
- actions: drop_backchannel 11, drop_side_talk 3, end_turn 12, fallback 3, hold_backchannel 15, interrupt 6, keep_listening 39

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_pitch": 38.97632074356079,
    "speech_dur_s": 5.19,
    "utmosv2": 2.08501797914505,
    "std_intensity": 14.868420124053955,
    "mean_pitch": 204.68647384643555,
    "mean_intensity": 59.43910503387451,
    "wpm": 183.51219559147904
   },
   "post": {
    "std_pitch": 39.38545894622803,
    "speech_dur_s": 2.51,
    "utmosv2": 1.8194444924592972,
    "std_intensity": 14.654790163040161,
    "mean_pitch": 206.68056869506836,
    "mean_intensity": 60.354487895965576,
    "wpm": 213.77062165367138
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.2,
   "C_RESUME": 0.4,
   "C_UNKNOWN": 0.4
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | yes | 3.228 | 1.956 | 1 | 1 | 10.160 | 0 | 1 | 0 | 0 |
| 12 | yes | 3.228 | 2.340 | 1 | 1 | 9.520 | 0 | 0 | 0 | 1 |
| 13 | yes | 2.300 | 2.596 | 1 | 1 | 8.640 | 0 | 0 | 0 | 1 |
| 32 | yes | 1.100 | 2.628 | 2 | 2 | 10.640 | 1 | 0 | 0 | 0 |
| 45 | yes | 2.300 | 1.892 | 1 | 1 | 9.040 | 0 | 1 | 0 | 0 |
| 59 | yes | 0.924 | 2.772 | 1 | 2 | 14.240 | 0 | 0 | 0 | 1 |
| 62 | yes | 3.388 | 2.628 | 1 | 1 | 10.640 | 0 | 0 | 0 | 1 |
| 65 | yes | 3.324 | 2.500 | 1 | 1 | 11.440 | 0 | 1 | 0 | 0 |
| 85 | no | - | 2.596 | 0 | 1 | 12.160 | 1 | 0 | 0 | 0 |
| 9 | yes | 2.972 | 3.268 | 1 | 1 | 9.920 | 0 | 1 | 0 | 0 |

Timing: {"total_s": 102.8, "asr": [{"model_load_s": 2.52, "transcribe_s": 10.65, "audio_s": 150.14, "files": 10, "wall_s": 16.69, "audio_name": "output.wav"}, {"model_load_s": 2.6, "transcribe_s": 10.68, "audio_s": 150.14, "files": 10, "wall_s": 16.84, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 43.9, "behavior": 24.2}}
