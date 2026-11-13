"""Helpers shared by the tests that run the real text-channel pipeline with a scripted LLM."""

from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import (
    FunctionCallFromLLM,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import LLMService

from hr_screener.models import CallSummary, Candidate, Channel, Screening, ScreeningStatus
from hr_screener.pipeline.textcall import TextCall

S = ScreeningStatus


@dataclass
class Fail:
    """A scripted step: the request fails the way Pipecat reports a stalled LLM request
    (its non-fatal "LLM completion timeout" ErrorFrame pushed upstream): Start, the error,
    End, and no text."""

    message: str = "LLM completion timeout"
    exception: Exception | None = None


class ScriptedLLM(LLMService):
    """Answers each LLM run with the next scripted step: (text, tool calls), or a `Fail`.
    Records the messages it was given, so tests see exactly what the user aggregator
    committed."""

    def __init__(self, script: list[Any]) -> None:
        super().__init__()
        self._script = list(script)
        self.runs: list[list[Any]] = []

    async def process_frame(self, frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if not isinstance(frame, LLMContextFrame):
            await self.push_frame(frame, direction)
            return
        self.runs.append(list(frame.context.messages))
        step = self._script.pop(0)
        await self.push_frame(LLMFullResponseStartFrame())
        if isinstance(step, Fail):
            await self.push_error(step.message, exception=step.exception or TimeoutError())
            await self.push_frame(LLMFullResponseEndFrame())
            return
        text, calls = step
        if text:
            await self.push_frame(LLMTextFrame(text))
        if calls:
            await self.run_function_calls(
                [
                    FunctionCallFromLLM(
                        function_name=name,
                        tool_call_id=f"call-{len(self.runs)}-{i}",
                        arguments=args,
                        context=frame.context,
                    )
                    for i, (name, args) in enumerate(calls)
                ]
            )
        await self.push_frame(LLMFullResponseEndFrame())


async def fake_summarizer(settings, candidate, opening, screening, facts, transcript):
    return CallSummary(outcome=None, key_points=["ok"], language="en", source="fallback")


async def claimed_screening(store, opening) -> Screening:
    candidate = await store.create_candidate(
        Candidate(name="Maria Lopez", phone="+34600", location="Madrid", opening_id=opening.id)
    )
    return await store.create_screening(
        Screening(candidate_id=candidate.id, channel=Channel.TEXT, status=S.IN_PROGRESS)
    )


def new_call(store, settings, screening, **kw) -> TextCall:
    return TextCall(screening.id, store=store, settings=settings, summarizer=fake_summarizer, **kw)
