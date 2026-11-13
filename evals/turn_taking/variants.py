"""Pipeline variants under test. A variant builds the conversation pipeline around a
bench transport; add new ones to VARIANTS.

Every variant gets the same fixed `BenchAgent` (prompt + tools). A variant may add its own
prompt text ONLY through `Variant.extra_instructions`, and declares its tunables in
`Variant.params`; both are recorded in the manifest. `required_keys` names Settings fields
(env vars) it needs on top of the agent's own providers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_turn_strategies import (
    ClassifierUserTurnStrategies,
    UserTurnStrategies,
)

from evals.turn_taking.agent import BenchAgent
from evals.turn_taking.designs import DESIGNS, QUESTION_SETS, question_sha_for
from evals.turn_taking.events import EventLog
from evals.turn_taking.fake_classifier import HeuristicFakeClassifier
from hr_screener.config import Settings
from hr_screener.pipeline.bot import ConversationPipeline, build_conversation_pipeline
from hr_screener.turn_taking.classifiers import LoggingClassifier
from hr_screener.turn_taking.design import make_system_one_classifier, system_one_hooks

# (transport, settings, agent, telephony, events, params) -> pipeline pieces. `events` is the
# session's EventLog: variants log their own diagnostics (e.g. system1.judgment) to it.
# `params` is the variant's RESOLVED params (defaults merged with the config's
# agent.variant_params); None means the variant's defaults.
VariantBuilder = Callable[
    [BaseTransport, Settings, BenchAgent, bool, EventLog, Mapping[str, Any] | None],
    ConversationPipeline,
]


def build_baseline(
    transport: BaseTransport,
    settings: Settings,
    agent: BenchAgent,
    telephony: bool,
    events: EventLog,
    params: Mapping[str, Any] | None = None,
) -> ConversationPipeline:
    """The turn-taking design Sofia used before 2026-11-11: Silero VAD + pipecat's default
    user-turn strategies (Smart Turn v3), with the shared bench agent. No greeting. Kept as the
    comparison point of every committed report; `build_conversation_pipeline` without hooks."""
    return build_conversation_pipeline(
        transport,
        settings,
        system_prompt=agent.system_prompt,
        tools=agent.tools,
        telephony=telephony,
    )


# Pipecat's own defaults for ClassifierUserTurnStrategies, except the classification timeout
# (1.5 s covers ~92% of hedged calls in a 40-call measurement; slower calls fall back).
SYSTEM_ONE_EOT_PARAMS: dict[str, Any] = {
    "model": "clef-flash",
    "hedge_after_secs": 0.45,
    "short_timeout": 5.0,
    "long_timeout": 10.0,
    "classification_timeout": 1.5,
}


def build_system_one_eot(
    transport: BaseTransport,
    settings: Settings,
    agent: BenchAgent,
    telephony: bool,
    events: EventLog,
    params: Mapping[str, Any] | None = None,
) -> ConversationPipeline:
    """Baseline plus a Clef flash end-of-turn classifier (system one) that must also agree,
    next to Smart Turn, that the user's turn is complete."""
    p = params or SYSTEM_ONE_EOT_PARAMS

    def strategies(context: LLMContext) -> UserTurnStrategies:
        classifier = LoggingClassifier(make_system_one_classifier(settings, p), events.add)
        return ClassifierUserTurnStrategies(
            classifier=classifier,
            context=context,
            short_timeout=p["short_timeout"],
            long_timeout=p["long_timeout"],
            classification_timeout=p["classification_timeout"],
        )

    return build_conversation_pipeline(
        transport,
        settings,
        system_prompt=agent.system_prompt,
        tools=agent.tools,
        telephony=telephony,
        user_turn_strategies=strategies,
    )


# The design a config gets when it does not name one: the first one, which the first runs used.
DEFAULT_SYSTEM_ONE_DESIGN = "v1"


def build_system_one(
    transport: BaseTransport,
    settings: Settings,
    agent: BenchAgent,
    telephony: bool,
    events: EventLog,
    params: Mapping[str, Any] | None = None,
) -> ConversationPipeline:
    """Open fast, decide late: the shared production hooks (external turn strategies, no Smart
    Turn, a controller judging the transcript with one multi-question call per check), run with
    the resolved params of the config's design."""
    p = params or DESIGNS[DEFAULT_SYSTEM_ONE_DESIGN]
    return build_conversation_pipeline(
        transport,
        settings,
        system_prompt=agent.system_prompt,
        tools=agent.tools,
        telephony=telephony,
        **system_one_hooks(
            settings,
            p,
            events.add,
            questions=QUESTION_SETS[p["question_set"]],
            classifier_factory=HeuristicFakeClassifier
            if p["provider"] == "fake-heuristic"
            else None,
        ),
    )


