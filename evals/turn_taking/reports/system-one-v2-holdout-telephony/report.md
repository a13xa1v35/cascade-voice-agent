# FDB evaluation: system-one-v2-holdout-telephony

- evaluated at: 2026-11-10T16:43:39+00:00
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

## v1/candor_turn_taking  (upstream task: `smooth_turn_taking`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 1.000 | 1.000 | 1.000 |
| latency_raw | 10 | 1.369 | 1.950 | 3.846 |
| latency | 10 | 2.154 | 1.950 | 3.846 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `latency_raw`: Same as latency but unclamped (negative = agent started before the user finished).
- `latency`: Seconds from the user turn/interruption end to the agent's first word, clamped at 0; only samples with TOR=1.

System one:

- samples with system1 events: 10/10; judgments: 77; outcomes: ok 61, stale 16
- latency over ok calls (ms): p50 230, p90 784; hedged share: 27.3%
- actions: drop_backchannel 3, end_turn 8, fallback 2, hold_backchannel 3, keep_listening 66

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 1.00000 | 1.00000 | yes |
| latency | 2.15400 | 2.15400 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | latency_raw | latency |
|---|---|---|---|
| 11 | 1 | 1.820 | 1.820 |
| 118 | 1 | 0.610 | 0.610 |
| 13 | 1 | 3.840 | 3.840 |
| 30 | 1 | 3.900 | 3.900 |
| 47 | 1 | -7.850 | 0 |
| 55 | 1 | 3.640 | 3.640 |
| 61 | 1 | 2.180 | 2.180 |
| 72 | 1 | 1.650 | 1.650 |
| 89 | 1 | 1.910 | 1.910 |
| 97 | 1 | 1.990 | 1.990 |

Timing: {"total_s": 17.4, "asr": [{"model_load_s": 3.05, "transcribe_s": 10.56, "audio_s": 135.21, "files": 10, "wall_s": 17.18, "audio_name": "output.wav"}], "eval_s": {"smooth_turn_taking": 0.3}}

