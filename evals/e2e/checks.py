"""Hard checks: deterministic pass/fail on a finished `RunRecord`.

Pure functions of the record and the scenario's `Expect`; no I/O, so each check is unit
tested with canned records. A run is only checked when the harness itself succeeded (the
drop condition fired, the calls finished); otherwise it is reported as invalid, never as an
Sofia failure. Silence is not that kind of problem: see `check_responsive`.
"""

import re
from collections.abc import Callable
from fnmatch import fnmatch
from typing import Any

from evals.common.language import ES_WORDS, detect, fold
from evals.e2e.drops import TOOL_FIELD
from evals.e2e.records import (
    CallRecord,
    CheckResult,
    RunRecord,
    ToolCallRecord,
    events_of,
    other_language,
    search_outcome,
    split_at_switch,
)
from evals.e2e.scenarios import Expect, KbExpect
from hr_screener.agent.prompt_text import PROMPT
from hr_screener.observability.metrics import ToolCall, build_tool_calls, tool_order_problems

Check = Callable[[RunRecord, Expect], CheckResult]


def _ok(name: str, detail: str = "") -> CheckResult:
    return CheckResult(name, True, detail)


def _fail(name: str, detail: str) -> CheckResult:
    return CheckResult(name, False, detail)


def _tool_names(call: CallRecord) -> list[str]:
    return [t.name for t in call.tool_calls]


def check_responsive(run: RunRecord, expect: Expect) -> CheckResult:
    """Sofia answered every time the candidate spoke, and did not have to give up the call.

    Fails when no reply came within `reply_timeout_secs` (`unresponsive`: a stalled or failed
    LLM request that nothing recovered) or when the call ended with end reason `llm_error` (the
    LLM failed twice, so the candidate got a spoken apology instead of a screening). Either way
    the candidate was not served, which is Sofia's failure whatever the provider's reason; the
    LLM errors seen in the call are listed. Quota errors are the exception, and never reach
    here: they make the run invalid (`provider_quota`)."""
    problems = []
    for call in run.calls:
        if call.unresponsive:
            problems.append(f"call {call.index}: no reply from Sofia in the reply timeout")
        elif call.end_reason == "llm_error":
            problems.append(f"call {call.index}: ended with an apology (LLM kept failing)")
        else:
            continue
        if call.llm_errors:
            problems[-1] += f"; LLM errors: {'; '.join(e[:120] for e in call.llm_errors[:3])}"
    return _fail("responsive", " | ".join(problems)) if problems else _ok("responsive")


def check_attempts(run: RunRecord, expect: Expect) -> CheckResult:
    got = tuple(c.attempt for c in run.calls)
    if got == expect.attempts:
        return _ok("attempts", str(got))
    return _fail("attempts", f"attempts {got}, expected {expect.attempts}")


def check_modes(run: RunRecord, expect: Expect) -> CheckResult:
    got = tuple(c.mode for c in run.calls)
    if got == expect.modes:
        return _ok("modes", str(got))
    return _fail("modes", f"call modes {got}, expected {expect.modes}")


def check_chain(run: RunRecord, expect: Expect) -> CheckResult:
    """previous_screening_id links each call to the one before it (or to the setup history)."""
    live_ids = {c.screening_id for c in run.calls}
    setup = [s for s in run.screenings if s["id"] not in live_ids]
    problems = []
    for i, call in enumerate(run.calls):
        previous = setup[-1]["id"] if setup else None
        want = run.calls[i - 1].screening_id if i > 0 else previous
        if call.previous_screening_id != want:
            problems.append(f"call {call.index} previous={call.previous_screening_id}, want {want}")
    return _fail("chain", "; ".join(problems)) if problems else _ok("chain")


def check_final_state(run: RunRecord, expect: Expect) -> CheckResult:
    if not run.calls:
        return _fail("final_state", "no calls")
    last = run.calls[-1]
    problems = []
    if last.status != expect.status:
        problems.append(f"status {last.status}, expected {expect.status}")
    if last.outcome != expect.outcome:
        problems.append(f"outcome {last.outcome}, expected {expect.outcome}")
    return _fail("final_state", "; ".join(problems)) if problems else _ok("final_state")


