"""Pure turn-taking policy for the "Jev VAD" design (Agora): open fast, decide late.

No clocks, no pipecat frames, no network: `TurnPolicy.decide(Inputs) -> Decision`, driven by
the four yes/no scores a system-one model returns. The glue lives in `controller.py`.

The four questions (one request, `noul` type in Clef):
  turn_complete       has the speaker handed over the floor?
  holding_floor       are they explicitly asking for more time?
  addressed_to_agent  is the latest speech meant for the assistant?
  taking_floor        while the agent talks: a real interruption, or a backchannel?
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pipecat.classifiers.base_classifier import YesNoQuestion

from hr_screener.i18n import Lang
from hr_screener.turn_taking.questions import SYSTEM_ONE_TEXTS


class Action(StrEnum):
    KEEP_LISTENING = "keep_listening"
    END_TURN = "end_turn"
    FALLBACK = "fallback"  # turn ended by the silence fallback, regardless of scores
    INTERRUPT = "interrupt"  # open a turn AND interrupt the agent
    OPEN_TURN = "open_turn"  # held speech turned out addressed after the agent finished
    DROP_SIDE_TALK = "drop_side_talk"
    CONTINUE_TURN = "continue_turn"  # speech right after the controller ended a turn: interrupt
    INTERRUPT_FAST = "interrupt_fast"  # a stop phrase while the agent speaks: interrupt now
    INTERRUPT_NAME = "interrupt_name"  # the caller just says her name while she speaks
    HOLD_BACKCHANNEL = "hold_backchannel"
    DROP_BACKCHANNEL = "drop_backchannel"


@dataclass(frozen=True)
class Knobs:
    """Every threshold and timing of the policy. The defaults ARE Sofia's production design
    (`design.SYSTEM_ONE_DESIGN`); the eval overrides them to reproduce earlier designs, so a
    knob whose production value switches it off is kept for that."""

    # turn_complete bar to end a turn: complete_start with no silence, relaxed linearly to
    # complete_floor as mic silence approaches relax_secs. The floor is low because finished
    # statements ("I have two years of experience") scored turn_complete 0.2-0.4.
    complete_start: float = 0.72
    complete_floor: float = 0.45
    relax_secs: float = 3.0
    addressed_threshold: float = 0.5
    # Low on purpose: polite topic switches score taking_floor 0.18-0.84 while backchannels
    # stayed <= 0.11, so there is room to interrupt earlier than 0.5.
    taking_threshold: float = 0.35
    holding_threshold: float = 0.5
    # VAD already waits stop_secs (0.2) before reporting quiet, so 0.3 s of real silence
    # only adds ~0.1 s of margin against a flickering VAD, which is cheap, and the STT
    # final lags the VAD stop by ~0.3 s anyway. Larger values cost latency 1:1.
    quiet_confirm_secs: float = 0.3
    # Silence after which the turn ends whatever the scores say (the classifier may be slow or
    # wrong). 3 s: statements that never reach complete_floor must not wait the old 5 s.
    fallback_secs: float = 3.0
    holding_fallback_secs: float = 12.0  # ...when the speaker asked for more time
    # Measured with Clef flash: side talk can score high on taking_floor ('Dad the microwave
    # quit' 0.71 vs addressed 0.18), so an interruption must also be addressed to the agent.
    interrupt_requires_addressed: bool = True
    # False: while the user is still speaking (agent idle), never drop as side talk; judge side
    # talk only after quiet confirmation (a drop is irreversible: the words are stripped later).
    # With True, side talk was dropped mid-sentence and its words lost for good.
    drop_side_talk_while_speaking: bool = False
    # Dropping as side talk needs this many consecutive judgments with addressed < threshold.
    side_talk_confirmations: int = 2
    # A new question or request while the agent is busy interrupts like taking_floor does
    # (Scores.new_request): it catches "by the way, how often should I..." even when
    # taking_floor stays low.
    new_request_threshold: float = 0.5
    # How sure the model must be that busy-agent speech is meant for the agent before it may
    # INTERRUPT (side-talk dropping keeps using addressed_threshold). Replay: with the
    # "assistant is the default listener" wording, background chatter ("I'm starving.") reached
    # addressed 0.5-0.87; requiring 0.6 to interrupt kept 9/10 real interruptions and cut false
    # ones from 5 samples to 2. It can't remove them all.
    interrupt_addressed_threshold: float = 0.6
    # A clearly unfinished turn (turn_complete below incomplete_threshold; 0 = off) gets the
    # longer incomplete_fallback_secs instead of fallback_secs: candidates think out loud (a
    # live call was cut off at 3 s). Only a transcript WITHOUT terminal punctuation counts: STT
    # punctuates complete answers ("Sí, sí.") and leaves unfinished ones bare ("...pero"), even
    # when the classifier underscores them.
    incomplete_threshold: float = 0.3
    incomplete_fallback_secs: float = 7.0
    # Speech within this many seconds after the controller itself ended a user turn, while the
    # agent is busy answering it, is a continuation: interrupt at once and never drop it (a
    # continuation right after a cut was held as a backchannel and lost). 0 = off.
    continuation_window_secs: float = 3.0
    # While the agent speaks, a stop phrase ("wait", "espera"...) interrupts without a judgment
    # ("por cierto," took ~1 s to interrupt through the classifier).
    stop_phrase_fast_path: bool = True
    # While the agent speaks, the newest speech being just her name, or her name with fillers or a
    # stop phrase ("Sofia", "Oye, Sofia", "Sofia, espera"), interrupts her without a judgment.
    # Calling someone by name mid-speech is how people ask them to stop, but the classifier read
    # it as side talk (addressed 0.19-0.38 against 0.6 to interrupt) and a live call
    # (17a8d16dcad3) went on for 32 s over four such calls. "Gracias, Sofia" or any sentence that
    # merely mentions her does not count. Needs the agent's name (Inputs.name_call).
    name_interrupts: bool = True
    # A held backchannel (agent speaking, not interrupting) is dropped only if the agent is STILL
    # speaking this long after the user went quiet. If the agent stops first, the held words get
    # the idle-agent rules, so a "Sí." answering the agent's closing question opens a turn.
    # 0 = drop at quiet confirmation.
    backchannel_hold_secs: float = 1.5
    # The agent is idle and its last message was a question (Inputs.awaiting_answer): the reply is
    # side talk only if addressed is below THIS instead of addressed_threshold, because short
    # answers ("No.", "¿Qué es ahí?") score 0.3-0.45 and were dropped, leaving the call dead.
    # 0 = off (the same threshold as always). Busy-agent rules are unchanged.
    answer_side_talk_threshold: float = 0.2
    # While the agent speaks, only a backchannel of at most this many words is dropped; longer
    # held speech ("Eso me va bien.", "No, la online.") stays held and, once the agent stops, gets
    # the idle-agent rules (needs backchannel_hold_secs > 0 to be delivered). 0 = off.
    backchannel_max_words: int = 2
    # True: tell the classifier when the agent's last message was cut off by an interruption
    # (state key agent_was_cut_off), so a short confirmation does not look like an unfinished
    # answer to her half-sentence. The key is omitted otherwise.
    report_agent_cut_off: bool = True
    # An explicit request for time ("un momentito", "hold on"; holding_floor >= holding_threshold)
    # that is addressed and followed by this much quiet ends the turn, so the agent can say a
    # short "sure, take your time" the way a person would. Waiting silently instead kept the
    # request in the open turn, and since it is judged on the whole turn, the hold never let go:
    # a live call (246271da2319) stayed silent through "No, sigue, perdón", "Hola" and "Hola,
    # Sofia" until the caller hung up. Also, while the agent speaks, such a request (addressed
    # enough to interrupt) interrupts her. 0 = off: wait up to holding_fallback_secs.
    hold_end_turn_secs: float = 0.8
    # After a turn that asked for time, the agent checks in ("¿Lo tienes?") once this long has
    # passed since the request, then again at twice it. Never reset by the caller's words; the
    # controller also needs the caller quiet for a moment (HOLD_CHECKIN_QUIET_SECS). Each check-in
    # is also at least this long after the end of the agent's last speech, so a hold that began
    # while she was talking (a false one, or a long answer) is not checked the moment she stops.
    # 0 = off.
    hold_checkin_secs: float = 10.0

    def as_params(self) -> dict[str, float | bool]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Scores:
    turn_complete: float
    holding_floor: float
    addressed_to_agent: float
    taking_floor: float
    new_request: float | None = None  # None when the question set does not ask it


@dataclass(frozen=True)
class Inputs:
    scores: Scores | None  # None: no judgment for the current transcript yet, or it failed
    classifier_failed: bool  # the judgment for the current transcript errored / timed out
    transcript: str  # current words (finals + partial, minus dropped speech)
    has_final: bool  # at least one finalized transcript is held
    vad_speaking: bool
    silence_secs: float  # mic silence so far (0 while speaking)
    agent_busy: bool  # speaking, or a response is in flight
    turn_open: bool  # a user turn has been announced to the aggregator
    # Consecutive judgments (incl. this one) with addressed < threshold. The default of 1 means
    # "this judgment alone".
    low_addressed_count: int = 1
    # --- Inputs of the optional knobs (the defaults are inert) ---
    agent_speaking: bool = False  # audio is playing (agent_busy also covers "response in flight")
    since_turn_end_secs: float | None = None  # since the controller ended a user turn
    # The held speech or its newest segment is a stop phrase (see `is_stop_request`).
    stop_phrase: bool = False
    # The newest segment is the agent's name, alone or with fillers / a stop phrase (see
    # `is_name_call`).
    name_call: bool = False
    protected: bool = False  # the open turn is a continuation: its words are never dropped
    # The agent is idle and its last message ended with a question (see answer_side_talk_threshold).
    awaiting_answer: bool = False
    # The words call the agent by its name ("Hola, Sofia"): addressed to it, never side talk, even
    # when the classifier reads the name as someone else's.
    names_agent: bool = False


@dataclass(frozen=True)
class Decision:
    action: Action
    threshold: float  # the turn_complete threshold in force
    fallback_secs: float


class TurnPolicy:
    def __init__(self, knobs: Knobs | None = None) -> None:
        self.k = knobs or Knobs()

    def complete_threshold(self, silence_secs: float, holding: bool) -> float:
        """0.72 at no silence, relaxing linearly to 0.55 at relax_secs; frozen while holding."""
        k = self.k
        if holding:
            return k.complete_start
        frac = min(max(silence_secs / k.relax_secs, 0.0), 1.0)
        return k.complete_start - (k.complete_start - k.complete_floor) * frac

    def addressed_floor(self, *, agent_busy: bool, awaiting_answer: bool) -> float:
        """The addressed_to_agent value below which speech counts as side talk right now."""
        k = self.k
        if awaiting_answer and not agent_busy and k.answer_side_talk_threshold > 0:
            return k.answer_side_talk_threshold
        return k.addressed_threshold

    def decide(self, i: Inputs) -> Decision:
        k, s = self.k, i.scores
        holding = bool(s and s.holding_floor >= k.holding_threshold)
        thr = self.complete_threshold(i.silence_secs, holding)
        fallback = k.holding_fallback_secs if holding else k.fallback_secs
        if (
            not holding
            and k.incomplete_threshold > 0
            and s is not None
            and s.turn_complete < k.incomplete_threshold
            and not ends_with_terminal_punctuation(i.transcript)
        ):
            fallback = max(k.fallback_secs, k.incomplete_fallback_secs)

        def out(action: Action) -> Decision:
            return Decision(action, thr, fallback)

        if (
            k.continuation_window_secs > 0
            and i.agent_busy
            and i.since_turn_end_secs is not None
            and i.since_turn_end_secs <= k.continuation_window_secs
            # Words required: a bare VAD onset (a cough, a door) would cut the agent off and open
            # a turn with no text, which never closes, so the agent would go silent.
            and i.transcript.strip()
        ):
            return out(Action.CONTINUE_TURN)  # no Clef wait, never judged as backchannel/side talk

        if not i.transcript.strip():
            return out(Action.KEEP_LISTENING)  # no text: never close, never reach the LLM

        quiet = not i.vad_speaking and i.silence_secs >= k.quiet_confirm_secs

        floor = self.addressed_floor(agent_busy=i.agent_busy, awaiting_answer=i.awaiting_answer)
        side_talk = bool(
            s
            and s.addressed_to_agent < floor
            and i.low_addressed_count >= k.side_talk_confirmations
            and not (i.protected and k.continuation_window_secs > 0)
            and not i.names_agent
        )

        if i.agent_busy:
            # Speech during agent speech is held, never forwarded unless it interrupts.
            if k.stop_phrase_fast_path and i.agent_speaking and i.stop_phrase:
                return out(Action.INTERRUPT_FAST)
            if k.name_interrupts and i.agent_speaking and i.name_call:
                return out(Action.INTERRUPT_NAME)
            if s is None:
                return out(Action.KEEP_LISTENING)  # includes Clef failure: never interrupt
            addressed = s.addressed_to_agent >= k.addressed_threshold
            addressed_to_interrupt = s.addressed_to_agent >= k.interrupt_addressed_threshold
            takes = (
                s.taking_floor >= k.taking_threshold
                or (s.new_request is not None and s.new_request >= k.new_request_threshold)
                # "Un momentito" while she talks asks her to stop (taking_floor scored it 0.33):
                # otherwise it is held as a two-word backchannel and dropped.
                or (k.hold_end_turn_secs > 0 and holding)
            )
            if takes and (addressed_to_interrupt or not k.interrupt_requires_addressed):
                return out(Action.INTERRUPT)
            if side_talk:
                return out(Action.DROP_SIDE_TALK)
            if not addressed:
                return out(Action.HOLD_BACKCHANNEL)  # low addressed, still unconfirmed
            hold = k.backchannel_hold_secs
            drop_ok = quiet and (hold <= 0 or (i.agent_speaking and i.silence_secs >= hold))
            if drop_ok and 0 < k.backchannel_max_words < len(normalize_words(i.transcript)):
                drop_ok = False  # too long for a backchannel: keep it for the idle-agent rules
            return out(Action.DROP_BACKCHANNEL if drop_ok else Action.HOLD_BACKCHANNEL)

        # Agent idle.
        if i.vad_speaking:
            # Judge side talk early (if enabled), but never end a turn while audibly speaking.
            if k.drop_side_talk_while_speaking and side_talk:
                return out(Action.DROP_SIDE_TALK)
            return out(Action.KEEP_LISTENING)
        if not quiet:
            return out(Action.KEEP_LISTENING)

        if i.silence_secs >= fallback and (i.turn_open or i.has_final):
            return out(Action.FALLBACK)  # hard fallback, even if Clef failed
        if s is None:
            return out(Action.KEEP_LISTENING)  # waiting for a judgment (or the fallback)
        if side_talk:
            return out(Action.DROP_SIDE_TALK)
        if s.addressed_to_agent < floor and not i.names_agent:
            return out(Action.KEEP_LISTENING)  # low addressed, awaiting more confirmations
        asks_for_time = (
            holding and k.hold_end_turn_secs > 0 and i.silence_secs >= k.hold_end_turn_secs
        )
        if (s.turn_complete >= thr or asks_for_time) and i.has_final:
            return out(Action.END_TURN if i.turn_open else Action.OPEN_TURN)
        return out(Action.KEEP_LISTENING)


# --- Questions (texts in questions.py), stop phrases and the state builder -----------------------


def make_questions(texts: Mapping[str, str]) -> Mapping[str, YesNoQuestion]:
    """Question texts -> the classifier's questions (English for every call, like the prompt).
    Question keys are canonical."""
    return {key: YesNoQuestion(instructions=text) for key, text in texts.items()}


# Stop words for the interruption fast path (Knobs.stop_phrase_fast_path). They match what the
# caller says, so they are per call language (not translations). The whole partial must be the
# phrase (+ at most one word), or the phrase repeated. The *exact* ones are ambiguous words
# (es 'para' = 'for', 'sorry' can open a longer apology) matched only as the whole
# partial/repeated.
STOP_PHRASES: Mapping[Lang, tuple[str, ...]] = {
    "en": ("wait", "stop", "hold on", "excuse me", "one second"),
    "es": ("espera", "espérate", "un momento", "oye espera"),
}
# Words that only get attention, in front of or behind a name or a stop phrase ("Oye, Sofia").
# Per call language like the stop phrases. Several words are allowed ("excuse me").
FILLERS: Mapping[Lang, tuple[str, ...]] = {
    "en": ("hey", "excuse me", "sorry", "uh", "um"),
    "es": ("oye", "hey", "eh", "perdona", "perdón", "oiga"),
}
STOP_PHRASES_EXACT: Mapping[Lang, tuple[str, ...]] = {
    "en": ("sorry",),  # "sorry, I did not catch..." is not a stop
    "es": ("para", "perdona", "perdón"),  # "para" also means "for" ("para mí es...")
}


SYSTEM_ONE_QUESTIONS: Mapping[str, YesNoQuestion] = make_questions(SYSTEM_ONE_TEXTS)


def question_set_sha(questions: Mapping[str, YesNoQuestion] = SYSTEM_ONE_QUESTIONS) -> str:
    """Short hash of the question texts actually used, so a wording edit shows in the call's
    `system1.config` event (and in an eval manifest)."""
    payload = json.dumps({n: q.instructions for n, q in questions.items()}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:10]


def build_state(
    *,
    transcript: str,
    previous_transcript: str,
    recent_turns: Sequence[Mapping[str, str]],
    agent_last_message: str,
    agent_speaking: bool,
    silence_secs: float,
    agent_was_cut_off: bool = False,
    agent_name: str | None = None,
) -> dict[str, Any]:
    """The state sent with the four questions (kept to a few hundred tokens). `agent_name` tells
    the model what the assistant is called, so "Hola, Sofia" is not read as a name for someone
    else (the addressed question treats other people's names as evidence of side talk)."""
    added = (
        transcript[len(previous_transcript) :].strip()
        if previous_transcript and transcript.startswith(previous_transcript)
        else transcript
    )
    state: dict[str, Any] = {
        "speaker_transcript_so_far": transcript[-600:],
        "change_since_last_check": {"added_words": added[-300:]},
        "agent_is_speaking_now": agent_speaking,
        "mic_silence_seconds": round(silence_secs, 2),
        "agent_last_message": agent_last_message[-400:],
        "recent_turns": [dict(t) for t in recent_turns][-4:],
    }
    if agent_was_cut_off:
        state["agent_was_cut_off"] = True
    if agent_name:
        state["assistant_name"] = agent_name
    return state


_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")  # unicode letters/digits: "espérate", "perdón"


def normalize_words(text: str) -> list[str]:
    return [m.group().lower() for m in _WORD.finditer(text)]


_TERMINAL = ".?!\u2026\u203d\u3002\uff01\uff1f"  # ... ? ! ellipsis, interrobang, CJK/fullwidth
# whitespace, quotes (straight and curly, guillemets) and closing brackets
TRAILING_CLOSERS = " \t\r\n\"'`\u201c\u201d\u2018\u2019\u00ab\u00bb)]}"


def ends_with_terminal_punctuation(text: str) -> bool:
    """Whether `text` ends a sentence (. ? ! … and their Unicode forms), ignoring trailing
    spaces, quotes and closing brackets."""
    stripped = text.rstrip(TRAILING_CLOSERS)
    return bool(stripped) and stripped[-1] in _TERMINAL


def _strip_accents(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c))


