"""What happens when Sofia's LLM request fails during a call, on any provider.

Pipecat reports a failed request (timeout, connectivity, 5xx, quota, ...) as a non-fatal
`ErrorFrame` pushed upstream by the LLM service, and does nothing else: the context is left
as it was and nobody asks the model again, so Sofia would stay silent until the idle timeout.
`LLMRecovery` is a pipeline observer that handles it:

- first failure since the last good response: run inference once more on the same context
  (an `LLMRunFrame`, the frame that starts the greeting) and record an `llm.retry` event;
- a second failure in a row, or a failure that retrying cannot fix (rate limit / quota, bad
  credentials, invalid request): speak a short apology without the model and end the call
  (`TTSSpeakFrame(append_to_context=False)` then `EndFrame`, the pattern of the
  context-unavailable path in bot.py) with end reason `llm_error`. The screening is finalized
  like a dropped call, so it stays resumable (see `bot._finish_status`).

Why an observer, and not the `on_error` event: an observer sees the `ErrorFrame` and the
`LLMFullResponseStartFrame` / `LLMFullResponseEndFrame` of the same response in one ordered
stream, so "this response ended without an error" is decided without races. It works on every
channel because it is the LLM service that pushes the error, whatever transport follows.

What counts as success: a response (Start ... End) during which the LLM reported no error;
one that ended in tool calls counts. That resets the failure counter.

Not retried: nothing after the agent has started to end the call (the hang-up controller is
armed / firing, or `end_call` completed) or after the call was stopped, so a late failure
never speaks into a closing line.

Known limit, voice only: the retry is an `LLMRunFrame` queued from the observer; if the
candidate is mid-turn at that moment, the run uses the context as it is then. A failure that
left a partial reply in the context makes the retry continue after that partial text.
"""

from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any

from loguru import logger
from pipecat.frames.frames import (
    EndFrame,
    ErrorFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMRunFrame,
    TTSSpeakFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.utils.errors import ErrorCategory

from hr_screener.llm.services import is_quota_error

if TYPE_CHECKING:
    from hr_screener.observability.observers import CallObservers

# After this many failures in a row (no good response between) the call is given up.
MAX_CONSECUTIVE_FAILURES = 2

QueueFrames = Callable[[Iterable[Frame]], Awaitable[None]]


class LLMRecovery(BaseObserver):
    def __init__(self, llm: Any, observers: "CallObservers", apology: Callable[[], str]) -> None:
        super().__init__(observe_every_push=False)  # one event per frame, not per hop
        self._llm = llm
        self._observers = observers
        # Read when the apology is spoken: the call language may have changed since the start.
        self._apology = apology
        self._queue_frames: QueueFrames | None = None
        self._failures = 0  # consecutive, reset by a response without an error
        self._response_failed = False
        self._stopped = False

    def bind(self, queue_frames: QueueFrames) -> None:
        """Give it the pipeline worker's `queue_frames` (the worker is built after the
        observers, so it cannot be a constructor argument)."""
        self._queue_frames = queue_frames

    def stop(self) -> None:
        """The call is being torn down: from now on only observe."""
        self._stopped = True

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if not isinstance(frame, (ErrorFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame)):
            return
        if not data.first_push:
            return
        try:
            if isinstance(frame, LLMFullResponseStartFrame):
                self._response_failed = False
            elif isinstance(frame, LLMFullResponseEndFrame):
                if not self._response_failed:
                    self._failures = 0
            elif frame.processor is self._llm and frame.category is not ErrorCategory.APPLICATION:
                # An ErrorFrame from Sofia's LLM, no other. APPLICATION is the LLM service
                # reporting a failure of our own code (a tool handler), not of the request:
                # asking the model again would not help.
                self._response_failed = True
                await self._on_llm_error(frame)
        except Exception:
            # An observer error must never touch the call; the worst case is no recovery.
            logger.exception(f"[{self._observers.screening_id}] LLM recovery failed")

    def _call_is_ending(self) -> bool:
        hangup = self._observers.hangup
        return (
            self._stopped
            or (hangup is not None and hangup.ending)
            or self._observers.saw_end_call()
        )

    async def _on_llm_error(self, error: ErrorFrame) -> None:
        if self._queue_frames is None or self._call_is_ending():
            return
        quota = is_quota_error(error)
        permanent = error.category is not None and error.category.is_permanent
        if quota or permanent or self._failures + 1 >= MAX_CONSECUTIVE_FAILURES:
            await self._give_up(error, quota=quota)
            return
        self._failures += 1
        self._observers.recorder.record("llm.retry", attempt=self._failures)
        logger.warning(
            f"[{self._observers.screening_id}] LLM request failed ({error.error}); "
            "running inference again"
        )
        await self._queue_frames([LLMRunFrame()])

    async def _give_up(self, error: ErrorFrame, *, quota: bool) -> None:
        self._stopped = True  # one apology, and no retry while it plays
        self._observers.set_end_reason("llm_error")
        self._observers.recorder.record("llm.gave_up", quota=quota, failures=self._failures + 1)
        logger.error(
            f"[{self._observers.screening_id}] LLM keeps failing ({error.error}): "
            "apologizing and ending the call"
        )
        assert self._queue_frames is not None
        # Same pattern as the context-unavailable path: the TTS holds the EndFrame until the
        # apology's audio is done. append_to_context=False: not a turn of the conversation.
        await self._queue_frames(
            [
                TTSSpeakFrame(
                    self._apology(),
                    append_to_context=False,
                ),
                EndFrame(),
            ]
        )
