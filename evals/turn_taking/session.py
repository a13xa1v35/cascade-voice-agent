"""One file session: play input wav into a pipeline, record the time-aligned output."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from pipecat.pipeline.worker import PipelineWorker
from pipecat.workers.runner import WorkerRunner

from evals.turn_taking.agent import BenchAgent
from evals.turn_taking.events import EventLog
from evals.turn_taking.variants import VariantBuilder
from evals.turn_taking.wav_transport import WavTransport, prepare_input, write_wav16k
from hr_screener.config import Settings


class SessionUnhealthy(RuntimeError):
    """A service reported an error or reconnected: the recorded audio is not a valid sample."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems
        self.rate_limited = any(is_rate_limit(p) for p in problems)


def is_rate_limit(message: str) -> bool:
    return "rate_limited" in message or "3009" in message or "1008" in message


def failed_wav_path(output_wav: Path) -> Path:
    return output_wav.with_name(output_wav.stem + ".failed.wav")


async def _no_wait() -> None:
    return None


async def run_session(
    *,
    builder: VariantBuilder,
    settings: Settings,
    agent: BenchAgent,
    telephony: bool,
    input_wav: Path,
    output_wav: Path,
    events_path: Path,
    trailing_silence_secs: float,
    warmup_secs: float = 1.0,
    before_start: Callable[[], Awaitable[None]] = _no_wait,
    variant_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    in_rate = 8000 if telephony else 16000
    samples, out_samples = await prepare_input(
        input_wav, in_rate=in_rate, telephony=telephony, trailing_silence_secs=trailing_silence_secs
    )
    transport = WavTransport(
        samples, in_rate=in_rate, out_samples=out_samples, warmup_secs=warmup_secs
    )
    log = EventLog(transport.clock)
    built = builder(transport, settings, agent, telephony, log, variant_params)
    log.attach_aggregators(built.user_agg, built.assistant_agg)
    log.watch_services(list(built.pipeline.processors))
    worker = PipelineWorker(built.pipeline, params=built.params, observers=[log])
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    await before_start()  # throttle: STT and TTS open their sessions when the pipeline starts
    run_task = asyncio.create_task(runner.run())
    done_task = asyncio.create_task(transport.input_done.wait())
    bad_task = asyncio.create_task(log.unhealthy.wait())
    try:
        await asyncio.wait({run_task, done_task, bad_task}, return_when=asyncio.FIRST_COMPLETED)
        log.closing = True
        if not log.problems and not transport.input_done.is_set():
            if run_task.done() and run_task.exception():
                raise RuntimeError("pipeline crashed") from run_task.exception()
            raise RuntimeError("pipeline ended before the input finished playing")
        if run_task.done() and run_task.exception() and not log.problems:
            raise RuntimeError("pipeline crashed") from run_task.exception()
        if not run_task.done():
            await runner.cancel()
            await asyncio.wait_for(run_task, timeout=30)
    finally:
        done_task.cancel()
        bad_task.cancel()
        if not run_task.done():
            run_task.cancel()
        log.write(events_path)

    if log.problems:
        # Keep the audio for debugging, but never as a valid output (skip_existing retries it).
        write_wav16k(failed_wav_path(output_wav), transport.timeline.buf)
        raise SessionUnhealthy(log.problems)
    failed_wav_path(output_wav).unlink(missing_ok=True)
    write_wav16k(output_wav, transport.timeline.buf)
    return {
        "input_secs": out_samples / 16000,
        "speech_secs": transport.timeline.speech_secs(),
        "events": len(log.events),
    }