def check_call_states(run: RunRecord, expect: Expect) -> CheckResult:
    """Per-call outcome / status / end reason the scenario pins down (e.g. callback, superseded)."""
    problems = []
    for field_, wanted, attr in (
        ("outcome", expect.call_outcomes, "outcome"),
        ("status", expect.call_statuses, "status"),
        ("end reason", expect.end_reasons, "end_reason"),
    ):
        for index, value in wanted.items():
            got = getattr(run.calls[index - 1], attr) if index <= len(run.calls) else None
            if got != value:
                problems.append(f"call {index} {field_} {got}, expected {value}")
    return _fail("call_states", "; ".join(problems)) if problems else _ok("call_states")


def check_booking(run: RunRecord, expect: Expect) -> CheckResult:
    problems = []
    if expect.booked and len(run.bookings) != 1:
        problems.append(f"{len(run.bookings)} bookings, expected exactly 1")
    if not expect.booked and run.bookings:
        problems.append(f"booking exists but none expected: {run.bookings}")
    if expect.booking_unchanged and run.bookings != run.bookings_before:
        problems.append(f"booking changed: {run.bookings_before} -> {run.bookings}")
    return _fail("booking", "; ".join(problems)) if problems else _ok("booking")


def _same(field_: str, saved: Any, wanted: Any) -> bool:
    if field_ == "experience":
        return bool(saved)
    if isinstance(wanted, list):
        return sorted(saved or []) == sorted(wanted)
    return saved == wanted


def check_facts(run: RunRecord, expect: Expect) -> CheckResult:
    """Every saved fact equals the persona's (or the corrected value); required ones exist."""
    problems = []
    problems.extend(
        f"{name} not saved"
        for name in expect.required_facts
        if run.final_facts.get(name) in (None, [], "")
    )
    for name, wanted in run.expected_facts.items():
        saved = run.final_facts.get(name)
        if saved in (None, [], ""):
            continue
        if not _same(name, saved, wanted):
            problems.append(f"{name}: saved {saved!r}, expected {wanted!r}")
    return _fail("facts", "; ".join(problems)) if problems else _ok("facts")


def check_facts_at_start(run: RunRecord, expect: Expect) -> CheckResult:
    problems = []
    for index, minimum in expect.min_facts_at_start.items():
        if index > len(run.calls):
            continue
        have = len(run.calls[index - 1].fields_at_start)
        if have < minimum:
            problems.append(f"call {index} started with {have} facts, expected >= {minimum}")
    return _fail("facts_at_start", "; ".join(problems)) if problems else _ok("facts_at_start")


def _as_tool_call(t: ToolCallRecord) -> ToolCall:
    return ToolCall(t=0.0, name=t.name, args=t.args, result=t.result, status=t.status)


def check_tool_order(run: RunRecord, expect: Expect) -> CheckResult:
    """`metrics.tool_order_problems` on every call. A call that was cut off (no end_call by
    design) is not blamed for the missing end_call."""
    problems = []
    for call in run.calls:
        found = tool_order_problems([_as_tool_call(t) for t in call.tool_calls])
        if call.end_reason != "end_call":
            found = [p for p in found if p != "no successful end_call"]
        problems += [f"call {call.index}: {p}" for p in found]
    return _fail("tool_order", "; ".join(problems)) if problems else _ok("tool_order")


def check_no_rerecord(run: RunRecord, expect: Expect) -> CheckResult:
    """A call must not record a fact that was already on file when it started (a
    correction, `allow_rerecord`, excepted)."""
    if not expect.check_rerecord:
        return _ok("no_rerecord", "not applicable")
    problems = []
    for call in run.calls:
        for name in _tool_names(call):
            field_ = TOOL_FIELD.get(name)
            if field_ and field_ in call.fields_at_start and field_ not in expect.allow_rerecord:
                problems.append(f"call {call.index} re-recorded {field_} ({name})")
    return _fail("no_rerecord", "; ".join(problems)) if problems else _ok("no_rerecord")