def name_forms(name: str) -> frozenset[str]:
    """How STT may write the agent's name, word by word: as configured and with doubled letters
    collapsed ("Allie" -> "allie", "alie"), compared without accents (Spanish STT may write
    "Sofia" as "Sofía")."""
    words = [_strip_accents(w) for w in normalize_words(name)]
    return frozenset(words) | {re.sub(r"(.)\1", r"\1", w) for w in words}


def mentions_name(text: str, forms: frozenset[str]) -> bool:
    """Whether `text` contains one of the name `forms` as a whole word, ignoring accents."""
    return bool(forms) and any(_strip_accents(w) in forms for w in normalize_words(text))


def matches_stop_phrase(
    text: str, phrases: Sequence[str], exact_phrases: Sequence[str] = ()
) -> bool:
    """Whether the WHOLE partial is a stop phrase.

    `phrases` match when the partial is the phrase, or starts with it and has at most one extra
    word ("wait", "stop talking"), or is the phrase repeated ("espera, espera"). `exact_phrases`
    are ambiguous words that can open an unrelated sentence (es "para" = "for", "sorry", "perdona"):
    they match only as the whole partial or repeated, so "para mí es..." does not fire."""
    words = normalize_words(text)
    if not words:
        return False

    def repeated(p: list[str]) -> bool:
        n = len(p)
        return len(words) % n == 0 and words == p * (len(words) // n)

    for phrase in exact_phrases:
        p = normalize_words(phrase)
        if p and repeated(p):
            return True
    for phrase in phrases:
        p = normalize_words(phrase)
        if p and (repeated(p) or (words[: len(p)] == p and len(words) <= len(p) + 1)):
            return True
    return False


def _fold_words(text: str) -> list[str]:
    return [_strip_accents(w) for w in normalize_words(text)]


def split_vocatives(
    text: str, forms: frozenset[str], fillers: Sequence[str] = ()
) -> tuple[list[str], bool]:
    """`text` without the agent's name and the fillers at its start and end ("Oye, Sofia, espera"
    -> ["espera"]), as (remaining words with their accents, whether the name was removed)."""
    words = normalize_words(text)
    folded = [_strip_accents(w) for w in words]
    phrases = [tuple(_fold_words(f)) for f in fillers]
    lo, hi, named = 0, len(words), False

    def eat(at: int, backwards: bool) -> int:
        """Length of the vocative that starts (or ends) at `at`, 0 if none."""
        if folded[at] in forms:
            return 1
        for p in phrases:
            n = len(p)
            if not n or n > hi - lo:
                continue
            seg = folded[hi - n : hi] if backwards else folded[lo : lo + n]
            if tuple(seg) == p:
                return n
        return 0

    while lo < hi:
        n = eat(lo, False)
        if n:
            named = named or any(w in forms for w in folded[lo : lo + n])
            lo += n
            continue
        n = eat(hi - 1, True)
        if n:
            named = named or any(w in forms for w in folded[hi - n : hi])
            hi -= n
            continue
        break
    return words[lo:hi], named


def last_sentence(text: str) -> str:
    """The last sentence of `text` (split after . ? ! ...); the whole text if it has one."""
    parts = [s for s in re.split(r"(?<=[.?!\u2026])\s+", text.strip()) if s.strip()]
    return parts[-1] if parts else ""


def is_stop_request(
    whole: str,
    segment: str,
    phrases: Sequence[str],
    exact_phrases: Sequence[str] = (),
    forms: frozenset[str] = frozenset(),
    fillers: Sequence[str] = (),
) -> bool:
    """Whether the held speech asks the agent to stop. `whole` is everything held, `segment` the
    newest speech (the latest STT final, or the partial since the last pause). The whole must be
    a stop phrase, or the segment or its last sentence is one once a leading or trailing name
    or filler is ignored: held "Sofia. Espera." is not a stop phrase as a whole, "Espera." is.
    The exact phrases keep their safety: "para mi es..." never matches."""
    candidates = [whole, segment, last_sentence(segment)]
    for text in list(candidates):
        rest, _ = split_vocatives(text, forms, fillers)
        candidates.append(" ".join(rest))
    return any(
        c.strip() and matches_stop_phrase(c, phrases, exact_phrases)
        for c in dict.fromkeys(candidates)
    )


def is_name_call(
    segment: str,
    forms: frozenset[str],
    fillers: Sequence[str] = (),
    phrases: Sequence[str] = (),
    exact_phrases: Sequence[str] = (),
) -> bool:
    """Whether the newest speech is the agent's name and nothing else: the name with fillers
    ("Oye, Sofia") or with a stop phrase ("Sofia, espera"). "Gracias, Sofia" is not."""
    if not forms:
        return False
    rest, named = split_vocatives(segment, forms, fillers)
    return named and (not rest or matches_stop_phrase(" ".join(rest), phrases, exact_phrases))


@dataclass
class DroppedSpeech:
    """Words already judged irrelevant. STT partials and finals repeat the whole turn so far,
    so they would otherwise bring those words back; this strips them."""

    words: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.words += normalize_words(text)

    def clear(self) -> None:
        self.words = []

    def remove_from(self, text: str) -> str:
        """Remove a leading run of already-dropped words from `text` (word-level match)."""
        if not self.words:
            return text
        want = normalize_words(text)
        if want[: len(self.words)] != self.words:
            return text
        # Drop the first len(words) tokens of the original text.
        tokens = list(_WORD.finditer(text))
        if len(tokens) < len(self.words):
            return text
        cut = tokens[len(self.words) - 1].end()
        return text[cut:].lstrip(" ,.;:!?-")
