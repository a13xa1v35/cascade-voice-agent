"""Print a call's scorecard.

    uv run python -m hr_screener.observability.report [screening_id]     (or: make report ID=<id>)

Reads the database (DATABASE_URL) and Redis (REDIS_URL), so it works without the server. While
the call's events are still in Redis the report is computed from them in full; after they
expire (EVENTS_TTL_DAYS) it is rebuilt from the stored call_metrics and tool_calls, without the
per-exchange detail. With no id it uses the most recently created screening.
"""

import argparse
import asyncio
import sys
from typing import Any

from redis.asyncio import Redis

from hr_screener.config import Settings
from hr_screener.storage.db import make_engine
from hr_screener.storage.store import ScreeningStore

SNIPPET = 60


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def _stats(stats: dict[str, Any] | None) -> str:
    if not stats or stats.get("p50") is None:
        return "-"
    n = f"  (n={stats['count']})" if stats.get("count") else ""
    return (
        f"p50 {_fmt(stats['p50'], 's')}  p95 {_fmt(stats['p95'], 's')}  "
        f"max {_fmt(stats['max'], 's')}{n}"
    )


def _snippet(text: str | None) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= SNIPPET else text[: SNIPPET - 1] + "…"


def _section(title: str, rows: list[tuple[str, str]]) -> list[str]:
    width = max((len(k) for k, _ in rows), default=0)
    return ["", title, "-" * len(title), *[f"  {k:<{width}}  {v}" for k, v in rows]]