def check_final_tools(run: RunRecord, expect: Expect) -> CheckResult:
    if not run.calls:
        return _fail("final_tools", "no calls")
    names = _tool_names(run.calls[-1])
    problems = [f"{t} never called" for t in expect.must_call if t not in names]
    for pattern in expect.must_not_call:
        hit = [n for n in names if fnmatch(n, pattern)]
        if hit:
            problems.append(f"called {sorted(set(hit))} (must not: {pattern})")
    if expect.only_tools is not None:
        extra = [n for n in names if n not in expect.only_tools]
        if extra or not names:
            problems.append(f"tools {names}, expected only {list(expect.only_tools)}")
    return _fail("final_tools", "; ".join(problems)) if problems else _ok("final_tools", str(names))


def check_language(run: RunRecord, expect: Expect) -> CheckResult:
    bad = [(c.index, d) for c in run.calls for d in c.drift if d.drifted]
    if not bad:
        return _ok("language")
    shown = "; ".join(
        f"call {i} turn {d.turn} detected {d.lang} (es={d.es_hits} en={d.en_hits}): {d.text[:70]!r}"
        for i, d in bad[:3]
    )
    return _fail("language", f"{len(bad)} drifted turn(s): {shown}")


def check_language_switch(run: RunRecord, expect: Expect) -> CheckResult:
    """The candidate asked to change language: `switch_language` was called exactly once, with
    the other language, and the `language_switched` event went from the run language to it.
    Sofia's turns before and after the switch being in the right language is `check_language`
    (re-judged at the switch by `records.mark_switch_drift`); here at least one turn after the
    turn that carries the switch must be recognisably in the new language, or that check would
    pass on turns too short to tell.

    Misses: a switch that happens at the wrong moment (before the candidate asked, if the
    request is not in the transcript the check cannot tell), and a new language that Sofia
    speaks only in short turns (all "unknown")."""
    new = other_language(run.language)
    calls = [t for c in run.calls for t in c.tool_calls if t.name == "switch_language"]
    problems = []
    if len(calls) != 1:
        problems.append(f"{len(calls)} switch_language call(s), expected 1")
    elif calls[0].args.get("language") != new or not calls[0].ok:
        problems.append(
            f"switch_language({calls[0].args}) status {calls[0].status}, expected {new}"
        )
    events = [e for c in run.calls for e in events_of(c, "language_switched")]
    if len(events) != 1 or (events[0]["data"].get("from"), events[0]["data"].get("to")) != (
        run.language,
        new,
    ):
        problems.append(f"language_switched events {[e['data'] for e in events]}")
    parts = [p for c in run.calls if (p := split_at_switch(c))]
    if parts and not any(d.lang == new for _, _, after in parts for d in after):
        problems.append(f"no Sofia turn after the switch detected as {new}")
    return _fail("language_switch", "; ".join(problems)) if problems else _ok("language_switch")


# --- knowledge-base checks (only for scenarios with `Expect.kb`) ----------------------------


def _kb(expect: Expect) -> KbExpect:
    assert expect.kb is not None  # the kb checks are only run for knowledge scenarios
    return expect.kb


def _searches(run: RunRecord) -> list[tuple[CallRecord, ToolCallRecord]]:
    return [(c, t) for c in run.calls for t in c.tool_calls if t.name == "search_knowledge"]


def _search_events(run: RunRecord) -> list[dict[str, Any]]:
    return [e["data"] for c in run.calls for e in events_of(c, "kb_search")]


_QUESTION = re.compile(r"[^.!?]*\?")


def _questions(text: str) -> list[set[str]]:
    """The word sets of the questions in a reply (the part after an opening "¿" if any)."""
    out = []
    for q in _QUESTION.findall(text):
        words = set(re.sub(r"[^\w\s]", " ", fold(q.split("¿")[-1])).split())
        if len(words) >= 3:
            out.append(words)
    return out


