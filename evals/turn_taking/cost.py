"""Cost per component of a turn-taking run, for the scoring report.

Everything is read back from files the run already wrote, so older runs work too:

- `bot.log` (pipecat usage metrics, DEBUG): Anthropic prompt/completion tokens, TTS characters
  and STT audio seconds. One log per session (`bot.log`, `clean_bot.log`); a retried session
  appends to the same log, so retries are counted.
- `events.json`: one `system1.judgment` per classifier decision (the Cloudflare calls); a hedged
  judgment sent the request twice.
- `eval/judge_usage.jsonl` (scoring, written through `FDB_JUDGE_USAGE_LOG`): the Claude judge.
  Runs scored before that existed have no such file, so the judge cost shows "not recorded".

A quantity that is not on disk is reported as "not recorded", never estimated. Prices come from
`evals/common/usage.py` for Anthropic models; for the other services none is stored in this
repo, so they show "price unknown" next to the quantity (add one to `UNIT_PRICES` to enable it).

This module is stdlib-only and also imported by the scoring env (py3.11, see scoring/run_eval.py).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.common.usage import Usage, cost

# $ per unit, with the source, e.g. {"stt_seconds": (0.0001, "https://...")}. Empty on purpose:
# no AssemblyAI or Cloudflare Workers AI price is recorded in this repo.
UNIT_PRICES: dict[str, tuple[float, str]] = {}

_LLM = re.compile(r"AnthropicLLMService#\d+ prompt tokens: (\d+), completion tokens: (\d+)")
_TTS = re.compile(r"TTSService#\d+ usage characters: (\d+)")
_STT = re.compile(r"STTService#\d+ usage audio seconds: ([\d.]+)")
LOG_NAMES = ("bot.log", "clean_bot.log")
JUDGE_LOG = "judge_usage.jsonl"


@dataclass
class RunUsage:
    sessions: int = 0  # sessions whose bot.log exists
    llm: Usage | None = None  # None: no log at all (usage not recorded)
    tts_chars: int | None = None
    stt_secs: float | None = None
    classifier_calls: int | None = None  # None: no events.json to count from
    judge: Usage | None = None  # None: judge off or its usage was not recorded
    judge_enabled: bool = False


def parse_bot_log(text: str) -> tuple[Usage, int, float]:
    llm = Usage()
    for m in _LLM.finditer(text):
        llm.calls += 1
        llm.input_tokens += int(m.group(1))
        llm.output_tokens += int(m.group(2))
    return (
        llm,
        sum(int(m.group(1)) for m in _TTS.finditer(text)),
        sum(float(m.group(1)) for m in _STT.finditer(text)),
    )


def classifier_calls(events: list[dict[str, Any]]) -> int:
    """Requests sent to the classifier backend: one per judgment, two when it was hedged."""
    return sum(2 if e.get("hedged") else 1 for e in events if e.get("type") == "system1.judgment")


def read_judge_usage(path: Path) -> Usage | None:
    if not path.is_file():
        return None
    u = Usage()
    for line in path.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            u.calls += 1
            u.input_tokens += int(d.get("input_tokens") or 0)
            u.output_tokens += int(d.get("output_tokens") or 0)
    return u


def collect(run: Path, manifest: dict[str, Any]) -> RunUsage:
    out = RunUsage()
    sessions = 0
    llm, chars, secs, calls, saw_events = Usage(), 0, 0.0, 0, False
    for s in manifest.get("samples", []):
        d = run / s["version"] / s["task"] / s["id"]
        for name in LOG_NAMES:
            log = d / name
            if not log.is_file():
                continue
            sessions += 1
            u, c, t = parse_bot_log(log.read_text(errors="replace"))
            llm.add(u)
            chars += c
            secs += t
        for ev_name in ("events.json", "clean_events.json"):
            ev = d / ev_name
            if ev.is_file():
                saw_events = True
                calls += classifier_calls(json.loads(ev.read_text()))
    out.sessions = sessions
    if sessions:
        out.llm, out.tts_chars, out.stt_secs = llm, chars, secs
    if saw_events:
        out.classifier_calls = calls
    ev_cfg = (manifest.get("config") or {}).get("eval") or {}
    out.judge_enabled = ev_cfg.get("metrics") == "all"
    if out.judge_enabled:
        out.judge = read_judge_usage(run / "eval" / JUDGE_LOG)
    return out


def _usd(v: float | None) -> str:
    return "price unknown" if v is None else f"${v:.4f}"


def _unit_cost(key: str, qty: float | None) -> float | None:
    price = UNIT_PRICES.get(key)
    return None if price is None or qty is None else qty * price[0]


def report_lines(usage: RunUsage, manifest: dict[str, Any]) -> list[str]:
    """Markdown for the "Cost" section of report.md."""
    agent = manifest.get("agent_resolved") or {}
    llm_model = agent.get("anthropic_model")
    variant_params = agent.get("variant_params")
    if isinstance(variant_params, str):
        try:
            variant_params = json.loads(variant_params)
        except ValueError:
            variant_params = {}
    classifier = (variant_params or {}).get("model") if usage.classifier_calls else None
    ev_cfg = (manifest.get("config") or {}).get("eval") or {}
    judge_model = (ev_cfg.get("judge") or {}).get("model")
    n = len(manifest.get("samples", []))

    rows: list[tuple[str, str, float | None]] = []
    known: list[float] = []

    def add(name: str, quantity: str, usd: float | None) -> None:
        rows.append((name, quantity, usd))
        if usd is not None:
            known.append(usd)

    if usage.llm is None:
        add(f"LLM ({llm_model or '?'})", "not recorded (no bot.log)", None)
    else:
        u = usage.llm
        add(
            f"LLM ({llm_model or '?'})",
            f"{u.calls} calls, {u.input_tokens} in / {u.output_tokens} out tokens",
            cost(u, llm_model),
        )
    for key, label, qty, text in (
        (
            "tts_chars",
            f"TTS ({agent.get('tts_provider', '?')})",
            usage.tts_chars,
            f"{usage.tts_chars} characters",
        ),
        (
            "stt_seconds",
            f"STT ({agent.get('stt_provider', '?')})",
            usage.stt_secs,
            f"{usage.stt_secs:.0f} audio seconds (pipecat metric)"
            if usage.stt_secs is not None
            else "",
        ),
    ):
        add(label, text if qty is not None else "not recorded (no bot.log)", _unit_cost(key, qty))
    if usage.classifier_calls is None:
        add("System-one classifier (Cloudflare)", "not recorded (no events.json)", None)
    elif usage.classifier_calls == 0:
        add("System-one classifier (Cloudflare)", "not used by this variant", 0.0)
    else:
        add(
            f"System-one classifier (Cloudflare {classifier or '?'})",
            f"{usage.classifier_calls} requests (hedged duplicates included)",
            _unit_cost("cloudflare_requests", usage.classifier_calls),
        )
    if not usage.judge_enabled:
        add("Judge", "not used (metrics: local)", 0.0)
    elif usage.judge is None:
        add(
            f"Judge ({judge_model or '?'})",
            "not recorded (scored before judge usage logging)",
            None,
        )
    else:
        j = usage.judge
        add(
            f"Judge ({judge_model or '?'})",
            f"{j.calls} calls, {j.input_tokens} in / {j.output_tokens} out tokens",
            cost(j, judge_model),
        )

    lines = [
        "## Cost",
        "",
        f"{usage.sessions} sessions over {n} samples, read from `bot.log` and `events.json`; "
        "token cost counts input and output tokens only. A quantity that was not logged is "
        "shown as not recorded, and a service without a stored price as price unknown.",
        "",
        "| Component | Quantity | Cost |",
        "|---|---|---|",
    ]
    lines += [f"| {name} | {qty} | {_usd(usd)} |" for name, qty, usd in rows]
    total = sum(known)
    skipped = [name for name, _, usd in rows if usd is None]
    lines += [
        "",
        f"Total ${total:.4f} for the priced components"
        + (f" (excluding: {', '.join(skipped)})." if skipped else "."),
    ]
    if known and n:
        lines.append(f"Per sample: ${total / n:.4f}.")
    return lines
