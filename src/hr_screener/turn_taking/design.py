"""Sofia's turn-taking design: the parameters plus the pipeline hooks.

Every voice call (web and phone) builds its pipeline from `system_one_hooks(SYSTEM_ONE_DESIGN)`.
The Full-Duplex-Bench variant calls the same function, so the live app and the benchmarked design
share one implementation; the eval keeps the earlier designs it measured in
`evals/turn_taking/designs.py` and passes their params instead.

The design is inspired by Agora's "Jev VAD" article: the turn opens on voice activity, and a small
decision model (Cloudflare Workers AI `clef-flash`) judges the streaming transcript (turn
complete? side talk? real interruption?) to decide when it ends. The old baseline (Silero VAD
with pipecat's default strategies and Smart Turn) is no longer an option here. Results of the
designs measured so far are in `evals/turn_taking/reports/SUMMARY.md`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any

from pipecat.classifiers.base_classifier import BaseClassifier, YesNoQuestion
from pipecat.classifiers.cloudflare.clef.classifier import ClefClassifier
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.turns.user_turn_strategies import ExternalUserTurnStrategies, UserTurnStrategies

from hr_screener.agent.prompt_text import PROMPT
from hr_screener.config import Settings
from hr_screener.i18n import Lang
from hr_screener.turn_taking.classifiers import HedgedClassifier
from hr_screener.turn_taking.controller import EventSink, SystemOneTurnController
from hr_screener.turn_taking.policy import (
    FILLERS,
    STOP_PHRASES,
    STOP_PHRASES_EXACT,
    SYSTEM_ONE_QUESTIONS,
    Knobs,
    TurnPolicy,
)

# Developer messages for the check-ins after the caller asked for time (Knobs.hold_checkin_secs),
# in order. English like the rest of the context; the agent answers in the call language.
HOLD_CHECKIN_MESSAGES: tuple[str, ...] = (PROMPT["hold_checkin"], PROMPT["hold_checkin_again"])

# The production design. The policy thresholds are the `Knobs` defaults (each documented there,
# with the measurement behind it); the rest is the plumbing around them.
SYSTEM_ONE_DESIGN: Mapping[str, Any] = MappingProxyType(
    {
        # "fake-heuristic" only via the eval's --fake-classifier
        "provider": "cloudflare-workers-ai",
        "model": "clef-flash",
        # Clef flash is bimodal (62% of calls ~0.4 s, ~30% 1.5-4 s): after this long, a
        # duplicate request goes out on a second HTTP/2 connection and the first answer wins.
        "hedge_after_secs": 0.45,
        **Knobs().as_params(),
        # A judgment slower than this is abandoned and the fallbacks take over (1.5 s covers ~92%
        # of hedged calls in a 40-call measurement).
        "classification_timeout": 1.5,
        "debounce_secs": 0.15,
        # pipecat's own user_turn_stop_timeout (default 5 s) would pre-empt the controller's
        # fallbacks (12 s while holding, with hold_end_turn_secs off); the controller owns every
        # fallback, so pipecat's is pushed out of reach.
        "pipecat_user_turn_stop_timeout": 3600.0,
    }
)


def design_sha(params: Mapping[str, Any] = SYSTEM_ONE_DESIGN) -> str:
    """Short stable hash of a design's params; every call records it (`system1.config`) so a
    transcript says which design ran it."""
    return hashlib.sha256(json.dumps(dict(params), sort_keys=True).encode()).hexdigest()[:10]


def make_system_one_classifier(settings: Settings, p: Mapping[str, Any]) -> HedgedClassifier:
    """Clef flash is bimodal (62% of calls ~0.4 s, ~30% 1.5-4 s): hedge with a duplicate request
    on a second HTTP/2 connection."""

    def one() -> ClefClassifier:
        return ClefClassifier(
            model=p["model"],
            account_id=settings.cloudflare_account_id,
            api_key=settings.cloudflare_api_token,
        )

    return HedgedClassifier(one(), one(), hedge_after_secs=p["hedge_after_secs"])


def system_one_hooks(
    settings: Settings,
    params: Mapping[str, Any],
    events: EventSink,
    *,
    questions: Mapping[str, YesNoQuestion] = SYSTEM_ONE_QUESTIONS,
    classifier_factory: Callable[[], BaseClassifier] | None = None,
    lang: Lang | Callable[[], Lang] = "en",
    agent_name: str | None = None,
) -> dict[str, Any]:
    """Keyword arguments for `build_conversation_pipeline` that switch it to the system-one
    design: external turn strategies (no Smart Turn, the adopt path never interrupts by itself),
    the controller between STT and the user aggregator, and aggregator params that keep pipecat
    from pre-empting the controller's fallbacks or answering empty turns.

    `params` is `SYSTEM_ONE_DESIGN` in production; the eval passes the params of an earlier design
    (and its `questions`). `lang` is the call language, or a callable returning it (read at
    every turn, so a language switch mid-call applies): it selects the stop phrases (the
    questions are English for every call). `events(type, **fields)` receives `system1.judgment` /
    `system1.action`. `classifier_factory` replaces the hedged Cloudflare pair (tests, the eval's
    `--fake-classifier`). `agent_name` (Sofia's calls) is told to the model and keeps "Hola, Sofia"
    from being dropped as side talk; the eval's agent has no name."""
    p = params
    knobs = Knobs(**{k: p[k] for k in Knobs().as_params()})

    def current_lang() -> Lang:
        return lang() if callable(lang) else lang

    def stop_phrases() -> tuple[Sequence[str], Sequence[str]]:
        return STOP_PHRASES[current_lang()], STOP_PHRASES_EXACT[current_lang()]

    def processors(context: LLMContext) -> list[FrameProcessor]:
        classifier = (
            classifier_factory() if classifier_factory else make_system_one_classifier(settings, p)
        )
        return [
            SystemOneTurnController(
                context=context,
                classifier=classifier,
                policy=TurnPolicy(knobs),
                questions=questions,
                stop_phrases_source=stop_phrases,
                fillers_source=lambda: FILLERS[current_lang()],
                events=events,
                classification_timeout=p["classification_timeout"],
                debounce_secs=p["debounce_secs"],
                agent_name=agent_name,
                hold_checkin_messages=HOLD_CHECKIN_MESSAGES,
            )
        ]

    def strategies(_context: LLMContext) -> UserTurnStrategies:
        return ExternalUserTurnStrategies(enable_interruptions=False)

    return {
        "user_turn_strategies": strategies,
        "processors_before_aggregator": processors,
        "user_params_overrides": {
            "user_turn_stop_timeout": p["pipecat_user_turn_stop_timeout"],
            # Never answer a turn that has no transcript (the controller never produces one).
            "empty_user_turn": None,
        },
    }
