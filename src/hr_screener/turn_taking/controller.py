"""Pipecat glue for the Jev VAD design: sits between STT and the user aggregator.

How it fits pipecat 1.15 (verified in the source):
- VAD runs once, in the user aggregator (`LLMUserAggregatorParams.vad_analyzer`). Its
  `VADUserStarted/StoppedSpeakingFrame` are broadcast both ways, so this processor, which is
  upstream of the aggregator, receives the UPSTREAM copies: same Silero params as the baseline.
- The aggregator uses `ExternalUserTurnStrategies`. This controller announces turns itself on
  the "adopt" path: it broadcasts `UserStartedSpeakingFrame` / `UserStoppedSpeakingFrame` and,
  to interrupt, `broadcast_interruption()`. The adopt path never interrupts by itself.
- Bot state comes from the UPSTREAM copies of `BotStarted/StoppedSpeakingFrame`.
- Transcripts are withheld: every final `TranscriptionFrame` is kept here and only pushed to the
  aggregator right before the stop frame of a turn that is really ending; interims are consumed
  here. Dropped speech therefore never reaches the aggregator (which would otherwise append it
  to the next turn) or the LLM.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pipecat.classifiers.base_classifier import BaseClassifier, YesNoQuestion
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    EndFrame,
    Frame,
    FunctionCallInProgressFrame,
    FunctionCallResultFrame,
    InterimTranscriptionFrame,
    LLMContextUserTurnFrame,
    LLMRunFrame,
    StartFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.utils.time import time_now_iso8601

from hr_screener.turn_taking.policy import (
    SYSTEM_ONE_QUESTIONS,
    TRAILING_CLOSERS,
    Action,
    Decision,
    DroppedSpeech,
    Inputs,
    Scores,
    TurnPolicy,
    build_state,
    is_name_call,
    is_stop_request,
    mentions_name,
    name_forms,
)

EventSink = Callable[..., None]
SETTLE_SECS = 0.03  # let data frames land before the system frame that follows them
IN_FLIGHT_MAX_SECS = 10.0  # an unanswered "response in flight" is forgotten after this
# A response armed by a turn end must be confirmed (the aggregator wrote the user message to the
# context and broadcast it) within this long, or it is not in flight after all.
IN_FLIGHT_CONFIRM_SECS = 2.0
# Words arriving this long after the VAD stop were not covered by that speech: VAD missed them.
WORDS_AFTER_VAD_GRACE_SECS = 1.5
REASK_MARKS = (1.5, 3.0)  # re-ask during silence at these mic-silence offsets
# A hold check-in (Knobs.hold_checkin_secs) also waits for the caller to be quiet this long, so
# Sofia does not talk over them while they talk to someone else or read something out.
HOLD_CHECKIN_QUIET_SECS = 3.0
# Candidate speech dropped or ignored this many times during one agent turn is one frustration
# hit (`frustration.ignored_attempts`, read by the FrustrationMonitor). Calibration: the live call
# 17a8d16dcad3 had six drops in a 32 s answer; routine backchannels ("ajá") do drop too, but one
# hit alone never sends a note (it needs a second hit in the window), and 2 would count a single
# "Vale" + "Sí" pair.
IGNORED_ATTEMPTS_HIT = 3


def _scores_dict(scores: Scores | None) -> dict[str, float] | None:
    if scores is None:
        return None
    return {k: v for k, v in scores.__dict__.items() if v is not None}


class SystemOneTurnController(FrameProcessor):
    def __init__(
        self,
        *,
        context: LLMContext,
        classifier: BaseClassifier,
        policy: TurnPolicy,
        events: EventSink,
        questions: Mapping[str, YesNoQuestion] = SYSTEM_ONE_QUESTIONS,
        stop_phrases: Sequence[str] = (),
        stop_phrases_exact: Sequence[str] = (),
        stop_phrases_source: Callable[[], tuple[Sequence[str], Sequence[str]]] | None = None,
        fillers: Sequence[str] = (),
        fillers_source: Callable[[], Sequence[str]] | None = None,
        classification_timeout: float = 1.0,
        debounce_secs: float = 0.15,
        agent_name: str | None = None,
        hold_checkin_messages: Sequence[str] = (),
        tick_secs: float = 0.05,
        clock: Callable[[], float] = time.monotonic,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._context = context
        self._classifier = classifier
        self._policy = policy
        self._log = events
        self._questions = questions
        self._stop_phrases = tuple(stop_phrases)
        self._stop_phrases_exact = tuple(stop_phrases_exact)
        # Read at every turn instead of the fixed tuples: the call language can change.
        self._stop_phrases_source = stop_phrases_source
        self._fillers = tuple(fillers)
        self._fillers_source = fillers_source
        self._agent_name = agent_name
        self._name_forms = name_forms(agent_name) if agent_name else frozenset()
        # Developer messages for the check-ins after a request for time, in order (none: off).
        self._checkin_messages = tuple(hold_checkin_messages)
        self._hold_since: float | None = None  # a turn asking for time ended at this moment
        self._checkins = 0  # check-ins made since then
        self._bot_stopped_at: float | None = None  # when the agent's last speech ended
        self._ignored = 0  # held speech dropped during the current agent turn
        self._turn_ended_at: float | None = None  # when this controller last ended a user turn
        self._onset_at: float | None = None  # when the user last started speaking (VAD)
        self._protected = False  # the open turn is a continuation: never dropped
        self._timeout = classification_timeout
        self._low_addressed = 0  # consecutive judgments with addressed < threshold
        self._debounce = debounce_secs
        self._tick_secs = tick_secs
        self._clock = clock

        self._vad_speaking = False
        self._quiet_since: float | None = None
        self._bot_speaking = False
        self._awaiting_since: float | None = None  # a turn ended; response not yet speaking
        self._awaiting_confirmed = False  # the aggregator confirmed it wrote the user message
        self._words_at: float | None = None  # last words heard that VAD did not cover
        self._turn_open = False
        # The agent's last audio was cut off by our interruption (until it speaks again).
        self._agent_cut_off = False
        # A tool result asked for a follow-up while a user turn was open: pipecat's assistant
        # aggregator owes that LLM run until the user turn ends, and an end with no text brings
        # none (verified in pipecat 1.15), so we release it ourselves.
        self._run_owed = False
        self._calls_in_progress: dict[str, str | None] = {}  # tool_call_id -> group_id

        self._finals: list[TranscriptionFrame] = []
        self._partial = ""
        self._dropped = DroppedSpeech()
        self._version = 0  # bumps when the transcript text changes
        self._last_change = 0.0
        self._judged_version = -1
        self._judged_text = ""
        self._scores: Scores | None = None
        self._failed_version = -1
        self._marks_asked: set[float] = set()
        self._call: asyncio.Task | None = None
        self._ticker: asyncio.Task | None = None
        self._busy_lock = asyncio.Lock()

    # --- state ---------------------------------------------------------------------------

    @property
    def agent_busy(self) -> bool:
        if self._bot_speaking:
            return True
        if self._awaiting_since is not None:
            age = self._clock() - self._awaiting_since
            limit = IN_FLIGHT_MAX_SECS if self._awaiting_confirmed else IN_FLIGHT_CONFIRM_SECS
            if age < limit:
                return True
            self._awaiting_since = None
        return False

    def _since_turn_end(self) -> float | None:
        """Seconds from the controller ending a turn to the user starting to speak again.

        Measured at speech onset, not when the words arrive: STT's first partial lags the onset
        by about 0.5 s, and a continuation that started inside the window must still count."""
        if self._turn_ended_at is None:
            return None
        started = self._onset_at
        if started is None or started < self._turn_ended_at:
            started = self._clock()  # no onset since the turn ended yet
        return started - self._turn_ended_at

    def _silence(self) -> float:
        """Seconds since the user last made a sound: the later of the VAD stop and the last words
        VAD did not cover (STT heard them, VAD missed them), so a stale VAD stop never makes a
        user who is still talking look quiet."""
        if self._vad_speaking:
            return 0.0
        marks = [t for t in (self._quiet_since, self._words_at) if t is not None]
        if not marks:
            return 0.0
        return max(0.0, self._clock() - max(marks))

    def _note_words(self) -> None:
        """New words arrived. If VAD is not speaking and its last stop does not explain them,
        restart the silence clock from now."""
        now = self._clock()
        if self._vad_speaking:
            return
        if self._quiet_since is None or now - self._quiet_since > WORDS_AFTER_VAD_GRACE_SECS:
            self._words_at = now
            self._marks_asked.clear()

    def _current_stop_phrases(self) -> tuple[Sequence[str], Sequence[str]]:
        if self._stop_phrases_source is not None:
            return self._stop_phrases_source()
        return self._stop_phrases, self._stop_phrases_exact

    def _current_fillers(self) -> Sequence[str]:
        return self._fillers_source() if self._fillers_source is not None else self._fillers

    def _newest_segment(self) -> str:
        """The newest speech: the partial since the last final, else the latest final. `_text()`
        joins every held final, so a stop phrase after earlier held words ("Sofia. Espera.") is
        only visible here."""
        if self._partial.strip():
            return self._partial.strip()
        return self._finals[-1].text.strip() if self._finals else ""

    def _text(self) -> str:
        parts = [f.text.strip() for f in self._finals]
        if self._partial:
            parts.append(self._partial.strip())
        return " ".join(p for p in parts if p).strip()

    def _bump(self) -> None:
        self._version += 1
        self._last_change = self._clock()
        self._scores = None

    # --- frames --------------------------------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            self._ticker = self.create_task(self._tick_loop())
            return
        if isinstance(frame, (EndFrame, CancelFrame)):
            await self._stop_tasks()
            await self.push_frame(frame, direction)
            return

        if direction == FrameDirection.UPSTREAM:
            await self._on_upstream(frame)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMRunFrame):
            # A response was requested outside a user turn (the greeting): until Sofia's first
            # audio, the agent counts as busy, so a caller talking over it follows the barge-in
            # rules instead of opening a turn the in-flight response would talk over.
            self._awaiting_since = self._clock()
            self._awaiting_confirmed = True  # a requested response is not a user turn to confirm
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, InterimTranscriptionFrame):
            text = self._dropped.remove_from(frame.text).strip()
            if text != self._partial:
                self._partial = text
                self._bump()
                if text:
                    self._note_words()
            return  # consumed: the aggregator never sees interims
        if isinstance(frame, TranscriptionFrame):
            text = self._dropped.remove_from(frame.text).strip()
            self._partial = ""
            self._dropped.clear()  # the next STT turn starts from scratch
            if text:
                frame.text = text
                self._finals.append(frame)
                self._note_words()
            self._bump()
            return  # withheld until the turn ends
        await self.push_frame(frame, direction)

    async def _on_upstream(self, frame: Frame) -> None:
        now = self._clock()
        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._vad_speaking = True
            self._onset_at = now
            self._quiet_since = None
            self._words_at = None
            self._marks_asked.clear()
            if not self._turn_open and not self.agent_busy:
                await self._open_turn()
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            self._vad_speaking = False
            self._quiet_since = now - frame.stop_secs  # silence began stop_secs ago
            self._marks_asked.clear()
        elif isinstance(frame, LLMContextUserTurnFrame):
            # The aggregator wrote the user's turn to the context: the LLM really runs.
            if self._awaiting_since is not None:
                self._awaiting_confirmed = True
        elif isinstance(frame, FunctionCallInProgressFrame):
            self._calls_in_progress[frame.tool_call_id] = frame.group_id
        elif isinstance(frame, FunctionCallResultFrame):
            # The assistant aggregator sees the same frame; with the user speaking (our turn is
            # open) it owes the follow-up run instead of making it.
            if self._result_asks_for_run(frame) and self._turn_open:
                self._run_owed = True
        elif isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            self._agent_cut_off = False
            self._awaiting_since = None
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            self._bot_stopped_at = now
            if not self._turn_open:
                await self._release_owed_run()
            if self._policy.k.backchannel_hold_secs > 0 and self._text():
                # Words were held while the agent talked and it stopped before the hold ran out:
                # they now follow the idle-agent rules (they may open a turn).
                self._log(
                    "system1.action",
                    action="convert_held_backchannel",
                    transcript=self._text(),
                    silence_secs=round(self._silence(), 2),
                )

    # --- turn announcements --------------------------------------------------------------

    async def _open_turn(self) -> None:
        self._turn_open = True
        await self.broadcast_frame(UserStartedSpeakingFrame)

    def _result_asks_for_run(self, frame: FunctionCallResultFrame) -> bool:
        """Mirrors LLMAssistantAggregator._handle_function_call_result (pipecat 1.15): whether a
        final result with content runs the LLM (a sibling still running in the group defers it)."""
        group = self._calls_in_progress.get(frame.tool_call_id)
        is_final = frame.properties.is_final if frame.properties else True
        if is_final:
            self._calls_in_progress.pop(frame.tool_call_id, None)
        if not frame.result:
            return False
        if frame.properties and frame.properties.run_llm is not None:
            return frame.properties.run_llm
        if frame.run_llm is not None:
            return frame.run_llm
        return not (group and any(g == group for g in self._calls_in_progress.values()))

    async def _close_empty_turn(self) -> None:
        """Side talk or a backchannel was dropped and nothing is left: end the turn we opened,
        without a transcript, so the aggregator stops treating the user as speaking (a tool
        follow-up it owes is held until then). Not a turn the agent should answer, so neither
        `_awaiting_since` nor `_turn_ended_at` is set."""
        self._turn_open = False
        self._protected = False
        await self.broadcast_frame(UserStoppedSpeakingFrame)
        await self._release_owed_run()

    async def _release_owed_run(self) -> None:
        """Run the LLM for a tool result whose follow-up the aggregator is holding. Pipecat's
        assistant aggregator pushes it when the next result arrives or a user turn with text
        brings its own run; an empty user turn does neither, so Sofia would stay silent. Only
        when we saw the owed result, and never over a speaking agent."""
        if not self._run_owed or self.agent_busy:
            return
        self._run_owed = False
        self._log(
            "system1.action", action="release_owed_run", silence_secs=round(self._silence(), 2)
        )
        self._awaiting_since = self._clock()  # a response is now in flight
        self._awaiting_confirmed = True
        await self.push_frame(LLMRunFrame())

    async def _end_turn(self) -> None:
        """Release the held finals, then announce the stop (adopt path). A stop is never sent
        without a start: if no turn is open (VAD missed the speech, or it came while the agent
        was busy), one is opened first."""
        text = self._text()
        k = self._policy.k
        # Just her name ("Sofia."), or the name with fillers, is a call for attention, not a
        # request for time, whatever holding_floor says (it scored 0.56 for both).
        asked_for_time = (
            self._scores is not None
            and self._scores.holding_floor >= k.holding_threshold
            and not is_name_call(text, self._name_forms, self._current_fillers())
        )
        if not self._turn_open:
            self._log(
                "system1.action",
                action="open_turn",
                reason="end_without_open_turn",
                transcript=text,
                silence_secs=round(self._silence(), 2),
            )
            await self._open_turn()
        if not self._finals and text:  # fallback with only a partial: promote it
            self._finals.append(
                TranscriptionFrame(text=text, user_id="", timestamp=time_now_iso8601())
            )
        finals, self._finals = self._finals, []
        self._low_addressed = 0
        self._partial = ""
        self._dropped.clear()
        self._bump()
        for f in finals:
            await self.push_frame(f)
        await asyncio.sleep(SETTLE_SECS)  # data frames are queued; the stop frame is not
        self._turn_open = False
        self._protected = False
        if finals:
            self._run_owed = False  # the turn's own LLM run settles an owed follow-up
        self._awaiting_since = self._clock() if finals else None
        self._awaiting_confirmed = False
        self._turn_ended_at = self._clock() if finals else None
        self._ignored = 0  # a new agent turn starts
        if finals:
            # A turn that asked for time starts the check-in clock; any other turn with words
            # means the caller is back.
            self._hold_since = self._clock() if asked_for_time else None
            self._checkins = 0
            if asked_for_time:
                self._log("system1.action", action="hold_started", transcript=text)
        await self.broadcast_frame(UserStoppedSpeakingFrame)

    async def _maybe_check_in(self) -> None:
        """The caller asked for time and has not come back: have the agent check in, the way
        the greeting is requested (a developer message, then an LLM run), so it can refer to
        the question still pending. One check-in per `hold_checkin_secs` since the request, as
        many as there are messages; then the hold is over."""
        k = self._policy.k
        if self._hold_since is None or k.hold_checkin_secs <= 0 or not self._checkin_messages:
            return
        if self._turn_open or self._text() or self._vad_speaking or self.agent_busy:
            return
        if self._silence() < HOLD_CHECKIN_QUIET_SECS:
            return
        # Due `hold_checkin_secs` per check-in after the request, and at least that long after the
        # agent's last speech: a hold that began while she talked is not checked the moment she
        # stops. The caller's words never move it.
        now = self._clock()
        due = self._hold_since + (self._checkins + 1) * k.hold_checkin_secs
        if self._bot_stopped_at is not None:
            due = max(due, self._bot_stopped_at + k.hold_checkin_secs)
        if now < due:
            return
        waited = now - self._hold_since
        message = self._checkin_messages[self._checkins]
        self._checkins += 1
        if self._checkins >= len(self._checkin_messages):
            self._hold_since = None
        self._log(
            "system1.action",
            action="hold_check_in",
            check_in=self._checkins,
            waited_secs=round(waited, 2),
            silence_secs=round(self._silence(), 2),
        )
        self._context.add_message({"role": "developer", "content": message})
        self._awaiting_since = self._clock()  # a response is now in flight
        self._awaiting_confirmed = True
        await self.push_frame(LLMRunFrame())

    async def _interrupt(self) -> None:
        await self.broadcast_interruption()
        # The agent is cut off: stop counting it as busy now (BotStopped follows shortly),
        # otherwise the same cached judgment would interrupt again on every tick.
        self._agent_cut_off = self._agent_cut_off or self._bot_speaking
        if self._bot_speaking:
            self._bot_stopped_at = self._clock()
        self._bot_speaking = False
        self._ignored = 0  # the candidate got through
        self._awaiting_since = None
        await asyncio.sleep(SETTLE_SECS)
        if not self._turn_open:
            await self._open_turn()

    # --- judgments -----------------------------------------------------------------------

    def _inputs(self) -> Inputs:
        busy = self.agent_busy
        return Inputs(
            scores=self._scores,
            classifier_failed=self._failed_version == self._version,
            transcript=self._text(),
            has_final=bool(self._finals),
            vad_speaking=self._vad_speaking,
            silence_secs=self._silence(),
            agent_busy=busy,
            turn_open=self._turn_open,
            low_addressed_count=self._low_addressed,
            agent_speaking=self._bot_speaking,
            since_turn_end_secs=self._since_turn_end(),
            stop_phrase=self._policy.k.stop_phrase_fast_path
            and is_stop_request(
                self._text(),
                self._newest_segment(),
                *self._current_stop_phrases(),
                self._name_forms,
                self._current_fillers(),
            ),
            name_call=self._policy.k.name_interrupts
            and is_name_call(
                self._newest_segment(),
                self._name_forms,
                self._current_fillers(),
                *self._current_stop_phrases(),
            ),
            protected=self._protected,
            awaiting_answer=not busy and self._awaiting_answer(),
            names_agent=mentions_name(self._text(), self._name_forms),
        )

    def _all_turns(self) -> list[dict[str, str]]:
        turns: list[dict[str, str]] = []
        for m in self._context.messages:
            if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                c = m.get("content")
                if isinstance(c, list):
                    c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
                if isinstance(c, str) and c.strip():
                    turns.append({"role": m["role"], "text": c.strip()})
        return turns

    def _recent_turns(self) -> list[dict[str, str]]:
        return [{"role": t["role"], "text": t["text"][-200:]} for t in self._all_turns()[-4:]]

    def _awaiting_answer(self) -> bool:
        """The last user/assistant message is the agent's and ends with a question."""
        if self._policy.k.answer_side_talk_threshold <= 0:
            return False
        turns = self._all_turns()
        if not turns or turns[-1]["role"] != "assistant":
            return False
        return turns[-1]["text"].rstrip(TRAILING_CLOSERS).endswith("?")

    def _agent_last(self) -> str:
        for t in reversed(self._recent_turns()):
            if t["role"] == "assistant":
                return t["text"]
        return ""

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self._tick_secs)
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # never let diagnostics/policy kill the call
                self._log("system1.error", message=repr(e))

    async def _tick(self) -> None:
        async with self._busy_lock:
            text = self._text()
            if text and self._call is None and self._should_ask(text):
                self._call = self.create_task(self._judge(text, self._version))
            await self._act(self._policy.decide(self._inputs()), judged=False)
            await self._maybe_check_in()

    def _should_ask(self, text: str) -> bool:
        now = self._clock()
        if self._version != self._judged_version and self._failed_version != self._version:
            new_words = len(text.split()) > len(self._judged_text.split())
            if self.agent_busy and new_words:
                return True  # potential interruption: judge partials immediately
            return now - self._last_change >= self._debounce
        # Same text: ask again at silence marks (state changed: the speaker stayed quiet).
        if not self._vad_speaking:
            for mark in REASK_MARKS:
                if mark not in self._marks_asked and self._silence() >= mark:
                    self._marks_asked.add(mark)
                    return True
        return False

    async def _judge(self, text: str, version: int) -> None:
        state = build_state(
            transcript=text,
            previous_transcript=self._judged_text,
            recent_turns=self._recent_turns(),
            agent_last_message=self._agent_last(),
            agent_speaking=self.agent_busy,
            silence_secs=self._silence(),
            agent_was_cut_off=self._agent_cut_off and self._policy.k.report_agent_cut_off,
            agent_name=self._agent_name,
        )
        awaiting_answer = not self.agent_busy and self._awaiting_answer()
        floor = self._policy.addressed_floor(
            agent_busy=self.agent_busy, awaiting_answer=awaiting_answer
        )
        started = time.perf_counter()
        scores: Scores | None = None
        outcome = "ok"
        try:
            res = await asyncio.wait_for(
                self._classifier.yes_no(state, self._questions), timeout=self._timeout
            )
            scores = Scores(**{name: r.probability for name, r in res.items()})
        except Exception as e:  # ClassifierError, TimeoutError, anything from the client
            outcome = f"error: {e!r}" if not isinstance(e, TimeoutError) else "timeout"
        latency_ms = round((time.perf_counter() - started) * 1000)
        try:
            async with self._busy_lock:
                if version == self._version:
                    self._judged_version, self._judged_text = version, text
                    self._scores = scores
                    if scores is None:
                        self._failed_version = version
                    elif scores.addressed_to_agent < floor:
                        self._low_addressed += 1
                    else:
                        self._low_addressed = 0
                stale = version != self._version
                decision = self._policy.decide(self._inputs())
                self._log(
                    "system1.judgment",
                    transcript=text,
                    scores=_scores_dict(scores),
                    low_addressed_count=self._low_addressed,
                    latency_ms=latency_ms,
                    outcome=outcome + (" (stale)" if stale else ""),
                    bot_speaking=self.agent_busy,
                    silence_secs=round(self._silence(), 2),
                    threshold=round(decision.threshold, 3),
                    fallback_secs=decision.fallback_secs,
                    action=decision.action.value if not stale else Action.KEEP_LISTENING.value,
                    state=state,
                    **getattr(self._classifier, "last_call", {}),
                )
                if not stale:
                    await self._act(decision, judged=True)
        finally:
            self._call = None

    async def _act(self, d: Decision, *, judged: bool) -> None:
        a = d.action
        if a is Action.KEEP_LISTENING or a is Action.HOLD_BACKCHANNEL:
            return
        text = self._text()
        if not judged:  # decisions taken from cached scores / time passing
            s = self._scores
            self._log(
                "system1.action",
                action=a.value,
                transcript=text,
                scores=_scores_dict(s),
                threshold=round(d.threshold, 3),
                silence_secs=round(self._silence(), 2),
                bot_speaking=self.agent_busy,
            )
        if a in (Action.END_TURN, Action.FALLBACK):
            await self._end_turn()
        elif a in (Action.INTERRUPT, Action.INTERRUPT_FAST, Action.INTERRUPT_NAME):
            await self._interrupt()
        elif a is Action.CONTINUE_TURN:
            # The user kept talking right after we ended their turn. pipecat can only resume a
            # turn that is still open (its speculation path); ours is closed and written to the
            # context, so this is a new turn: cut the in-flight answer, open a turn, keep the words.
            self._turn_ended_at = None
            self._protected = True
            await self._interrupt()
        elif a is Action.OPEN_TURN:
            if not self._turn_open:
                await self._open_turn()
            await self._end_turn()
        elif a in (Action.DROP_SIDE_TALK, Action.DROP_BACKCHANNEL):
            if a is Action.DROP_BACKCHANNEL:  # side talk was not meant for her: not ignored
                self._note_ignored()
            self._dropped.add(text)
            self._low_addressed = 0
            self._finals.clear()
            self._partial = ""
            self._bump()
            if self._turn_open and not self._vad_speaking:
                await self._close_empty_turn()

    def _note_ignored(self) -> None:
        """Held speech was dropped while the agent was busy. Every IGNORED_ATTEMPTS_HIT of them in
        one agent turn is one frustration hit, recorded for the FrustrationMonitor."""
        if not self.agent_busy:
            return
        self._ignored += 1
        if self._ignored >= IGNORED_ATTEMPTS_HIT:
            self._log("frustration.ignored_attempts", count=self._ignored)
            self._ignored = 0

    # --- lifecycle -----------------------------------------------------------------------

    async def _stop_tasks(self) -> None:
        for t in (self._ticker, self._call):
            if t:
                await self.cancel_task(t)
        self._ticker = self._call = None

    async def cleanup(self) -> None:
        await super().cleanup()
        await self._stop_tasks()