def check_no_repeated_question(run: RunRecord, expect: Expect) -> CheckResult:
    """No Sofia reply asks the same question twice (README, lesson 17: she asked the next
    question with a record_* call, and the forced follow-up reply asked it again).

    Two questions in one reply count as the same when at least 80% of the words of the
    shorter one are in the other. Misses: a repeat reworded enough to share fewer words, and
    a repeat spread over two replies; flags two genuinely different questions that share most
    of their words (rare in these calls)."""
    bad = []
    for c in run.calls:
        for i, t in enumerate(x for x in c.transcript if x.role == "agent"):
            qs = _questions(t.text)
            if any(
                len(a & b) >= 0.8 * min(len(a), len(b))
                for n, a in enumerate(qs)
                for b in qs[n + 1 :]
            ):
                bad.append(f"call {c.index} reply {i}: {t.text[:120]!r}")
    if bad:
        return _fail("no_repeated_question", "; ".join(bad[:3]))
    return _ok("no_repeated_question")


def check_kb_searched(run: RunRecord, expect: Expect) -> CheckResult:
    """`search_knowledge` was called for the knowledge questions and not for anything else.

    Limit: it counts calls in the whole conversation against the scenario's bounds; a search
    made on the wrong turn (for a screening answer) stays within the bounds and passes unless
    it pushes the count above the maximum."""
    kb = _kb(expect)
    n = len(_searches(run))
    if kb.min_searches <= n <= kb.max_searches:
        return _ok("kb_searched", f"{n} search_knowledge call(s)")
    return _fail(
        "kb_searched",
        f"{n} search_knowledge call(s), expected {kb.min_searches} to {kb.max_searches}",
    )


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# English content words that are not Spanish words: function words alone would call most short
# queries "unknown" (`evals/common/language.py` needs three stopwords).
ENGLISH_QUERY_WORDS = _words(
    """
    pay paid payment payments salary wage wages rate rates hour hours much many contract
    contracts tax taxes invoice invoices invoicing lessons lesson classes private cancel
    cancelled cancellation student students family families documents certificate insurance
    fee fees freelance monthly weekly income withholding withheld worker employee employees
    session requirements requirement
    """
)


def english_query_evidence(query: str) -> tuple[bool, str]:
    """(looks English, why). English when the stopword detector says "en", or when at least
    two English content words appear and no Spanish stopword does.

    Limit: a one-word or all-proper-noun query ("VAT", "Verifactu", "modelo 130") has no
    evidence either way and passes."""
    det = detect(query)
    if det.lang == "en":
        return True, f"en={det.en_hits} es={det.es_hits}"
    tokens = set(re.findall(r"[a-z]+", fold(query)))
    content = sorted(tokens & ENGLISH_QUERY_WORDS)
    spanish = len(tokens & ES_WORDS)
    if len(content) >= 2 and spanish == 0:
        return True, f"English words {content}"
    return False, ""


def _queries(run: RunRecord) -> list[str]:
    """Every query the model sent: the recorded `kb_search` events, plus the tool arguments
    of searches that never ran (already_searching, empty_query)."""
    queries = [str(d.get("query", "")) for d in _search_events(run)]
    queries += [
        str(t.args.get("query", ""))
        for _, t in _searches(run)
        if isinstance(t.args, dict) and str(t.args.get("query", "")) not in queries
    ]
    return [q for q in queries if q.strip()]


def check_kb_query_spanish(run: RunRecord, expect: Expect) -> CheckResult:
    """Every `search_knowledge` query is Spanish (the knowledge base is Spanish; the model
    must translate the candidate's English). Catches clearly English queries only."""
    bad = []
    for query in _queries(run):
        english, why = english_query_evidence(query)
        if english:
            bad.append(f"{query!r} ({why})")
    if bad:
        return _fail("kb_query_spanish", f"query not in Spanish: {'; '.join(bad[:3])}")
    return _ok("kb_query_spanish", f"{len(_queries(run))} quer(ies)")


