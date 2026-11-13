"""The two LLM roles of the harness besides Sofia: the simulated candidate and the judge.

Both use the Anthropic SDK directly (like `hr_screener.screening.summary`). Sofia's own usage is not
measured here: it comes from the call metrics the app already stores (pipecat usage events).
"""

import json
import re
from collections.abc import Collection, Mapping
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field

from evals.common.usage import Usage, add_usage
from evals.e2e.records import CallRecord, events_of, search_outcome
from hr_screener.citations import quote_found

SIMULATOR_MODEL = "claude-haiku-5-5"
JUDGE_MODEL = "claude-sonnet-5-5"

LANGUAGE_NAMES = {"es": "Spanish (Spain)", "en": "English"}
# In the call language: Spanish examples in an English call made the simulator answer in
# Spanish in 35 of 42 English baseline runs.
DATE_EXAMPLES = {
    "es": '"el próximo lunes" o "el 16 de noviembre"',
    "en": '"next Monday" or "on November 16th"',
}

# Glossary so the simulator can say canonical values in natural words (the card is neutral).
_GLOSSARY = (
    "Levels: primary = primaria; secondary = ESO (ages 12-16); upper_secondary = Bachillerato "
    "(ages 16-18); university = university. Availability: workdays_morning = weekday "
    "mornings; workdays_afternoon = weekday afternoons; saturday_morning / "
    "saturday_afternoon = Saturday mornings / afternoons. Teaching format: in_person, online, "
    "or both."
)

SIMULATOR_SYSTEM = """\
You play a job candidate on a phone call with a recruiter called Sofia from a tutoring \
agency. You are not an assistant: you are the person described on the card below, answering \
the phone.

Rules:
- {language_rule}
- Say only facts that are on your card. If asked something the card does not cover, say you \
do not know or are not sure. Never invent a fact (dates, places, employers, numbers).
- Answer what Sofia asked, in the style on your card. Do not volunteer answers to questions \
she has not asked yet, and never answer several screening questions at once, unless your \
style says so.
- Dates: your earliest start date is on the card. Say it the way a person would in {language} \
(for example {date_examples}), never as an ISO date.
- If Sofia offers onboarding sessions, pick one of the options she read out. The onboarding \
session is a short meeting before you start; it does not have to be on or after your start \
date. If she says goodbye, answer with a short goodbye.
- Reply with only the words you say aloud: one short spoken turn, no quotes, no stage \
directions, no name prefix.

{glossary}

Your card:
{card}
{instruction}"""


def simulator_system(
    language: str, card: str, instruction: str, switch_to: str | None = None
) -> str:
    """The simulator's system prompt: the card text (see `Persona.card_text`), the call
    language and the scenario's extra instruction for this call (empty for none). `switch_to`
    (language-switch scenarios): the language the extra instruction has the candidate move to;
    the rule against changing language is lifted for it, and its date examples are given too."""
    extra = f"\nExtra instruction for this call (follow it over the style):\n{instruction}\n"
    return SIMULATOR_SYSTEM.format(
        language=LANGUAGE_NAMES[language],
        language_rule=(
            f"Speak {LANGUAGE_NAMES[language]} until your extra instruction has you change to "
            f"{LANGUAGE_NAMES[switch_to]}; then speak only that."
            if switch_to
            else f"Speak only {LANGUAGE_NAMES[language]}. Never switch language, whatever "
            "language Sofia uses."
        ),
        date_examples=DATE_EXAMPLES[language]
        + (
            f" ({DATE_EXAMPLES[switch_to]} once you speak {LANGUAGE_NAMES[switch_to]})"
            if switch_to
            else ""
        ),
        glossary=_GLOSSARY,
        card=card,
        instruction=extra if instruction else "",
    )


