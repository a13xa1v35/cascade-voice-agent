"""Hang-up safety: a cancelable grace window between `end_call` and closing the line.

Problem this solves: Smart Turn can end the user's turn early ("Gracias." ...), the LLM
then says goodbye and calls `end_call`, and the candidate keeps talking. Closing the line
the instant the tool runs cuts them off. Instead `end_call` only *arms* a
`HangupController`; the line closes only after

    marker seen at the output transport  (everything queued before it has been sent)
    AND the response that produced the goodbye has fully passed the output transport
    AND the bot is not speaking
    -> then `grace_secs` of silence from the candidate.

If the candidate starts a user turn at any point before the hang-up fires, it is
cancelled and the conversation continues (the LLM must call `end_call` again). While the
VAD hears the candidate during the grace window the timer is held, and it restarts from
zero once they stop: a short word can reach the transcript only after the window would
have ended (call a7852d728714: "Una." arrived 0.4 s after a 1.5 s window).

Firing closes the line immediately (`immediate`, the worker's cancel) when the bot is
silent: the goodbye has already played, and a graceful EndFrame would let late user speech
trigger one more reply ("¿qué querías preguntar?") that is then cut off. If the bot is
still speaking (max_wait safety net) the graceful `end` is used instead.

Ordering note (verified in pipecat 1.15.0 for both Sofia LLM services): `AnthropicLLMService`
(`_process_context`: `run_function_calls` in the `try`, the end frame in the `finally`) and
`OpenAILLMService` (`BaseOpenAILLMService._process_context` ends with `run_function_calls`;
`process_frame` pushes `LLMFullResponseEndFrame` in its `finally`, after `_process_context`
returns) both run the function calls (`run_function_calls`, which spawns the tool as a
background task) BEFORE they push `LLMFullResponseEndFrame`. (OpenAI reports the usage metrics
inside `_process_context`, before the end frame; nothing here depends on that.) So the tool
can run and push `HangupMarkerFrame` ahead of the response-end frame. TTS only flushes the last
(unfinished) sentence of the response when it sees that end frame, so the marker CAN overtake
the final goodbye sentence's audio.
The marker alone is therefore not proof that the goodbye has played. We additionally
require an `LLMFullResponseEndFrame` seen from the output transport (it is queued behind
that sentence's audio, so by the time it passes, the audio has been sent). The flag is
cleared by every `LLMFullResponseStartFrame` seen from the output transport, so an end
frame that passed before `arm()` (slow tool) still counts, and one belonging to an earlier
response does not.

States: idle -> armed -> grace -> fired, with suspended for a cancelled hang-up.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ControlFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.processors.frame_processor import FrameDirection
from pipecat.transports.base_output import BaseOutputTransport

DEFAULT_GRACE_SECS = 3.0  # people take a beat after a goodbye on the phone
DEFAULT_RESUME_TIMEOUT_SECS = 3.0
DEFAULT_MAX_WAIT_SECS = 20.0


@dataclass
class HangupMarkerFrame(ControlFrame):
    """Pushed downstream by `end_call`. Being a non-system frame it is queued behind the
    TTS audio and the transport's audio, so seeing it leave the output transport means
    the audio queued before it has been sent."""


class HangupState(StrEnum):
    IDLE = "idle"
    ARMED = "armed"  # waiting for the goodbye to finish playing
    GRACE = "grace"  # goodbye done; waiting grace_secs for the candidate to speak
    FIRED = "fired"
    SUSPENDED = "suspended"  # cancelled because the candidate spoke


_WATCHED_FRAMES = (
    HangupMarkerFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)


class HangupController(BaseObserver):
    def __init__(
        self,
        *,
        record: Callable[..., None],
        grace_secs: float = DEFAULT_GRACE_SECS,
        resume_timeout_secs: float = DEFAULT_RESUME_TIMEOUT_SECS,
        max_wait_secs: float = DEFAULT_MAX_WAIT_SECS,
        end: Callable[[], Awaitable[Any]] | None = None,
        immediate: Callable[[], Awaitable[Any]] | None = None,
        on_fire: Callable[[], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # Every hop must be seen: we filter on the *source* being the output transport.
        super().__init__(observe_every_push=True)
        self._record = record
        self.grace_secs = grace_secs
        self.resume_timeout_secs = resume_timeout_secs
        self.max_wait_secs = max_wait_secs
        self._end = end
        self._immediate = immediate
        self._on_fire = on_fire
        self._clock = clock

        self.state = HangupState.IDLE
        self._outcome: str | None = None
        self._armed_at = 0.0
        self._goodbye_done_at: float | None = None
        self._marker_seen = False
        self._response_ended = False  # see module note
        self._bot_speaking = False
        self._user_speaking = False  # per VAD
        self._grace_task: asyncio.Task[None] | None = None
        self._max_wait_task: asyncio.Task[None] | None = None
        self._resume_task: asyncio.Task[None] | None = None

    # --- public API ----------------------------------------------------------------------

    def bind_end(
        self,
        end: Callable[[], Awaitable[Any]],
        immediate: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        """Set how the line is closed: `end` gracefully (bot.py: `worker.stop_when_done`),
        `immediate` at once (bot.py: `worker.cancel`)."""
        self._end = end
        self._immediate = immediate

    @property
    def fired(self) -> bool:
        return self.state is HangupState.FIRED

    @property
    def ending(self) -> bool:
        """The agent was ending the call (armed, in grace, or already hung up)."""
        return self.state in (HangupState.ARMED, HangupState.GRACE, HangupState.FIRED)

    def arm(self, outcome: str | None = None) -> None:
        """Called by `end_call`. Idempotent while armed/in grace; ignored once fired."""
        if self.state in (HangupState.ARMED, HangupState.GRACE, HangupState.FIRED):
            return
        self._cancel_tasks()
        self._set_state(HangupState.ARMED)
        self._outcome = outcome
        self._armed_at = self._clock()
        self._goodbye_done_at = None
        self._marker_seen = False
        self._record("hangup.armed", outcome=outcome)
        self._max_wait_task = asyncio.create_task(self._max_wait())

    async def close(self) -> None:
        """Cancel pending timers (call from the call's cleanup)."""
        tasks = self._cancel_tasks()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("hangup timer failed during close")

    # --- aggregator events (register on the user aggregator) --------------------------------

    async def on_user_turn_started(self, *_args: Any) -> None:
        if self.state in (HangupState.ARMED, HangupState.GRACE):
            phase = self.state.value
            self._cancel_tasks()
            self._set_state(HangupState.SUSPENDED)
            self._record("hangup.canceled", phase=phase, outcome=self._outcome)
        elif self.state is HangupState.SUSPENDED:
            self._cancel_resume()  # still talking: don't hang up on them

    async def on_user_turn_stopped(self, *_args: Any) -> None:
        if self.state is HangupState.SUSPENDED:
            self._cancel_resume()
            self._resume_task = asyncio.create_task(self._resume_wait())

    # --- observer --------------------------------------------------------------------------

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if not isinstance(frame, _WATCHED_FRAMES):  # audio and everything else: no-op
            return
        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._user_speaking = True
            if self.state is HangupState.GRACE and self._grace_task is not None:
                logger.info("hangup: candidate speaking, grace timer held")
                self._cancel_grace()
            return
        if isinstance(frame, VADUserStoppedSpeakingFrame):
            self._user_speaking = False
            if self.state is HangupState.GRACE and self._grace_task is None:
                self._start_grace()  # restart the full window after they stop
            return
        if (
            isinstance(frame, LLMFullResponseStartFrame)
            and self.state is HangupState.SUSPENDED
            and data.first_push
        ):
            # The LLM is answering the candidate: the conversation resumed. It must
            # call end_call again to hang up.
            self._cancel_resume()
            self._set_state(HangupState.IDLE)
        # Only what leaves the output transport downstream: that is what was actually
        # sent, and it is seen once (not on every hop, not as a broadcast duplicate).
        if data.direction is not FrameDirection.DOWNSTREAM:
            return
        if not isinstance(data.source, BaseOutputTransport):
            return

        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            if self.state is HangupState.GRACE:
                # More bot speech during the window: wait for it to end first.
                self._cancel_grace()
                self._goodbye_done_at = None
                self._set_state(HangupState.ARMED)
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            self._check()
        elif isinstance(frame, LLMFullResponseStartFrame):
            self._response_ended = False
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._response_ended = True
            self._check()
        elif isinstance(frame, HangupMarkerFrame) and self.state is HangupState.ARMED:
            self._marker_seen = True
            self._check()

    # --- internals -------------------------------------------------------------------------

    def _set_state(self, state: HangupState) -> None:
        if state is not self.state:
            logger.info(f"hangup: {self.state.value} -> {state.value}")
            self.state = state

    def _check(self) -> None:
        if (
            self.state is HangupState.ARMED
            and self._marker_seen
            and self._response_ended
            and not self._bot_speaking
        ):
            self._goodbye_done_at = self._clock()
            self._set_state(HangupState.GRACE)
            if not self._user_speaking:
                self._start_grace()  # else held until the VAD says they stopped

    def _start_grace(self) -> None:
        self._cancel_grace()
        self._grace_task = asyncio.create_task(self._grace())

    async def _grace(self) -> None:
        await asyncio.sleep(self.grace_secs)
        await self._fire("goodbye_finished")

    async def _max_wait(self) -> None:
        await asyncio.sleep(self.max_wait_secs)
        if self.state is HangupState.ARMED:  # marker dropped (interruption) or bot never quiet
            await self._fire("max_wait")

    async def _resume_wait(self) -> None:
        await asyncio.sleep(self.resume_timeout_secs)
        if self.state is HangupState.SUSPENDED:  # noise blip: nobody answered
            await self._fire("no_response_after_cancel")

    async def _fire(self, reason: str) -> None:
        if self.state is HangupState.FIRED:
            return
        self._cancel_tasks()  # skips the calling timer task itself
        self._set_state(HangupState.FIRED)
        now = self._clock()
        self._record(
            "hangup.fired",
            reason=reason,
            outcome=self._outcome,
            waited_secs=round(now - self._armed_at, 3),
            since_goodbye_secs=(
                round(now - self._goodbye_done_at, 3) if self._goodbye_done_at is not None else None
            ),
        )
        if self._on_fire is not None:
            try:
                self._on_fire()
            except Exception:
                logger.exception("hangup on_fire callback failed")
        close = self._end
        if self._immediate is not None and not self._bot_speaking:
            close = self._immediate  # goodbye already played: nothing left to flush
        if close is not None:
            try:
                await close()
            except Exception:
                logger.exception("hangup: closing the line failed")

    def _cancel_grace(self) -> None:
        if self._grace_task is not None:
            self._grace_task.cancel()
            self._grace_task = None

    def _cancel_resume(self) -> None:
        if self._resume_task is not None:
            self._resume_task.cancel()
            self._resume_task = None

    def _cancel_tasks(self) -> list[asyncio.Task[None]]:
        """Cancel every timer; return the ones that were pending (to await on close)."""
        tasks = [t for t in (self._grace_task, self._max_wait_task, self._resume_task) if t]
        for task in tasks:
            if task is not asyncio.current_task():
                task.cancel()
        self._grace_task = self._max_wait_task = self._resume_task = None
        return tasks
