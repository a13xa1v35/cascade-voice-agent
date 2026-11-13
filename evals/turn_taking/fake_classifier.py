"""Offline stand-in for the system-one model (`--fake-classifier`, tests). Bench/test only."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from pipecat.classifiers.base_classifier import (
    BaseClassifier,
    ClassifierImage,
    ClassifierQuestion,
    ClassifierResult,
    YesNoResult,
)
from pipecat.metrics.metrics import LLMTokenUsage


class HeuristicFakeClassifier(BaseClassifier):
    """Offline stand-in for Clef (`--fake-classifier`): keyword heuristics over the state,
    answering the four Jev questions in one request. For pipeline smoke tests only."""

    def __init__(self, latency_secs: float = 0.2, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._latency = latency_secs

    @property
    def model(self) -> str | None:
        return "fake-heuristic"

    async def _ask(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: Mapping[str, ClassifierQuestion],
        images: Sequence[ClassifierImage] = (),
    ) -> tuple[dict[str, ClassifierResult], LLMTokenUsage | None]:
        await asyncio.sleep(self._latency)
        text = (
            state.get("speaker_transcript_so_far", "") if isinstance(state, dict) else ""
        ).lower()
        words = text.split()
        open_ended = bool(words) and words[-1] in {"and", "but", "so", "is", "the", "to", "of", "a"}
        takes = any(w in text for w in ("wait", "stop", "actually", "hold on", "sorry", "but")) or (
            len(words) >= 4
        )
        scores = {
            "turn_complete": 0.05 if open_ended or len(words) < 2 else 0.9,
            "holding_floor": 0.85 if "hold on" in text or "one second" in text else 0.05,
            "addressed_to_agent": 0.1 if "dad" in text or "mom" in text else 0.9,
            "taking_floor": 0.95 if takes else 0.03,
            "new_request": 0.9 if takes else 0.1,
        }
        return {n: YesNoResult(probability=scores[n]) for n in questions}, None
