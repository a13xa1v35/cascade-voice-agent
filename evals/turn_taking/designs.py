"""The turn-taking designs the benchmark measured, by name.

`v1`, `v2` and `v3` are steps in developing the system-one design; v3 was promoted to Sofia on
2026-11-11 as her only design, so `production` is `hr_screener.turn_taking.design.SYSTEM_ONE_DESIGN`
(whatever Sofia runs today). Every historical design spells out ALL of its params, so it never
depends on the defaults of `Knobs` (which are the production values and may move on): a committed
report stays reproducible. A config picks one with `agent.design` and may override single params
with `agent.variant_params`.

Question sets: `v1` is the first wording (four questions, the article's); `v2` is the production
wording (`hr_screener.turn_taking.questions`), which adds `new_request`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pipecat.classifiers.base_classifier import YesNoQuestion

from hr_screener.turn_taking.design import SYSTEM_ONE_DESIGN
from hr_screener.turn_taking.policy import (
    SYSTEM_ONE_QUESTIONS,
    make_questions,
    question_set_sha,
)

# --- Question sets ------------------------------------------------------------------------

QUESTION_TEXTS_V1: dict[str, str] = {
    "turn_complete": (
        "The speaker is talking to a voice assistant; the words come from speech "
        "recognition, without punctuation, and may be cut off. Has the speaker actually "
        "handed over the floor, so that the assistant should answer now? A complete "
        "question, command or answer is complete even if short. Trailing off, an unfinished "
        "phrase such as 'so what I want to know is', or a pause for thought is not."
    ),
    "holding_floor": (
        "Is the speaker explicitly asking for more time or asking the assistant to wait, for "
        "example 'hold on, let me type something' or 'give me a second'?"
    ),
    "addressed_to_agent": (
        "Is the speaker's latest speech meant for the voice assistant, as opposed to another "
        "person in the room, a TV, or themselves? 'Hey, can you hold my coffee?' said to a "
        "person is not addressed to the assistant."
    ),
    "taking_floor": (
        "The assistant is currently speaking. Is the speaker's latest speech a real "
        "interruption that tries to take the floor (stop, correct, redirect, or ask "
        "something new), as opposed to a backchannel such as 'right', 'yeah' or 'uh huh' "
        "that means keep going? If the assistant is not speaking, answer no."
    ),
}

QUESTION_SETS: Mapping[str, Mapping[str, YesNoQuestion]] = {
    "v1": make_questions(QUESTION_TEXTS_V1),
    "v2": SYSTEM_ONE_QUESTIONS,
}


def questions_for(name: str) -> Mapping[str, YesNoQuestion]:
    return QUESTION_SETS[name]


def question_sha_for(name: str) -> str:
    return question_set_sha(QUESTION_SETS[name])


# --- Designs ------------------------------------------------------------------------------

# v1: the first design, as in the article. Every Knobs value spelled out.
_V1: dict[str, Any] = {
    "provider": "cloudflare-workers-ai",  # "fake-heuristic" only via --fake-classifier
    "model": "clef-flash",
    "question_set": "v1",
    "hedge_after_secs": 0.45,
    "complete_start": 0.72,
    "complete_floor": 0.55,
    "relax_secs": 3.0,
    "addressed_threshold": 0.5,
    "taking_threshold": 0.5,
    "holding_threshold": 0.5,
    "quiet_confirm_secs": 0.3,
    "fallback_secs": 5.0,
    "holding_fallback_secs": 12.0,
    "interrupt_requires_addressed": True,
    "drop_side_talk_while_speaking": True,
    "side_talk_confirmations": 1,
    "new_request_threshold": 0.5,  # unused: question set v1 does not ask new_request
    "interrupt_addressed_threshold": 0.5,
    "incomplete_threshold": 0.0,
    "incomplete_fallback_secs": 0.0,
    "continuation_window_secs": 0.0,
    "stop_phrase_fast_path": False,
    "name_interrupts": False,
    "backchannel_hold_secs": 0.0,
    "answer_side_talk_threshold": 0.0,
    "backchannel_max_words": 0,
    "report_agent_cut_off": False,
    "hold_end_turn_secs": 0.0,  # waits silently while holding, up to holding_fallback_secs
    "hold_checkin_secs": 0.0,
    "classification_timeout": 1.5,
    "debounce_secs": 0.15,
    "pipecat_user_turn_stop_timeout": 3600.0,
}

# v2: tuned on the 60-sample benchmark and confirmed on a held-out set. Each value answers a
# failure seen in the v1 run.
_V2: dict[str, Any] = {
    **_V1,
    # The assistant is the default listener (no false "not addressed" on cold starts) and
    # statements can be complete.
    "question_set": "v2",
    # Side talk was dropped mid-sentence and the words were stripped for good: judge it only once
    # the user is quiet, and require two consecutive low "addressed" judgments.
    "drop_side_talk_while_speaking": False,
    "side_talk_confirmations": 2,
    # Polite topic switches score taking_floor 0.18-0.84 while backchannels stayed <= 0.11.
    "taking_threshold": 0.35,
    # new_request catches "by the way, how often should I..." even when taking_floor stays low.
    "new_request_threshold": 0.5,
    # Replay: requiring 0.6 to INTERRUPT (dropping still uses 0.5) kept 9/10 real interruptions
    # and cut false ones from 5 samples to 2.
    "interrupt_addressed_threshold": 0.6,
    # Statements scored turn_complete 0.2-0.4 under v1: a lower floor lets them end sooner...
    "complete_floor": 0.45,
    # ...and when no score reaches it, wait 3 s instead of 5 s.
    "fallback_secs": 3.0,
}

# v3: refined from manual testing of live calls; NOT benchmarked. Promoted to Sofia on 2026-11-11.
_V3: dict[str, Any] = {
    **_V2,
    "incomplete_threshold": 0.3,
    "incomplete_fallback_secs": 7.0,
    "continuation_window_secs": 3.0,
    "stop_phrase_fast_path": True,
    "backchannel_hold_secs": 1.5,
    "answer_side_talk_threshold": 0.2,
    "backchannel_max_words": 2,
    "report_agent_cut_off": True,
}

# What Sofia runs now, taken from the production definition, so a change to Sofia's design shows up
# here (and in the next run's manifest) without editing the eval. v3 plus the hold handling from
# live call 246271da2319 (hold_end_turn_secs, hold_checkin_secs), not benchmarked.
_PRODUCTION: dict[str, Any] = {**SYSTEM_ONE_DESIGN, "question_set": "v2"}

DESIGNS: Mapping[str, Mapping[str, Any]] = {
    "v1": _V1,
    "v2": _V2,
    "v3": _V3,
    "production": _PRODUCTION,
}
