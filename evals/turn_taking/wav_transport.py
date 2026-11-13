"""A pipecat transport that plays one wav file in as the "caller" and records the bot's
audio onto a time-aligned timeline (Full-Duplex-Bench needs output.wav to line up with
input.wav sample for sample).

Pure helpers (resampling, mu-law, `OutputTimeline`) are separate from the pipecat glue
(`WavTransport`) so they can be unit-tested without a pipeline.
"""

from __future__ import annotations

import asyncio
import wave
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr
from pipecat.audio.resamplers.soxr_resampler import SOXRAudioResampler
from pipecat.audio.utils import pcm_to_ulaw, ulaw_to_pcm
from pipecat.frames.frames import Frame, InputAudioRawFrame, InterruptionFrame, OutputAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams

FDB_RATE = 16000  # FDB wavs and the output.wav the evaluators read
CHUNK_SECS = 0.02  # input is pushed in 20 ms frames, like a phone/WebRTC stream


# --- Pure audio helpers --------------------------------------------------------------------


def resample_pcm16(pcm: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Resample mono int16 audio (stateless; fine for the 20-40 ms chunks used here)."""
    if src == dst or len(pcm) == 0:
        return pcm.astype(np.int16, copy=False)
    out = soxr.resample(pcm.astype(np.float32) / 32768.0, src, dst, quality="HQ")
    return np.clip(np.rint(out * 32768.0), -32768, 32767).astype(np.int16)


async def mulaw_roundtrip(pcm: np.ndarray, rate: int = 8000) -> np.ndarray:
    """Encode to G.711 mu-law and back, the quantization a Twilio stream applies."""
    resampler = SOXRAudioResampler()
    ulaw = await pcm_to_ulaw(pcm.astype(np.int16).tobytes(), rate, rate, resampler)
    back = await ulaw_to_pcm(ulaw, rate, rate, resampler)
    return np.frombuffer(back, dtype=np.int16)


def read_wav_mono16(path: Path) -> tuple[np.ndarray, int]:
    # Read as float and scale ourselves: libsndfile does NOT rescale float WAVs when asked
    # for int16 (values in [-1, 1] truncate to 0/±1, i.e. silence). Some FDB v1 subsets
    # (candor_turn_taking, synthetic_pause_handling) ship 32-bit float WAVs.
    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    return np.clip(np.rint(mono * 32768.0), -32768, 32767).astype(np.int16), rate


def wav_duration_secs(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate


async def prepare_input(
    path: Path, *, in_rate: int, telephony: bool, trailing_silence_secs: float
) -> tuple[np.ndarray, int]:
    """Load a wav and return (samples at in_rate incl. trailing silence, original sample count
    at 16 kHz). Telephony adds the mu-law round-trip."""
    pcm, rate = read_wav_mono16(path)
    orig_16k = round(len(pcm) * FDB_RATE / rate)
    pcm = resample_pcm16(pcm, rate, in_rate)
    if telephony:
        pcm = await mulaw_roundtrip(pcm, in_rate)
    silence = np.zeros(round(trailing_silence_secs * in_rate), dtype=np.int16)
    return np.concatenate([pcm, silence]), orig_16k


def write_wav16k(path: Path, pcm: np.ndarray) -> None:
    """Mono 16-bit PCM 16 kHz, written atomically (never through a symlink)."""
    tmp = path.with_name(path.name + ".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FDB_RATE)
        w.writeframes(pcm.astype(np.int16).tobytes())
    tmp.replace(path)


class OutputTimeline:
    """Silence-initialized 16 kHz buffer; bot chunks are placed at the offset they were
    "played" (seconds since input started). Pure: no clocks, no pipecat."""

    def __init__(self, total_samples: int, rate: int = FDB_RATE) -> None:
        self.rate = rate
        self.total = total_samples
        self.buf = np.zeros(total_samples, dtype=np.int16)
        self.cursor = 0.0  # seconds: end of the last placed chunk

    def place_chunk(self, now_secs: float, pcm: np.ndarray) -> tuple[float, float]:
        """Place a chunk at max(cursor, now) so chunks never overlap; returns (start, end)
        in seconds. Samples past the buffer end are dropped (truncation)."""
        start = max(self.cursor, now_secs)
        end = start + len(pcm) / self.rate
        i = round(start * self.rate)
        j = min(i + len(pcm), self.total)
        if j > i:
            self.buf[i:j] = pcm[: j - i]
        self.cursor = end
        return start, end

    def cut(self, at_secs: float) -> None:
        """Playback stopped at `at_secs` (interruption): erase anything scheduled later."""
        i = max(0, min(round(at_secs * self.rate), self.total))
        j = min(round(self.cursor * self.rate), self.total)
        if j > i:
            self.buf[i:j] = 0
        self.cursor = min(self.cursor, at_secs)

    def speech_secs(self, threshold: int = 500, win: int = 320) -> float:
        """Rough amount of non-silent audio (for diagnostics)."""
        n = len(self.buf) // win
        if n == 0:
            return 0.0
        rms = np.sqrt((self.buf[: n * win].reshape(n, win).astype(np.float64) ** 2).mean(axis=1))
        return float((rms > threshold).sum() * win / self.rate)


# --- pipecat glue --------------------------------------------------------------------------


class SessionClock:
    """t0 = wall-clock time of the first input chunk. now() = seconds since t0."""

    def __init__(self) -> None:
        self.t0: float | None = None

    def start(self) -> None:
        self.t0 = asyncio.get_running_loop().time()

    def now(self) -> float:
        if self.t0 is None:
            return 0.0
        return asyncio.get_running_loop().time() - self.t0


class _WavInput(BaseInputTransport):
    def __init__(self, params: TransportParams, owner: WavTransport, **kwargs):
        super().__init__(params, **kwargs)
        self._owner = owner
        self._feeder: asyncio.Task | None = None

    async def start(self, frame):
        await super().start(frame)
        await self.set_transport_ready(frame)
        self._feeder = self.create_task(self._feed())

    async def cleanup(self):
        if self._feeder:
            await self.cancel_task(self._feeder)
            self._feeder = None
        await super().cleanup()

    async def _feed(self) -> None:
        o = self._owner
        loop = asyncio.get_running_loop()
        await asyncio.sleep(o.warmup_secs)  # let STT/LLM/TTS connections come up first
        o.clock.start()
        t_start = loop.time()
        step = round(CHUNK_SECS * o.in_rate)
        for k, i in enumerate(range(0, len(o.samples), step)):
            # Absolute deadlines: a slow iteration is caught up, never accumulated as drift.
            await asyncio.sleep(max(0.0, t_start + k * CHUNK_SECS - loop.time()))
            audio = o.samples[i : i + step].tobytes()
            await self.push_audio_frame(
                InputAudioRawFrame(audio=audio, sample_rate=o.in_rate, num_channels=1)
            )
        await asyncio.sleep(max(0.0, t_start + len(o.samples) / o.in_rate - loop.time()))
        o.input_done.set()


class _WavOutput(BaseOutputTransport):
    def __init__(self, params: TransportParams, owner: WavTransport, **kwargs):
        super().__init__(params, **kwargs)
        self._owner = owner

    async def start(self, frame):
        await super().start(frame)
        await self.set_transport_ready(frame)  # creates the MediaSender that plays/paces audio

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, InterruptionFrame):
            # The bot's speaker stops now; the base class drops what is still queued.
            self._owner.timeline.cut(self._owner.clock.now())
        await super().process_frame(frame, direction)

    async def write_audio_frame(self, frame: OutputAudioRawFrame) -> bool:
        """Block for (almost) the chunk's playback time, like a real speaker, and place the
        chunk on the timeline. Returning half a chunk early keeps the next write ahead of
        the cursor so consecutive chunks stay contiguous."""
        o = self._owner
        loop = asyncio.get_running_loop()
        pcm = np.frombuffer(frame.audio, dtype=np.int16)
        pcm16 = resample_pcm16(pcm, frame.sample_rate, FDB_RATE)
        start, end = o.timeline.place_chunk(o.clock.now(), pcm16)
        dur = end - start
        wake = (o.clock.t0 + end - dur / 2) if o.clock.t0 is not None else loop.time() + dur / 2
        try:
            await asyncio.sleep(max(0.0, wake - loop.time()))
        except asyncio.CancelledError:
            o.timeline.cut(o.clock.now())  # interrupted mid-chunk: the rest never played
            raise
        return True


class WavTransport(BaseTransport):
    """One file session. `samples` are int16 at `in_rate` (already includes trailing
    silence); `out_samples` is the exact length of the resulting 16 kHz output."""

    def __init__(
        self,
        samples: np.ndarray,
        *,
        in_rate: int,
        out_samples: int,
        warmup_secs: float = 1.0,
    ) -> None:
        super().__init__()
        self.samples = samples
        self.in_rate = in_rate
        self.warmup_secs = warmup_secs
        self.clock = SessionClock()
        self.timeline = OutputTimeline(out_samples)
        self.input_done = asyncio.Event()
        params = TransportParams(
            audio_in_enabled=True, audio_out_enabled=True, audio_out_end_silence_secs=0
        )
        self._input = _WavInput(params, self)
        self._output = _WavOutput(params, self)

    def input(self) -> BaseInputTransport:
        return self._input

    def output(self) -> BaseOutputTransport:
        return self._output