# Quantities and form names the knowledge base holds. Only these are tested: an answer from
# memory in prose (no number, no form) is not detectable here; the judge's faithfulness
# question looks at it.
KB_FACT_MARKERS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\d+(?:[.,]\d+)?\s*(?:€|eur\b|euros?\b)",  # 16 euros, 16 €
        r"€\s*\d",
        r"\d+(?:[.,]\d+)?\s*(?:%|por ciento|percent|per cent)",  # 15%, 15 por ciento
        r"\b(?:quince|siete|catorce|dieciseis|dieciocho|veintidos)\s+(?:por ciento|euros)",
        r"\b(?:fifteen|seven)\s+(?:percent|per cent)",
        r"\b(?:fourteen|sixteen|eighteen|twenty-two)\s+euros?\b",
        r"modelos?\s*(?:130|111|303|036|037)",
        r"\bverifactu\b",
    )
)


def kb_fact_markers(text: str) -> list[str]:
    folded = fold(text)
    return [m.group(0) for p in KB_FACT_MARKERS if (m := p.search(folded))]


def check_kb_no_answer_from_memory(run: RunRecord, expect: Expect) -> CheckResult:
    """A call where no search returned chunks must not state knowledge-base facts (euro
    amounts, percentages, form names). Applies to calls with no search at all, and to calls
    where every search was `no_match` or failed.

    Limits: only these numeric/form markers are looked for; a call with at least one
    successful search is not examined (the record does not align events with turns, so a
    fact stated before the search cannot be told from one stated after it); prose answers
    without a number or form name pass."""
    problems = []
    for call in run.calls:
        outcomes = [search_outcome(e["data"]) for e in events_of(call, "kb_search")]
        if "found" in outcomes:
            continue
        for turn in call.saved_transcript:
            if turn.get("role") != "assistant":
                continue
            if found := kb_fact_markers(turn.get("text", "")):
                problems.append(f"call {call.index}: {found} in {turn['text'][:80]!r}")
    if problems:
        return _fail(
            "kb_no_answer_from_memory",
            "knowledge facts without a returned chunk: " + "; ".join(problems[:3]),
        )
    return _ok("kb_no_answer_from_memory")


# Phrases the model uses to announce a lookup. The holding line is played for it; saying
# one of these too doubles the filler ("Let me check that. ... Let me check that.").
FILLER = re.compile(
    r"\b(?:let me (?:check|look|see|find|have a look|pull)|let's (?:check|see)|one moment|"
    r"just a (?:moment|second|sec)|give me a (?:moment|second)|hold on|i(?:'ll| will) "
    r"(?:check|look|find)|i am (?:checking|looking)|i'm (?:checking|looking)|"
    r"dejame (?:comprobar|mirar|ver|consultar|revisar|buscar)|un momento|un segundo|"
    r"un momentito|voy a (?:comprobar|mirar|consultar|revisar|buscar)|lo compruebo|"
    r"lo miro|lo consulto|espera un)\b"
)


def check_kb_no_doubled_holding_line(run: RunRecord, expect: Expect) -> CheckResult:
    """The holding line is played once per search and the model adds no filler of its own.

    The line is not in the stored transcript (kept out of the LLM context); it is in the
    `kb_holding_line` events and, in the text channel, in the live reply it is flushed with.
    In that reply anything besides the line is the model's text written before the tool call;
    a filler phrase there, or the line repeated, is a doubled line.

    Limit: a filler in the reply that comes after the result is not counted (it is not the
    same moment as the holding line), and a filler that the transcript does not show passes."""
    problems = []
    for call in run.calls:
        lines = [str(e["data"].get("text", "")) for e in events_of(call, "kb_holding_line")]
        lines = [line for line in lines if line]
        if not lines:
            continue
        line_set = set(lines)
        live = [t.text for t in call.transcript if t.role == "agent"]
        for text in live:
            hit = next((line for line in line_set if line in text), None)
            if hit is None:
                continue
            if text.count(hit) > 1:
                problems.append(f"call {call.index}: holding line twice in {text[:80]!r}")
            rest = fold(text.replace(hit, " "))
            if FILLER.search(rest):
                problems.append(f"call {call.index}: model filler next to the line: {text[:80]!r}")
        if sum(t.count(line) for t in live for line in line_set) > len(lines):
            problems.append(f"call {call.index}: more holding lines than searches")
    if problems:
        return _fail("kb_no_doubled_holding_line", "; ".join(problems[:3]))
    return _ok("kb_no_doubled_holding_line")


