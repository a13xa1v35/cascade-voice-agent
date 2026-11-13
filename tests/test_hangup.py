"""The hang-up never cuts off a candidate who starts speaking during the goodbye, and a call
whose goodbye marker never arrives still ends. HangupController driven with fake FramePushed
events and tiny timings."""

import asyncio
from typing import Any
from unittest.mock import MagicMock

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
)
from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frame_processor import FrameDirection
from pipecat.transports.base_output import BaseOutputTransport

from hr_screener.pipeline.hangup import HangupController, HangupMarkerFrame, HangupState

GRACE = 0.05


class Rig:
    def __init__(self, **kw: Any) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.ended = 0

        async def end() -> None:
            self.ended += 1

        self.hc = HangupController(
            record=lambda t, **d: self.events.append((t, d)),
            grace_secs=GRACE,
            resume_timeout_secs=kw.pop("resume", 0.1),
            max_wait_secs=kw.pop("max_wait", 0.4),
            end=end,
            **kw,
        )
        self.out = MagicMock(spec=BaseOutputTransport)

    async def push(
        self,
        frame: Any,
        *,
        source: Any = None,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        await self.hc.on_push_frame(
            FramePushed(
                source=source or self.out,
                destination=MagicMock(),
                frame=frame,
                direction=direction,
                timestamp=0,
            )
        )

    async def goodbye_played(self) -> None:
        """What the output transport emits for a goodbye + end_call."""
        await self.push(LLMFullResponseStartFrame())
        await self.push(BotStartedSpeakingFrame())
        await self.push(HangupMarkerFrame())
        await self.push(LLMFullResponseEndFrame())
        await self.push(BotStoppedSpeakingFrame())


async def test_user_turn_during_grace_cancels_and_never_fires():
    r = Rig()
    r.hc.arm("scheduled")
    await r.goodbye_played()
    await r.hc.on_user_turn_started(None, None)
    assert r.hc.state is HangupState.SUSPENDED and not r.hc.ending
    assert r.events[-1] == ("hangup.canceled", {"phase": "grace", "outcome": "scheduled"})
    await asyncio.sleep(GRACE + 0.1)
    assert not r.hc.fired and r.ended == 0
    await r.hc.close()


async def test_marker_never_seen_fires_at_max_wait():
    r = Rig(max_wait=0.05)
    r.hc.arm("scheduled")
    await asyncio.sleep(0.15)
    assert r.hc.fired and r.ended == 1
    assert r.events[-1][1]["reason"] == "max_wait"
    assert r.events[-1][1]["since_goodbye_secs"] is None
    await r.hc.close()