## v1.5/background_speech  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.879 | 0.780 | 1.647 | 10 | 0.879 | 0.780 | 1.647 |
| resp_latency | 10 | 2.678 | 2.660 | 3.463 | 10 | 2.678 | 2.660 | 3.463 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.500 | 1.500 | 2.000 | 10 | 1.500 | 1.500 | 2.000 |
| pre_utmosv2 | 10 | 1.954 | 1.942 | 2.294 | 10 | 1.954 | 1.942 | 2.294 |
| pre_wpm | 10 | 141.375 | 139.757 | 171.409 | 10 | 141.375 | 139.757 | 171.409 |
| pre_speech_dur_s | 10 | 2.920 | 2.840 | 3.816 | 10 | 2.920 | 2.840 | 3.816 |
| pre_mean_pitch | 10 | 199.171 | 201.045 | 205.347 | 10 | 199.171 | 201.045 | 205.347 |
| pre_std_pitch | 10 | 38.339 | 34.350 | 53.639 | 10 | 38.339 | 34.350 | 53.639 |
| pre_mean_intensity | 10 | 61.093 | 61.224 | 63.231 | 10 | 61.093 | 61.224 | 63.231 |
| pre_std_intensity | 10 | 13.840 | 14.325 | 15.535 | 10 | 13.840 | 14.325 | 15.535 |
| post_utmosv2 | 10 | 1.601 | 1.862 | 2.024 | 10 | 1.601 | 1.862 | 2.024 |
| post_wpm | 10 | 256.978 | 201.801 | 369.643 | 10 | 256.978 | 201.801 | 369.643 |
| post_speech_dur_s | 10 | 2.208 | 1.640 | 4.648 | 10 | 2.208 | 1.640 | 4.648 |
| post_mean_pitch | 10 | 175.376 | 198.434 | 238.935 | 10 | 175.376 | 198.434 | 238.935 |
| post_std_pitch | 10 | 32.553 | 33.843 | 57.214 | 10 | 32.553 | 33.843 | 57.214 |
| post_mean_intensity | 10 | 23.298 | 57.206 | 58.877 | 10 | 23.298 | 57.206 | 58.877 |
| post_std_intensity | 10 | 12.790 | 14.853 | 16.976 | 10 | 12.790 | 14.853 | 16.976 |
| clean_utmosv2 | 10 | 2.092 | 2.155 | 2.230 | 10 | 2.092 | 2.155 | 2.230 |
| clean_wpm | 10 | 152.958 | 152.103 | 181.250 | 10 | 152.958 | 152.103 | 181.250 |
| clean_speech_dur_s | 10 | 5.440 | 4.520 | 8.704 | 10 | 5.440 | 4.520 | 8.704 |
| clean_mean_pitch | 10 | 197.822 | 196.220 | 208.017 | 10 | 197.822 | 196.220 | 208.017 |
| clean_std_pitch | 10 | 46.253 | 48.582 | 54.135 | 10 | 46.253 | 48.582 | 54.135 |
| clean_mean_intensity | 10 | 59.372 | 59.335 | 62.357 | 10 | 59.372 | 59.335 | 62.357 |
| clean_std_intensity | 10 | 15.008 | 15.646 | 16.082 | 10 | 15.008 | 15.646 | 16.082 |
| split_t | 10 | 7.944 | 7.560 | 9.224 | 10 | 7.944 | 7.560 | 9.224 |
| behavior_C_RESPOND | 10 | 0.300 | 0.000 | 1.000 | 10 | 0.300 | 0.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.200 | 0.000 | 1.000 | 10 | 0.200 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNKNOWN | 10 | 0.400 | 0.000 | 1.000 | 10 | 0.400 | 0.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 51; outcomes: ok 41, stale 10
- latency over ok calls (ms): p50 186, p90 640; hedged share: 25.5%
- actions: drop_backchannel 2, drop_side_talk 2, end_turn 13, fallback 4, hold_backchannel 3, interrupt 4, keep_listening 30

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "wpm": 144.17405771873567,
    "utmosv2": 1.940720558166504,
    "std_intensity": 13.766800284385681,
    "std_pitch": 37.74889039993286,
    "speech_dur_s": 2.8900000000000006,
    "mean_pitch": 199.1912727355957,
    "mean_intensity": 61.109771728515625
   },
   "post": {
    "wpm": 180.59696884306038,
    "utmosv2": 1.5514832999971178,
    "std_intensity": 13.84081518650055,
    "std_pitch": 27.850882927576702,
    "speech_dur_s": 2.17,
    "mean_pitch": 153.945797390408,
    "mean_intensity": 46.2784429192543
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.3,
   "C_RESUME": 0.2,
   "C_UNCERTAIN_HANDLING": 0.1,
   "C_UNKNOWN": 0.4
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 17 | yes | 0.060 | 1.956 | 1 | 1 | 6.960 | 0 | 1 | 0 | 0 |
| 34 | yes | 0.924 | 3.396 | 1 | 2 | 10.160 | 1 | 0 | 0 | 0 |
| 37 | yes | 0.028 | 3.140 | 1 | 2 | 9.120 | 1 | 0 | 0 | 0 |
| 4 | yes | 1.628 | 2.980 | 1 | 2 | 7.520 | 0 | 0 | 1 | 0 |
| 74 | yes | 1.436 | 2.276 | 1 | 1 | 8.160 | 0 | 0 | 0 | 1 |
| 79 | yes | 0.444 | 2.340 | 1 | 1 | 6.400 | 0 | 0 | 0 | 1 |
| 87 | yes | 1.404 | 3.428 | 1 | 1 | 7.520 | 0 | 0 | 0 | 1 |
| 90 | yes | 1.820 | 3.780 | 1 | 1 | 7.520 | 0 | 0 | 0 | 1 |
| 92 | yes | 0.412 | 1.956 | 1 | 2 | 8.480 | 1 | 0 | 0 | 0 |
| 94 | yes | 0.636 | 1.524 | 1 | 2 | 7.600 | 0 | 1 | 0 | 0 |

Timing: {"total_s": 99.8, "asr": [{"model_load_s": 2.76, "transcribe_s": 10.19, "audio_s": 122.32, "files": 10, "wall_s": 16.5, "audio_name": "output.wav"}, {"model_load_s": 2.7, "transcribe_s": 10.4, "audio_s": 122.32, "files": 10, "wall_s": 16.67, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.1, "general_before_after": 43.2, "behavior": 22.4}}

## v1.5/talking_to_other  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 1.642 | 1.868 | 2.367 | 10 | 1.642 | 1.868 | 2.367 |
| resp_latency | 10 | 2.361 | 2.180 | 3.191 | 10 | 2.361 | 2.180 | 3.191 |
| n_stop_intervals | 10 | 1.100 | 1.000 | 1.100 | 10 | 1.100 | 1.000 | 1.100 |
| n_resp_intervals | 10 | 1.300 | 1.000 | 2.000 | 10 | 1.300 | 1.000 | 2.000 |
| pre_utmosv2 | 10 | 1.965 | 2.004 | 2.149 | 10 | 1.965 | 2.004 | 2.149 |
| pre_wpm | 10 | 169.470 | 160.714 | 206.731 | 10 | 169.470 | 160.714 | 206.731 |
| pre_speech_dur_s | 10 | 3.592 | 3.880 | 4.496 | 10 | 3.592 | 3.880 | 4.496 |
| pre_mean_pitch | 10 | 201.355 | 202.443 | 208.384 | 10 | 201.355 | 202.443 | 208.384 |
| pre_std_pitch | 10 | 38.009 | 37.822 | 44.412 | 10 | 38.009 | 37.822 | 44.412 |
| pre_mean_intensity | 10 | 60.366 | 60.337 | 63.050 | 10 | 60.366 | 60.337 | 63.050 |
| pre_std_intensity | 10 | 14.110 | 13.871 | 15.578 | 10 | 14.110 | 13.871 | 15.578 |
| post_utmosv2 | 10 | 1.691 | 1.845 | 2.166 | 10 | 1.691 | 1.845 | 2.166 |
| post_wpm | 10 | 117.163 | 133.621 | 195.784 | 10 | 117.163 | 133.621 | 195.784 |
| post_speech_dur_s | 10 | 3.256 | 4.520 | 4.992 | 10 | 3.256 | 4.520 | 4.992 |
| post_mean_pitch | 10 | 156.177 | 189.429 | 207.065 | 10 | 156.177 | 189.429 | 207.065 |
| post_std_pitch | 10 | 24.701 | 24.086 | 50.496 | 10 | 24.701 | 24.086 | 50.496 |
| post_mean_intensity | 10 | 49.144 | 59.150 | 60.308 | 10 | 49.144 | 59.150 | 60.308 |
| post_std_intensity | 10 | 14.311 | 14.854 | 17.119 | 10 | 14.311 | 14.854 | 17.119 |
| clean_utmosv2 | 10 | 2.031 | 2.020 | 2.256 | 10 | 2.031 | 2.020 | 2.256 |
| clean_wpm | 10 | 160.661 | 159.967 | 189.375 | 10 | 160.661 | 159.967 | 189.375 |
| clean_speech_dur_s | 10 | 7.016 | 8.480 | 9.600 | 10 | 7.016 | 8.480 | 9.600 |
| clean_mean_pitch | 10 | 198.623 | 200.355 | 204.417 | 10 | 198.623 | 200.355 | 204.417 |
| clean_std_pitch | 10 | 40.017 | 42.129 | 48.615 | 10 | 40.017 | 42.129 | 48.615 |
| clean_mean_intensity | 10 | 59.426 | 59.985 | 60.986 | 10 | 59.426 | 59.985 | 60.986 |
| clean_std_intensity | 10 | 15.072 | 15.004 | 15.828 | 10 | 15.072 | 15.004 | 15.828 |
| split_t | 10 | 7.808 | 7.920 | 8.336 | 10 | 7.808 | 7.920 | 8.336 |
| behavior_C_RESPOND | 10 | 0.200 | 0.000 | 1.000 | 10 | 0.200 | 0.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.500 | 0.500 | 1.000 | 10 | 0.500 | 0.500 | 1.000 |
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

- samples with system1 events: 10/10; judgments: 53; outcomes: ok 52, stale 1
- latency over ok calls (ms): p50 186, p90 611; hedged share: 17.0%
- actions: drop_backchannel 2, drop_side_talk 10, end_turn 12, hold_backchannel 16, interrupt 2, keep_listening 16

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "mean_pitch": 202.09618759155273,
    "mean_intensity": 60.452993869781494,
    "std_pitch": 37.89659571647644,
    "wpm": 166.9161095067311,
    "std_intensity": 13.985419988632202,
    "utmosv2": 1.9547244608402252,
    "speech_dur_s": 3.6300000000000003
   },
   "post": {
    "mean_pitch": 148.76226806640625,
    "mean_intensity": 52.47077763080597,
    "std_pitch": 20.19244564904107,
    "wpm": 106.19171953988418,
    "std_intensity": 14.748145580291748,
    "utmosv2": 1.7537515759468079,
    "speech_dur_s": 3.031111111111111
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.2,
   "C_RESUME": 0.5,
   "C_UNKNOWN": 0.3
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 14 | yes | 2.364 | 2.116 | 1 | 2 | 8.240 | 1 | 0 | 0 | 0 |
| 15 | yes | 2.300 | 1.700 | 1 | 1 | 7.840 | 0 | 1 | 0 | 0 |
| 16 | yes | 1.116 | 3.364 | 1 | 1 | 6.720 | 0 | 0 | 0 | 1 |
| 43 | yes | 0.492 | 2.020 | 2 | 1 | 8.320 | 0 | 1 | 0 | 0 |
| 6 | yes | 2.332 | 2.452 | 1 | 2 | 8.080 | 0 | 1 | 0 | 0 |
| 82 | yes | 1.596 | 2.692 | 1 | 2 | 7.600 | 1 | 0 | 0 | 0 |
| 83 | yes | 2.396 | 3.172 | 1 | 1 | 8.480 | 0 | 0 | 0 | 1 |
| 86 | yes | 2.140 | 2.244 | 1 | 1 | 8.000 | 0 | 1 | 0 | 0 |
| 90 | yes | 0.796 | 2.052 | 1 | 1 | 7.840 | 0 | 1 | 0 | 0 |
| 92 | yes | 0.892 | 1.796 | 1 | 1 | 6.960 | 0 | 0 | 0 | 1 |

Timing: {"total_s": 102.0, "asr": [{"model_load_s": 2.76, "transcribe_s": 10.52, "audio_s": 133.47, "files": 10, "wall_s": 16.78, "audio_name": "output.wav"}, {"model_load_s": 2.67, "transcribe_s": 10.48, "audio_s": 133.47, "files": 10, "wall_s": 16.7, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.1, "general_before_after": 42.7, "behavior": 24.7}}

## v1.5/user_backchannel  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.793 | 0.764 | 0.921 | 10 | 0.793 | 0.764 | 0.921 |
| resp_latency | 10 | 2.430 | 2.116 | 3.316 | 10 | 2.430 | 2.116 | 3.316 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.100 | 1.000 | 1.100 | 10 | 1.100 | 1.000 | 1.100 |
| pre_utmosv2 | 10 | 1.924 | 2.008 | 2.369 | 10 | 1.924 | 2.008 | 2.369 |
| pre_wpm | 10 | 140.410 | 160.010 | 178.131 | 10 | 140.410 | 160.010 | 178.131 |
| pre_speech_dur_s | 10 | 2.696 | 2.880 | 3.464 | 10 | 2.696 | 2.880 | 3.464 |
| pre_mean_pitch | 10 | 185.331 | 204.506 | 208.352 | 10 | 185.331 | 204.506 | 208.352 |
| pre_std_pitch | 10 | 35.103 | 36.298 | 45.596 | 10 | 35.103 | 36.298 | 45.596 |
| pre_mean_intensity | 10 | 35.144 | 61.180 | 63.760 | 10 | 35.144 | 61.180 | 63.760 |
| pre_std_intensity | 10 | 11.807 | 12.875 | 14.701 | 10 | 11.807 | 12.875 | 14.701 |
| post_utmosv2 | 10 | 2.156 | 2.162 | 2.289 | 10 | 2.156 | 2.162 | 2.289 |
| post_wpm | 10 | 196.923 | 181.751 | 250.403 | 10 | 196.923 | 181.751 | 250.403 |
| post_speech_dur_s | 10 | 4.960 | 4.960 | 5.336 | 10 | 4.960 | 4.960 | 5.336 |
| post_mean_pitch | 10 | 200.718 | 201.341 | 204.248 | 10 | 200.718 | 201.341 | 204.248 |
| post_std_pitch | 10 | 35.763 | 33.491 | 43.860 | 10 | 35.763 | 33.491 | 43.860 |
| post_mean_intensity | 10 | 59.045 | 59.092 | 60.133 | 10 | 59.045 | 59.092 | 60.133 |
| post_std_intensity | 10 | 15.731 | 15.960 | 16.770 | 10 | 15.731 | 15.960 | 16.770 |
| clean_utmosv2 | 10 | 2.216 | 2.191 | 2.530 | 10 | 2.216 | 2.191 | 2.530 |
| clean_wpm | 10 | 176.294 | 175.914 | 204.008 | 10 | 176.294 | 175.914 | 204.008 |
| clean_speech_dur_s | 10 | 7.728 | 7.760 | 8.568 | 10 | 7.728 | 7.760 | 8.568 |
| clean_mean_pitch | 10 | 202.535 | 202.711 | 208.756 | 10 | 202.535 | 202.711 | 208.756 |
| clean_std_pitch | 10 | 40.546 | 41.364 | 47.908 | 10 | 40.546 | 41.364 | 47.908 |
| clean_mean_intensity | 10 | 59.845 | 59.826 | 61.635 | 10 | 59.845 | 59.826 | 61.635 |
| clean_std_intensity | 10 | 14.772 | 14.727 | 15.891 | 10 | 14.772 | 14.727 | 15.891 |
| split_t | 10 | 7.032 | 6.960 | 8.008 | 10 | 7.032 | 6.960 | 8.008 |
| behavior_C_RESPOND | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_RESUME | 10 | 0.400 | 0.000 | 1.000 | 10 | 0.400 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNKNOWN | 10 | 0.600 | 1.000 | 1.000 | 10 | 0.600 | 1.000 | 1.000 |

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

- samples with system1 events: 10/10; judgments: 45; outcomes: ok 40, stale 4, timeout 1
- latency over ok calls (ms): p50 238, p90 625; hedged share: 28.9%
- actions: drop_backchannel 17, end_turn 9, fallback 1, hold_backchannel 8, keep_listening 18

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_pitch": 37.69166898727417,
    "mean_pitch": 204.03664588928223,
    "mean_intensity": 60.80496644973755,
    "speech_dur_s": 2.91,
    "utmosv2": 2.021849736571312,
    "wpm": 149.06976807152938,
    "std_intensity": 12.83548367023468
   },
   "post": {
    "std_pitch": 35.45497250556946,
    "mean_pitch": 200.9322910308838,
    "mean_intensity": 59.080278396606445,
    "speech_dur_s": 4.960000000000001,
    "utmosv2": 2.1693400740623474,
    "wpm": 197.21247403095296,
    "std_intensity": 15.745696306228638
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
| 15 | yes | 0.860 | 2.020 | 1 | 1 | 7.120 | 0 | 0 | 0 | 1 |
| 41 | yes | 0.732 | 2.116 | 1 | 1 | 6.960 | 0 | 1 | 0 | 0 |
| 47 | yes | 0.700 | 2.276 | 1 | 1 | 6.640 | 0 | 0 | 0 | 1 |
| 58 | yes | 1.180 | 3.236 | 1 | 2 | 7.440 | 0 | 0 | 0 | 1 |
| 62 | yes | 0.892 | 2.116 | 1 | 1 | 6.960 | 0 | 1 | 0 | 0 |
| 63 | yes | 0.796 | 2.756 | 1 | 1 | 6.720 | 0 | 0 | 0 | 1 |
| 67 | yes | 0.892 | 1.956 | 1 | 1 | 8.080 | 0 | 1 | 0 | 0 |
| 72 | yes | 0.604 | 4.036 | 1 | 1 | 5.440 | 0 | 0 | 0 | 1 |
| 88 | yes | 0.604 | 1.988 | 1 | 1 | 6.960 | 0 | 1 | 0 | 0 |
| 95 | yes | 0.668 | 1.796 | 1 | 1 | 8.000 | 0 | 0 | 0 | 1 |

Timing: {"total_s": 110.2, "asr": [{"model_load_s": 3.5, "transcribe_s": 11.01, "audio_s": 122.74, "files": 10, "wall_s": 18.13, "audio_name": "output.wav"}, {"model_load_s": 3.1, "transcribe_s": 10.36, "audio_s": 122.74, "files": 10, "wall_s": 17.34, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.1, "general_before_after": 43.7, "behavior": 29.9}}

## v1.5/user_interruption  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 1.846 | 1.820 | 2.860 | 10 | 1.846 | 1.820 | 2.860 |
| resp_latency | 10 | 2.175 | 2.092 | 2.582 | 10 | 2.175 | 2.092 | 2.582 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 2.000 | 2.000 | 2.000 | 10 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 2.016 | 2.089 | 2.123 | 10 | 2.016 | 2.089 | 2.123 |
| pre_wpm | 10 | 180.702 | 185.731 | 209.191 | 10 | 180.702 | 185.731 | 209.191 |
| pre_speech_dur_s | 10 | 5.200 | 4.800 | 5.968 | 10 | 5.200 | 4.800 | 5.968 |
| pre_mean_pitch | 10 | 209.781 | 206.391 | 217.877 | 10 | 209.781 | 206.391 | 217.877 |
| pre_std_pitch | 10 | 46.931 | 48.595 | 62.294 | 10 | 46.931 | 48.595 | 62.294 |
| pre_mean_intensity | 10 | 59.666 | 59.474 | 60.964 | 10 | 59.666 | 59.474 | 60.964 |
| pre_std_intensity | 10 | 15.208 | 15.253 | 15.917 | 10 | 15.208 | 15.253 | 15.917 |
| post_utmosv2 | 10 | 1.906 | 1.928 | 2.472 | 10 | 1.906 | 1.928 | 2.472 |
| post_wpm | 10 | 164.872 | 178.752 | 314.062 | 10 | 164.872 | 178.752 | 314.062 |
| post_speech_dur_s | 10 | 2.208 | 2.720 | 4.896 | 10 | 2.208 | 2.720 | 4.896 |
| post_mean_pitch | 10 | 220.916 | 221.139 | 252.358 | 10 | 220.916 | 221.139 | 252.358 |
| post_std_pitch | 10 | 41.792 | 44.776 | 59.837 | 10 | 41.792 | 44.776 | 59.837 |
| post_mean_intensity | 10 | 62.591 | 62.481 | 66.756 | 10 | 62.591 | 62.481 | 66.756 |
| post_std_intensity | 10 | 13.787 | 14.257 | 16.945 | 10 | 13.787 | 14.257 | 16.945 |
| clean_utmosv2 | 10 | 2.160 | 2.212 | 2.365 | 10 | 2.160 | 2.212 | 2.365 |
| clean_wpm | 10 | 191.224 | 188.815 | 226.387 | 10 | 191.224 | 188.815 | 226.387 |
| clean_speech_dur_s | 10 | 10.448 | 10.680 | 11.608 | 10 | 10.448 | 10.680 | 11.608 |
| clean_mean_pitch | 10 | 204.174 | 204.467 | 208.360 | 10 | 204.174 | 204.467 | 208.360 |
| clean_std_pitch | 10 | 44.481 | 44.205 | 51.725 | 10 | 44.481 | 44.205 | 51.725 |
| clean_mean_intensity | 10 | 59.982 | 60.114 | 60.860 | 10 | 59.982 | 60.114 | 60.860 |
| clean_std_intensity | 10 | 14.921 | 15.115 | 15.425 | 10 | 14.921 | 15.115 | 15.425 |
| split_t | 10 | 11.248 | 11.720 | 13.624 | 10 | 11.248 | 11.720 | 13.624 |
| behavior_C_RESPOND | 10 | 0.500 | 0.500 | 1.000 | 10 | 0.500 | 0.500 | 1.000 |
| behavior_C_RESUME | 10 | 0.200 | 0.000 | 1.000 | 10 | 0.200 | 0.000 | 1.000 |
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

- samples with system1 events: 10/10; judgments: 70; outcomes: ok 64, stale 6
- latency over ok calls (ms): p50 146, p90 469; hedged share: 14.3%
- actions: drop_backchannel 7, end_turn 21, hold_backchannel 11, interrupt 11, keep_listening 33

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "speech_dur_s": 4.8500000000000005,
    "std_intensity": 15.229179859161377,
    "wpm": 185.14728924549246,
    "utmosv2": 2.0264725536108017,
    "mean_intensity": 59.61698579788208,
    "mean_pitch": 206.1404685974121,
    "std_pitch": 47.15415287017822
   },
   "post": {
    "speech_dur_s": 1.8933333333333333,
    "std_intensity": 14.531307816505432,
    "wpm": 146.73315452003973,
    "utmosv2": 1.955134928226471,
    "mean_intensity": 62.01875400543213,
    "mean_pitch": 218.52666473388672,
    "std_pitch": 43.04989981651306
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.5,
   "C_RESUME": 0.2,
   "C_UNKNOWN": 0.3
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 135 | yes | 1.916 | 3.028 | 1 | 2 | 8.960 | 0 | 1 | 0 | 0 |
| 144 | yes | 1.628 | 1.716 | 1 | 2 | 13.120 | 0 | 1 | 0 | 0 |
| 17 | yes | 3.580 | 2.452 | 1 | 2 | 11.040 | 1 | 0 | 0 | 0 |
| 190 | yes | 1.916 | 1.812 | 1 | 2 | 9.840 | 1 | 0 | 0 | 0 |
| 194 | yes | 2.780 | 1.924 | 1 | 2 | 8.960 | 1 | 0 | 0 | 0 |
| 23 | yes | 0.828 | 2.036 | 1 | 2 | 7.600 | 0 | 0 | 0 | 1 |
| 34 | yes | 2.108 | 2.212 | 1 | 2 | 14.560 | 0 | 0 | 0 | 1 |
| 39 | yes | 0.924 | 2.532 | 1 | 2 | 13.520 | 0 | 0 | 0 | 1 |
| 52 | yes | 1.724 | 1.892 | 1 | 2 | 12.400 | 1 | 0 | 0 | 0 |
| 93 | yes | 1.052 | 2.148 | 1 | 2 | 12.480 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 107.1, "asr": [{"model_load_s": 2.61, "transcribe_s": 10.82, "audio_s": 153.04, "files": 10, "wall_s": 17.11, "audio_name": "output.wav"}, {"model_load_s": 2.78, "transcribe_s": 10.72, "audio_s": 153.04, "files": 10, "wall_s": 17.12, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 43.7, "behavior": 27.9}}

## v1/candor_pause_handling  (upstream task: `pause_handling`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.300 | 0.000 | 1.000 |
| n_words | 10 | 4.500 | 0.000 | 15.300 |
| premature_turn_end | 10 | 0.100 | 0.000 | 0.100 |
| premature_llm_start | 10 | 0.100 | 0.000 | 0.100 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `n_words`: Number of ASR words in the agent's output.
- `premature_turn_end`: Pause handling: 1 if the design tried to take the turn during the pause even if no audio came out (a user_turn.stopped event in [pause start - 0.3 s, pause end + 0.5 s]).
- `premature_llm_start`: Pause handling: 1 if an llm.text event followed that premature stop (up to pause end + 2.5 s), i.e. the LLM actually started answering.

System one:

- samples with system1 events: 10/10; judgments: 123; outcomes: ok 114, stale 9
- latency over ok calls (ms): p50 196, p90 568; hedged share: 13.8%
- actions: drop_backchannel 5, drop_side_talk 5, end_turn 6, hold_backchannel 5, interrupt 2, keep_listening 106, open_turn 1

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.30000 | 0.30000 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | n_words | premature_turn_end | premature_llm_start |
|---|---|---|---|---|
| 102 | 0 | 0 | 0 | 0 |
| 104 | 0 | 0 | 0 | 0 |
| 107 | 1 | 14 | 0 | 0 |
| 134 | 1 | 27 | 1 | 1 |
| 26 | 0 | 0 | 0 | 0 |
| 40 | 0 | 0 | 0 | 0 |
| 63 | 1 | 4 | 0 | 0 |
| 75 | 0 | 0 | 0 | 0 |
| 82 | 0 | 0 | 0 | 0 |
| 88 | 0 | 0 | 0 | 0 |

Timing: {"total_s": 7.4, "asr": [{"model_load_s": 2.46, "transcribe_s": 1.25, "audio_s": 27.04, "files": 1, "wall_s": 7.17, "audio_name": "output.wav"}], "eval_s": {"pause_handling": 0.2}}