def check_kb_question_referred(run: RunRecord, expect: Expect) -> CheckResult:
    """When the scenario expects the hand-off (`referred` True): exactly one
    `refer_to_recruiter` call and exactly one stored `referred_questions` row Sofia wrote
    (`automatic` false). The system's own rows (`automatic` true, written at finalize for a
    search nobody referred) are allowed and not counted. Otherwise: not checked.

    Limits: it does not read what the question says (it can be vague or in the wrong
    language), nor whether Sofia told the candidate a colleague would get back to them before
    the call; `judge` and the transcript show it. A scenario with several unanswered
    questions would need a different count."""
    if not _kb(expect).referred:
        return _ok("kb_question_referred", "not applicable")
    calls = [t for c in run.calls for t in c.tool_calls if t.name == "refer_to_recruiter"]
    rows = [r for c in run.calls for r in c.referred_questions if not r.get("automatic")]
    problems = []
    if len(calls) != 1:
        problems.append(f"{len(calls)} refer_to_recruiter call(s), expected 1")
    if len(rows) != 1:
        problems.append(f"{len(rows)} row(s) written by Sofia, expected 1")
    if problems:
        return _fail("kb_question_referred", "; ".join(problems))
    return _ok("kb_question_referred", "one call, one row")


_RESUME_TOOLS = ("record_*", "list_onboarding_slots", "schedule_onboarding")


def check_kb_screening_resumes(run: RunRecord, expect: Expect) -> CheckResult:
    """After the first search the screening goes on: a `record_*` or booking tool runs later
    in the same call (the question that was pending when the candidate asked).

    Limit: it does not tell which fact was pending; any later record or booking tool counts.
    Not applied to closed calls (no screening)."""
    if not _kb(expect).resume:
        return _ok("kb_screening_resumes", "not applicable")
    for call in run.calls:
        names = [t.name for t in call.tool_calls]
        if "search_knowledge" not in names:
            continue
        after = names[names.index("search_knowledge") + 1 :]
        if any(fnmatch(n, p) for n in after for p in _RESUME_TOOLS):
            return _ok("kb_screening_resumes")
        return _fail(
            "kb_screening_resumes",
            f"call {call.index}: no record or booking tool after the search (tools after: {after})",
        )
    return _fail("kb_screening_resumes", "no call searched")


def _end_call_errors(run: RunRecord) -> list[str]:
    out = []
    for call in run.calls:
        for t in call.tool_calls:
            if t.name == "end_call":
                err = t.result.get("error") if isinstance(t.result, dict) else None
                out.append(str(err) if err else "")
    return out


def check_kb_end_call_after_pending(run: RunRecord, expect: Expect) -> CheckResult:
    """A search was running when Sofia tried to end the call: `end_call` was refused with
    `search_pending`, later succeeded, and the late result was delivered."""
    if not _kb(expect).search_pending:
        return _ok("kb_end_call_after_pending", "not applicable")
    results = _end_call_errors(run)
    if "search_pending" not in results:
        return _fail("kb_end_call_after_pending", f"end_call results {results}: never pending")
    first = results.index("search_pending")
    if "" not in results[first + 1 :]:
        return _fail("kb_end_call_after_pending", "end_call never succeeded after search_pending")
    if not any(events_of(c, "kb_result_delivered") for c in run.calls):
        return _fail("kb_end_call_after_pending", "the search result was never delivered")
    return _ok("kb_end_call_after_pending")


