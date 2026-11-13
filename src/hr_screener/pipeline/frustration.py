"""In-call frustration check: telemetry, and optionally a short note to Sofia.

After each candidate turn the monitor asks the Cloudflare Workers AI decision model (the one the
turn-taking design uses, `clef-flash`) one yes/no question: is the candidate frustrated or
annoyed with the call or the assistant? The answer is recorded as a `frustration.judgment` event
and summarized in the scorecard. With `FRUSTRATION_NOTES_ENABLED` (off by default) a small state
machine over the judgments can also tell Sofia, see "Notes" below; with it off nothing is sent
and the conversation does not change.

- Trigger: the user aggregator's `on_user_turn_stopped` event. The request runs as a background
  task, so it never delays the turn, and no failure reaches the pipeline: every error becomes an
  `outcome` on the event.
- Gap: at most one request in flight, and at least `min_gap_secs` between the starts of two
  requests. A turn that ends inside the gap, or while a request is in flight, is not dropped:
  the newest such turn is judged as soon as the gap is over (older ones are still in its
  window), so the candidate's last words before hanging up are judged too.
- Window: the model sees the last `WINDOW_TURNS` turns (candidate and assistant) plus the
  candidate's latest turn, and how many times the candidate has interrupted so far.
- Notes: a note is pushed only on a change of state, at most once per level and per call (see
  the constants below; errors and timeouts are not judgments and do not enter the
  window). It is a `developer` message appended to the context through the worker's
  `queue_frames` (`bind`), with no LLM run: Sofia reads it on her next reply, so she reacts one
  turn late. The background task never writes to the context itself. Her rules for the note are
  in the system prompt (`agent/templates/_shared.j2`, only when notes are on for the call).
- Ignored attempts: the turn-taking controller records `frustration.ignored_attempts` (count) when
  the candidate's held speech was dropped several times during one agent turn. The monitor reads
  those events from the call's event list when a candidate turn stops, before judging it, and
  feeds each one to the state machine as a hit (a judgment at `NOTE_PROBABILITY`); no request,
  no extra event.
- Lifecycle: `stop()` cancels the request in flight and closes the classifier. The call runs it
  before the scorecard is computed from the recorder's list, so no judgment or note lands
  after it.

The classifier is its own `HedgedClassifier`, not the turn-taking one: the turn controller logs
`classifier.last_call` into its judgment events.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from loguru import logger
from pipecat.classifiers.base_classifier import BaseClassifier, YesNoQuestion
from pipecat.frames.frames import Frame, LLMMessagesAppendFrame
from pipecat.processors.aggregators.llm_context import LLMContext

from hr_screener.agent.prompt_text import PROMPT
from hr_screener.config import Settings
from hr_screener.turn_taking.design import SYSTEM_ONE_DESIGN, make_system_one_classifier

Record = Callable[..., None]
Events = Callable[[], Sequence[Mapping[str, Any]]]
Sender = Callable[[list[Frame]], Awaitable[None]]  # the worker's `queue_frames`

WINDOW_TURNS = 6  # recent turns sent with the candidate's latest turn
TURN_CHARS = 300  # each turn is cut to its last this many characters
REQUEST_TIMEOUT_SECS = 5.0  # abandoned after this; shorter than the default gap
QUESTION_KEY = "frustrated"

# Notes to Sofia (only when `frustration_notes_enabled`). Each level is sent at most once per call.
# Calibrated on the m1 / m2 evals (clef-flash scores conservatively): a calm, curt candidate
# scored 0.02-0.06 on every turn, an impatient one mostly 0.1-0.3 with peaks of 0.5-0.7.
# Single scores jump from turn to turn, so the rule counts hits in a window, not a streak.
NOTE_PROBABILITY = 0.25  # a judgment at or above this is a hit
NOTE_WINDOW = 3  # level 1 ("frustrated"): NOTE_HITS hits among the last NOTE_WINDOW judgments
NOTE_HITS = 2
NOTE_SINGLE_PROBABILITY = 0.5  # a single judgment at or above this is enough for level 1
NOTE_HITS_STILL = 3  # level 2 ("still frustrated"): this many further hits after level 1
# Candidate speech dropped or ignored while Sofia talked is a hit too (no classifier): the turn-
# taking controller records `frustration.ignored_attempts` every IGNORED_ATTEMPTS_HIT such drops in
# one agent turn (turn_taking/controller.py), and the monitor counts each event as a judgment at
# NOTE_PROBABILITY. A single hit never sends a note by itself.
IGNORED_EVENT = "frustration.ignored_attempts"

# Model-facing text, English for every call like the prompt and the turn-taking questions.
QUESTION_TEXT = (
    "A tutor candidate is on a screening call with a voice assistant (the words come from speech "
    "recognition). Judge the candidate's latest turn (candidate_latest_turn) in the light of "
    "recent_turns. Is the candidate frustrated or annoyed with the call or with the assistant? "
    "Signs: repeating or correcting something they already said ('I already told you'), "
    "complaining about being asked the same thing again, sarcasm, curt or irritated replies, "
    "complaints that the assistant does not understand or interrupts, asking to stop or to speak "
    "to a person, or many interruptions (candidate_interruptions_so_far). Brief or neutral "
    "answers, hesitation, an ordinary correction or a request to repeat are not frustration."
)
QUESTION_SHA = hashlib.sha256(QUESTION_TEXT.encode()).hexdigest()[:10]


def _turns(context: LLMContext) -> list[dict[str, str]]:
    """User and assistant messages of the context that have text, oldest first."""
    turns: list[dict[str, str]] = []
    for m in context.messages:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        content = m.get("content")
        if isinstance(content, list):
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        if isinstance(content, str) and content.strip():
            turns.append({"role": m["role"], "text": content.strip()[-TURN_CHARS:]})
    return turns


class FrustrationMonitor:
    def __init__(
        self,
        *,
        classifier: BaseClassifier,
        context: LLMContext,
        record: Record,
        events: Events,
        min_gap_secs: float,
        notes_enabled: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._classifier = classifier
        self._context = context
        self._record = record
        self._events = events
        self.min_gap_secs = min_gap_secs
        self._clock = clock
        self._question = {QUESTION_KEY: YesNoQuestion(instructions=QUESTION_TEXT)}
        self._last_start: float | None = None
        self._task: asyncio.Task[None] | None = None  # the check loop (kept referenced)
        self._pending: str | None = None  # the newest candidate turn not judged yet
        self._stopped = False
        self.notes_enabled = notes_enabled
        self._send: Sender | None = None  # bound once the worker exists
        self._level = 0  # the highest note level sent so far (0: none)
        self._recent: deque[bool] = deque(maxlen=NOTE_WINDOW)  # hits of the last judgments
        self._hits_since_note = 0  # hits since the last note
        self._ignored_seen = 0  # frustration.ignored_attempts events already counted

    def bind(self, send: Sender) -> None:
        """Where notes go: the worker's `queue_frames`. Without it no note is sent."""
        self._send = send

    def record_config(self) -> None:
        self._record(
            "frustration.config",
            question_sha=QUESTION_SHA,
            min_gap_secs=self.min_gap_secs,
            window_turns=WINDOW_TURNS,
            notes_enabled=self.notes_enabled,
        )

    async def on_user_turn_stopped(self, _aggregator: Any, _strategy: Any, message: Any) -> None:
        """Handler for the user aggregator's `on_user_turn_stopped`. It only notes the turn and
        starts the background loop if it is not running; it never waits for a request."""
        try:
            latest = (getattr(message, "content", None) or "").strip()
            if self._stopped or not latest:
                return
            self._pending = latest
            await self._count_ignored_attempts()
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._run())
        except Exception:
            logger.exception("frustration check could not start")

    async def _run(self) -> None:
        """Judge the newest pending turn, waiting out the gap first; repeat while turns keep
        arriving."""
        while self._pending is not None and not self._stopped:
            if self._last_start is not None:
                wait = self.min_gap_secs - (self._clock() - self._last_start)
                if wait > 0:
                    await asyncio.sleep(wait)
            latest, self._pending = self._pending, None
            if latest is None:
                return
            self._last_start = self._clock()
            try:
                state = self._state(latest)
            except Exception:
                logger.exception("frustration check state could not be built")
                continue
            await self._judge(state, latest)

    def _state(self, latest: str) -> dict[str, Any]:
        turns = _turns(self._context)
        # The aggregator may already have written the latest turn to the context: it is sent
        # once, as its own field.
        if turns and turns[-1]["role"] == "user" and latest.endswith(turns[-1]["text"]):
            turns.pop()
        interruptions = sum(1 for e in self._events() if e.get("type") == "interruption")
        return {
            "recent_turns": turns[-WINDOW_TURNS:],
            "candidate_latest_turn": latest[-600:],
            "candidate_interruptions_so_far": interruptions,
        }

    async def _judge(self, state: dict[str, Any], latest: str) -> None:
        started = time.perf_counter()
        probability: float | None = None
        outcome = "ok"
        try:
            res = await asyncio.wait_for(
                self._classifier.yes_no(state, self._question), timeout=REQUEST_TIMEOUT_SECS
            )
            probability = round(res[QUESTION_KEY].probability, 3)
        except asyncio.CancelledError:
            raise  # stop(): the call is over, nothing is recorded
        except TimeoutError:
            outcome = "timeout"
        except Exception as e:  # ClassifierError, anything from the client
            outcome = f"error: {e!r}"[:300]
        latency_ms = round((time.perf_counter() - started) * 1000)
        try:
            self._record(
                "frustration.judgment",
                probability=probability,
                latency_ms=latency_ms,
                outcome=outcome,
                turns_judged=len(state["recent_turns"]) + 1,
                candidate_turn=latest,
            )
        except Exception:
            logger.exception("frustration judgment could not be recorded")
        if probability is not None and self.notes_enabled:
            await self._maybe_note(probability)

    async def _count_ignored_attempts(self) -> None:
        """Count the `frustration.ignored_attempts` events recorded since the last call as hits."""
        if not self.notes_enabled:
            return
        total = sum(1 for e in self._events() if e.get("type") == IGNORED_EVENT)
        new, self._ignored_seen = total - self._ignored_seen, total
        for _ in range(max(new, 0)):
            await self._maybe_note(NOTE_PROBABILITY)

    def _next_level(self, probability: float) -> int | None:
        """Advance the state machine with one ok judgment; the level to announce, or None."""
        hit = probability >= NOTE_PROBABILITY
        self._recent.append(hit)
        self._hits_since_note += hit
        if self._level == 0 and (
            sum(self._recent) >= NOTE_HITS or probability >= NOTE_SINGLE_PROBABILITY
        ):
            return 1
        if self._level == 1 and self._hits_since_note >= NOTE_HITS_STILL:
            return 2
        return None

    async def _maybe_note(self, probability: float) -> None:
        """Send the note this judgment calls for, if any. Never raises."""
        try:
            level = self._next_level(probability)
            if level is None or self._stopped or self._send is None:
                return
            self._level, self._hits_since_note = level, 0
            frame = LLMMessagesAppendFrame(
                messages=[{"role": "developer", "content": PROMPT[f"frustration_note_{level}"]}],
                run_llm=False,
            )
            await self._send([frame])
            if not self._stopped:
                self._record("frustration.note", level=level, probability=probability)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("frustration note could not be sent")

    async def stop(self) -> None:
        """Cancel the request in flight and close the classifier. After this nothing is
        recorded; the call runs it before the scorecard is computed."""
        self._stopped = True
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        try:
            await self._classifier.cleanup()
        except Exception:
            logger.exception("frustration classifier cleanup failed")


def check_available(settings: Settings) -> bool:
    """The check runs: switched on and Cloudflare configured (the text channel then runs with
    only the Anthropic key without it)."""
    return bool(
        settings.frustration_check_enabled
        and settings.cloudflare_account_id
        and settings.cloudflare_api_token
    )


def notes_available(settings: Settings) -> bool:
    """Notes are on for a call: the setting is on and the monitor can exist. The system prompt
    and the monitor both take this value, so Sofia is told the rules exactly when notes can
    arrive."""
    return settings.frustration_notes_enabled and check_available(settings)


def make_frustration_monitor(
    settings: Settings, context: LLMContext, record: Record, events: Events
) -> FrustrationMonitor | None:
    """The monitor, or None when the check is switched off or Cloudflare is not configured."""
    if not check_available(settings):
        return None
    return FrustrationMonitor(
        classifier=make_system_one_classifier(settings, SYSTEM_ONE_DESIGN),
        context=context,
        record=record,
        events=events,
        min_gap_secs=settings.frustration_min_gap_secs,
        notes_enabled=notes_available(settings),
    )
