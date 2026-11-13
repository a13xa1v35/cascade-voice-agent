"""Detects a dead browser connection faster than the transport does.

SmallWebRTC reads the mic with a 2 s `recv()` timeout and only logs a warning when no audio
arrives; the media stream errors out ~30 s after the tab closed. A live WebRTC audio track
keeps delivering frames while the person is silent, so a gap in `InputAudioRawFrame`s means
the connection is gone. Browser channel only (the phone has the websocket close).

Muting: pipecat's `SmallWebRTCTrack.recv()` ignores `enabled` for audio (only video returns
None when disabled), and a muted browser track (`track.enabled = false`) keeps sending silent
frames, so a mute does not create a gap. The transport's own gap warning is nevertheless gated
on `is_enabled()`, so as a precaution the watchdog also stands down while the track reports
itself disabled (`is_muted`).
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

from loguru import logger
from pipecat.frames.frames import Frame, InputAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class AudioWatchdog(FrameProcessor):
    """Pass-through processor (put it right after `transport.input()`) that timestamps
    audio frames, plus a monitor task that calls `on_lost` once if none arrives for
    `lost_secs`."""

    def __init__(
        self,
        lost_secs: float,
        on_lost: Callable[[], Awaitable[None]],
        *,
        is_muted: Callable[[], bool] = lambda: False,
        poll_secs: float = 0.5,
    ) -> None:
        super().__init__()
        self._lost_secs = lost_secs
        self._on_lost = on_lost
        self._is_muted = is_muted
        self._poll_secs = poll_secs
        self._last_audio = time.monotonic()
        self._task: asyncio.Task[None] | None = None

    @property
    def enabled(self) -> bool:
        return self._lost_secs > 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            self.note_audio()
        await self.push_frame(frame, direction)

    def note_audio(self) -> None:
        self._last_audio = time.monotonic()

    def start(self) -> None:
        """Arm the monitor (call when the client is ready). Idempotent; no-op if disabled."""
        if not self.enabled or self._task is not None:
            return
        self._last_audio = time.monotonic()
        self._task = asyncio.create_task(self._monitor())

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _monitor(self) -> None:
        while True:
            await asyncio.sleep(self._poll_secs)
            if self._is_muted():
                self._last_audio = time.monotonic()  # count the gap from the unmute
                continue
            gap = time.monotonic() - self._last_audio
            if gap >= self._lost_secs:
                logger.warning(f"no audio from the browser for {gap:.1f}s: connection lost")
                self._task = None  # on_lost may end the call, which calls stop()
                await self._on_lost()
                return
