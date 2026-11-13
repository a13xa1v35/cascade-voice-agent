# Per-call metrics

Design: record raw events during the call, compute metrics after it.

```
frames + aggregator events -> CallRecorder -> Redis screening:{id}:events (last 5000, TTL)
at call end: compute_scorecard() -> call_metrics row + tool_calls rows (SQL)
```

- `CallRecorder` (`observability/observers.py`) is a pipecat observer. An `isinstance` allowlist
  comes first, so audio and other frames return at once. It never awaits Redis: it appends to a
  list, and a background task flushes every 2 s, plus a final flush at call end.
- `compute_scorecard` (`metrics.py`) is a pure function of the events, the screening and its
  facts, run on the complete in-memory list. Scalars go to one `call_metrics` row, the tool
  calls that ran to `tool_calls` rows.
- Events are telemetry with a TTL (`EVENTS_TTL_DAYS`, 30). In production, OpenTelemetry would
  replace Redis.
- Read it with `GET /screenings/{id}/metrics` or `make report ID=<id>`. After the events
  expire it is rebuilt from the stored rows and marked `exchanges_expired: true`.

Every event has `t` (seconds on one monotonic clock since the recorder was created) and `wall`
(ISO UTC, derived from `t`). Pipecat's own timestamps are not used.

## Events

| event | source | key data |
| --- | --- | --- |
| `call.connected` / `call.ended` | `bot.py` | `end_reason` on end |
| `user.speech_started` / `_stopped`, `user.turn_started` / `_ended` | VAD, user aggregator | `strategy`, `text` |
| `turn_model.prediction` | Smart Turn | `is_complete`, `probability` |
| `system1.config` / `.judgment` / `.action` / `.error` | turn-taking controller | scores, `latency_ms`, `outcome`, `action` |
| `frustration.ignored_attempts` | turn-taking controller; `FrustrationMonitor` counts it as a hit | `count`: candidate speech dropped this many times in one agent turn |
| `stt.final` | `TranscriptionFrame` | `text` |
| `llm.started` / `llm.ended` | LLM response frames | |
| `llm.ttfb` / `tts.ttfb` / `stt.ttfb`, `llm.usage`, `tts.chars` | pipecat metrics frames | `seconds`; token counts (cache, reasoning `null` if not reported); `chars` |
| `llm.error` / `llm.retry` / `llm.gave_up` | LLM service, `LLMRecovery` | `message`, `quota`, `failures` |
| `tool.event` | `FunctionCallObserver` | `name`, `kind` (started ... failed / timed_out), `args`, `result`, `error` |
| `language_switched` | `switch_language` tool | `from`, `to` |
| `kb_search`, `kb_result_delivered`, `kb_holding_line` | `search_knowledge`, `bot.py` | `query`, `no_match`, `error`, `total_ms`; `mode` (`inline` / `deferred`); `text` |
| `question_referred` | `refer_to_recruiter`, `_finalize` | `question`, `automatic` |
| `frustration.config` / `.judgment` / `.note` / `.note_echo_removed` | `FrustrationMonitor` | `probability`, `latency_ms`, `outcome`, `level` |
| `bot.speech_started` / `_stopped`, `bot.said`, `interruption` | bot frames, assistant aggregator | `text`, `interrupted`; `bot_speaking` |
| `hangup.armed` / `.canceled` / `.fired` | `HangupController` | `outcome`, `phase`, `reason`, `waited_secs` |
| `latency.breakdown` | `UserBotLatencyObserver` | `total_secs`, `measured_from`, `stages` |

Hang-up: `end_call` arms the controller. After the goodbye plays it waits `HANGUP_GRACE_SECS`
(3 s), then fires. A candidate turn before that cancels it. `max_wait` fires it after 20 s.

`end_reason` is set once, by priority: `end_call` > `error` > `llm_error` > `context_unavailable`
> `superseded` > `connection_lost` > `idle_timeout` > `hangup`. `unknown` means none applied.

## Exchanges

An **exchange** is one `user.turn_ended` (time `T`) and what follows up to the next turn end.
`B` = first `bot.speech_started` after `T`; `R` = first `user.speech_started` after `T`.

- `false_endpoint`: `R` exists and (`B` is missing, or `R < B`, or `R - B` < 1.0 s).
- `answered`: not a false endpoint, and `B` exists. `unanswered`: no `B` and no `R`.
- `barge_in`: an `answered` exchange that owns an interruption with `bot_speaking=true`. The
  interruption belongs to the latest exchange whose turn ended before it (a false endpoint
  keeps it, so it is not counted twice). One over the greeting has no exchange.

