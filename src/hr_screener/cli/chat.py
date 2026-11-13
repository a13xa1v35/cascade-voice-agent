"""Chat with Sofia in the terminal: the real call pipeline over text.

    uv run python -m hr_screener.cli.chat [--candidate ID]        (or: make chat [ID=<candidate>])

Creates a screening the way the browser does (supersede a live call of the candidate, resume
the last one as a follow-up when it was dropped or unfinished, claim it in_progress), then
runs it as a text call (see textcall.py). Type your lines; Ctrl-D or Ctrl-C hangs up, which
finalizes the screening as a dropped call. It uses DATABASE_URL and REDIS_URL like `make dev`,
so a call started here can be resumed by a voice call and the other way round.
"""

import argparse
import asyncio
import contextlib
import signal
import sys
import threading
from collections.abc import Awaitable
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from hr_screener.config import Settings
from hr_screener.knowledge.service import open_knowledge_base
from hr_screener.models import Channel
from hr_screener.pipeline.providers import missing_keys
from hr_screener.pipeline.textcall import TextCall
from hr_screener.screening.calls import LiveCalls, start_screening
from hr_screener.screening.followup import CallMode, default_candidate, load_call_context
from hr_screener.storage.db import make_engine
from hr_screener.storage.store import ScreeningStore


class StdinLines:
    """Lines from stdin without blocking the loop. A daemon thread does the blocking read,
    so a process stuck waiting for input can still exit."""

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        for line in sys.stdin:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, line.rstrip("\n"))
        self._loop.call_soon_threadsafe(self._queue.put_nowait, None)  # EOF = Ctrl-D

    async def next(self) -> str | None:
        return await self._queue.get()


async def interruptible[T](awaitable: Awaitable[T], interrupted: asyncio.Event) -> T | None:
    """The awaitable's result, or None if Ctrl-C comes first."""
    task = asyncio.ensure_future(awaitable)
    stop = asyncio.ensure_future(interrupted.wait())
    try:
        await asyncio.wait({task, stop}, return_when=asyncio.FIRST_COMPLETED)
        return task.result() if task.done() and not interrupted.is_set() else None
    finally:
        for pending in (task, stop):
            if not pending.done():
                pending.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pending


async def next_line(lines: StdinLines, call: TextCall) -> str | None:
    """The next typed line, or None on EOF or when the call ends first."""
    ended = asyncio.ensure_future(call.wait_ended())
    line = asyncio.ensure_future(lines.next())
    try:
        await asyncio.wait({ended, line}, return_when=asyncio.FIRST_COMPLETED)
        return None if ended.done() else line.result()
    finally:
        for pending in (ended, line):
            if not pending.done():
                pending.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pending


async def pick_candidate(store: ScreeningStore, settings: Settings, candidate_id: str | None):
    """An explicit id must exist (None if not); otherwise the shared default."""
    if candidate_id:
        return await store.get_candidate(candidate_id)
    return await default_candidate(store, settings)


async def print_result(store: ScreeningStore, call: TextCall) -> None:
    screening = await store.get_screening(call.screening_id)
    if screening is None:
        return
    facts = await store.get_facts(screening.id)
    print("\n--- call result ---")
    print(f"screening: {screening.id}")
    print(f"attempt:   {screening.attempt}")
    print(f"status:    {screening.status.value}")
    print(f"outcome:   {screening.outcome.value if screening.outcome else '-'}")
    print(f"ended by:  {await call.end_reason() or '-'}")
    print("facts:")
    for name, value in facts.model_dump(mode="json").items():
        print(f"  {name}: {value if value not in (None, []) else '-'}")


async def chat(candidate_id: str | None) -> int:
    settings = Settings()
    if problems := missing_keys(settings, text_only=True):
        print(f"missing settings: {', '.join(problems)} (set them in .env)", file=sys.stderr)
        return 1
    logger.remove()
    logger.add(sys.stderr, level="WARNING")  # the per-call log file keeps the details

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    engine = make_engine(settings.database_url)
    # Same as the server: sync KB_DIR (when configured to) and never fail the chat; without a
    # usable knowledge base the search tool reports kb_unavailable.
    knowledge = await open_knowledge_base(settings, redis=redis)
    try:
        store = ScreeningStore(engine, redis)
        candidate = await pick_candidate(store, settings, candidate_id)
        if candidate is None:
            print("no candidate to call: run `make seed` first", file=sys.stderr)
            return 1
        live_calls = LiveCalls()
        screening = await start_screening(
            store,
            live_calls,
            candidate,
            channel=Channel.TEXT,
            timezone=settings.timezone,
            supersede_wait_secs=settings.supersede_wait_secs,
        )
        mode = (await load_call_context(store, screening)).mode
        kind = {
            CallMode.FRESH: "new call",
            CallMode.FOLLOWUP: f"follow-up, attempt {screening.attempt}",
        }.get(mode, f"already decided ({mode.value}), no screening")
        print(f"Calling {candidate.name} ({kind}, screening {screening.id}).")
        print("Type your lines. Ctrl-D or Ctrl-C hangs up.\n")

        interrupted = asyncio.Event()
        asyncio.get_running_loop().add_signal_handler(signal.SIGINT, interrupted.set)
        lines = StdinLines()
        call = TextCall(
            screening.id,
            store=store,
            settings=settings,
            live_calls=live_calls,
            knowledge=knowledge,
        )
        call.start()
        while True:
            reply = await interruptible(call.next_reply(), interrupted)
            if reply is None:
                break  # Sofia ended the call, it failed, or Ctrl-C
            print(f"Sofia: {reply}\n")
            line = await interruptible(next_line(lines, call), interrupted)
            if line is None:
                break  # Sofia ended the call, EOF, or Ctrl-C
            if not sys.stdin.isatty():
                print(f"You:  {line}\n")  # piped input is not echoed by a terminal
            await call.send(line)
        if not call.ended and not interrupted.is_set():
            # EOF right after Sofia's goodbye (piped input) beats the pipeline shutting down
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(call.wait_ended(), 1.0)
        if not call.ended:
            print("(you hung up)")
            await call.drop()
        else:
            print("(Sofia ended the call)")
        await call.wait_done()
        await print_result(store, call)
        return 0
    finally:
        await knowledge.close()
        await engine.dispose()
        await redis.aclose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--candidate", help="candidate id (default: DEMO_CANDIDATE_ID, else the latest candidate)"
    )
    args: Any = parser.parse_args(argv)
    sys.exit(asyncio.run(chat(args.candidate)))


if __name__ == "__main__":
    main()
