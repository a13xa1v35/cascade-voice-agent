"""Frames of our own that pass through the Pipecat pipeline."""

from collections.abc import Callable

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    DataFrame,
    Frame,
    FunctionCallsStartedFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from hr_screener.agent.prompt_text import PROMPT


class HoldingLineFrame(TTSSpeakFrame):
    """The fixed line played while a knowledge search runs ("Déjame comprobarlo"). A plain
    TTSSpeakFrame to every Pipecat service; its own type so the text channel can tell it from
    the fixed apologies, which end the call."""


class NoFollowUpFrame(DataFrame):
    """Pushed by a tool that asks for no LLM run after its result (`run_llm=False`): Sofia's turn
    ends with what she already said in the response. Voice needs nothing more (the assistant
    aggregator honours `run_llm`); the text channel uses it to deliver the reply instead of
    waiting for a response that will not come."""


# What every monitor note starts with (agent/prompt_text.py, `frustration_note_*`).
NOTE_MARKER = "[Call monitor"


def _notes() -> list[str]:
    """The note texts, whitespace-collapsed and casefolded."""
    return [
        " ".join(v.split()).casefold()
        for k, v in PROMPT.items()
        if k.startswith("frustration_note_")
    ]


def _after(held: str, note: str) -> str:
    """What follows `note` at the start of `held`: the note's words are skipped one by one, so
    the whitespace between them may differ."""
    rest = held
    for word in note.split():
        rest = rest.lstrip()[len(word) :]
    return rest


class NoteEchoGuard(FrameProcessor):
    """Right after the LLM: a reply that starts by repeating a monitor note loses the note, so
    it is never spoken, shown in the text channel or written to the transcript. The model reads
    the notes as a user message (Pipecat sends a developer message to Claude as one) and can
    echo it; the prompt forbids that, this makes it impossible.

    Only the start of a response is checked, where the echo was seen: its first text is held
    until it either cannot be the marker or the note's closing bracket arrives (a few
    characters, no audible delay). `record(type, **data)`, if set, logs each removal."""

    def __init__(self) -> None:
        super().__init__(name="NoteEchoGuard")
        self._held: str | None = None  # text held at the start of a response; None: passing
        self.record: Callable[..., None] | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM:
            if isinstance(frame, LLMFullResponseStartFrame):
                self._held = ""
            elif isinstance(frame, LLMTextFrame) and self._held is not None:
                self._held += frame.text
                await self._decide()
                return
            elif isinstance(frame, (LLMFullResponseEndFrame, FunctionCallsStartedFrame)):
                await self._release()
            elif isinstance(frame, (InterruptionFrame, CancelFrame)):
                self._held = None
        await self.push_frame(frame, direction)

    async def _decide(self) -> None:
        held = self._held or ""
        start = " ".join(held.split()).casefold()
        for note in _notes():
            if start.startswith(note):
                self._held = None
                rest = _after(held, note)
                self._dropped(held[: len(held) - len(rest)].strip())
                if rest.strip():
                    await self.push_frame(LLMTextFrame(rest.lstrip()))
                return
        if any(note.startswith(start) for note in _notes()):
            return  # could still be a note: keep holding
        if start.startswith(NOTE_MARKER.casefold()) and "]" in held:
            # The bracket echoed with other words after it: drop the bracket only.
            self._held = None
            rest = held[held.index("]") + 1 :]
            self._dropped(held[: held.index("]") + 1].strip())
            if rest.strip():
                await self.push_frame(LLMTextFrame(rest.lstrip()))
            return
        if start.startswith(NOTE_MARKER.casefold()):
            return  # the bracket is still arriving
        self._held = None
        await self.push_frame(LLMTextFrame(held))

    async def _release(self) -> None:
        """The response ended (or turned to tool calls) while text was held."""
        held, self._held = self._held, None
        if not held:
            return
        start = " ".join(held.split()).casefold()
        if start.startswith(NOTE_MARKER.casefold()) or any(n.startswith(start) for n in _notes()):
            self._dropped(held.strip())  # an unfinished note: drop it all
        else:
            await self.push_frame(LLMTextFrame(held))

    def _dropped(self, text: str) -> None:
        logger.warning(f"the model repeated a monitor note; removed: {text[:120]!r}")
        if self.record is not None:
            self.record("frustration.note_echo_removed", text=text[:200])