def simulator_messages(transcript: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Sofia's lines are the `user` role, the candidate's are `assistant`; consecutive lines of
    one speaker are merged (the API wants alternation, starting with the user)."""
    messages: list[dict[str, str]] = []
    for speaker, text in transcript:
        role = "user" if speaker == "agent" else "assistant"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + text
        else:
            messages.append({"role": role, "content": text})
    if not messages or messages[0]["role"] != "user" or messages[-1]["role"] != "user":
        raise ValueError("the simulator needs a transcript that starts and ends with Sofia")
    return messages


def clean_line(raw: str, persona_name: str) -> str:
    """Strip quotes and a leading speaker label the model sometimes adds."""
    text = raw.strip().strip('"“”«»').strip()
    for label in (persona_name, persona_name.split()[0], "Candidate", "Candidato", "Candidata"):
        for sep in (":", " -"):
            if text.lower().startswith(label.lower() + sep):
                text = text[len(label) + len(sep) :].strip().strip('"“”«»').strip()
    return text


async def simulate_line(
    client: anthropic.AsyncAnthropic,
    system: str,
    transcript: list[tuple[str, str]],
    persona_name: str,
    usage: Usage,
    model: str = SIMULATOR_MODEL,
) -> str:
    # No `thinking`: a one-line reply needs none. Haiku 5.5 rejects non-default sampling
    # parameters, so none are sent. max_tokens leaves room for any adaptive thinking.
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=simulator_messages(transcript),  # ty: ignore[invalid-argument-type]
        output_config={"effort": "low"},
    )
    add_usage(usage, response.usage)
    text = "".join(b.text for b in response.content if b.type == "text")
    line = clean_line(text, persona_name)
    if not line:
        raise RuntimeError(f"the simulator returned no text (stop_reason={response.stop_reason})")
    return line


# --- judge -----------------------------------------------------------------------------

# (id, question, answer that signals a problem or None when informational)
RUBRIC: tuple[tuple[str, str, str | None], ...] = (
    (
        "re_asked",
        "Did Sofia ask again, in words, one of the screening questions (start date, subjects "
        "and levels, weekly availability, teaching format, work authorization, experience) "
        "that the candidate had already answered, in this call or an earlier one, or whose "
        "answer was on file at the start? Not a re-ask: confirming who she is speaking to, "
        "the interest check (asked separately below), a short confirmation of a fact the "
        "candidate just changed, and reading back the booked onboarding session.",
        "yes",
    ),
    (
        "reasked_interest",
        "In a follow-up call (mode followup) whose facts_saved_at_start is not empty, did Sofia "
        "ask again whether the candidate is still interested, or whether they have a few "
        "minutes / it is a good time? Such a call follows the earlier one within minutes, so "
        "either question is redundant. 'n/a' for first calls, closed-mode calls and follow-ups "
        "with no facts saved at the start.",
        "yes",
    ),
    (
        "acknowledged_previous",
        "In a follow-up call (attempt 2 or more, mode followup), did Sofia acknowledge the "
        "earlier call naturally, in about one sentence, and carry on? 'n/a' for first calls "
        "and closed-mode calls.",
        "no",
    ),
    (
        "recap_matches",
        "If Sofia recapped or read back facts, did the recap match the facts on file / said? "
        "'n/a' when there was no recap.",
        "no",
    ),
    (
        "joined_questions",
        "Did any single Sofia turn ask the candidate two or more separate questions (for "
        "example 'do you have a few minutes and are you still interested?', or a screening "
        "question plus another one)? Not a joined question: one question that lists its "
        "possible answers (weekday mornings, afternoons...), offering two onboarding options "
        "to choose from, or a statement followed by one question.",
        "yes",
    ),
    (
        "narrated",
        "Did Sofia narrate tools, saving, notes, the system or the calendar (for example 'I'll "
        "note that down', 'let me check the system', 'I'm saving that')?",
        "yes",
    ),
    (
        "date_repeated",
        "Did Sofia read the candidate's START date back more than once in one call, or say "
        "an ISO date like 2026-11-16 aloud? Reading back the booked onboarding session "
        "after booking is expected and does not count.",
        "yes",
    ),
    (
        "revealed_rejection",
        "Only for a closed call to a rejected candidate: did Sofia reveal or hint at WHY the "
        "candidate was rejected (any reason, criterion or rule)? 'n/a' for every other call.",
        "yes",
    ),
    (
        "claimed_upcoming",
        "In this conversation the candidate's onboarding session is in the PAST (it already "
        "took place; attendance is unknown to Sofia). Did Sofia speak of the session as upcoming "
        "or in the future (for example 'you are booked for', 'see you on', 'we look forward "
        "to'), or say or imply that the candidate did or did not attend it? Answer 'no' when "
        "she only said when it was and that a colleague will be in touch.",
        "yes",
    ),
    (
        "frustration_adapted",
        "Only for a call with `frustration_notes` (hidden notes sent to Sofia after the candidate "
        "turn quoted in each; she reads one on her next reply). After the first note, did Sofia "
        "acknowledge once and briefly what was bothering the candidate, keep her replies short, "
        "and stop asking for things the candidate had already given, without naming or labelling "
        "their feelings (for example 'I understand you are frustrated')? 'n/a' when the call has "
        "no `frustration_notes`.",
        "no",
    ),
    (
        "language_consistent",
        "Did Sofia speak only the call language in every turn?",
        "no",
    ),
    # Knowledge-base questions: asked only where the scenario turns them on (KB_ITEMS).
    (
        "kb_faithful",
        "Does every factual claim Sofia made in answer to the candidate's knowledge questions "
        "(numbers, amounts, dates, form names, conditions, who must do what) appear in the "
        "chunk texts the search returned (`kb_searches`)? Answer 'no' if she states something "
        "the chunks do not say, or states facts about the topic when the search found "
        "nothing or failed. A paraphrase or a translation that keeps the facts is fine. "
        "'n/a' when the candidate asked no knowledge question.",
        "no",
    ),
    (
        "kb_regulation_caveats",
        "For an answer that relies on a chunk of kind 'regulation': did Sofia say it is "
        "general information as of the chunk's as_of date (the date or the year, in her own "
        "words) AND suggest checking with a gestor (a Spanish tax adviser) or the official "
        "source? 'n/a' when no returned chunk is a regulation.",
        "no",
    ),
    (
        "kb_spanish_terms",
        "In an English call: did Sofia keep the Spanish administrative terms from the chunks "
        "(for example autónomo, RETA, IRPF, IVA, modelo 130, gestor) and explain them briefly "
        "in English, instead of translating them away or leaving them unexplained? 'n/a' for "
        "Spanish calls and when the answer used no such term.",
        "no",
    ),
    (
        "kb_two_sentences",
        "Is each spoken answer to a knowledge question at most two sentences (the holding "
        "line and any screening question that follows it do not count)? 'n/a' when the "
        "candidate asked no knowledge question.",
        "no",
    ),
)
RUBRIC_BY_ID = {r[0]: r for r in RUBRIC}
# Asked only when the scenario turns them on (they make no sense in other calls).
KB_ITEMS = frozenset(
    {"kb_faithful", "kb_regulation_caveats", "kb_spanish_terms", "kb_two_sentences"}
)
CONDITIONAL_ITEMS = (
    frozenset({"revealed_rejection", "claimed_upcoming", "frustration_adapted"}) | KB_ITEMS
)

JUDGE_SYSTEM = """\
You review a recorded phone screening between "Sofia" (an AI recruiter, `Agent` in the transcript) \
and a job candidate. \
You receive the call language, then every call of the conversation (a conversation can have \
several calls when a call dropped and Sofia called back) with: the call mode, attempt number, \
the facts already saved when the call started, the transcript with numbered turns, the tools \
Sofia called, and how the call ended. Answer each rubric question with 'yes', 'no' or 'n/a' \
and quote the single most relevant turn verbatim as evidence (empty when n/a or when the \
answer is 'no' and there is nothing to quote). Give the call number the evidence is from. \
Judge only what the transcript shows; do not guess. When a call has `kb_searches`, each entry \
is one knowledge-base lookup with the chunk texts the model was given (the only text it may \
rely on); turns tagged [holding line] are fixed text the system plays while a lookup runs, \
not words Sofia wrote, so they never count as narrating. When a call has `frustration_notes`, \
each entry is a hidden note the app sent to Sofia (the candidate never sees it) after the \
candidate turn quoted in `after_candidate_turn`."""


class JudgeItem(BaseModel):
    id: str = Field(description="the rubric question id")
    answer: Literal["yes", "no", "n/a"]
    evidence: str = Field(description="one turn quoted verbatim, or an empty string")
    call: int | None = Field(description="1-based call number of the evidence, or null")


class JudgeOutput(BaseModel):
    verdicts: list[JudgeItem]


def kb_searches(call: CallRecord, kb_chunks: Mapping[str, Mapping[str, Any]]) -> list[dict]:
    """The call's lookups for the judge: the query, how it ended and the chunk texts returned."""
    out = []
    for event in events_of(call, "kb_search"):
        data = event["data"]
        ids = list(data.get("chunk_ids") or [])
        out.append(
            {
                "query": data.get("query"),
                "result": search_outcome(data),
                "chunks": [
                    {"id": i, **kb_chunks.get(i, {"text": "(text not recorded)"})} for i in ids
                ],
            }
        )
    return out


def frustration_notes(call: CallRecord) -> list[dict]:
    """The call's notes to Sofia for the judge: the level and the candidate turn judged just
    before it (the last judgment event that is not later than the note)."""
    judgments = events_of(call, "frustration.judgment")
    out = []
    for note in events_of(call, "frustration.note"):
        before = [j for j in judgments if j["t"] <= note["t"]]
        out.append(
            {
                "level": note["data"].get("level"),
                "after_candidate_turn": before[-1]["data"].get("candidate_turn")
                if before
                else None,
            }
        )
    return out


def transcript_lines(call: CallRecord) -> list[str]:
    """Numbered transcript; the holding line (an event, not model text) is tagged."""
    holding = {str(e["data"].get("text", "")) for e in events_of(call, "kb_holding_line")} - {""}
    lines = []
    for i, t in enumerate(call.transcript):
        tag = " [holding line]" if t.role == "agent" and any(h in t.text for h in holding) else ""
        lines.append(f"[{i}] {t.role.capitalize()}{tag}: {t.text}")
    return lines


_TURN_PREFIX = re.compile(r"^\s*\[\d+\]\s*(agent|candidate)[^:]*:\s*", re.IGNORECASE)


def evidence_found(evidence: str, calls: list[CallRecord], call: int | None) -> bool:
    """The judge's quote is in a turn of the call it names (any call when it names none). The
    `[3] Agent:` prefix of the numbered transcript it read may be copied along."""
    quote = _TURN_PREFIX.sub("", evidence.strip().strip('"“”«»'))
    turns = [t.text for c in calls if call is None or c.index == call for t in c.transcript]
    return quote_found(quote, turns)


def judge_payload(
    language: str,
    calls: list[CallRecord],
    final_facts: dict[str, Any],
    extra: Collection[str] = (),
    kb_chunks: Mapping[str, Mapping[str, Any]] | None = None,
    switched_to: str | None = None,
) -> str:
    """`extra`: the ids of the conditional rubric items to ask in addition to the general ones.
    `kb_chunks`: id -> chunk (title, kind, as_of, text) for the `kb_searches` of each call.
    `switched_to`: the call language after the candidate asked to change it (language-switch
    scenarios), so `language_consistent` is judged against the switch."""
    questions = [
        {"id": qid, "question": q}
        for qid, q, _ in RUBRIC
        if qid not in CONDITIONAL_ITEMS or qid in extra
    ]
    payload = {
        "call_language": LANGUAGE_NAMES[language]
        + (
            f" at the start; the candidate asks to continue in {LANGUAGE_NAMES[switched_to]} "
            "and Sofia switches. Sofia's turns must be in the first language before the switch "
            "and in the second after it (the turn that announces the switch may carry both)"
            if switched_to
            else ""
        ),
        "rubric": questions,
        "calls": [
            {
                "call": c.index,
                "mode": c.mode,
                "attempt": c.attempt,
                "facts_saved_at_start": c.facts_at_start,
                "ended_by": c.end_reason,
                "transcript": transcript_lines(c),
                "tools": [{"name": t.name, "args": t.args} for t in c.tool_calls],
                **(
                    {"kb_searches": kb_searches(c, kb_chunks or {})}
                    if events_of(c, "kb_search")
                    else {}
                ),
                **(
                    {"frustration_notes": frustration_notes(c)}
                    if events_of(c, "frustration.note")
                    else {}
                ),
            }
            for c in calls
        ],
        "final_facts": final_facts,
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


async def judge_run(
    client: anthropic.AsyncAnthropic,
    language: str,
    calls: list[CallRecord],
    final_facts: dict[str, Any],
    extra: Collection[str],
    usage: Usage,
    model: str = JUDGE_MODEL,
    kb_chunks: Mapping[str, Mapping[str, Any]] | None = None,
    switched_to: str | None = None,
) -> list[JudgeItem]:
    # Same call shape as hr_screener.screening.summary: structured output through messages.parse.
    response = await client.messages.parse(
        model=model,
        max_tokens=4000,
        system=JUDGE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": judge_payload(
                    language, calls, final_facts, extra, kb_chunks, switched_to
                ),
            }
        ],
        output_format=JudgeOutput,
        output_config={"effort": "low"},
    )
    add_usage(usage, response.usage)
    if response.parsed_output is None:
        raise RuntimeError(
            f"the judge returned no parsed output (stop_reason={response.stop_reason})"
        )
    return response.parsed_output.verdicts
