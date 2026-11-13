# FDB evaluation: baseline-env-telephony

- evaluated at: 2026-11-10T11:49:36+00:00
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
  "variant_extra_instructions": ""
}
```

## v1.5/background_speech  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.409 | 0.444 | 0.479 | 10 | 0.409 | 0.444 | 0.479 |
| resp_latency | 10 | 1.982 | 2.068 | 2.220 | 10 | 1.982 | 2.068 | 2.220 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 2.000 | 2.000 | 2.000 | 10 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 1.940 | 1.954 | 2.168 | 10 | 1.940 | 1.954 | 2.168 |
| pre_wpm | 10 | 182.197 | 186.189 | 234.044 | 10 | 182.197 | 186.189 | 234.044 |
| pre_speech_dur_s | 10 | 2.496 | 2.480 | 3.032 | 10 | 2.496 | 2.480 | 3.032 |
| pre_mean_pitch | 10 | 203.891 | 201.487 | 213.508 | 10 | 203.891 | 201.487 | 213.508 |
| pre_std_pitch | 10 | 40.915 | 37.854 | 51.012 | 10 | 40.915 | 37.854 | 51.012 |
| pre_mean_intensity | 10 | 62.103 | 62.069 | 65.742 | 10 | 62.103 | 62.069 | 65.742 |
| pre_std_intensity | 10 | 13.523 | 14.009 | 16.104 | 10 | 13.523 | 14.009 | 16.104 |
| post_utmosv2 | 10 | 2.091 | 2.090 | 2.251 | 10 | 2.091 | 2.090 | 2.251 |
| post_wpm | 10 | 203.360 | 225.833 | 264.051 | 10 | 203.360 | 225.833 | 264.051 |
| post_speech_dur_s | 10 | 3.112 | 3.560 | 3.688 | 10 | 3.112 | 3.560 | 3.688 |
| post_mean_pitch | 10 | 203.628 | 205.861 | 210.178 | 10 | 203.628 | 205.861 | 210.178 |
| post_std_pitch | 10 | 47.247 | 44.033 | 69.786 | 10 | 47.247 | 44.033 | 69.786 |
| post_mean_intensity | 10 | 60.399 | 59.787 | 63.516 | 10 | 60.399 | 59.787 | 63.516 |
| post_std_intensity | 10 | 14.825 | 15.304 | 16.086 | 10 | 14.825 | 15.304 | 16.086 |
| clean_utmosv2 | 10 | 2.148 | 2.188 | 2.496 | 10 | 2.148 | 2.188 | 2.496 |
| clean_wpm | 10 | 159.894 | 160.153 | 190.595 | 10 | 159.894 | 160.153 | 190.595 |
| clean_speech_dur_s | 10 | 6.784 | 8.280 | 9.472 | 10 | 6.784 | 8.280 | 9.472 |
| clean_mean_pitch | 10 | 194.855 | 197.833 | 202.564 | 10 | 194.855 | 197.833 | 202.564 |
| clean_std_pitch | 10 | 39.430 | 39.147 | 51.900 | 10 | 39.430 | 39.147 | 51.900 |
| clean_mean_intensity | 10 | 60.239 | 60.130 | 62.013 | 10 | 60.239 | 60.130 | 62.013 |
| clean_std_intensity | 10 | 14.333 | 14.417 | 15.092 | 10 | 14.333 | 14.417 | 15.092 |
| split_t | 10 | 8.496 | 8.480 | 9.368 | 10 | 8.496 | 8.480 | 9.368 |
| behavior_C_RESPOND | 10 | 0.800 | 1.000 | 1.000 | 10 | 0.800 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNKNOWN | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |

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
    "mean_pitch": 204.14680862426758,
    "utmosv2": 1.9425968676805496,
    "std_intensity": 13.511692643165588,
    "speech_dur_s": 2.4399999999999995,
    "mean_intensity": 62.08624601364136,
    "wpm": 180.91846163347523,
    "std_pitch": 38.926132917404175
   },
   "post": {
    "mean_pitch": 204.0631332397461,
    "utmosv2": 2.088212266564369,
    "std_intensity": 14.814095139503479,
    "speech_dur_s": 3.42,
    "mean_intensity": 60.33507823944092,
    "wpm": 217.61433043521387,
    "std_pitch": 46.702247619628906
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.8,
   "C_UNCERTAIN_HANDLING": 0.1,
   "C_UNKNOWN": 0.1
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 0.412 | 2.196 | 1 | 2 | 8.400 | 1 | 0 | 0 | 0 |
| 100 | yes | 0.476 | 1.380 | 1 | 2 | 7.520 | 0 | 0 | 1 | 0 |
| 11 | yes | 0.156 | 1.972 | 1 | 2 | 9.440 | 1 | 0 | 0 | 0 |
| 21 | yes | 0.444 | 1.460 | 1 | 2 | 8.560 | 1 | 0 | 0 | 0 |
| 49 | yes | 0.476 | 2.292 | 1 | 2 | 9.360 | 1 | 0 | 0 | 0 |
| 54 | yes | 0.444 | 2.212 | 1 | 2 | 7.440 | 0 | 0 | 0 | 1 |
| 61 | yes | 0.348 | 2.068 | 1 | 2 | 8.880 | 1 | 0 | 0 | 0 |
| 76 | yes | 0.508 | 2.180 | 1 | 2 | 8.000 | 1 | 0 | 0 | 0 |
| 80 | yes | 0.348 | 2.068 | 1 | 2 | 9.040 | 1 | 0 | 0 | 0 |
| 98 | yes | 0.476 | 1.988 | 1 | 2 | 8.320 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 107.0, "asr": [{"model_load_s": 2.76, "transcribe_s": 11.26, "audio_s": 125.02, "files": 10, "wall_s": 18.33, "audio_name": "output.wav"}, {"model_load_s": 2.79, "transcribe_s": 11.23, "audio_s": 125.02, "files": 10, "wall_s": 18.13, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 47.1, "behavior": 22.2}}

## v1.5/talking_to_other  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.415 | 0.428 | 0.476 | 10 | 0.415 | 0.428 | 0.476 |
| resp_latency | 10 | 2.055 | 2.004 | 2.217 | 10 | 2.055 | 2.004 | 2.217 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 2.000 | 2.000 | 2.000 | 10 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 1.942 | 1.986 | 2.160 | 10 | 1.942 | 1.986 | 2.160 |
| pre_wpm | 10 | 143.125 | 142.428 | 157.560 | 10 | 143.125 | 142.428 | 157.560 |
| pre_speech_dur_s | 10 | 2.536 | 2.520 | 3.224 | 10 | 2.536 | 2.520 | 3.224 |
| pre_mean_pitch | 10 | 206.014 | 206.800 | 213.354 | 10 | 206.014 | 206.800 | 213.354 |
| pre_std_pitch | 10 | 37.437 | 37.545 | 47.082 | 10 | 37.437 | 37.545 | 47.082 |
| pre_mean_intensity | 10 | 60.538 | 61.055 | 63.152 | 10 | 60.538 | 61.055 | 63.152 |
| pre_std_intensity | 10 | 14.705 | 14.881 | 16.842 | 10 | 14.705 | 14.881 | 16.842 |
| post_utmosv2 | 10 | 2.043 | 2.007 | 2.283 | 10 | 2.043 | 2.007 | 2.283 |
| post_wpm | 10 | 225.346 | 216.886 | 256.667 | 10 | 225.346 | 216.886 | 256.667 |
| post_speech_dur_s | 10 | 3.056 | 3.280 | 3.600 | 10 | 3.056 | 3.280 | 3.600 |
| post_mean_pitch | 10 | 203.704 | 205.022 | 211.177 | 10 | 203.704 | 205.022 | 211.177 |
| post_std_pitch | 10 | 42.832 | 44.208 | 52.724 | 10 | 42.832 | 44.208 | 52.724 |
| post_mean_intensity | 10 | 59.172 | 59.745 | 61.118 | 10 | 59.172 | 59.745 | 61.118 |
| post_std_intensity | 10 | 15.611 | 15.007 | 18.143 | 10 | 15.611 | 15.007 | 18.143 |
| clean_utmosv2 | 10 | 2.106 | 2.078 | 2.337 | 10 | 2.106 | 2.078 | 2.337 |
| clean_wpm | 10 | 148.027 | 140.481 | 167.425 | 10 | 148.027 | 140.481 | 167.425 |
| clean_speech_dur_s | 10 | 6.928 | 8.000 | 8.680 | 10 | 6.928 | 8.000 | 8.680 |
| clean_mean_pitch | 10 | 198.902 | 198.780 | 204.694 | 10 | 198.902 | 198.780 | 204.694 |
| clean_std_pitch | 10 | 40.249 | 41.366 | 46.167 | 10 | 40.249 | 41.366 | 46.167 |
| clean_mean_intensity | 10 | 59.712 | 59.482 | 61.465 | 10 | 59.712 | 59.482 | 61.465 |
| clean_std_intensity | 10 | 14.784 | 15.269 | 15.431 | 10 | 14.784 | 15.269 | 15.431 |
| split_t | 10 | 9.568 | 9.480 | 9.896 | 10 | 9.568 | 9.480 | 9.896 |
| behavior_C_RESPOND | 10 | 0.700 | 1.000 | 1.000 | 10 | 0.700 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_UNKNOWN | 10 | 0.200 | 0.000 | 1.000 | 10 | 0.200 | 0.000 | 1.000 |

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
    "mean_intensity": 60.646074295043945,
    "utmosv2": 1.9547324031591415,
    "std_intensity": 14.807336449623108,
    "mean_pitch": 205.58235359191895,
    "std_pitch": 36.26897954940796,
    "wpm": 143.53178616441696,
    "speech_dur_s": 2.4999999999999996
   },
   "post": {
    "mean_intensity": 59.33875846862793,
    "utmosv2": 2.044829413294792,
    "std_intensity": 15.433330655097961,
    "mean_pitch": 204.08166313171387,
    "std_pitch": 42.145795583724976,
    "wpm": 221.0056390977443,
    "speech_dur_s": 3.3333333333333335
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.7,
   "C_UNCERTAIN_HANDLING": 0.1,
   "C_UNKNOWN": 0.2
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 0.348 | 1.604 | 1 | 2 | 9.040 | 1 | 0 | 0 | 0 |
| 20 | yes | 0.444 | 2.068 | 1 | 2 | 9.440 | 1 | 0 | 0 | 0 |
| 3 | yes | 0.444 | 1.604 | 1 | 2 | 9.600 | 0 | 0 | 0 | 1 |
| 39 | yes | 0.380 | 3.268 | 1 | 2 | 11.840 | 0 | 0 | 0 | 1 |
| 45 | yes | 0.476 | 2.020 | 1 | 2 | 9.680 | 0 | 0 | 1 | 0 |
| 48 | yes | 0.412 | 1.988 | 1 | 2 | 9.520 | 1 | 0 | 0 | 0 |
| 56 | yes | 0.476 | 2.100 | 1 | 2 | 9.120 | 1 | 0 | 0 | 0 |
| 75 | yes | 0.284 | 1.924 | 1 | 2 | 8.960 | 1 | 0 | 0 | 0 |
| 88 | yes | 0.412 | 1.908 | 1 | 2 | 9.600 | 1 | 0 | 0 | 0 |
| 99 | yes | 0.476 | 2.068 | 1 | 2 | 8.880 | 1 | 0 | 0 | 0 |

Timing: {"total_s": 110.9, "asr": [{"model_load_s": 2.81, "transcribe_s": 11.3, "audio_s": 129.8, "files": 10, "wall_s": 18.17, "audio_name": "output.wav"}, {"model_load_s": 2.83, "transcribe_s": 11.32, "audio_s": 129.8, "files": 10, "wall_s": 18.28, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.3, "general_before_after": 47.3, "behavior": 25.9}}

## v1.5/user_backchannel  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 10/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 10 | 0.396 | 0.380 | 0.454 | 10 | 0.396 | 0.380 | 0.454 |
| resp_latency | 10 | 1.897 | 1.628 | 2.951 | 10 | 1.897 | 1.628 | 2.951 |
| n_stop_intervals | 10 | 1.000 | 1.000 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 2.000 | 2.000 | 2.000 | 10 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 2.081 | 2.081 | 2.343 | 10 | 2.081 | 2.081 | 2.343 |
| pre_wpm | 10 | 173.869 | 171.133 | 207.684 | 10 | 173.869 | 171.133 | 207.684 |
| pre_speech_dur_s | 10 | 2.992 | 3.000 | 3.280 | 10 | 2.992 | 3.000 | 3.280 |
| pre_mean_pitch | 10 | 212.174 | 210.342 | 221.057 | 10 | 212.174 | 210.342 | 221.057 |
| pre_std_pitch | 10 | 44.175 | 42.129 | 54.509 | 10 | 44.175 | 42.129 | 54.509 |
| pre_mean_intensity | 10 | 62.097 | 62.123 | 64.321 | 10 | 62.097 | 62.123 | 64.321 |
| pre_std_intensity | 10 | 12.579 | 12.235 | 14.342 | 10 | 12.579 | 12.235 | 14.342 |
| post_utmosv2 | 10 | 1.930 | 2.039 | 2.245 | 10 | 1.930 | 2.039 | 2.245 |
| post_wpm | 10 | 193.357 | 208.430 | 274.621 | 10 | 193.357 | 208.430 | 274.621 |
| post_speech_dur_s | 10 | 3.024 | 3.440 | 5.520 | 10 | 3.024 | 3.440 | 5.520 |
| post_mean_pitch | 10 | 202.511 | 199.897 | 212.336 | 10 | 202.511 | 199.897 | 212.336 |
| post_std_pitch | 10 | 36.585 | 33.564 | 55.421 | 10 | 36.585 | 33.564 | 55.421 |
| post_mean_intensity | 10 | 59.881 | 59.735 | 61.863 | 10 | 59.881 | 59.735 | 61.863 |
| post_std_intensity | 10 | 14.904 | 14.589 | 17.380 | 10 | 14.904 | 14.589 | 17.380 |
| clean_utmosv2 | 10 | 2.110 | 2.111 | 2.359 | 10 | 2.110 | 2.111 | 2.359 |
| clean_wpm | 10 | 168.542 | 166.702 | 189.392 | 10 | 168.542 | 166.702 | 189.392 |
| clean_speech_dur_s | 10 | 8.224 | 8.240 | 8.504 | 10 | 8.224 | 8.240 | 8.504 |
| clean_mean_pitch | 10 | 204.838 | 202.934 | 211.523 | 10 | 204.838 | 202.934 | 211.523 |
| clean_std_pitch | 10 | 37.417 | 37.051 | 42.971 | 10 | 37.417 | 37.051 | 42.971 |
| clean_mean_intensity | 10 | 60.771 | 60.497 | 62.697 | 10 | 60.771 | 60.497 | 62.697 |
| clean_std_intensity | 10 | 14.006 | 13.668 | 15.044 | 10 | 14.006 | 13.668 | 15.044 |
| split_t | 10 | 7.968 | 8.520 | 9.256 | 10 | 7.968 | 8.520 | 9.256 |
| behavior_C_RESPOND | 10 | 0.100 | 0.000 | 0.100 | 10 | 0.100 | 0.000 | 0.100 |
| behavior_C_RESUME | 10 | 0.200 | 0.000 | 1.000 | 10 | 0.200 | 0.000 | 1.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.300 | 0.000 | 1.000 | 10 | 0.300 | 0.000 | 1.000 |
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

Upstream-printed (trimmed/ratio) aggregates:

```json
{
 "general_before_after": {
  "trimmed_means": {
   "pre": {
    "std_pitch": 43.20639991760254,
    "mean_pitch": 211.6024570465088,
    "utmosv2": 2.06827574968338,
    "wpm": 173.69112232418556,
    "speech_dur_s": 3.0222222222222226,
    "std_intensity": 12.602261900901794,
    "mean_intensity": 62.16464328765869
   },
   "post": {
    "std_pitch": 36.38592529296875,
    "mean_pitch": 202.0767002105713,
    "utmosv2": 1.9403131902217865,
    "wpm": 205.2376568388639,
    "speech_dur_s": 3.3599999999999994,
    "std_intensity": 14.936275720596313,
    "mean_intensity": 59.652100563049316
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.1,
   "C_RESUME": 0.2,
   "C_UNCERTAIN_HANDLING": 0.3,
   "C_UNKNOWN": 0.4
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 21 | yes | 0.444 | 1.572 | 1 | 2 | 9.120 | 0 | 0 | 1 | 0 |
| 29 | yes | 0.444 | 1.684 | 1 | 2 | 8.720 | 0 | 0 | 1 | 0 |
| 3 | yes | 0.380 | 1.444 | 1 | 2 | 8.320 | 0 | 0 | 0 | 1 |
| 32 | yes | 0.444 | 1.428 | 1 | 2 | 6.320 | 0 | 0 | 1 | 0 |
| 34 | yes | 0.348 | 2.932 | 1 | 2 | 6.080 | 0 | 1 | 0 | 0 |
| 55 | yes | 0.348 | 1.748 | 1 | 2 | 9.040 | 0 | 0 | 0 | 1 |
| 64 | yes | 0.348 | 1.300 | 1 | 2 | 6.400 | 0 | 1 | 0 | 0 |
| 7 | yes | 0.380 | 2.244 | 1 | 2 | 10.480 | 0 | 0 | 0 | 1 |
| 92 | yes | 0.540 | 1.492 | 1 | 2 | 8.720 | 1 | 0 | 0 | 0 |
| 97 | yes | 0.284 | 3.124 | 1 | 2 | 6.480 | 0 | 0 | 0 | 1 |

Timing: {"total_s": 116.2, "asr": [{"model_load_s": 2.8, "transcribe_s": 11.16, "audio_s": 121.9, "files": 10, "wall_s": 18.02, "audio_name": "output.wav"}, {"model_load_s": 2.78, "transcribe_s": 11.2, "audio_s": 121.91, "files": 10, "wall_s": 18.09, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.2, "general_before_after": 47.0, "behavior": 31.9}}

## v1.5/user_interruption  (upstream task: `timing+general_before_after+behavior`)

samples expected 10, scored 10

valid overlaps: 8/10

| metric | n (all) | mean (all) | median (all) | p90 (all) | n (valid) | mean (valid) | median (valid) | p90 (valid) |
|---|---|---|---|---|---|---|---|---|
| stop_latency | 9 | 0.376 | 0.380 | 0.450 | 8 | 0.388 | 0.396 | 0.454 |
| resp_latency | 10 | 2.103 | 1.660 | 2.998 | 8 | 1.960 | 1.580 | 3.065 |
| n_stop_intervals | 10 | 0.900 | 1.000 | 1.000 | 8 | 1.000 | 1.000 | 1.000 |
| n_resp_intervals | 10 | 1.900 | 2.000 | 2.000 | 8 | 2.000 | 2.000 | 2.000 |
| pre_utmosv2 | 10 | 1.930 | 2.022 | 2.391 | 8 | 2.130 | 2.068 | 2.434 |
| pre_wpm | 10 | 176.542 | 175.850 | 251.163 | 8 | 189.427 | 175.850 | 247.843 |
| pre_speech_dur_s | 10 | 3.872 | 3.760 | 5.520 | 8 | 4.780 | 4.000 | 6.640 |
| pre_mean_pitch | 10 | 197.966 | 210.803 | 229.298 | 8 | 210.943 | 210.803 | 219.971 |
| pre_std_pitch | 10 | 47.532 | 50.328 | 61.544 | 8 | 52.207 | 50.328 | 64.534 |
| pre_mean_intensity | 10 | 57.775 | 61.134 | 63.457 | 8 | 60.829 | 61.134 | 62.227 |
| pre_std_intensity | 10 | 12.978 | 13.583 | 16.325 | 8 | 14.332 | 13.991 | 16.701 |
| post_utmosv2 | 10 | 1.881 | 1.826 | 2.121 | 8 | 1.900 | 1.930 | 2.188 |
| post_wpm | 10 | 193.126 | 196.898 | 335.625 | 8 | 172.323 | 196.184 | 266.463 |
| post_speech_dur_s | 10 | 2.544 | 3.120 | 3.640 | 8 | 2.360 | 2.920 | 3.720 |
| post_mean_pitch | 10 | 213.377 | 206.285 | 231.693 | 8 | 213.664 | 206.285 | 229.828 |
| post_std_pitch | 10 | 51.701 | 54.035 | 69.878 | 8 | 50.858 | 47.299 | 77.772 |
| post_mean_intensity | 10 | 59.616 | 58.867 | 65.522 | 8 | 60.293 | 59.229 | 65.918 |
| post_std_intensity | 10 | 14.542 | 15.385 | 18.097 | 8 | 13.721 | 14.606 | 17.320 |
| clean_utmosv2 | 10 | 2.141 | 2.166 | 2.360 | 8 | 2.117 | 2.166 | 2.326 |
| clean_wpm | 10 | 190.584 | 193.328 | 210.247 | 8 | 192.004 | 193.328 | 212.137 |
| clean_speech_dur_s | 10 | 10.648 | 11.160 | 11.816 | 8 | 11.200 | 11.400 | 11.928 |
| clean_mean_pitch | 10 | 200.919 | 201.153 | 203.537 | 8 | 200.636 | 199.960 | 203.696 |
| clean_std_pitch | 10 | 39.252 | 39.668 | 44.745 | 8 | 39.650 | 40.171 | 44.882 |
| clean_mean_intensity | 10 | 59.750 | 59.747 | 60.496 | 8 | 59.804 | 59.869 | 60.667 |
| clean_std_intensity | 10 | 15.023 | 14.871 | 15.477 | 8 | 15.021 | 14.871 | 15.572 |
| split_t | 10 | 11.424 | 11.480 | 13.728 | 8 | 11.390 | 11.480 | 13.824 |
| behavior_C_RESPOND | 10 | 0.700 | 1.000 | 1.000 | 8 | 0.625 | 1.000 | 1.000 |
| behavior_C_RESUME | 10 | 0.000 | 0.000 | 0.000 | 8 | 0.000 | 0.000 | 0.000 |
| behavior_C_UNCERTAIN_HANDLING | 10 | 0.100 | 0.000 | 0.100 | 8 | 0.125 | 0.000 | 0.300 |
| behavior_C_UNKNOWN | 10 | 0.200 | 0.000 | 1.000 | 8 | 0.250 | 0.000 | 1.000 |

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
    "speech_dur_s": 3.5200000000000005,
    "utmosv2": 2.021723195910454,
    "wpm": 187.97396260735897,
    "std_intensity": 13.730954647064209,
    "mean_pitch": 210.94305610656738,
    "std_pitch": 50.04011154174805,
    "mean_intensity": 60.82897233963013
   },
   "post": {
    "speech_dur_s": 2.382222222222223,
    "utmosv2": 1.87449112534523,
    "wpm": 175.00161877140908,
    "std_intensity": 15.213884949684143,
    "mean_pitch": 210.2152442932129,
    "std_pitch": 50.368507385253906,
    "mean_intensity": 59.2003870010376
   }
  }
 },
 "behavior": {
  "ratios": {
   "C_RESPOND": 0.7,
   "C_UNCERTAIN_HANDLING": 0.1,
   "C_UNKNOWN": 0.2
  }
 }
}
```

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | valid | stop_latency | resp_latency | n_stop_intervals | n_resp_intervals | split_t | behavior_C_RESPOND | behavior_C_RESUME | behavior_C_UNCERTAIN_HANDLING | behavior_C_UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | yes | 0.380 | 2.964 | 1 | 2 | 14.160 | 0 | 0 | 0 | 1 |
| 12 | no | - | 2.404 | 0 | 1 | 11.200 | 1 | 0 | 0 | 0 |
| 13 | yes | 0.380 | 1.540 | 1 | 2 | 10.160 | 1 | 0 | 0 | 0 |
| 32 | no | 0.284 | 2.948 | 1 | 2 | 11.920 | 1 | 0 | 0 | 0 |
| 45 | yes | 0.444 | 3.300 | 1 | 2 | 7.360 | 0 | 0 | 0 | 1 |
| 59 | yes | 0.252 | 1.700 | 1 | 2 | 11.520 | 1 | 0 | 0 | 0 |
| 62 | yes | 0.412 | 1.508 | 1 | 2 | 11.520 | 1 | 0 | 0 | 0 |
| 65 | yes | 0.412 | 1.540 | 1 | 2 | 13.680 | 1 | 0 | 0 | 0 |
| 85 | yes | 0.348 | 1.620 | 1 | 2 | 11.440 | 1 | 0 | 0 | 0 |
| 9 | yes | 0.476 | 1.508 | 1 | 2 | 11.280 | 0 | 0 | 1 | 0 |

Timing: {"total_s": 106.4, "asr": [{"model_load_s": 2.76, "transcribe_s": 11.42, "audio_s": 150.14, "files": 10, "wall_s": 18.17, "audio_name": "output.wav"}, {"model_load_s": 2.72, "transcribe_s": 11.54, "audio_s": 150.14, "files": 10, "wall_s": 18.29, "audio_name": "clean_output.wav"}], "eval_s": {"get_timing": 1.3, "general_before_after": 46.9, "behavior": 21.7}}

## v1/candor_pause_handling  (upstream task: `pause_handling`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.100 | 0.000 | 0.100 |
| n_words | 10 | 0.700 | 0.000 | 0.700 |
| premature_turn_end | 10 | 0.400 | 0.000 | 1.000 |
| premature_llm_start | 10 | 0.300 | 0.000 | 1.000 |

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
| 123 | 0 | 0 | 0 | 0 |
| 139 | 0 | 0 | 1 | 0 |
| 141 | 0 | 0 | 1 | 1 |
| 154 | 0 | 0 | 0 | 0 |
| 172 | 0 | 0 | 0 | 0 |
| 200 | 0 | 0 | 0 | 0 |
| 37 | 0 | 0 | 0 | 0 |
| 44 | 1 | 7 | 1 | 1 |
| 6 | 0 | 0 | 1 | 1 |
| 68 | 0 | 0 | 0 | 0 |

Timing: {"total_s": 0.3, "asr": [], "eval_s": {"pause_handling": 0.3}}

## v1/candor_turn_taking  (upstream task: `smooth_turn_taking`)

samples expected 10, scored 10

| metric | n | mean | median | p90 |
|---|---|---|---|---|
| TOR | 10 | 0.800 | 1.000 | 1.000 |
| latency_raw | 8 | 2.251 | 2.700 | 4.133 |
| latency | 8 | 2.516 | 2.700 | 4.133 |

- `TOR`: Turn-taking rate: share of samples where the agent took a turn (>3 words or >=1 s of speech). For pause_handling/backchannel LOWER is better; for turn_taking/interruption HIGHER is better.
- `latency_raw`: Same as latency but unclamped (negative = agent started before the user finished).
- `latency`: Seconds from the user turn/interruption end to the agent's first word, clamped at 0; only samples with TOR=1.

Cross-check against upstream-printed aggregate:

| metric | per-sample mean | upstream printed | match |
|---|---|---|---|
| TOR | 0.80000 | 0.80000 | yes |
| latency | 2.51625 | 2.51625 | yes |

Per-sample values (all; the full table is in the raw run's results.json, not published):

| id | TOR | latency_raw | latency |
|---|---|---|---|
| 1 | 1 | 1.330 | 1.330 |
| 10 | 1 | 4.090 | 4.090 |
| 105 | 1 | 4.140 | 4.140 |
| 113 | 1 | 4.070 | 4.070 |
| 115 | 0 | - | - |
| 17 | 1 | -2.120 | 0 |
| 18 | 1 | 1.160 | 1.160 |
| 32 | 1 | 1.210 | 1.210 |
| 53 | 0 | - | - |
| 69 | 1 | 4.130 | 4.130 |

Timing: {"total_s": 0.3, "asr": [], "eval_s": {"smooth_turn_taking": 0.3}}