def render(card: dict[str, Any]) -> str:
    """Readable text for a scorecard dict (as stored / returned by the API)."""
    out = [f"Scorecard for screening {card['screening_id']}"]
    if card.get("partial"):
        out.append("PARTIAL: no event timeline for this call, only the task section is available")
    elif card.get("exchanges_expired"):
        out.append(
            f"{card.get('event_count', 0)} events over {_fmt(card.get('duration_secs'), 's')}"
        )
        out.append(
            "Event timeline expired: showing the stored metrics and tool calls; exchanges, "
            "stage medians and endpoint-delay stats are no longer available"
        )
    else:
        out.append(
            f"{card.get('event_count', 0)} events over {_fmt(card.get('duration_secs'), 's')}"
        )

    if r := card.get("responsiveness"):
        rows = [
            ("reply latency", _stats(r["reply_latency"])),
            ("tool-turn latency", _stats(r["tool_turn_latency"])),
            ("llm time to first byte", _stats(r.get("llm_ttfb"))),
            ("first greeting", _fmt(r["first_greeting_secs"], "s")),
        ]
        rows += [(f"stage: {k}", _fmt(v, "s")) for k, v in r["stage_medians"].items()]
        out += _section("Responsiveness (stage values are medians)", rows)

    if t := card.get("turn_taking"):
        rate = t.get("false_endpoint_rate")
        rate_text = f"{t['false_endpoints']} ({rate:.0%})" if rate is not None else "-"
        out += _section(
            "Turn taking",
            [
                ("user turns", _fmt(t["user_turns"])),
                ("false endpoints", rate_text),
                ("endpoint delay", _stats(t.get("endpoint_delay"))),
                ("silence fallbacks", _fmt(t["silence_fallbacks"])),
                ("barge-ins", _fmt(t["barge_ins"])),
                ("unsafe hang-up", _fmt(t["unsafe_hangup"])),
                ("hang-up cancels", _fmt(t.get("hangup_cancels", 0))),
                ("hang-up wait", _fmt(t.get("hangup_wait_secs"), "s")),
            ],
        )

    if so := card.get("system_one"):
        actions = ", ".join(f"{k} x{v}" for k, v in so["actions"].items()) or "none"
        out += _section(
            "System-one turn taking",
            [
                ("judgments", f"{so['judgments']} ({so['failed']} failed, {so['hedged']} hedged)"),
                (
                    "latency",
                    f"p50 {_fmt(so['latency_p50_ms'], ' ms')}  "
                    f"p95 {_fmt(so['latency_p95_ms'], ' ms')}",
                ),
                ("actions", actions),
            ],
        )

    k = card["task"]
    task_rows = [
        ("status", _fmt(k["status"])),
        ("outcome", _fmt(k["outcome"])),
        ("end reason", _fmt(k["end_reason"])),
        ("facts complete", _fmt(k["facts_complete"])),
    ]
    task_rows += [
        ("tool errors", _fmt(k["tool_errors"])),
        ("tool order valid", _fmt(k["tool_order_valid"])),
        ("booked only if qualified", _fmt(k["booked_only_if_qualified"])),
        ("goodbye spoken", _fmt(k["goodbye_spoken"])),
    ]
    task_rows += [("  error", e) for e in k["tool_error_list"]]
    task_rows += [("  order problem", p) for p in k["tool_order_problems"]]
    out += _section("Task", task_rows)

    if c := card.get("cost"):
        out += _section(
            "Cost",
            [
                ("llm calls", _fmt(c["llm_calls"])),
                ("prompt tokens", _fmt(c["prompt_tokens"])),
                ("completion tokens", _fmt(c["completion_tokens"])),
                ("  of which reasoning", _fmt(c.get("reasoning_tokens"))),
                ("cache read tokens", _fmt(c.get("cache_read_tokens"))),
                ("wasted llm calls", _fmt(c["wasted_llm_calls"])),
                ("llm errors", _fmt(c.get("llm_errors"))),
                ("llm retries", _fmt(c.get("llm_retries"))),
                ("tts chars", _fmt(c["tts_chars"])),
            ],
        )

    if (kb := card.get("knowledge")) and (kb["searches"] or kb["questions_referred"]):
        # Only calls that used the knowledge base: the section would be all zeros otherwise.
        out += _section(
            "Knowledge base",
            [
                ("searches", _fmt(kb["searches"])),
                ("no match", _fmt(kb["no_match"])),
                ("unavailable", _fmt(kb["unavailable"])),
                (
                    "search time",
                    f"p50 {_fmt(kb['search_ms']['p50'], ' ms')}  "
                    f"max {_fmt(kb['search_ms']['max'], ' ms')}",
                ),
                ("late results", _fmt(kb["late_results"])),
                ("questions referred", _fmt(kb["questions_referred"])),
            ],
        )

    if fr := card.get("frustration"):
        out += _section(
            "Frustration",
            [
                ("checks", _fmt(fr["checks"])),
                ("max probability", _fmt(fr["max_probability"])),
                ("last probability", _fmt(fr["last_probability"])),
                ("frustrated checks", _fmt(fr["frustrated_checks"])),
                ("errors", _fmt(fr["errors"])),
                ("notes sent to Sofia", _fmt(fr["notes"])),
            ],
        )

    if card.get("exchanges"):
        out += ["", "Exchanges", "---------"]
        for x in card["exchanges"]:
            flags = " fallback" if x["silence_fallback"] else ""
            tools = f" tools={','.join(x['tools'])}" if x["tools"] else ""
            out.append(
                f"  #{x['index']:<2} t={x['turn_ended_t']:>7.2f}s  {x['kind']:<14}"
                f" reply={_fmt(x['reply_latency_secs'], 's'):>7}"
                f" endpoint={_fmt(x['endpoint_delay_secs'], 's'):>6}{flags}{tools}"
            )
            out.append(f"       user: {_snippet(x['user_text'])}")
            if x["bot_text"]:
                out.append(f"       bot:  {_snippet(x['bot_text'])}")

    if card.get("tool_calls"):
        out += ["", "Tool calls (in order)", "---------------------"]
        for i, call in enumerate(card["tool_calls"], 1):
            args = ", ".join(f"{k}={_snippet(str(v))}" for k, v in call["args"].items())
            result = f" -> {_snippet(str(call['result']))}" if call["result"] is not None else ""
            out.append(
                f"  {i}. t={call['t']:>7.2f}s  {call['name']}({args}) [{call['status']}]{result}"
            )
    return "\n".join(out)


async def _run(screening_id: str | None, settings: Settings) -> int:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    engine = make_engine(settings.database_url)
    try:
        store = ScreeningStore(engine, redis)
        screening_id = screening_id or await store.latest_screening_id()
        if screening_id is None:
            print("no screenings found", file=sys.stderr)
            return 1
        card = await store.load_scorecard(screening_id)
        if card is None:
            print(f"screening {screening_id} not found", file=sys.stderr)
            return 1
        print(render(card))
        return 0
    finally:
        await engine.dispose()
        await redis.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a call scorecard (stored, else computed from the Redis events)."
    )
    parser.add_argument("screening_id", nargs="?", help="default: the most recent screening")
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.screening_id or None, Settings())))


if __name__ == "__main__":
    main()
