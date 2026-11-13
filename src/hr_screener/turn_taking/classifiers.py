"""System-one helpers: small decision-model calls that sit beside the main LLM."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pipecat.classifiers.base_classifier import (
    BaseClassifier,
    ChoiceResult,
    ClassifierError,
    ClassifierImage,
    ClassifierQuestion,
    ClassifierResult,
    ScoreResult,
    YesNoResult,
)
from pipecat.metrics.metrics import LLMTokenUsage
from pipecat.utils.asyncio.task_manager import BaseTaskManager

# add(type, **fields): EventLog.add in the bench
EventSink = Callable[..., None]


def _dump(result: ClassifierResult) -> dict[str, Any]:
    if isinstance(result, YesNoResult):
        return {"probability": round(result.probability, 4)}
    if isinstance(result, ChoiceResult):
        return {
            "choice": result.choice,
            "confidence": round(result.confidence, 4),
            "probabilities": {k: round(v, 4) for k, v in result.probabilities.items()},
        }
    if isinstance(result, ScoreResult):
        return {"score": round(result.score, 4), "confidence": round(result.confidence, 4)}
    return {"result": str(result)}


def _snapshot(state: Any, limit: int = 400) -> Any:
    if isinstance(state, str):
        return state[-limit:]
    if isinstance(state, Mapping):
        return {k: (v[-limit:] if isinstance(v, str) else v) for k, v in state.items()}
    return state


class HedgedClassifier(BaseClassifier):
    """Latency hedge for a bimodal backend: ask `primary`; if it has not answered within
    `hedge_after_secs` (or it failed), ask `secondary` too and take the first success. The
    loser is cancelled. `ClassifierError` is raised only if both fail. Give the two
    classifiers separate HTTP clients, so a slow connection does not stall the duplicate.

    After each call `last_call` holds {"hedged": bool, "winner": "primary" | "secondary"}."""

    def __init__(
        self,
        primary: BaseClassifier,
        secondary: BaseClassifier,
        *,
        hedge_after_secs: float = 0.45,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._primary = primary
        self._secondary = secondary
        self._hedge_after = hedge_after_secs
        self.last_call: dict[str, Any] = {}

    @property
    def model(self) -> str | None:
        return self._primary.model

    @property
    def supports_images(self) -> bool:
        return self._primary.supports_images and self._secondary.supports_images

    async def setup(self, task_manager: BaseTaskManager) -> None:
        await super().setup(task_manager)
        await self._primary.setup(task_manager)
        await self._secondary.setup(task_manager)

    async def cleanup(self) -> None:
        await super().cleanup()
        await self._primary.cleanup()
        await self._secondary.cleanup()

    async def _ask(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: Mapping[str, ClassifierQuestion],
        images: Sequence[ClassifierImage] = (),
    ) -> tuple[dict[str, ClassifierResult], LLMTokenUsage | None]:
        tasks: dict[asyncio.Task, str] = {
            asyncio.ensure_future(self._primary._ask(state, questions, images)): "primary"
        }
        hedged = False
        errors: list[str] = []
        try:
            done, _ = await asyncio.wait(tasks, timeout=self._hedge_after)
            while True:
                for t in done:
                    name = tasks.pop(t)
                    if t.exception() is None:
                        self.last_call = {"hedged": hedged, "winner": name}
                        return t.result()
                    errors.append(f"{name}: {t.exception()}")
                if not hedged:  # slow or failed primary: send the duplicate
                    hedged = True
                    tasks[asyncio.ensure_future(self._secondary._ask(state, questions, images))] = (
                        "secondary"
                    )
                if not tasks:
                    self.last_call = {"hedged": hedged, "winner": None}
                    raise ClassifierError("; ".join(errors))
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:  # the loser, or everything if the caller timed us out
                t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)


class LoggingClassifier(BaseClassifier):
    """Delegates every question to `inner` and records it as a `system1.judgment` event:
    the state, verdict or probabilities, latency, and the outcome (ok / error / timeout).
    Errors and timeouts are re-raised untouched, so the caller's fallback still happens."""

    def __init__(self, inner: BaseClassifier, sink: EventSink, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._inner = inner
        self._sink = sink

    @property
    def model(self) -> str | None:
        return self._inner.model

    @property
    def supports_images(self) -> bool:
        return self._inner.supports_images

    async def setup(self, task_manager: BaseTaskManager) -> None:
        await super().setup(task_manager)
        await self._inner.setup(task_manager)

    async def cleanup(self) -> None:
        await super().cleanup()
        await self._inner.cleanup()

    async def _ask(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: Mapping[str, ClassifierQuestion],
        images: Sequence[ClassifierImage] = (),
    ) -> tuple[dict[str, ClassifierResult], LLMTokenUsage | None]:
        started = time.perf_counter()
        record: dict[str, Any] = {"state": _snapshot(state), "questions": list(questions)}
        try:
            results, usage = await self._inner._ask(state, questions, images)
        except ClassifierError as e:
            self._log(record, started, f"error: {e}")
            raise
        except BaseException as e:  # a timeout cancels the call: record it, then propagate
            self._log(
                record,
                started,
                f"cancelled ({type(e).__name__}): superseded by new speech or timed out",
            )
            raise
        record["results"] = {name: _dump(r) for name, r in results.items()}
        self._log(record, started, "ok")
        return results, usage

    def _log(self, record: dict[str, Any], started: float, outcome: str) -> None:
        self._sink(
            "system1.judgment",
            latency_ms=round((time.perf_counter() - started) * 1000),
            outcome=outcome,
            **getattr(self._inner, "last_call", {}),
            **record,
        )
