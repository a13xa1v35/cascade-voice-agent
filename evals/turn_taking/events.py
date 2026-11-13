"""Turn-taking diagnostics: a frame observer plus aggregator handlers that write
events.json (each event has t = seconds since the first input chunk)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ErrorFrame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.processors.frame_processor import FrameDirection

from evals.turn_taking.wav_transport import SessionClock

INTERIM_MIN_GAP = 0.3  # seconds between logged stt.interim events

_SIMPLE = {
    VADUserStartedSpeakingFrame: "vad.user_started",
    VADUserStoppedSpeakingFrame: "vad.user_stopped",
    UserStartedSpeakingFrame: "user.started_speaking",
    UserStoppedSpeakingFrame: "user.stopped_speaking",
    BotStartedSpeakingFrame: "bot.started_speaking",
    BotStoppedSpeakingFrame: "bot.stopped_speaking",
    InterruptionFrame: "interruption",
}


class EventLog(BaseObserver):
    def __init__(self, clock: SessionClock) -> None:
        super().__init__()
        self.clock = clock
        self.events: list[dict[str, Any]] = []
        self._seen: set[int] = set()  # a frame is observed once per hop; log it once
        self._llm: dict[str, Any] | None = None
        self._last_interim: tuple[float, str] = (-1.0, "")
        self.interim_count = 0  # every interim seen; only some are logged (see below)
        # Session health: any service ErrorFrame or websocket reconnect makes the run invalid.
        self.problems: list[str] = []
        self.unhealthy = asyncio.Event()
        self.closing = False  # set before a deliberate shutdown; later disconnects are fine
        self._connects: dict[int, int] = {}

    def report_problem(self, service: str, message: str, type_: str = "service.error") -> None:
        self.add(type_, service=service, message=message)
        self.problems.append(f"{service}: {message}")
        self.unhealthy.set()

    def watch_services(self, processors: list[Any]) -> None:
        """Count websocket (re)connects on every service that exposes connection events."""
        for proc in processors:
            handlers = getattr(proc, "_event_handlers", {})
            if "on_connected" not in handlers:
                continue
            name = type(proc).__name__

            async def connected(_svc: Any, *_a: Any, key: int = id(proc), name: str = name) -> None:
                self._connects[key] = self._connects.get(key, 0) + 1
                if self._connects[key] > 1:
                    self.report_problem(name, "websocket reconnected", "service.reconnect")

            async def disconnected(_svc: Any, *_a: Any, name: str = name) -> None:
                if not self.closing:
                    self.report_problem(
                        name, "websocket disconnected mid-session", "service.reconnect"
                    )

            proc.add_event_handler("on_connected", connected)
            if "on_disconnected" in handlers:
                proc.add_event_handler("on_disconnected", disconnected)

    def add(self, type_: str, **fields: Any) -> None:
        self.events.append({"t": round(self.clock.now(), 3), "type": type_, **fields})

    def _flush_llm(self) -> None:
        if self._llm and self._llm["text"]:
            self.events.append(self._llm)
        self._llm = None

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if isinstance(frame, ErrorFrame):  # travels upstream, so check before the direction filter
            if frame.id not in self._seen:
                self._seen.add(frame.id)
                self.report_problem(
                    type(frame.processor).__name__ if frame.processor else "unknown", frame.error
                )
            return
        # Broadcast frames exist as an upstream and a downstream copy: log the downstream one.
        if data.direction != FrameDirection.DOWNSTREAM or frame.id in self._seen:
            return
        if isinstance(frame, LLMTextFrame):
            if self._llm is None:
                self._llm = {"t": round(self.clock.now(), 3), "type": "llm.text", "text": ""}
            self._llm["text"] += frame.text
            return
        if isinstance(frame, LLMFullResponseStartFrame):
            self._seen.add(frame.id)
            self._flush_llm()
            return
        if isinstance(frame, LLMFullResponseEndFrame):
            self._seen.add(frame.id)
            self._flush_llm()
            return
        if isinstance(frame, InterimTranscriptionFrame):
            self._seen.add(frame.id)
            self.interim_count += 1
            now = self.clock.now()
            # Interims repeat the turn's text so far; log changes at most every 0.3 s.
            if (
                frame.text != self._last_interim[1]
                and now - self._last_interim[0] >= INTERIM_MIN_GAP
            ):
                self._last_interim = (now, frame.text)
                self.add("stt.interim", text=frame.text)
            return
        if isinstance(frame, TranscriptionFrame):
            self._seen.add(frame.id)
            self.add("stt.final", text=frame.text)
            return
        for cls, name in _SIMPLE.items():
            if isinstance(frame, cls):
                self._seen.add(frame.id)
                if cls is InterruptionFrame:
                    self._flush_llm()
                self.add(name)
                return

    def attach_aggregators(self, user_agg: Any, assistant_agg: Any) -> None:
        async def user_started(_agg: Any, strategy: Any) -> None:
            self.add("user_turn.started", strategy=type(strategy).__name__)

        async def user_stopped(_agg: Any, strategy: Any, message: Any) -> None:
            self.add(
                "user_turn.stopped",
                strategy=type(strategy).__name__,
                text=getattr(message, "content", None),
            )

        async def assistant_stopped(_agg: Any, message: Any) -> None:
            self.add(
                "assistant_turn.stopped",
                text=getattr(message, "content", ""),
                interrupted=bool(getattr(message, "interrupted", False)),
            )

        user_agg.add_event_handler("on_user_turn_started", user_started)
        user_agg.add_event_handler("on_user_turn_stopped", user_stopped)
        assistant_agg.add_event_handler("on_assistant_turn_stopped", assistant_stopped)

    def write(self, path: Path) -> None:
        self._flush_llm()
        events = sorted(self.events, key=lambda e: e["t"])
        path.write_text(json.dumps(events, indent=1, ensure_ascii=False))
