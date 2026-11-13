# FDB evaluation: baseline-holdout-telephony

- evaluated at: 2026-11-10T16:27:08+00:00
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
  "variant": "baseline",
  "bench_agent_version": "1",
  "bench_agent_fingerprint": "c05110edaeed",
  "tools": "control_device,manage_timers,calendar,send_message,read_messages,play_media,add_note,lookup_info",
  "variant_extra_instructions": "",
  "variant_params": "{}"
}
```

## v1/candor_pause_handling  (upstream task: `pause_handling`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.100 | 0.000 | 0.100 |
| n_words | 10 | 1.700 | 0.000 | 1.700 |
| premature_turn_end | 10 | 0.400 | 0.000 | 1.000 |
| premature_llm_start | 10 | 0.200 | 0.000 | 1.000 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `n_words`: Number of ASR words in the agent's output.
- `premature_turn_end`: Pause handling: 1 if the design tried to take the turn during the pause even if no audio came out (a user_turn.stopped event in [pause start - 0.3 s, pause end + 0.5 s]).
- `premature_llm_start`: Pause handling: 1 if an llm.text event followed that premature stop (up to pause end + 2.5 s), i.e. the LLM actually started answering.

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.10000 | 0.10000 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | n_words | premature_turn_end | premature_llm_start |
|---|---|---|---|---|
| 102 | 0 | 0 | 0 | 0 |
| 104 | 0 | 0 | 0 | 0 |
| 107 | 1 | 17 | 1 | 1 |
| 134 | 0 | 0 | 1 | 0 |
| 26 | 0 | 0 | 0 | 0 |
| 40 | 0 | 0 | 1 | 1 |
| 63 | 0 | 0 | 0 | 0 |
| 75 | 0 | 0 | 0 | 0 |
| 82 | 0 | 0 | 1 | 0 |
| 88 | 0 | 0 | 0 | 0 |

Timing: {"total_s": 21.9, "asr": [{"model_load_s": 6.31, "transcribe_s": 10.75, "audio_s": 123.84, "files": 10, "wall_s": 21.58, "audio_name": "output.wav"}], "eval_s": {"pause_handling": 0.3}}

## v1/candor_turn_taking  (upstream task: `smooth_turn_taking`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.700 | 1.000 | 1.000 |
| latency_raw | 7 | 3.281 | 3.980 | 4.222 |
| latency | 7 | 3.281 | 3.980 | 4.222 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `latency_raw`: Same as latency but unclamped (negative = agent started before the user finished).
- `latency`: Seconds from the user turn/interruption end to the agent's first word, clamped at 0; only samples with TOR=1.

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.70000 | 0.70000 | yes |
| latency | 3.28143 | 3.28143 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | latency_raw | latency |
|---|---|---|---|
| 11 | 1 | 3.980 | 3.980 |
| 118 | 0 | - | - |
| 13 | 1 | 4.000 | 4.000 |
| 30 | 1 | 1.340 | 1.340 |
| 47 | 1 | 1.190 | 1.190 |
| 55 | 0 | - | - |
| 61 | 1 | 3.940 | 3.940 |
| 72 | 1 | 4.450 | 4.450 |
| 89 | 1 | 4.070 | 4.070 |
| 97 | 0 | - | - |

Timing: {"total_s": 17.6, "asr": [{"model_load_s": 2.91, "transcribe_s": 10.6, "audio_s": 135.21, "files": 10, "wall_s": 17.29, "audio_name": "output.wav"}], "eval_s": {"smooth_turn_taking": 0.3}}

## v1.5/background_speech  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 6 | 0.465 | 0.492 | 0.556 | 6 | 0.465 | 0.492 | 0.556 |
| resp_latency | 10 | 1.830 | 1.676 | 2.295 | 10 | 1.830 | 1.676 | 2.295 |
| n_stop_intervals | 10 | 0.600 | 1.000 | 1.000 | 10 | 0.600 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 2.000 | 2.000 | 2.000 | 10 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 2.071 | 1.971 | 2.467 | 10 | 2.071 | 1.971 | 2.467 |
| pre_wpm | 10 | 149.287 | 148.171 | 176.250 | 10 | 149.287 | 148.171 | 176.250 |
| pre_speech_dur_s | 10 | 2.784 | 2.760 | 3.544 | 10 | 2.784 | 2.760 | 3.544 |
| pre_mean_pitch | 10 | 204.140 | 202.768 | 210.396 | 10 | 204.140 | 202.768 | 210.396 |
| pre_std_pitch | 10 | 45.909 | 49.586 | 55.278 | 10 | 45.909 | 49.586 | 55.278 |
| pre_mean_intensity | 10 | 60.898 | 60.113 | 64.715 | 10 | 60.898 | 60.113 | 64.715 |
| pre_std_intensity | 10 | 14.150 | 14.236 | 16.606 | 10 | 14.150 | 14.236 | 16.606 |
| post_utmosv2 | 10 | 2.045 | 2.073 | 2.133 | 10 | 2.045 | 2.073 | 2.133 |
| post_wpm | 10 | 221.096 | 223.718 | 251.786 | 10 | 221.096 | 223.718 | 251.786 |
| post_speech_dur_s | 10 | 3.288 | 3.360 | 3.608 | 10 | 3.288 | 3.360 | 3.608 |
| post_mean_pitch | 10 | 210.481 | 209.865 | 216.036 | 10 | 210.481 | 209.865 | 216.036 |
| post_std_pitch | 10 | 47.988 | 49.917 | 54.501 | 10 | 47.988 | 49.917 | 54.501 |
| post_mean_intensity | 10 | 60.067 | 59.994 | 61.363 | 10 | 60.067 | 59.994 | 61.363 |
| post_std_intensity | 10 | 15.510 | 15.927 | 16.620 | 10 | 15.510 | 15.927 | 16.620 |
| clean_utmosv2 | 10 | 2.076 | 2.040 | 2.220 | 10 | 2.076 | 2.040 | 2.220 |
| clean_wpm | 10 | 149.159 | 144.767 | 183.435 | 10 | 149.159 | 144.767 | 183.435 |
| clean_speech_dur_s | 10 | 5.600 | 4.880 | 9.160 | 10 | 5.600 | 4.880 | 9.160 |
| clean_mean_pitch | 10 | 200.491 | 200.858 | 205.243 | 10 | 200.491 | 200.858 | 205.243 |
| clean_std_pitch | 10 | 44.943 | 43.480 | 53.199 | 10 | 44.943 | 43.480 | 53.199 |
| clean_mean_intensity | 10 | 59.902 | 60.008 | 61.628 | 10 | 59.902 | 60.008 | 61.628 |
| clean_std_intensity | 10 | 14.456 | 14.759 | 15.345 | 10 | 14.456 | 14.759 | 15.345 |
| split_t | 10 | 8.624 | 8.640 | 9.048 | 10 | 8.624 | 8.640 | 9.048 |
| behavior_C_RESPOND | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |

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

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "utmosv2": 2.057191491127014,
    "std_intensity": 14.088086724281311,
    "std_pitch": 46.1388144493103,
    "wpm": 152.75459751148674,
    "speech_dur_s": 2.76,
    "mean_intensity": 60.84912443161011,
    "mean_pitch": 203.5626106262207
   },
   "post": {
    "utmosv2": 2.0416323244571686,
    "std_intensity": 15.77621304988861,
    "std_pitch": 49.03101825714111,
    "wpm": 224.59537744863837,
    "speech_dur_s": 3.3499999999999996,
    "mean_intensity": 60.154690742492676,
    "mean_pitch": 210.6698112487793
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 1.0
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 17 | yes | - | 1.524 | 0 | 2 | 8.160 | 1 | 0 | 0 | 0 |
| 34 | yes | 0.572 | 2.036 | 1 | 2 | 8.320 | 1 | 0 | 0 | 0 |
| 37 | yes | - | 2.612 | 0 | 2 | 8.400 | 1 | 0 | 0 | 0 |
| 4 | yes | 0.476 | 1.700 | 1 | 2 | 9.120 | 1 | 0 | 0 | 0 |
| 74 | yes | 0.412 | 1.652 | 1 | 2 | 9.040 | 1 | 0 | 0 | 0 |
| 79 | yes | - | 1.588 | 0 | 2 | 8.800 | 1 | 0 | 0 | 0 |
| 87 | yes | 0.508 | 1.940 | 1 | 2 | 8.960 | 1 | 0 | 0 | 0 |
| 90 | yes | 0.540 | 2.260 | 1 | 2 | 9.040 | 1 | 0 | 0 | 0 |
| 92 | yes | 0.284 | 1.396 | 1 | 2 | 7.920 | 1 | 0 | 0 | 0 |
| 94 | yes | - | 1.588 | 0 | 2 | 8.480 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 100.2, "asr": [{"model_load_s": 2.89, "transcribe_s": 10.79, "audio_s": 122.32, "files": 10, "wall_s": 17.4, "audio_name": "output.wav"}, {"model_load_s": 2.98, "transcribe_s": 10.79, "audio_s": 122.32, "files": 10, "wall_s": 17.57, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 44.5, "behavior": 19.6}}

## v1.5/talking_to_other  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 9 | 0.376 | 0.412 | 0.476 | 9 | 0.376 | 0.412 | 0.476 |
| resp_latency | 10 | 1.761 | 1.612 | 2.186 | 10 | 1.761 | 1.612 | 2.186 |
| n_stop_intervals | 10 | 0.900 | 1.000 | 1.000 | 10 | 0.900 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 2.000 | 2.000 | 2.000 | 10 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 1.863 | 1.903 | 2.075 | 10 | 1.863 | 1.903 | 2.075 |
| pre_wpm | 10 | 171.159 | 173.226 | 221.936 | 10 | 171.159 | 173.226 | 221.936 |
| pre_speech_dur_s | 10 | 2.888 | 3.000 | 3.296 | 10 | 2.888 | 3.000 | 3.296 |
| pre_mean_pitch | 10 | 204.503 | 205.727 | 222.447 | 10 | 204.503 | 205.727 | 222.447 |
| pre_std_pitch | 10 | 39.237 | 39.450 | 52.586 | 10 | 39.237 | 39.450 | 52.586 |
| pre_mean_intensity | 10 | 60.831 | 60.541 | 64.647 | 10 | 60.831 | 60.541 | 64.647 |
| pre_std_intensity | 10 | 13.954 | 14.573 | 15.637 | 10 | 13.954 | 14.573 | 15.637 |
| post_utmosv2 | 10 | 2.135 | 2.187 | 2.316 | 10 | 2.135 | 2.187 | 2.316 |
| post_wpm | 10 | 253.540 | 243.968 | 274.751 | 10 | 253.540 | 243.968 | 274.751 |
| post_speech_dur_s | 10 | 3.248 | 3.360 | 3.440 | 10 | 3.248 | 3.360 | 3.440 |
| post_mean_pitch | 10 | 202.839 | 200.197 | 213.291 | 10 | 202.839 | 200.197 | 213.291 |
| post_std_pitch | 10 | 41.015 | 41.127 | 51.202 | 10 | 41.015 | 41.127 | 51.202 |
| post_mean_intensity | 10 | 61.559 | 61.651 | 63.473 | 10 | 61.559 | 61.651 | 63.473 |
| post_std_intensity | 10 | 14.115 | 13.956 | 14.768 | 10 | 14.115 | 13.956 | 14.768 |
| clean_utmosv2 | 10 | 2.060 | 2.166 | 2.335 | 10 | 2.060 | 2.166 | 2.335 |
| clean_wpm | 10 | 161.071 | 161.438 | 175.426 | 10 | 161.071 | 161.438 | 175.426 |
| clean_speech_dur_s | 10 | 7.192 | 8.760 | 9.952 | 10 | 7.192 | 8.760 | 9.952 |
| clean_mean_pitch | 10 | 198.804 | 200.657 | 203.844 | 10 | 198.804 | 200.657 | 203.844 |
| clean_std_pitch | 10 | 38.806 | 37.836 | 45.912 | 10 | 38.806 | 37.836 | 45.912 |
| clean_mean_intensity | 10 | 60.062 | 60.108 | 61.549 | 10 | 60.062 | 60.108 | 61.549 |
| clean_std_intensity | 10 | 14.608 | 14.624 | 15.438 | 10 | 14.608 | 14.624 | 15.438 |
| split_t | 10 | 9.800 | 9.720 | 10.152 | 10 | 9.800 | 9.720 | 10.152 |
| behavior_C_RESPOND | 10 | 0.900 | 1.000 | 1.000 | 10 | 0.900 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNKNOWN | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |

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

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_intensity": 14.196842551231384,
    "utmosv2": 1.8719367384910583,
    "mean_pitch": 204.99879455566406,
    "speech_dur_s": 2.9099999999999997,
    "std_pitch": 39.55219388008118,
    "wpm": 170.8109874083753,
    "mean_intensity": 60.686561584472656
   },
   "post": {
    "std_intensity": 13.951967358589172,
    "utmosv2": 2.15280444920063,
    "mean_pitch": 202.36780548095703,
    "speech_dur_s": 3.2888888888888896,
    "std_pitch": 40.34199905395508,
    "wpm": 241.7759970420236,
    "mean_intensity": 61.454872131347656
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.9,
   "C_UNCERTAIN_HANDLING": 0.1
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 14 | yes | 0.444 | 1.540 | 1 | 2 | 10.080 | 1 | 0 | 0 | 0 |
| 15 | yes | 0.060 | 1.460 | 1 | 2 | 9.600 | 1 | 0 | 0 | 0 |
| 16 | yes | 0.476 | 2.388 | 1 | 2 | 9.600 | 1 | 0 | 0 | 0 |
| 43 | yes | 0.444 | 1.652 | 1 | 2 | 9.840 | 0 | 0 | 1 | 0 |
| 6 | yes | 0.380 | 1.572 | 1 | 2 | 9.840 | 1 | 0 | 0 | 0 |
| 82 | yes | 0.380 | 2.004 | 1 | 2 | 9.120 | 1 | 0 | 0 | 0 |
| 83 | yes | 0.476 | 2.164 | 1 | 2 | 10.800 | 1 | 0 | 0 | 0 |
| 86 | yes | 0.412 | 1.604 | 1 | 2 | 9.680 | 1 | 0 | 0 | 0 |
| 90 | yes | - | 1.620 | 0 | 2 | 9.680 | 1 | 0 | 0 | 0 |
| 92 | yes | 0.316 | 1.604 | 1 | 2 | 9.760 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 103.2, "asr": [{"model_load_s": 2.8, "transcribe_s": 11.02, "audio_s": 133.47, "files": 10, "wall_s": 17.52, "audio_name": "output.wav"}, {"model_load_s": 2.76, "transcribe_s": 10.97, "audio_s": 133.47, "files": 10, "wall_s": 17.48, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 44.6, "behavior": 22.4}}

## v1.5/user_backchannel  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.399 | 0.380 | 0.482 | 10 | 0.399 | 0.380 | 0.482 |
| resp_latency | 10 | 1.998 | 1.580 | 2.999 | 10 | 1.998 | 1.580 | 2.999 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.900 | 2.000 | 2.000 | 10 | 1.900 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 2.079 | 2.068 | 2.277 | 10 | 2.079 | 2.068 | 2.277 |
| pre_wpm | 10 | 161.117 | 155.870 | 186.931 | 10 | 161.117 | 155.870 | 186.931 |
| pre_speech_dur_s | 10 | 3.296 | 3.240 | 3.608 | 10 | 3.296 | 3.240 | 3.608 |
| pre_mean_pitch | 10 | 204.218 | 204.895 | 208.681 | 10 | 204.218 | 204.895 | 208.681 |
| pre_std_pitch | 10 | 36.750 | 32.379 | 44.488 | 10 | 36.750 | 32.379 | 44.488 |
| pre_mean_intensity | 10 | 61.648 | 62.483 | 64.234 | 10 | 61.648 | 62.483 | 64.234 |
| pre_std_intensity | 10 | 13.313 | 13.003 | 16.196 | 10 | 13.313 | 13.003 | 16.196 |
| post_utmosv2 | 10 | 1.832 | 2.021 | 2.310 | 10 | 1.832 | 2.021 | 2.310 |
| post_wpm | 10 | 156.041 | 196.295 | 263.590 | 10 | 156.041 | 196.295 | 263.590 |
| post_speech_dur_s | 10 | 2.136 | 3.200 | 3.688 | 10 | 2.136 | 3.200 | 3.688 |
| post_mean_pitch | 10 | 185.039 | 203.387 | 215.760 | 10 | 185.039 | 203.387 | 215.760 |
| post_std_pitch | 10 | 40.737 | 38.232 | 64.853 | 10 | 40.737 | 38.232 | 64.853 |
| post_mean_intensity | 10 | 34.820 | 60.451 | 63.039 | 10 | 34.820 | 60.451 | 63.039 |
| post_std_intensity | 10 | 13.467 | 15.047 | 16.067 | 10 | 13.467 | 15.047 | 16.067 |
| clean_utmosv2 | 10 | 2.119 | 2.079 | 2.348 | 10 | 2.119 | 2.079 | 2.348 |
| clean_wpm | 10 | 177.130 | 170.620 | 205.287 | 10 | 177.130 | 170.620 | 205.287 |
| clean_speech_dur_s | 10 | 8.352 | 8.360 | 8.808 | 10 | 8.352 | 8.360 | 8.808 |
| clean_mean_pitch | 10 | 203.457 | 203.284 | 208.996 | 10 | 203.457 | 203.284 | 208.996 |
| clean_std_pitch | 10 | 40.250 | 40.033 | 45.251 | 10 | 40.250 | 40.033 | 45.251 |
| clean_mean_intensity | 10 | 59.835 | 59.750 | 61.402 | 10 | 59.835 | 59.750 | 61.402 |
| clean_std_intensity | 10 | 14.835 | 15.001 | 15.199 | 10 | 14.835 | 15.001 | 15.199 |
| split_t | 10 | 8.384 | 8.160 | 9.680 | 10 | 8.384 | 8.160 | 9.680 |
| behavior_C_RESPOND | 10 | 0.200 | 0.000 | 1.000 | 10 | 0.200 | 0.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.200 | 0.000 | 1.000 | 10 | 0.200 | 0.000 | 1.000 |
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

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "wpm": 158.94071358064178,
    "mean_intensity": 61.9918098449707,
    "std_pitch": 33.88342070579529,
    "std_intensity": 13.17376172542572,
    "speech_dur_s": 3.29,
    "mean_pitch": 204.0209903717041,
    "utmosv2": 2.068578377366066
   },
   "post": {
    "wpm": 142.1292491191242,
    "mean_intensity": 60.31979513168335,
    "std_pitch": 42.77161979675293,
    "std_intensity": 14.820816040039062,
    "speech_dur_s": 1.9555555555555557,
    "mean_pitch": 203.2573013305664,
    "utmosv2": 1.9034372866153717
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.2,
   "C_RESUME": 0.2,
   "C_UNCERTAIN_HANDLING": 0.1,
   "C_UNKNOWN": 0.5
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | yes | 0.412 | 2.996 | 1 | 2 | 7.040 | 0 | 0 | 0 | 1 |
| 41 | yes | 0.380 | 1.428 | 1 | 2 | 8.880 | 1 | 0 | 0 | 0 |
| 47 | yes | 0.316 | 1.476 | 1 | 2 | 8.000 | 0 | 0 | 1 | 0 |
| 58 | yes | 0.380 | 1.956 | 1 | 1 | 7.120 | 0 | 0 | 0 | 1 |
| 62 | yes | 0.348 | 1.508 | 1 | 2 | 8.320 | 0 | 1 | 0 | 0 |
| 63 | yes | 0.380 | 3.028 | 1 | 2 | 7.040 | 0 | 1 | 0 | 0 |
| 67 | yes | 0.476 | 1.540 | 1 | 2 | 9.520 | 0 | 0 | 0 | 1 |
| 72 | yes | 0.348 | 1.620 | 1 | 2 | 7.760 | 0 | 0 | 0 | 1 |
| 88 | yes | 0.540 | 2.884 | 1 | 2 | 11.120 | 1 | 0 | 0 | 0 |
| 95 | yes | 0.412 | 1.540 | 1 | 2 | 9.040 | 0 | 0 | 0 | 1 |

Timing: {"total_s": 115.9, "asr": [{"model_load_s": 3.15, "transcribe_s": 10.82, "audio_s": 122.74, "files": 10, "wall_s": 17.74, "audio_name": "output.wav"}, {"model_load_s": 2.7, "transcribe_s": 10.9, "audio_s": 122.74, "files": 10, "wall_s": 17.42, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 44.6, "behavior": 35.0}}

## v1.5/user_interruption  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 8/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 9 | 0.341 | 0.380 | 0.386 | 8 | 0.336 | 0.380 | 0.390 |
| resp_latency | 10 | 2.074 | 1.764 | 2.913 | 8 | 1.708 | 1.684 | 1.996 |
| n_stop_intervals | 10 | 0.900 | 1.000 | 1.000 | 8 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.900 | 2.000 | 2.000 | 8 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 2.039 | 2.092 | 2.375 | 8 | 2.174 | 2.149 | 2.376 |
| pre_wpm | 10 | 139.347 | 157.680 | 211.674 | 8 | 174.184 | 179.699 | 215.023 |
| pre_speech_dur_s | 10 | 2.920 | 3.560 | 4.104 | 8 | 3.650 | 3.680 | 4.152 |
| pre_mean_pitch | 10 | 225.863 | 211.552 | 272.521 | 8 | 206.020 | 204.880 | 221.933 |
| pre_std_pitch | 10 | 49.165 | 52.480 | 60.867 | 8 | 53.585 | 55.500 | 60.958 |
| pre_mean_intensity | 10 | 61.001 | 60.316 | 63.500 | 8 | 60.385 | 60.316 | 62.514 |
| pre_std_intensity | 10 | 13.933 | 14.114 | 16.277 | 8 | 13.877 | 14.114 | 15.575 |
| post_utmosv2 | 10 | 1.718 | 1.821 | 1.987 | 8 | 1.754 | 1.877 | 2.011 |
| post_wpm | 10 | 271.790 | 239.160 | 375.000 | 8 | 311.960 | 268.674 | 458.333 |
| post_speech_dur_s | 10 | 2.144 | 2.360 | 3.680 | 8 | 2.410 | 2.880 | 3.680 |
| post_mean_pitch | 10 | 218.339 | 207.950 | 230.885 | 8 | 209.075 | 206.683 | 218.285 |
| post_std_pitch | 10 | 46.766 | 48.468 | 60.839 | 8 | 44.476 | 48.468 | 56.326 |
| post_mean_intensity | 10 | 60.631 | 59.007 | 63.791 | 8 | 61.110 | 59.007 | 65.718 |
| post_std_intensity | 10 | 14.149 | 15.286 | 17.808 | 8 | 14.076 | 15.588 | 17.843 |
| clean_utmosv2 | 10 | 2.096 | 2.099 | 2.264 | 8 | 2.086 | 2.099 | 2.260 |
| clean_wpm | 10 | 190.230 | 191.918 | 201.981 | 8 | 190.075 | 191.918 | 200.325 |
| clean_speech_dur_s | 10 | 10.296 | 10.200 | 11.312 | 8 | 10.740 | 10.320 | 11.696 |
| clean_mean_pitch | 10 | 204.503 | 204.502 | 209.564 | 8 | 202.772 | 202.958 | 206.899 |
| clean_std_pitch | 10 | 44.462 | 44.774 | 50.752 | 8 | 44.531 | 45.330 | 50.965 |
| clean_mean_intensity | 10 | 59.657 | 59.809 | 60.520 | 8 | 59.910 | 60.080 | 60.574 |
| clean_std_intensity | 10 | 14.998 | 14.875 | 15.516 | 8 | 14.837 | 14.655 | 15.427 |
| split_t | 10 | 12.482 | 11.880 | 15.376 | 8 | 12.510 | 11.880 | 15.568 |
| behavior_C_RESPOND | 10 | 0.600 | 1.000 | 1.000 | 8 | 0.625 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.200 | 0.000 | 1.000 | 8 | 0.250 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 8 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.200 | 0.000 | 1.000 | 8 | 0.125 | 0.000 | 0.300 |

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

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "speech_dur_s": 2.764444444444445,
    "mean_intensity": 60.38508749008179,
    "std_intensity": 13.877169370651245,
    "utmosv2": 2.1199638545513153,
    "std_pitch": 51.96953773498535,
    "wpm": 129.63624489896503,
    "mean_pitch": 215.24966430664062
   },
   "post": {
    "speech_dur_s": 2.3822222222222225,
    "mean_intensity": 59.561609745025635,
    "std_intensity": 15.074243664741516,
    "utmosv2": 1.7519589215517044,
    "std_pitch": 49.70577907562256,
    "wpm": 245.98788956639572,
    "mean_pitch": 209.8078842163086
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.6,
   "C_RESUME": 0.2,
   "C_UNKNOWN": 0.2
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 135 | no | - | 2.756 | 0 | 1 | 14.320 | 1 | 0 | 0 | 0 |
| 144 | yes | 0.380 | 1.924 | 1 | 2 | 13.600 | 1 | 0 | 0 | 0 |
| 17 | yes | 0.348 | 2.164 | 1 | 2 | 15.280 | 0 | 1 | 0 | 0 |
| 190 | yes | 0.348 | 1.396 | 1 | 2 | 9.520 | 1 | 0 | 0 | 0 |
| 194 | yes | 0.412 | 1.620 | 1 | 2 | 11.920 | 1 | 0 | 0 | 0 |
| 23 | yes | 0.380 | 1.524 | 1 | 2 | 16.240 | 0 | 0 | 0 | 1 |
| 34 | yes | 0.380 | 1.508 | 1 | 2 | 11.360 | 1 | 0 | 0 | 0 |
| 39 | yes | 0.060 | 1.780 | 1 | 2 | 10.320 | 1 | 0 | 0 | 0 |
| 52 | no | 0.380 | 4.324 | 1 | 2 | 10.421 | 0 | 0 | 0 | 1 |
| 93 | yes | 0.380 | 1.748 | 1 | 2 | 11.840 | 0 | 1 | 0 | 0 |

Timing: {"total_s": 105.1, "asr": [{"model_load_s": 2.98, "transcribe_s": 11.14, "audio_s": 153.04, "files": 10, "wall_s": 17.85, "audio_name": "output.wav"}, {"model_load_s": 2.66, "transcribe_s": 11.21, "audio_s": 153.04, "files": 10, "wall_s": 17.66, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.3, "general_before_after": 44.8, "behavior": 23.4}}
