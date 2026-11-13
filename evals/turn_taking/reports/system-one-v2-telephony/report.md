# FDB evaluation: system-one-v2-telephony

- evaluated at: 2026-11-10T15:19:08+00:00
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
  "variant_params": "{\"addressed_threshold\": 0.5, \"classification_timeout\": 1.5, \"complete_floor\": 0.45, \"complete_start\": 0.72, \"debounce_secs\": 0.15, \"drop_side_talk_while_speaking\": false, \"fallback_secs\": 3.0, \"hedge_after_secs\": 0.45, \"holding_fallback_secs\": 12.0, \"holding_threshold\": 0.5, \"interrupt_addressed_threshold\": 0.6, \"interrupt_requires_addressed\": true, \"model\": \"clef-flash\", \"new_request_threshold\": 0.5, \"pipecat_user_turn_stop_timeout\": 3600.0, \"provider\": \"cloudflare-workers-ai\", \"question_set\": \"v2\", \"question_set_sha\": \"be7d55a41f\", \"quiet_confirm_secs\": 0.3, \"relax_secs\": 3.0, \"side_talk_confirmations\": 2, \"taking_threshold\": 0.35}"
}
```

## v1/candor_pause_handling  (upstream task: `pause_handling`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.200 | 0.000 | 1.000 |
| n_words | 10 | 2.500 | 0.000 | 9.700 |
| premature_turn_end | 10 | 0.100 | 0.000 | 0.100 |
| premature_llm_start | 10 | 0.100 | 0.000 | 0.100 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `n_words`: Number of ASR words in the agent's output.
- `premature_turn_end`: Pause handling: 1 if the design tried to take the turn during the pause even if no audio came out (a user_turn.stopped event in [pause start - 0.3 s, pause end + 0.5 s]).
- `premature_llm_start`: Pause handling: 1 if an llm.text event followed that premature stop (up to pause end + 2.5 s), i.e. the LLM actually started answering.

System one:

- samples with system1 events: 10/10; judgments: 113; outcomes: ok 95, stale 18
- latency over ok calls (ms): p50 197, p90 615; hedged share: 25.0%
- actions: drop_backchannel 4, drop_side_talk 4, end_turn 5, fallback 1, hold_backchannel 6, interrupt 1, keep_listening 97

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.20000 | 0.20000 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | n_words | premature_turn_end | premature_llm_start |
|---|---|---|---|---|
| 123 | 0 | 0 | 0 | 0 |
| 139 | 1 | 16 | 0 | 0 |
| 141 | 0 | 0 | 0 | 0 |
| 154 | 0 | 0 | 0 | 0 |
| 172 | 0 | 0 | 0 | 0 |
| 200 | 0 | 0 | 0 | 0 |
| 37 | 0 | 0 | 0 | 0 |
| 44 | 0 | 0 | 0 | 0 |
| 6 | 1 | 9 | 1 | 1 |
| 68 | 0 | 0 | 0 | 0 |

Timing: {"total_s": 21.9, "asr": [{"model_load_s": 4.15, "transcribe_s": 11.07, "audio_s": 115.04, "files": 10, "wall_s": 21.48, "audio_name": "output.wav"}], "eval_s": {"pause_handling": 0.4}}

## v1/candor_turn_taking  (upstream task: `smooth_turn_taking`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.800 | 1.000 | 1.000 |
| latency_raw | 8 | 0.794 | 2.085 | 4.173 |
| latency | 8 | 2.135 | 2.085 | 4.173 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `latency_raw`: Same as latency but unclamped (negative = agent started before the user finished).
- `latency`: Seconds from the user turn/interruption end to the agent's first word, clamped at 0; only samples with TOR=1.

System one:

- samples with system1 events: 10/10; judgments: 74; outcomes: ok 69, stale 5
- latency over ok calls (ms): p50 164, p90 440; hedged share: 13.5%
- actions: drop_backchannel 1, drop_side_talk 6, end_turn 7, fallback 2, hold_backchannel 5, keep_listening 59

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.80000 | 0.80000 | yes |
| latency | 2.13500 | 2.13500 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | latency_raw | latency |
|---|---|---|---|
| 1 | 0 | - | - |
| 10 | 0 | - | - |
| 105 | 1 | 4.140 | 4.140 |
| 113 | 1 | -10.730 | 0 |
| 115 | 1 | 2.270 | 2.270 |
| 17 | 1 | 1.880 | 1.880 |
| 18 | 1 | 1.960 | 1.960 |
| 32 | 1 | 4.250 | 4.250 |
| 53 | 1 | 2.210 | 2.210 |
| 69 | 1 | 0.370 | 0.370 |

Timing: {"total_s": 18.9, "asr": [{"model_load_s": 2.76, "transcribe_s": 11.26, "audio_s": 125.0, "files": 10, "wall_s": 18.57, "audio_name": "output.wav"}], "eval_s": {"smooth_turn_taking": 0.3}}

## v1.5/background_speech  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 9/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.993 | 1.036 | 1.647 | 9 | 1.100 | 1.276 | 1.666 |
| resp_latency | 10 | 2.761 | 2.692 | 3.322 | 9 | 2.644 | 2.564 | 3.242 |
| n_stop_intervals | 10 | 1.100 | 1.000 | 1.100 | 9 | 1.111 | 1.000 | 1.200 |
| n_resp_intervals | 10 | 1.500 | 1.500 | 2.000 | 9 | 1.444 | 1.000 | 2.000 |
| pre_utmosv2 | 10 | 1.994 | 2.082 | 2.176 | 9 | 2.045 | 2.100 | 2.184 |
| pre_wpm | 10 | 154.425 | 164.773 | 212.670 | 9 | 171.584 | 170.455 | 214.402 |
| pre_speech_dur_s | 10 | 2.488 | 2.600 | 3.920 | 9 | 2.764 | 2.640 | 3.920 |
| pre_mean_pitch | 10 | 201.918 | 201.198 | 211.448 | 9 | 200.645 | 195.546 | 208.371 |
| pre_std_pitch | 10 | 30.833 | 31.643 | 35.744 | 9 | 32.197 | 31.923 | 35.934 |
| pre_mean_intensity | 10 | 61.367 | 61.335 | 65.054 | 9 | 60.889 | 61.092 | 63.312 |
| pre_std_intensity | 10 | 13.670 | 14.399 | 15.419 | 9 | 13.942 | 14.483 | 15.513 |
| post_utmosv2 | 10 | 1.842 | 1.965 | 2.154 | 9 | 1.845 | 2.041 | 2.170 |
| post_wpm | 10 | 161.213 | 164.103 | 222.618 | 9 | 153.084 | 161.538 | 214.262 |
| post_speech_dur_s | 10 | 3.784 | 4.760 | 5.248 | 9 | 4.062 | 4.800 | 5.296 |
| post_mean_pitch | 10 | 230.121 | 205.380 | 251.163 | 9 | 230.435 | 204.716 | 261.870 |
| post_std_pitch | 10 | 34.780 | 36.925 | 49.555 | 9 | 33.732 | 35.946 | 50.410 |
| post_mean_intensity | 10 | 52.688 | 59.567 | 60.565 | 9 | 52.033 | 59.755 | 60.733 |
| post_std_intensity | 10 | 15.220 | 15.189 | 16.581 | 9 | 15.341 | 15.548 | 16.601 |
| clean_utmosv2 | 10 | 2.049 | 2.103 | 2.243 | 9 | 2.029 | 2.075 | 2.177 |
| clean_wpm | 10 | 170.113 | 159.729 | 201.429 | 9 | 172.348 | 164.286 | 202.857 |
| clean_speech_dur_s | 10 | 6.376 | 7.320 | 8.752 | 9 | 6.773 | 7.360 | 8.784 |
| clean_mean_pitch | 10 | 198.885 | 197.998 | 209.627 | 9 | 198.712 | 197.362 | 209.708 |
| clean_std_pitch | 10 | 38.391 | 38.687 | 41.646 | 9 | 38.505 | 39.425 | 42.072 |
| clean_mean_intensity | 10 | 60.038 | 60.498 | 61.687 | 9 | 59.714 | 60.418 | 61.171 |
| clean_std_intensity | 10 | 14.674 | 14.509 | 15.873 | 9 | 14.956 | 14.536 | 16.040 |
| split_t | 10 | 7.568 | 7.720 | 9.104 | 9 | 7.404 | 7.680 | 8.336 |
| behavior_C_RESPOND | 10 | 0.400 | 0.000 | 1.000 | 9 | 0.333 | 0.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.300 | 0.000 | 1.000 | 9 | 0.333 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 9 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.300 | 0.000 | 1.000 | 9 | 0.333 | 0.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 46; outcomes: ok 39, stale 7
- latency over ok calls (ms): p50 171, p90 628; hedged share: 26.7%
- actions: drop_backchannel 7, drop_side_talk 4, end_turn 14, hold_backchannel 10, interrupt 4, keep_listening 17, open_turn 1

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "speech_dur_s": 2.7644444444444445,
    "wpm": 164.49914482838588,
    "std_intensity": 13.767561793327332,
    "std_pitch": 31.54030203819275,
    "mean_intensity": 61.248111724853516,
    "mean_pitch": 201.6453628540039,
    "utmosv2": 2.019566461443901
   },
   "post": {
    "speech_dur_s": 4.0200000000000005,
    "wpm": 172.21939668150824,
    "std_intensity": 15.199364304542542,
    "std_pitch": 36.31936955451965,
    "mean_intensity": 59.24604606628418,
    "mean_pitch": 205.4573745727539,
    "utmosv2": 1.9295637607574463
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.4,
   "C_RESUME": 0.3,
   "C_UNKNOWN": 0.3
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 0.188 | 2.820 | 1 | 1 | 5.520 | 0 | 0 | 0 | 1 |
| 100 | yes | 0.764 | 2.420 | 1 | 2 | 6.240 | 0 | 0 | 0 | 1 |
| 11 | yes | 1.276 | 2.116 | 1 | 1 | 8.000 | 0 | 1 | 0 | 0 |
| 21 | yes | 1.820 | 1.908 | 1 | 2 | 7.360 | 1 | 0 | 0 | 0 |
| 49 | yes | 1.468 | 2.308 | 1 | 2 | 7.680 | 1 | 0 | 0 | 0 |
| 54 | yes | 1.596 | 3.268 | 1 | 1 | 6.640 | 0 | 0 | 0 | 1 |
| 61 | yes | 1.628 | 3.236 | 1 | 1 | 7.760 | 0 | 1 | 0 | 0 |
| 76 | yes | 0.796 | 3.156 | 1 | 2 | 9.680 | 1 | 0 | 0 | 0 |
| 80 | yes | 0.364 | 2.564 | 2 | 1 | 7.760 | 0 | 1 | 0 | 0 |
| 98 | no | 0.028 | 3.812 | 1 | 2 | 9.040 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 105.6, "asr": [{"model_load_s": 2.72, "transcribe_s": 11.31, "audio_s": 125.02, "files": 10, "wall_s": 18.31, "audio_name": "output.wav"}, {"model_load_s": 2.78, "transcribe_s": 11.6, "audio_s": 125.02, "files": 10, "wall_s": 18.56, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 45.7, "behavior": 21.9}}

## v1.5/talking_to_other  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 1.721 | 1.740 | 2.038 | 10 | 1.721 | 1.740 | 2.038 |
| resp_latency | 10 | 2.993 | 3.028 | 3.284 | 10 | 2.993 | 3.028 | 3.284 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| pre_utmosv2 | 10 | 1.891 | 1.812 | 2.151 | 10 | 1.891 | 1.812 | 2.151 |
| pre_wpm | 10 | 148.826 | 145.833 | 178.618 | 10 | 148.826 | 145.833 | 178.618 |
| pre_speech_dur_s | 10 | 3.040 | 3.120 | 3.368 | 10 | 3.040 | 3.120 | 3.368 |
| pre_mean_pitch | 10 | 201.047 | 202.366 | 207.500 | 10 | 201.047 | 202.366 | 207.500 |
| pre_std_pitch | 10 | 39.135 | 39.847 | 46.099 | 10 | 39.135 | 39.847 | 46.099 |
| pre_mean_intensity | 10 | 59.856 | 59.525 | 62.393 | 10 | 59.856 | 59.525 | 62.393 |
| pre_std_intensity | 10 | 14.464 | 14.421 | 15.824 | 10 | 14.464 | 14.421 | 15.824 |
| post_utmosv2 | 10 | 1.848 | 2.111 | 2.290 | 10 | 1.848 | 2.111 | 2.290 |
| post_wpm | 10 | 126.060 | 145.462 | 185.789 | 10 | 126.060 | 145.462 | 185.789 |
| post_speech_dur_s | 10 | 3.336 | 4.680 | 5.296 | 10 | 3.336 | 4.680 | 5.296 |
| post_mean_pitch | 10 | 207.773 | 192.772 | 238.114 | 10 | 207.773 | 192.772 | 238.114 |
| post_std_pitch | 10 | 29.635 | 36.119 | 41.400 | 10 | 29.635 | 36.119 | 41.400 |
| post_mean_intensity | 10 | 29.015 | 59.387 | 63.631 | 10 | 29.015 | 59.387 | 63.631 |
| post_std_intensity | 10 | 11.824 | 13.658 | 15.320 | 10 | 11.824 | 13.658 | 15.320 |
| clean_utmosv2 | 10 | 2.072 | 2.031 | 2.228 | 10 | 2.072 | 2.031 | 2.228 |
| clean_wpm | 10 | 149.179 | 147.955 | 163.035 | 10 | 149.179 | 147.955 | 163.035 |
| clean_speech_dur_s | 10 | 6.648 | 7.480 | 8.272 | 10 | 6.648 | 7.480 | 8.272 |
| clean_mean_pitch | 10 | 198.962 | 201.275 | 205.590 | 10 | 198.962 | 201.275 | 205.590 |
| clean_std_pitch | 10 | 39.606 | 40.533 | 43.847 | 10 | 39.606 | 40.533 | 43.847 |
| clean_mean_intensity | 10 | 59.526 | 59.231 | 60.698 | 10 | 59.526 | 59.231 | 60.698 |
| clean_std_intensity | 10 | 14.932 | 14.939 | 15.977 | 10 | 14.932 | 14.939 | 15.977 |
| split_t | 10 | 7.736 | 7.800 | 8.112 | 10 | 7.736 | 7.800 | 8.112 |
| behavior_C_RESPOND | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_RESUME | 10 | 0.300 | 0.000 | 1.000 | 10 | 0.300 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.700 | 1.000 | 1.000 | 10 | 0.700 | 1.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 51; outcomes: ok 45, stale 6
- latency over ok calls (ms): p50 210, p90 638; hedged share: 23.5%
- actions: drop_backchannel 1, drop_side_talk 10, end_turn 10, hold_backchannel 16, keep_listening 15

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "speech_dur_s": 3.059999999999999,
    "std_pitch": 38.95286774635315,
    "mean_pitch": 200.56844902038574,
    "std_intensity": 14.55922782421112,
    "utmosv2": 1.8640680313110352,
    "mean_intensity": 59.92517852783203,
    "wpm": 147.33354102826894
   },
   "post": {
    "speech_dur_s": 3.1022222222222227,
    "std_pitch": 31.8688323199749,
    "mean_pitch": 193.8697624206543,
    "std_intensity": 12.838085293769836,
    "utmosv2": 1.932833656668663,
    "mean_intensity": 53.258559226989746,
    "wpm": 117.84496023158916
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESUME": 0.3,
   "C_UNKNOWN": 0.7
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 1.500 | 2.212 | 1 | 1 | 6.960 | 0 | 0 | 0 | 1 |
| 20 | yes | 1.564 | 3.204 | 1 | 1 | 8.080 | 0 | 0 | 0 | 1 |
| 3 | yes | 1.820 | 2.724 | 1 | 1 | 7.840 | 0 | 0 | 0 | 1 |
| 39 | yes | 1.532 | 2.980 | 1 | 1 | 7.760 | 0 | 1 | 0 | 0 |
| 45 | yes | 2.268 | 3.428 | 1 | 1 | 8.400 | 0 | 0 | 0 | 1 |
| 48 | yes | 1.148 | 2.980 | 1 | 1 | 7.120 | 0 | 0 | 0 | 1 |
| 56 | yes | 1.724 | 2.980 | 1 | 1 | 7.840 | 0 | 0 | 0 | 1 |
| 75 | yes | 2.012 | 3.268 | 1 | 1 | 7.680 | 0 | 1 | 0 | 0 |
| 88 | yes | 1.884 | 3.076 | 1 | 1 | 8.000 | 0 | 0 | 0 | 1 |
| 99 | yes | 1.756 | 3.076 | 1 | 1 | 7.680 | 0 | 1 | 0 | 0 |

Timing: {"total_s": 105.4, "asr": [{"model_load_s": 2.73, "transcribe_s": 11.02, "audio_s": 129.8, "files": 10, "wall_s": 17.65, "audio_name": "output.wav"}, {"model_load_s": 2.73, "transcribe_s": 11.23, "audio_s": 129.8, "files": 10, "wall_s": 17.83, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 46.0, "behavior": 22.8}}

## v1.5/user_backchannel  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 9/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 9 | 0.597 | 0.636 | 0.764 | 9 | 0.597 | 0.636 | 0.764 |
| resp_latency | 10 | 2.740 | 2.580 | 3.434 | 9 | 2.834 | 2.628 | 3.505 |
| n_stop_intervals | 10 | 0.900 | 1.000 | 1.000 | 9 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.100 | 1.000 | 1.100 | 9 | 1.111 | 1.000 | 1.200 |
| pre_utmosv2 | 10 | 1.862 | 1.886 | 2.367 | 9 | 1.992 | 1.981 | 2.376 |
| pre_wpm | 10 | 137.574 | 150.966 | 202.825 | 9 | 152.860 | 163.043 | 203.726 |
| pre_speech_dur_s | 10 | 1.808 | 2.120 | 2.488 | 9 | 2.009 | 2.160 | 2.496 |
| pre_mean_pitch | 10 | 199.934 | 209.670 | 232.491 | 9 | 222.149 | 210.334 | 241.794 |
| pre_std_pitch | 10 | 32.890 | 34.584 | 46.386 | 9 | 36.545 | 35.185 | 46.454 |
| pre_mean_intensity | 10 | 37.145 | 63.540 | 66.230 | 9 | 63.494 | 65.079 | 66.328 |
| pre_std_intensity | 10 | 10.752 | 11.846 | 14.172 | 9 | 11.946 | 12.161 | 14.210 |
| post_utmosv2 | 10 | 2.053 | 1.992 | 2.224 | 9 | 2.038 | 1.984 | 2.235 |
| post_wpm | 10 | 192.107 | 185.574 | 228.246 | 9 | 189.330 | 177.966 | 231.493 |
| post_speech_dur_s | 10 | 4.832 | 4.880 | 5.360 | 9 | 5.031 | 4.960 | 5.360 |
| post_mean_pitch | 10 | 203.278 | 202.459 | 213.273 | 9 | 200.929 | 200.870 | 208.877 |
| post_std_pitch | 10 | 38.375 | 35.120 | 52.684 | 9 | 36.886 | 33.579 | 49.445 |
| post_mean_intensity | 10 | 59.909 | 59.603 | 61.611 | 9 | 59.940 | 59.580 | 61.652 |
| post_std_intensity | 10 | 15.061 | 15.043 | 17.186 | 9 | 14.800 | 14.961 | 16.133 |
| clean_utmosv2 | 10 | 1.968 | 2.080 | 2.320 | 9 | 2.111 | 2.110 | 2.329 |
| clean_wpm | 10 | 155.116 | 162.879 | 209.719 | 9 | 172.351 | 166.667 | 209.880 |
| clean_speech_dur_s | 10 | 6.536 | 7.240 | 8.024 | 9 | 7.262 | 7.280 | 8.048 |
| clean_mean_pitch | 10 | 183.189 | 200.971 | 211.349 | 9 | 203.543 | 201.717 | 211.388 |
| clean_std_pitch | 10 | 36.700 | 38.909 | 49.974 | 9 | 40.777 | 39.956 | 50.060 |
| clean_mean_intensity | 10 | 33.981 | 58.871 | 62.339 | 9 | 59.979 | 58.894 | 62.387 |
| clean_std_intensity | 10 | 12.987 | 14.610 | 15.878 | 9 | 14.430 | 14.767 | 15.887 |
| split_t | 10 | 7.144 | 7.160 | 7.424 | 9 | 6.969 | 7.120 | 7.280 |
| behavior_C_RESPOND | 10 | 0.000 | 0.000 | 0.000 | 9 | 0.000 | 0.000 | 0.000 |
| behavior_C_RESUME | 10 | 0.400 | 0.000 | 1.000 | 9 | 0.444 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 9 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.600 | 1.000 | 1.000 | 9 | 0.556 | 1.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 51; outcomes: ok 39, stale 10, timeout 2
- latency over ok calls (ms): p50 192, p90 604; hedged share: 31.4%
- actions: drop_backchannel 13, drop_side_talk 1, end_turn 9, fallback 1, hold_backchannel 3, keep_listening 28

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "mean_intensity": 63.041841983795166,
    "std_intensity": 11.625712156295776,
    "speech_dur_s": 1.9400000000000002,
    "utmosv2": 1.9348917305469513,
    "std_pitch": 35.237961769104004,
    "mean_pitch": 210.3904323577881,
    "wpm": 145.6001661705606
   },
   "post": {
    "mean_intensity": 59.839651107788086,
    "std_intensity": 15.021007537841797,
    "speech_dur_s": 5.0311111111111115,
    "utmosv2": 2.0254624634981155,
    "std_pitch": 37.812541246414185,
    "mean_pitch": 202.3608055114746,
    "wpm": 191.3183155027499
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESUME": 0.4,
   "C_UNKNOWN": 0.6
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | yes | 0.892 | 2.884 | 1 | 1 | 7.280 | 0 | 0 | 0 | 1 |
| 29 | yes | 0.604 | 2.948 | 1 | 1 | 7.280 | 0 | 1 | 0 | 0 |
| 3 | yes | 0.476 | 2.468 | 1 | 1 | 6.560 | 0 | 0 | 0 | 1 |
| 32 | yes | 0.444 | 3.364 | 1 | 1 | 6.960 | 0 | 0 | 0 | 1 |
| 34 | yes | 0.252 | 4.068 | 1 | 2 | 6.160 | 0 | 1 | 0 | 0 |
| 55 | yes | 0.636 | 2.436 | 1 | 1 | 7.200 | 0 | 0 | 0 | 1 |
| 64 | yes | 0.732 | 2.532 | 1 | 1 | 6.960 | 0 | 1 | 0 | 0 |
| 7 | yes | 0.636 | 2.628 | 1 | 1 | 7.200 | 0 | 1 | 0 | 0 |
| 92 | yes | 0.700 | 2.180 | 1 | 1 | 7.120 | 0 | 0 | 0 | 1 |
| 97 | no | - | 1.892 | 0 | 1 | 8.720 | 0 | 0 | 0 | 1 |

Timing: {"total_s": 107.7, "asr": [{"model_load_s": 2.63, "transcribe_s": 10.92, "audio_s": 121.9, "files": 10, "wall_s": 17.3, "audio_name": "output.wav"}, {"model_load_s": 2.63, "transcribe_s": 10.82, "audio_s": 121.91, "files": 10, "wall_s": 17.27, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 44.8, "behavior": 27.2}}

## v1.5/user_interruption  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 1.562 | 1.724 | 2.169 | 10 | 1.562 | 1.724 | 2.169 |
| resp_latency | 10 | 2.514 | 2.548 | 3.228 | 10 | 2.514 | 2.548 | 3.228 |
| n_stop_intervals | 10 | 1.100 | 1.000 | 1.100 | 10 | 1.100 | 1.000 | 1.100 |
| n_resp_intervals | 10 | 2.000 | 2.000 | 2.000 | 10 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 2.027 | 2.048 | 2.203 | 10 | 2.027 | 2.048 | 2.203 |
| pre_wpm | 10 | 186.693 | 184.267 | 227.667 | 10 | 186.693 | 184.267 | 227.667 |
| pre_speech_dur_s | 10 | 5.168 | 4.720 | 6.632 | 10 | 5.168 | 4.720 | 6.632 |
| pre_mean_pitch | 10 | 206.638 | 205.181 | 222.387 | 10 | 206.638 | 205.181 | 222.387 |
| pre_std_pitch | 10 | 44.249 | 41.802 | 59.208 | 10 | 44.249 | 41.802 | 59.208 |
| pre_mean_intensity | 10 | 59.633 | 59.577 | 61.420 | 10 | 59.633 | 59.577 | 61.420 |
| pre_std_intensity | 10 | 14.877 | 14.587 | 16.625 | 10 | 14.877 | 14.587 | 16.625 |
| post_utmosv2 | 10 | 1.959 | 2.086 | 2.353 | 10 | 1.959 | 2.086 | 2.353 |
| post_wpm | 10 | 158.416 | 198.529 | 242.692 | 10 | 158.416 | 198.529 | 242.692 |
| post_speech_dur_s | 10 | 1.952 | 2.040 | 3.336 | 10 | 1.952 | 2.040 | 3.336 |
| post_mean_pitch | 10 | 218.889 | 212.421 | 252.824 | 10 | 218.889 | 212.421 | 252.824 |
| post_std_pitch | 10 | 44.360 | 47.073 | 65.694 | 10 | 44.360 | 47.073 | 65.694 |
| post_mean_intensity | 10 | 58.663 | 59.561 | 61.369 | 10 | 58.663 | 59.561 | 61.369 |
| post_std_intensity | 10 | 15.900 | 15.240 | 18.236 | 10 | 15.900 | 15.240 | 18.236 |
| clean_utmosv2 | 10 | 2.104 | 2.068 | 2.390 | 10 | 2.104 | 2.068 | 2.390 |
| clean_wpm | 10 | 195.852 | 192.639 | 216.392 | 10 | 195.852 | 192.639 | 216.392 |
| clean_speech_dur_s | 10 | 10.696 | 10.640 | 11.432 | 10 | 10.696 | 10.640 | 11.432 |
| clean_mean_pitch | 10 | 202.001 | 203.019 | 207.063 | 10 | 202.001 | 203.019 | 207.063 |
| clean_std_pitch | 10 | 42.552 | 41.894 | 47.510 | 10 | 42.552 | 41.894 | 47.510 |
| clean_mean_intensity | 10 | 59.931 | 59.885 | 60.713 | 10 | 59.931 | 59.885 | 60.713 |
| clean_std_intensity | 10 | 14.910 | 14.732 | 15.705 | 10 | 14.910 | 14.732 | 15.705 |
| split_t | 10 | 11.336 | 11.600 | 13.712 | 10 | 11.336 | 11.600 | 13.712 |
| behavior_C_RESPOND | 10 | 0.600 | 1.000 | 1.000 | 10 | 0.600 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.300 | 0.000 | 1.000 | 10 | 0.300 | 0.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 71; outcomes: ok 63, stale 6, timeout 2
- latency over ok calls (ms): p50 203, p90 590; hedged share: 16.9%
- actions: drop_backchannel 5, end_turn 18, fallback 3, hold_backchannel 8, interrupt 11, keep_listening 36

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_pitch": 42.942731618881226,
    "speech_dur_s": 4.67,
    "mean_pitch": 205.9553680419922,
    "utmosv2": 2.0280055105686188,
    "mean_intensity": 59.718846797943115,
    "wpm": 188.14304873492046,
    "std_intensity": 14.785645842552185
   },
   "post": {
    "std_pitch": 46.249374866485596,
    "speech_dur_s": 1.5822222222222224,
    "mean_pitch": 215.88964462280273,
    "utmosv2": 1.9644581824541092,
    "mean_intensity": 58.87812376022339,
    "wpm": 137.12880256997903,
    "std_intensity": 15.427558660507202
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.6,
   "C_RESUME": 0.1,
   "C_UNKNOWN": 0.3
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | yes | 1.980 | 3.204 | 1 | 2 | 8.880 | 0 | 1 | 0 | 0 |
| 12 | yes | 0.476 | 3.444 | 1 | 2 | 6.560 | 0 | 0 | 0 | 1 |
| 13 | yes | 1.308 | 2.212 | 1 | 2 | 11.040 | 1 | 0 | 0 | 0 |
| 32 | yes | 1.100 | 1.700 | 2 | 2 | 10.240 | 1 | 0 | 0 | 0 |
| 45 | yes | 0.764 | 2.804 | 1 | 2 | 12.000 | 1 | 0 | 0 | 0 |
| 59 | yes | 2.428 | 2.292 | 1 | 2 | 12.480 | 0 | 0 | 0 | 1 |
| 62 | yes | 1.980 | 2.900 | 1 | 2 | 15.440 | 0 | 0 | 0 | 1 |
| 65 | yes | 1.660 | 2.932 | 1 | 2 | 13.520 | 1 | 0 | 0 | 0 |
| 85 | yes | 1.788 | 1.764 | 1 | 2 | 11.520 | 1 | 0 | 0 | 0 |
| 9 | yes | 2.140 | 1.892 | 1 | 2 | 11.680 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 107.8, "asr": [{"model_load_s": 2.78, "transcribe_s": 11.14, "audio_s": 150.14, "files": 10, "wall_s": 17.76, "audio_name": "output.wav"}, {"model_load_s": 2.94, "transcribe_s": 11.35, "audio_s": 150.14, "files": 10, "wall_s": 18.15, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.3, "general_before_after": 45.7, "behavior": 24.9}}
