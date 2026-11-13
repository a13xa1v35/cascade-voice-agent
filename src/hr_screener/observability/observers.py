"""Pipeline observers: watch a live call without changing it.

An observer sees every frame moving between processors but cannot alter the flow,
so it is the right place for logging and metrics. Two levels:

- Always on (cheap, the numbers you want from every call):
  * user->bot latency per turn, broken down by stage (endpointing wait, STT,
    LLM, TTS), plus time to the first greeting;
  * turn boundaries and interruptions (barge-in), from the TurnTrackingObserver
    the PipelineWorker already runs;
  * a latency summary (median / max) when the call ends.
- DEBUG_PIPELINE=true (verbose, for learning and debugging): every transcript,
  every LLM request/response, every tool-call step, and raw service metrics
  (TTFB, processing time, token usage).

Everything is logged with the screening id so concurrent calls can be told apart.

On top of that, `CallRecorder` writes a normalized raw event timeline to Redis
(`screening:{id}:events`); `metrics.compute_scorecard` turns it into the per-call
scorecard after the call. See docs/metrics.md.
"""

import asyncio
import contextlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ErrorFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    MetricsFrame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.metrics.metrics import (
    LLMUsageMetricsData,
    TTFBMetricsData,
    TTSUsageMetricsData,
    TurnMetricsData,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.observers.function_call_observer import FunctionCallEvent, FunctionCallObserver
from pipecat.observers.loggers.llm_log_observer import LLMLogObserver
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.observers.loggers.transcription_log_observer import TranscriptionLogObserver
from pipecat.observers.turn_tracking_observer import TurnTrackingObserver
from pipecat.observers.user_bot_latency_observer import LatencyBreakdown, UserBotLatencyObserver
from pipecat.processors.frame_processor import FrameDirection

from hr_screener.llm.services import is_quota_error
from hr_screener.storage.store import events_key

EVENTS_CAP = 5000  # keep the last N events per call in Redis
FLUSH_INTERVAL_SECS = 2.0

# Only these frame types are ever looked at. Everything else (audio above all) is
# rejected by one isinstance check, before any other work.
_RECORDED_FRAMES = (
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
    MetricsFrame,
    TranscriptionFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    InterruptionFrame,
)

# Higher wins when several things could explain the end of the call. on_client_disconnected
# fires after EndWorkerFrame on the end_call path, so it must not overwrite end_call.
_END_REASON_PRIORITY = {
    "end_call": 8,
    "error": 7,
    "llm_error": 6,  # Sofia's LLM kept failing: apology and end (see llm/recovery.py)
    "context_unavailable": 5,  # history lookup failed: apology and end (see bot.py)
    "superseded": 4,  # a newer call for the same candidate ended this one
    "connection_lost": 3,  # the audio watchdog saw no browser audio
    "idle_timeout": 2,
    "hangup": 1,  # on_client_disconnected also fires after the two above
}


class CallRecorder(BaseObserver):
    """Records a normalized event timeline for one call.

    Never perturbs the pipeline: `on_push_frame` only appends to an in-memory list (no
    awaits, no Redis). A background task flushes batches to Redis every couple of
    seconds, and `stop()` does a final flush, so a crash mid-call still leaves most of
    the timeline.

    Clock: every event has `t` (seconds since the recorder was created, from one
    monotonic clock) and `wall` (ISO UTC derived from `t` plus the wall time captured at
    the same instant, so the two never disagree). `FramePushed.timestamp` (pipeline clock)
    and the `timestamp` fields on VAD frames / function-call events (wall clock) are
    deliberately not used.
    """

    def __init__(
        self,
        screening_id: str,
        redis: Any = None,
        *,
        clock: Any = time.monotonic,
        flush_interval: float = FLUSH_INTERVAL_SECS,
        events_ttl_secs: int | None = None,
    ) -> None:
        # One event per frame, not per hop: the dispatcher only calls us for first pushes.
        super().__init__(observe_every_push=False)
        self.screening_id = screening_id
        self.events: list[dict[str, Any]] = []
        self._redis = redis
        self._clock = clock
        self._flush_interval = flush_interval
        # Events are telemetry, not a record: the key expires this long after the last flush.
        self._events_ttl_secs = events_ttl_secs
        self._t0 = clock()
        self._wall0 = datetime.now(UTC)
        self._flushed = 0
        self._flush_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._bot_speaking = False

    @property
    def key(self) -> str:
        return events_key(self.screening_id)

    # --- recording (sync, cheap) ---------------------------------------------------

    def record(self, type_: str, **data: Any) -> None:
        t = self._clock() - self._t0
        self.events.append(
            {
                "t": round(t, 4),
                "wall": (self._wall0 + timedelta(seconds=t)).isoformat(),
                "type": type_,
                "data": data,
            }
        )

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if not isinstance(frame, _RECORDED_FRAMES):  # audio and everything else: no-op
            return
        if not data.first_push:
            return
        # Broadcast frames travel as an upstream and a downstream copy; keep one.
        if frame.broadcast_sibling_id is not None and data.direction is FrameDirection.UPSTREAM:
            return

        if isinstance(frame, VADUserStartedSpeakingFrame):
            self.record("user.speech_started")
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            self.record("user.speech_stopped")
        elif isinstance(frame, TranscriptionFrame):
            if frame.text.strip():
                self.record("stt.final", text=frame.text)
        elif isinstance(frame, LLMFullResponseStartFrame):
            self.record("llm.started")
        elif isinstance(frame, LLMFullResponseEndFrame):
            self.record("llm.ended")
        elif isinstance(frame, BotStartedSpeakingFrame):
            if not self._bot_speaking:
                self._bot_speaking = True
                self.record("bot.speech_started")
        elif isinstance(frame, BotStoppedSpeakingFrame):
            if self._bot_speaking:
                self._bot_speaking = False
                self.record("bot.speech_stopped")
        elif isinstance(frame, InterruptionFrame):
            self.record("interruption", bot_speaking=self._bot_speaking)
        elif isinstance(frame, MetricsFrame):
            self._record_metrics(frame)

    def _record_metrics(self, frame: MetricsFrame) -> None:
        for item in frame.data:
            if isinstance(item, TurnMetricsData):  # also covers SmartTurnMetricsData
                self.record(
                    "turn_model.prediction",
                    is_complete=item.is_complete,
                    probability=item.probability,
                    e2e_processing_time_ms=item.e2e_processing_time_ms,
                )
            elif isinstance(item, TTFBMetricsData):
                if item.value <= 0:  # PipelineWorker pushes a zeroed initial frame
                    continue
                name = item.processor.lower()
                for tag in ("llm", "tts", "stt"):
                    if tag in name:
                        self.record(f"{tag}.ttfb", processor=item.processor, seconds=item.value)
                        break
            elif isinstance(item, LLMUsageMetricsData):
                self.record(
                    "llm.usage",
                    processor=item.processor,
                    prompt_tokens=item.value.prompt_tokens,
                    completion_tokens=item.value.completion_tokens,
                    cache_read_tokens=item.value.cache_read_input_tokens,
                    reasoning_tokens=item.value.reasoning_tokens,
                )
            elif isinstance(item, TTSUsageMetricsData):
                self.record("tts.chars", processor=item.processor, chars=item.value)

    # --- Redis flushing -----------------------------------------------------------

    def start(self) -> None:
        """Begin periodic flushing (needs a running loop). Safe to call once."""
        if self._redis is not None and self._task is None:
            self._task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush()

    async def flush(self) -> None:
        """Write events not yet in Redis. Failures are logged and retried next time."""
        if self._redis is None:
            return
        async with self._flush_lock:
            batch = self.events[self._flushed :]
            if not batch:
                return
            try:
                async with self._redis.pipeline(transaction=True) as pipe:
                    pipe.rpush(self.key, *[json.dumps(e, default=str) for e in batch])
                    pipe.ltrim(self.key, -EVENTS_CAP, -1)
                    if self._events_ttl_secs:
                        pipe.expire(self.key, self._events_ttl_secs)
                    await pipe.execute()
                self._flushed += len(batch)
            except Exception:
                logger.exception(f"[{self.screening_id}] event flush failed (will retry)")

    async def stop(self) -> None:
        """Stop the periodic task and do the final flush."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self.flush()


class CallObservers:
    """Builds the observers for one call and keeps the numbers for its summary."""

    def __init__(
        self,
        screening_id: str,
        *,
        debug: bool = False,
        redis: Any = None,
        events_ttl_secs: int | None = None,
        on_llm_error: Callable[[ErrorFrame, bool], None] | None = None,
    ) -> None:
        self.screening_id = screening_id
        self.debug = debug
        # Called with (error frame, is it a rate-limit / quota error) for each LLM error.
        self._on_llm_error = on_llm_error
        self.recorder = CallRecorder(screening_id, redis, events_ttl_secs=events_ttl_secs)
        self.hangup: Any = None  # HangupController, when the call has one
        self.recovery: Any = None  # LLMRecovery, when the call has an LLM
        self._end_reason: str | None = None
        self.latencies: list[float] = []  # seconds, user stopped -> bot started, per turn
        self.interruptions = 0
        self.turns = 0

    def build(self) -> list[BaseObserver]:
        """Observers to pass to `PipelineWorker(observers=...)`."""
        latency = UserBotLatencyObserver()
        latency.add_event_handler("on_latency_measured", self._on_latency)
        latency.add_event_handler("on_latency_breakdown", self._on_breakdown)
        latency.add_event_handler("on_first_bot_speech_latency", self._on_first_speech)
        # The recorder and the function-call observer always run; DEBUG_PIPELINE only
        # adds the verbose log observers.
        function_calls = FunctionCallObserver(include_results=True)
        function_calls.add_event_handler("on_function_call_event", self._on_function_call)
        observers: list[BaseObserver] = [latency, self.recorder, function_calls]
        if self.recovery is not None:
            observers.append(self.recovery)

        if self.debug:
            observers += [TranscriptionLogObserver(), LLMLogObserver(), MetricsLogObserver()]
        return observers

    def attach_aggregators(self, user_agg: Any, assistant_agg: Any) -> None:
        """Record user/assistant turn boundaries from the context aggregators' events."""

        async def user_started(_agg: Any, strategy: Any) -> None:
            self.recorder.record("user.turn_started", strategy=type(strategy).__name__)

        async def user_stopped(_agg: Any, strategy: Any, message: Any) -> None:
            self.recorder.record(
                "user.turn_ended",
                strategy=type(strategy).__name__,
                text=getattr(message, "content", None),
            )

        async def assistant_stopped(_agg: Any, message: Any) -> None:
            self.recorder.record(
                "bot.said",
                text=getattr(message, "content", ""),
                interrupted=bool(getattr(message, "interrupted", False)),
            )

        user_agg.add_event_handler("on_user_turn_started", user_started)
        user_agg.add_event_handler("on_user_turn_stopped", user_stopped)
        assistant_agg.add_event_handler("on_assistant_turn_stopped", assistant_stopped)

    def attach_llm(self, llm: Any) -> None:
        """Record the LLM service's errors (rate limit, quota, server trouble) as `llm.error`
        events, through the `on_error` event every Pipecat processor raises."""

        async def llm_error(_llm: Any, error: ErrorFrame) -> None:
            quota = is_quota_error(error)
            self.recorder.record(
                "llm.error",
                message=str(error.error)[:500],
                category=error.category.value if error.category else None,
                quota=quota,
            )
            if self._on_llm_error is not None:
                self._on_llm_error(error, quota)

        llm.add_event_handler("on_error", llm_error)

    def attach_recovery(self, recovery: Any) -> None:
        """Let the LLM recovery observer (retry once, then apologize and end) watch the call.
        Call before `build()`."""
        self.recovery = recovery

    def attach_hangup(self, hangup: Any) -> None:
        """Let the hang-up controller decide whether the agent ended the call."""
        self.hangup = hangup

    async def hangup_close(self) -> None:
        if self.hangup is not None:
            await self.hangup.close()

    # --- call lifecycle (called from bot.py) ---

    def call_connected(self) -> None:
        self.recorder.record("call.connected")

    def set_end_reason(self, reason: str) -> None:
        """Remember why the call ended. Highest priority wins, not the last write."""
        if _END_REASON_PRIORITY.get(reason, 0) > _END_REASON_PRIORITY.get(
            self._end_reason or "", 0
        ):
            self._end_reason = reason

    async def on_idle_timeout(self, _worker: Any) -> None:
        self.set_end_reason("idle_timeout")

    def saw_end_call(self) -> bool:
        """True if the end_call tool completed without returning an error."""
        for e in self.recorder.events:
            d = e["data"]
            if e["type"] == "tool.event" and d.get("name") == "end_call":
                result = d.get("result")
                if d.get("kind") == "completed" and not (
                    isinstance(result, dict) and "error" in result
                ):
                    return True
        return False

    def end_call(self, *, ended_by_tool: bool) -> str:
        """Record call.ended with the resolved reason and return it.

        With a hang-up controller it is authoritative: "end_call" only if the agent was
        ending the call when it stopped (armed, in grace, or fired; a candidate who hangs
        up during the grace window is a clean end). An end_call that was cancelled because
        the candidate spoke, and never re-armed, is a plain "hangup" even though the tool
        completed. Without a controller (standalone use) fall back to the legacy inference
        from the screening status / the end_call tool event.
        """
        if self.hangup is not None:
            if self.hangup.ending:
                self.set_end_reason("end_call")
        elif ended_by_tool or self.saw_end_call():
            self.set_end_reason("end_call")
        reason = self._end_reason or "unknown"
        self.recorder.record("call.ended", end_reason=reason)
        return reason

    def attach_turn_tracking(self, turn_tracking: TurnTrackingObserver | None) -> None:
        """Hook into the turn tracker the PipelineWorker creates by default."""
        if turn_tracking is None:
            return
        turn_tracking.add_event_handler("on_turn_started", self._on_turn_started)
        turn_tracking.add_event_handler("on_turn_ended", self._on_turn_ended)

    def log_summary(self) -> None:
        """One line per call: how many turns, how fast, how often interrupted."""
        if self.latencies:
            stats = (
                f"latency median={median(self.latencies):.2f}s "
                f"max={max(self.latencies):.2f}s over {len(self.latencies)} replies"
            )
        else:
            stats = "no bot replies measured"
        logger.info(
            f"[{self.screening_id}] call summary: turns={self.turns} "
            f"interruptions={self.interruptions} {stats}"
        )

    # --- event handlers --------------------------------------------------------------

    async def _on_latency(self, _observer: Any, seconds: float) -> None:
        self.latencies.append(seconds)

    async def _on_breakdown(self, _observer: Any, breakdown: LatencyBreakdown) -> None:
        # Example output, one line per stage:
        #   0.200s  endpointing wait   [config: VAD stop_secs]
        #   0.180s  transcription      [AssemblyAISTTService#0]
        #   0.410s  LLM inference      [AnthropicLLMService#0]
        #   0.220s  speech synthesis   [AssemblyAITTSService#0]
        #   1.010s  TOTAL
        lines = "\n    ".join(breakdown.turn_contribution_lines())
        logger.info(f"[{self.screening_id}] user->bot latency breakdown:\n    {lines}")
        stages: dict[str, float] = {}
        for c in breakdown.contributions:
            stages[c.key] = round(stages.get(c.key, 0.0) + c.duration_secs, 4)
        self.recorder.record(
            "latency.breakdown",
            total_secs=round(breakdown.total_secs, 4),
            measured_from=breakdown.measured_from.value if breakdown.measured_from else None,
            stages=stages,
        )

    async def _on_first_speech(self, _observer: Any, seconds: float) -> None:
        logger.info(f"[{self.screening_id}] first bot speech {seconds:.2f}s after connect")

    async def _on_turn_started(self, _observer: Any, turn: int) -> None:
        self.turns = turn
        logger.debug(f"[{self.screening_id}] turn {turn} started")

    async def _on_turn_ended(
        self, _observer: Any, turn: int, duration: float, was_interrupted: bool
    ) -> None:
        if was_interrupted:
            self.interruptions += 1
        note = " (bot was interrupted)" if was_interrupted else ""
        logger.info(f"[{self.screening_id}] turn {turn} ended after {duration:.1f}s{note}")

    async def _on_function_call(self, _observer: Any, event: FunctionCallEvent) -> None:
        self.recorder.record(
            "tool.event",
            name=event.function_name,
            kind=event.kind.value.removeprefix("function_call_"),
            tool_call_id=event.tool_call_id,
            args=event.arguments,
            result=event.result,
            error=event.error,
        )
        if self.debug:
            logger.debug(
                f"[{self.screening_id}] tool {event.function_name} {event.kind.value}"
                + (f" args={event.arguments}" if event.arguments is not None else "")
                + (f" result={event.result}" if event.result is not None else "")
            )