## Scorecard

Percentiles are interpolated; empty gives `null`. Thresholds: `MetricsThresholds`.

### responsiveness

- **reply latency** p50 / p95 / max: `B` minus the last `user.speech_stopped` before `T`, over
  `answered` and `barge_in` exchanges.
- **stage medians**: median seconds per `latency.breakdown` stage (greeting excluded).
- **tool-turn latency**: reply latency where a tool call began between `T` and `B`.
- **first greeting**: first `bot.speech_started` minus `call.connected`.
- **llm ttfb**: `seconds` of each `llm.ttfb` (excludes the rate limiter wait).

### turn_taking

- `user_turns`, `false_endpoints`, `false_endpoint_rate`, `barge_ins`, **endpoint delay** p50 /
  p95 (`T` minus the last `user.speech_stopped`).
- **silence_fallbacks**: turns whose last `turn_model.prediction` was incomplete, or with
  endpoint delay of at least 2.8 s. Inferred: Smart Turn emits no event when its `stop_secs`
  fires. Voice calls use system-one, which emits no prediction, so only the delay rule applies.
- **unsafe_hangup**: at `hangup.fired`, the candidate was mid-speech or stopped less than 2.0 s
  earlier. Hanging up during the grace window is not unsafe.
- `hangup_cancels`; `hangup_wait_secs` (last `hangup.armed` to `hangup.fired`).

### task

- `outcome`, `status`, `end_reason`, `facts_complete`, `tool_errors` (failed, timed out or
  `{"error": ...}` results).
- **tool_order_valid** (reasons in `tool_order_problems`): `record_*` tools in any order, then
  `list_onboarding_slots` (after a `qualified: true` result), `schedule_onboarding` (once, no
  `record_*` after), and a successful `end_call` last. Knowledge tools and `switch_language` may
  come anywhere before it. Early exits skip the middle steps. No successful `end_call` is invalid.
- `booked_only_if_qualified`: a booking needs a latest `record_*` verdict of `qualified: true`.
- **goodbye_spoken**: the last `bot.said` has a farewell word (`FAREWELL_WORDS`).

### knowledge

All zero for a call that never searched.

- `searches`, `no_match` (backlog for new content), `unavailable` (deadline, embedding or store
  error), `search_ms` (count, p50, p95, max of `total_ms`).
- `late_results`: delivered late because the candidate spoke while the search ran.
- `questions_referred`: by Sofia, or by `_finalize` for searches that did not answer.

### frustration

`null` if the check did not run. A decision model judges the last 6 turns plus the latest;
requests start at least `FRUSTRATION_MIN_GAP_SECS` (3) apart.

- `checks` (outcome `ok`), `errors` (timeout or failure), `max_probability`, `last_probability`.
- `frustrated_checks`: checks at or above 0.5. `notes`: notes pushed to Sofia (needs `FRUSTRATION_NOTES_ENABLED`).

### cost

- `llm_calls`, `llm_errors`, `llm_retries`, `tts_chars`: counts and sums of the matching events.
- `prompt_tokens`, `completion_tokens`, `cache_read_tokens`, `reasoning_tokens`: sums of
  `llm.usage`. Anthropic prompt tokens are net of cache, OpenAI's gross; the eval subtracts
  cache reads for OpenAI only (`evals/common/usage.py`).
- **wasted_llm_calls**: an `llm.started` whose window (until the next `llm.started`,
  `interruption`, `user.turn_started` or call end) ended by interruption or new user turn, with
  no `bot.speech_started` and no `tool.event` inside. A tool-only response is not wasted.

`system_one` (voice only): judgment, failure and action counts, latency. Not stored.

## Heuristic or inferred

`silence_fallbacks`, `goodbye_spoken`, `wasted_llm_calls`, barge-in attribution,
`booked_only_if_qualified` (read from the tool result).

## Measurement limits

- Timestamps are server-side; network transit and client playout are not included.
- The VAD reports speech end after `stop_secs` (0.2 s) of silence, so it lags real speech.
- A false endpoint is timing only. Labeled metrics (answer correctness) are not computed.
- No cross-call aggregation in the app; use SQL on `call_metrics`.
- A call with no events and no row returns the task section only, with `"partial": true`.

## Stored columns

`call_metrics` (one row per screening) is defined in `src/hr_screener/storage/db.py`; `tool_calls`
holds the calls that ran. Lost when events expire: exchanges, stage medians, endpoint-delay
percentiles, `false_endpoint_rate`, `hangup_cancels`, `last_probability`, frustration `errors`,
`system_one`, thresholds. Tool errors and order problems are recomputed from `tool_calls`.