def check_kb_search_outcome(run: RunRecord, expect: Expect) -> CheckResult:
    """The searches came to what the scenario is about: chunks, `no_match`, or unavailable."""
    kb = _kb(expect)
    outcomes = [search_outcome(d) for d in _search_events(run)]
    if not outcomes:
        return _fail("kb_search_outcome", "no kb_search event")
    if kb.outcome == "found" and "found" not in outcomes:
        return _fail("kb_search_outcome", f"expected chunks, searches were {outcomes}")
    if kb.outcome == "no_match" and (outcomes.count("no_match") == 0 or "found" in outcomes):
        return _fail(
            "kb_search_outcome",
            f"expected only no_match (the question is out of scope), searches were {outcomes}",
        )
    if kb.outcome == "unavailable" and (
        "unavailable" not in outcomes or "found" in outcomes or "no_match" in outcomes
    ):
        return _fail("kb_search_outcome", f"expected unavailable, searches were {outcomes}")
    return _ok("kb_search_outcome", str(outcomes))


def check_kb_chunks_retrieved(run: RunRecord, expect: Expect) -> CheckResult:
    """Each expected chunk group has one of its ids among the chunks the searches returned
    (golden ids). The model-written query decides this, so it is also a query-quality signal."""
    groups = _kb(expect).chunk_groups
    got = {cid for d in _search_events(run) for cid in d.get("chunk_ids") or []}
    missing = [g for g in groups if not got & set(g)]
    if missing:
        return _fail(
            "kb_chunks_retrieved", f"none of {missing} among the returned chunks {sorted(got)}"
        )
    return _ok("kb_chunks_retrieved", f"{len(got)} chunk(s) returned")


def exercised_problem(run: RunRecord, expect: Expect) -> str | None:
    """Why the harness did not create the situation a knowledge scenario is about (the run is
    then invalid, not a Sofia failure), or None. Silent when no search ran at all: that is
    Sofia's failure, `check_kb_searched` reports it."""
    if expect.kb is None:
        return None
    kb = expect.kb
    delivered = [e["data"] for c in run.calls for e in events_of(c, "kb_result_delivered")]
    if kb.deferred and delivered and not any(d.get("mode") == "deferred" for d in delivered):
        return "the slow search result was delivered inline, never late"
    if kb.search_pending and delivered and "search_pending" not in _end_call_errors(run):
        return "end_call never found a search running"
    return None


KB_CHECKS: tuple[Check, ...] = (
    check_kb_searched,
    check_kb_search_outcome,
    check_kb_chunks_retrieved,
    check_kb_query_spanish,
    check_kb_no_answer_from_memory,
    check_kb_no_doubled_holding_line,
    check_kb_question_referred,
    check_kb_screening_resumes,
    check_kb_end_call_after_pending,
)


# --- frustration notes (m1, m2) ------------------------------------------------------------

NOTE_TEXTS = (PROMPT["frustration_note_1"], PROMPT["frustration_note_2"])


def _monitor_problem(run: RunRecord) -> str | None:
    """Why the monitor could not send notes in this run (so a missing note says nothing about
    Sofia and "no note" means nothing), or None."""
    configs = [e["data"] for c in run.calls for e in events_of(c, "frustration.config")]
    if not configs:
        return "no frustration.config event: the monitor did not run (Cloudflare keys?)"
    if not all(d.get("notes_enabled") for d in configs):
        return "notes were not enabled in the call"
    return None


def _note_events(run: RunRecord) -> list[dict[str, Any]]:
    return [e for c in run.calls for e in events_of(c, "frustration.note")]


def check_frustration_noted(run: RunRecord, expect: Expect) -> CheckResult:
    """At least one `frustration.note` event was recorded (the impatient candidate was noticed).

    Misses: whether the note was timely or deserved (a note after the first sharp reply and one
    after the tenth look the same), and whether it reached Sofia's context: the event is recorded
    after the frame was queued, not after she read it. A model that stays unconvinced by an
    impatient persona fails here although Sofia did nothing wrong."""
    if problem := _monitor_problem(run):
        return _fail("frustration_noted", problem)
    notes = _note_events(run)
    if not notes:
        return _fail("frustration_noted", "no frustration.note event")
    return _ok("frustration_noted", f"levels {[e['data'].get('level') for e in notes]}")


