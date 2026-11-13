"""The text channel: the real call pipeline driven over typed lines instead of audio.

`TextTransport` plugs into `run_screening_bot(..., channel=Channel.TEXT)` where a voice
transport would, so a typed call runs the same prompt, tools, context, observers and
`_finalize` as a phone or browser call. `TextCall` is the API a program drives (the terminal
chat in chat.py, and later an eval with a simulated candidate):

    call = TextCall(screening_id, store=store, settings=settings, live_calls=live_calls)
    call.start()
    greeting = await call.next_reply()     # Sofia speaks first
    reply = await call.say("Hola, soy yo") # send a line, wait for her whole reply
    await call.drop()                      # the candidate hangs up (or: Sofia ends the call)
    await call.wait_done()                 # finalize (status, transcript, metrics, summary)

The caller must already have claimed the screening (status in_progress), exactly like
api.py does before it starts a voice bot. Everything the call needs comes in through the
`Settings` passed in; nothing here reads the environment.

How a typed line becomes a user turn (verified in pipecat/turns/user_stop/
external_user_turn_stop_strategy.py and user_start/external_user_turn_start_strategy.py):
`TextInput` sends ProposedUserStartedSpeakingFrame, TranscriptionFrame, then
ProposedUserStoppedSpeakingFrame. The user aggregator's ExternalUserTurnStrategies resolve
the proposals into UserStarted/StoppedSpeakingFrame, commit the transcript as one user
message and run the LLM, the same path the STT output takes in voice.

What "Sofia's reply" is: everything the LLM says (or a TTSSpeakFrame, the fixed apology when
the call history cannot be loaded) until it is waiting for the candidate again.
A response that ends in tool calls is followed by another LLM run (with the tool results),
so its text is joined with the next one's.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    EndWorkerFrame,
    ErrorFrame,
    Frame,
    FunctionCallsStartedFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    StartFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_transport import BaseTransport
from pipecat.utils.time import time_now_iso8601

from hr_screener.config import Settings
from hr_screener.models import Channel
from hr_screener.pipeline.bot import run_screening_bot
from hr_screener.pipeline.frames import HoldingLineFrame, NoFollowUpFrame
from hr_screener.screening.calls import LiveCalls
from hr_screener.screening.summary import Summarizer, summarize_call
from hr_screener.storage.store import ScreeningStore

if TYPE_CHECKING:
    from hr_screener.knowledge.store import KnowledgeBase

CANDIDATE_ID = "text-candidate"


class TextInput(FrameProcessor):
    """Head of the text pipeline: turns `send()` calls into the frames STT + turn detection
    would produce, and reports the client as connected once the pipeline has started."""

    def __init__(self, transport: "TextTransport") -> None:
        super().__init__(name="TextInput")
        self._transport = transport

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if isinstance(frame, StartFrame):
            await self._transport._call_event_handler("on_client_connected", None)

    async def send(self, text: str) -> None:
        """Queue one typed line as one complete user turn."""
        await self.queue_frame(ProposedUserStartedSpeakingFrame())
        await self.queue_frame(
            TranscriptionFrame(text=text, user_id=CANDIDATE_ID, timestamp=time_now_iso8601())
        )
        await self.queue_frame(ProposedUserStoppedSpeakingFrame())


class TextOutput(FrameProcessor):
    """Between the LLM and the assistant aggregator: collects what Sofia says and hands one
    reply per assistant turn to the transport. Frames always pass through untouched."""

    def __init__(self, transport: "TextTransport") -> None:
        super().__init__(name="TextOutput")
        self._transport = transport
        self._parts: list[str] = []
        # FunctionCallsStartedFrame comes before the LLMFullResponseEndFrame of the response
        # that made the calls; such a response is usually followed by another run, so it is
        # not the end of Sofia's turn. It is when a tool asks for no further run and says so
        # with a NoFollowUpFrame (a save after which she already asked the next question, see
        # agent/tools.py), which can arrive before or after that end frame.
        self._tool_calls = False
        self._no_follow_up = False  # a NoFollowUpFrame came for the current tool calls
        self._waiting = False  # the response with tool calls ended; waiting for the next one

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM:
            if isinstance(frame, LLMTextFrame):
                self._parts.append(frame.text)
            elif isinstance(frame, TTSSpeakFrame):
                # Fixed text the bot speaks without the LLM (the voice path hands it to TTS).
                # The holding line of a knowledge search is a reply of its own and the call
                # goes on; any other fixed line is an apology, always followed by an EndFrame,
                # so the call is ending.
                self._parts.append(frame.text)
                if not isinstance(frame, HoldingLineFrame):
                    self._transport.ending = True
                self._flush()
            elif isinstance(frame, FunctionCallsStartedFrame):
                self._tool_calls = True
            elif isinstance(frame, NoFollowUpFrame):
                if self._waiting:
                    self._end_turn()  # the response already ended: the turn is over now
                else:
                    self._no_follow_up = True
            elif isinstance(frame, LLMFullResponseEndFrame):
                if self._tool_calls and self._no_follow_up:
                    self._end_turn()
                elif self._tool_calls:
                    self._tool_calls, self._waiting = False, True  # the results start another
                    self._parts.append(" ")
                else:
                    self._end_turn()
            elif isinstance(frame, (EndWorkerFrame, EndFrame)):
                self._flush()  # end_call: the goodbye came with the tool call, so deliver it
            elif isinstance(frame, CancelFrame):
                self._parts.clear()  # a dropped call: the half-said reply is never delivered
        await self.push_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM and isinstance(frame, (EndFrame, CancelFrame)):
            self._transport.close()  # the pipeline is over; finalize still follows

    def _end_turn(self) -> None:
        self._tool_calls = self._no_follow_up = self._waiting = False
        self._flush()

    def _flush(self) -> None:
        text = "".join(self._parts).strip()
        self._parts.clear()
        if text:
            self._transport.deliver(text)


class TextTransport(BaseTransport):
    """A transport with no wire: replies go to a queue, lines come from `send()`.

    Raises the same events a voice transport does (`on_client_connected` once the pipeline
    is up, `on_client_disconnected` from `disconnect()`), so bot.py treats it like any other.
    """

    def __init__(self) -> None:
        super().__init__(name="TextTransport")
        self._input = TextInput(self)
        self._output = TextOutput(self)
        self._replies: asyncio.Queue[str | None] = asyncio.Queue()
        self._closed = False
        # True once Sofia has spoken her last (fixed) words: the pipeline is about to end.
        self.ending = False
        self._ended = asyncio.Event()
        self._register_event_handler("on_client_connected")
        self._register_event_handler("on_client_disconnected")

    def input(self) -> FrameProcessor:
        return self._input

    def output(self) -> FrameProcessor:
        return self._output

    @property
    def closed(self) -> bool:
        return self._closed

    async def wait_closed(self) -> None:
        await self._ended.wait()

    def deliver(self, text: str) -> None:
        self._replies.put_nowait(text)

    def close(self) -> None:
        """No more replies will come. Idempotent; replies already queued are still read."""
        if not self._closed:
            self._closed = True
            self._ended.set()
            self._replies.put_nowait(None)

    async def send(self, text: str) -> None:
        await self._input.send(text)

    async def next_reply(self) -> str | None:
        """The next reply, or None once the call is over and every reply has been read."""
        if self._closed and self._replies.empty():
            return None
        reply = await self._replies.get()
        if reply is None:
            self._replies.put_nowait(None)  # stay closed for later readers
        return reply

    async def disconnect(self) -> None:
        """The candidate hangs up: raises the event the browser transport raises."""
        await self._call_event_handler("on_client_disconnected", None)


class TextCall:
    """One text call to a claimed (in_progress) screening. See the module docstring."""

    def __init__(
        self,
        screening_id: str,
        *,
        store: ScreeningStore,
        settings: Settings,
        summarizer: Summarizer = summarize_call,
        live_calls: LiveCalls | None = None,
        knowledge: "KnowledgeBase | None" = None,
    ) -> None:
        self.screening_id = screening_id
        self._store = store
        self._settings = settings
        self._summarizer = summarizer
        self._live_calls = live_calls
        self._knowledge = knowledge
        self._transport = TextTransport()
        self._task: asyncio.Task[None] | None = None
        self.llm_errors: list[str] = []  # what the LLM service reported, oldest first
        self.quota_error: str | None = None  # the first of them that was a rate limit / quota

    def start(self) -> None:
        """Start the call in the background. Sofia speaks first: read it with `next_reply()`."""
        if self._task is not None:
            raise RuntimeError("the call was already started")
        self._task = asyncio.create_task(
            run_screening_bot(
                self._transport,
                screening_id=self.screening_id,
                store=self._store,
                settings=self._settings,
                channel=Channel.TEXT,
                summarizer=self._summarizer,
                live_calls=self._live_calls,
                on_llm_error=self._on_llm_error,
                knowledge=self._knowledge,
            ),
            name=f"text-call-{self.screening_id}",
        )
        # However the bot ends (end_call, drop, supersede, crash), readers are released.
        self._task.add_done_callback(lambda _task: self._transport.close())

    def _on_llm_error(self, error: ErrorFrame, quota: bool) -> None:
        self.llm_errors.append(error.error)
        if quota and self.quota_error is None:
            self.quota_error = error.error

    async def next_reply(self, wait_secs: float | None = None) -> str | None:
        """Sofia's next reply; None when the call has ended and there is nothing left to read.
        Raises TimeoutError after `wait_secs` seconds."""
        return await asyncio.wait_for(self._transport.next_reply(), wait_secs)

    async def send(self, text: str) -> None:
        """Send one line as a complete user turn. Send after Sofia's reply has been read:
        there is no interruption in text."""
        await self._transport.send(text)

    async def say(self, text: str, wait_secs: float | None = None) -> str | None:
        """`send` + `next_reply`."""
        await self.send(text)
        return await self.next_reply(wait_secs)

    async def drop(self) -> None:
        """The candidate hangs up: exactly what a browser disconnect does (end reason
        "hangup", pipeline cancelled), so finalize treats it as a real dropped call."""
        if self._task is None or self._task.done():
            return
        logger.info(f"[{self.screening_id}] text call dropped by the candidate")
        await self._transport.disconnect()

    @property
    def ended(self) -> bool:
        """True once the pipeline has stopped (finalize may still be running)."""
        return self._transport.closed

    @property
    def ending(self) -> bool:
        """True once Sofia said her last, fixed words (an apology): the call is about to end,
        so a line sent now would go nowhere. The reply read last was those words."""
        return self._transport.ending

    async def wait_ended(self) -> None:
        """Wait until the pipeline has stopped (Sofia ended the call, or it was dropped)."""
        await self._transport.wait_closed()

    async def wait_done(self) -> None:
        """Wait for the bot to finish, including `_finalize` (summary included)."""
        if self._task is not None:
            await asyncio.shield(self._task)

    async def end_reason(self) -> str | None:
        """Why the call ended ("end_call", "hangup", "superseded", ...); after `wait_done`."""
        card = await self._store.get_call_metrics(self.screening_id)
        return card.task.end_reason if card else None

    async def __aenter__(self) -> "TextCall":
        self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.drop()
        await self.wait_done()
