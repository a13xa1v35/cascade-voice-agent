"""Production plumbing for the system-one design: event sink and scorecard summary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from statistics import median
from typing import Any

from loguru import logger

EventRecord = Callable[..., None]  # CallRecorder.record(type_, **data)


def recording_sink(
    record: EventRecord, screening_id: str, *, keep_state: bool = False
) -> Callable[..., None]:
    """The controller's `events(type, **fields)` callable for a live call: every event goes to
    the call's event recorder (timeline, Redis, scorecard) and judgments also get one compact
    INFO line in the per-call log. The full state sent to the model is kept only with
    `keep_state` (DEBUG_PIPELINE): it repeats the transcript and recent turns."""

    def sink(type_: str, **fields: Any) -> None:
        if not keep_state:
            fields.pop("state", None)
        record(type_, **fields)
        if type_ == "system1.judgment":
            s = fields.get("scores") or {}
            scores = " ".join(f"{k[:4]}={v:.2f}" for k, v in s.items()) or "no scores"
            logger.info(
                f"[{screening_id}] system1 {fields.get('outcome')} {fields.get('latency_ms')}ms "
                f"{scores} -> {fields.get('action')} ({fields.get('transcript', '')[-60:]!r})"
            )

    return sink


def summarize_events(events: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """Counts for the scorecard: judgments, latency percentiles, outcomes and actions.
    None when the call did not use the system-one design."""
    judgments = [e["data"] for e in events if e["type"] == "system1.judgment"]
    actions = [e["data"] for e in events if e["type"] == "system1.action"]
    if not judgments and not actions:
        return None
    lat = sorted(j["latency_ms"] for j in judgments if j.get("latency_ms") is not None)
    taken: dict[str, int] = {}
    for d in [*judgments, *actions]:
        a = d.get("action")
        if a and a != "keep_listening":
            taken[a] = taken.get(a, 0) + 1
    return {
        "judgments": len(judgments),
        "latency_p50_ms": round(median(lat)) if lat else None,
        "latency_p95_ms": lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None,
        "failed": sum(1 for j in judgments if not str(j.get("outcome", "ok")).startswith("ok")),
        "hedged": sum(1 for j in judgments if j.get("hedged")),
        "actions": dict(sorted(taken.items())),
    }