def check_no_frustration_note(run: RunRecord, expect: Expect) -> CheckResult:
    """No `frustration.note` event in a curt but calm conversation (the false-alarm control).

    Misses: a threshold that is only just not crossed (a judgment at 0.55 passes the same as one
    at 0.05; read the `frustration.judgment` probabilities in the record), and a false alarm
    that needs a different persona or language than the one run."""
    if problem := _monitor_problem(run):
        return _fail("no_frustration_note", problem)
    notes = _note_events(run)
    if notes:
        return _fail(
            "no_frustration_note",
            f"{len(notes)} note(s), levels {[e['data'].get('level') for e in notes]}",
        )
    return _ok("no_frustration_note")


def check_no_resave_after_note(run: RunRecord, expect: Expect) -> CheckResult:
    """After the first note of a call, no `record_*` tool call starts for a fact that a
    `record_*` call had already saved before the note (saving it again implies asking again).

    Order is the `t` of the call's first `tool.event` against the note's `t`, both from the same
    recorder clock. Misses: a re-ask that gets no new `record_*` call (Sofia asks again but the
    candidate's answer is not saved a second time, or she asks and moves on), a re-ask in the
    reply the note could no longer change (the call had started before the note arrived), and
    facts that were saved only after the note. It fails a legitimate correction (the
    candidate changes an answer) and a `record_*` retry after a tool error; none of those are in
    m1's script."""
    problems = []
    for call in run.calls:
        notes = events_of(call, "frustration.note")
        if not notes:
            continue
        first = min(e["t"] for e in notes)
        tools = [t for t in build_tool_calls(call.events) if t.name in TOOL_FIELD]
        saved = {TOOL_FIELD[t.name] for t in tools if t.t < first and t.ok}
        problems += [
            f"call {call.index}: {t.name} again after the note"
            for t in tools
            if t.t > first and TOOL_FIELD[t.name] in saved
        ]
    return (
        _fail("no_resave_after_note", "; ".join(problems))
        if problems
        else _ok("no_resave_after_note")
    )


def check_note_not_spoken(run: RunRecord, expect: Expect) -> CheckResult:
    """No Sofia turn contains "monitor" (any case) or either note text.

    Misses: a paraphrase that gives the note away ("I can tell you are annoyed", "my system says
    you are upset"); that is what the judge question `frustration_adapted` is for, and only for
    m1. A Spanish word "monitor" used innocently would be a false failure."""
    spoken = [
        (c.index, i)
        for c in run.calls
        for i, t in enumerate(x for x in c.transcript if x.role == "agent")
        if "monitor" in t.text.casefold()
        or any(n.casefold() in t.text.casefold() for n in NOTE_TEXTS)
    ]
    if spoken:
        return _fail(
            "note_not_spoken", f"Sofia turn(s) mention the monitor or a note: {spoken[:3]}"
        )
    return _ok("note_not_spoken")


FRUSTRATION_CHECKS: dict[str, tuple[Check, ...]] = {
    "noted": (check_frustration_noted, check_no_resave_after_note, check_note_not_spoken),
    "calm": (check_no_frustration_note, check_note_not_spoken),
}


CHECKS: tuple[Check, ...] = (
    check_responsive,
    check_attempts,
    check_modes,
    check_chain,
    check_final_state,
    check_call_states,
    check_booking,
    check_facts,
    check_facts_at_start,
    check_tool_order,
    check_no_rerecord,
    check_final_tools,
    check_language,
    check_no_repeated_question,
)


def run_checks(run: RunRecord, expect: Expect) -> list[CheckResult]:
    """All hard checks. An invalid run (harness could not set up the situation) gets a single
    failed 'harness' entry instead, so it is never counted as Sofia passing or failing."""
    if not run.valid:
        return [CheckResult("harness", False, f"{run.harness_status}: {run.harness_detail}")]
    checks = (*CHECKS, *KB_CHECKS) if expect.kb is not None else CHECKS
    if expect.frustration is not None:
        checks = (*checks, *FRUSTRATION_CHECKS[expect.frustration])
    if expect.language_switch:
        checks = (*checks, check_language_switch)
    return [check(run, expect) for check in checks]