def _system_one_derived(params: dict[str, Any]) -> dict[str, Any]:
    return {"question_set_sha": question_sha_for(params["question_set"])}


@dataclass(frozen=True)
class Variant:
    build: VariantBuilder
    extra_instructions: str = ""  # appended to the shared prompt; empty for all today
    # Default tunables. Never mutated: per-run changes go through resolve_params().
    params: Mapping[str, Any] = field(default_factory=dict)
    # Named param sets a config selects with `agent.design` (the defaults then come from there
    # instead of `params`); `default_design` is used when the config names none.
    designs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    default_design: str | None = None
    required_keys: tuple[str, ...] = ()  # Settings field names that must be non-empty
    # Keys a config may NOT override (the model and classifier identity).
    locked: tuple[str, ...] = ("provider", "model")
    choices: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # enum-like params
    derive: Callable[[dict[str, Any]], dict[str, Any]] | None = None  # computed, recorded params

    def base_params(self, design: str | None = None) -> Mapping[str, Any]:
        """The params a config starts from: the named design, or the variant's defaults."""
        if not self.designs:
            if design is not None:
                raise ValueError(f"this variant has no designs; got design {design!r}")
            return self.params
        name = design or self.default_design
        if name is None or name not in self.designs:
            raise ValueError(f"unknown design {name!r}; known: {sorted(self.designs)}")
        return self.designs[name]

    def resolve_params(
        self,
        overrides: Mapping[str, Any] | None = None,
        *,
        design: str | None = None,
        fake_classifier: bool = False,
    ) -> dict[str, Any]:
        """The base design (or defaults) merged with a config's `agent.variant_params`,
        validated: unknown keys, locked keys and wrong types are errors. This dict is what the
        builder uses AND what the manifest records."""
        base = self.base_params(design)
        merged: dict[str, Any] = dict(base)
        for key, value in (overrides or {}).items():
            if key not in base:
                raise ValueError(f"unknown variant param {key!r}; known: {sorted(base)}")
            if key in self.locked:
                raise ValueError(f"variant param {key!r} cannot be overridden from the config")
            default = base[key]
            if isinstance(default, bool):
                ok = isinstance(value, bool)
            elif isinstance(default, int):
                ok = isinstance(value, int) and not isinstance(value, bool)
            elif isinstance(default, float):
                ok = isinstance(value, int | float) and not isinstance(value, bool)
            else:
                ok = isinstance(value, type(default))
            if not ok:
                raise ValueError(
                    f"variant param {key!r} must be {type(default).__name__}, got {value!r}"
                )
            if key in self.choices and value not in self.choices[key]:
                raise ValueError(f"variant param {key!r} must be one of {self.choices[key]}")
            merged[key] = float(value) if isinstance(default, float) else value
        if fake_classifier:
            merged["provider"] = "fake-heuristic"
        if self.derive:
            merged |= self.derive(merged)
        return merged


VARIANTS: dict[str, Variant] = {
    "baseline": Variant(build_baseline),
    "system_one_eot": Variant(
        build_system_one_eot,
        params=SYSTEM_ONE_EOT_PARAMS,
        required_keys=("cloudflare_account_id", "cloudflare_api_token"),
    ),
    "system_one": Variant(
        build_system_one,
        designs=DESIGNS,
        default_design=DEFAULT_SYSTEM_ONE_DESIGN,
        required_keys=("cloudflare_account_id", "cloudflare_api_token"),
        choices={"question_set": tuple(QUESTION_SETS)},
        derive=_system_one_derived,
    ),
}


def missing_variant_keys(
    variant: Variant, settings: Settings, params: Mapping[str, Any] | None = None
) -> list[str]:
    if (params or variant.params).get("provider") == "fake-heuristic":
        return []  # offline smoke run: no Cloudflare calls
    return [k.upper() for k in variant.required_keys if not getattr(settings, k)]
