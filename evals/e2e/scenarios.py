"""The scenarios, in code. Each is: persona + optional setup + a plan of live calls + the
hard checks to apply (`Expect`).

How they were chosen: they walk the follow-up state machine (`followup.CallMode`, what is on
file when the next call starts), repeat past bugs (README, "Lessons from test calls":
re-asking answered questions, stale dates, narrating tools) and cover the business harm cases
(booking someone who does not qualify, telling a rejected candidate why, double-booking). A
plan entry says how a call ends: `drop` (the harness hangs up when the condition holds),
`supersede` (the next call starts while this one is live) or neither (Sofia ends the call).

`k1`..`k8` are the knowledge-base scenarios (README): the call gets a knowledge
base (`Scenario.kb`: the real index, a slow one, or one that is down) and the candidate asks
a question. They are checked by the `kb_*` checks in `checks.py` through `Expect.kb`.

`n1` is the language-switch scenario (`Expect.language_switch`): the candidate asks to continue
the call in the other language (en to es, es to en, whichever the run language is).

`m1` and `m2` are the frustration-note scenarios (`Scenario.frustration_notes`, which turns
`FRUSTRATION_NOTES_ENABLED` on for the call and needs the Cloudflare keys): an impatient
candidate who must trigger a note and a curt but calm one who must not (the false-alarm
control). They are checked through `Expect.frustration` (`checks.py`, `FRUSTRATION_CHECKS`).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from evals.e2e import setups
from evals.e2e.drops import (
    FACT_FIELDS,
    AfterFacts,
    AfterTool,
    AfterTurnsNoFacts,
    AvailabilityWithoutFormat,
    DropCondition,
    SubjectsWithoutLevels,
)
from evals.e2e.kb import SLOW_DELAY_SECS, KbSpec

RECORD_ALL = tuple(
    f"record_{n}"
    for n in (
        "start_date",
        "subjects",
        "levels",
        "availability",
        "teaching_format",
        "work_authorization",
        "experience",
    )
)


@dataclass(frozen=True)
class CallPlan:
    drop: DropCondition | None = None
    supersede: DropCondition | None = None  # call ends because the next call starts
    # Extra instruction for the simulated candidate in this call: one text, or one per call
    # language (a knowledge question is worded differently in Spanish and in English).
    instruction: str | Mapping[str, str] = ""

    def text(self, language: str) -> str:
        return self.instruction if isinstance(self.instruction, str) else self.instruction[language]


@dataclass(frozen=True)
class KbExpect:
    """What the knowledge base should have done in a knowledge scenario (see `checks.py`)."""

    min_searches: int  # search_knowledge tool calls over the whole conversation
    max_searches: int
    # What the searches must have come to: found (chunks, no error), no_match, unavailable.
    outcome: Literal["found", "no_match", "unavailable"] = "found"
    # Each group needs one of its chunk ids among the chunks the searches returned.
    chunk_groups: tuple[tuple[str, ...], ...] = ()
    # True: exactly one refer_to_recruiter call and one stored row Sofia wrote (not automatic).
    referred: bool | None = None
    resume: bool = True  # a record_* / slots / booking tool runs after the first search
    deferred: bool = False  # the result must have been delivered late (else: invalid run)
    search_pending: bool = False  # end_call must hit a running search (else: invalid run)


@dataclass(frozen=True)
class Expect:
    outcome: str | None  # outcome of the last call's screening
    booked: bool  # a booking exists for the candidate at the end
    attempts: tuple[int, ...]  # attempt of each live call
    modes: tuple[str, ...]  # call mode of each live call
    status: str = "completed"  # status of the last call's screening
    booking_unchanged: bool = False
    call_outcomes: dict[int, str] = field(default_factory=dict)
    call_statuses: dict[int, str] = field(default_factory=dict)
    end_reasons: dict[int, str] = field(default_factory=dict)
    min_facts_at_start: dict[int, int] = field(default_factory=dict)
    # facts that must be saved at the end (and every saved fact must match the persona)
    required_facts: tuple[str, ...] = FACT_FIELDS
    # fact -> relative date spec the candidate corrects it to (start_date only)
    corrected: dict[str, str] = field(default_factory=dict)
    # tools of the LAST call: must be called / must not be called (fnmatch patterns)
    must_call: tuple[str, ...] = ()
    must_not_call: tuple[str, ...] = ()
    only_tools: tuple[str, ...] | None = None
    # follow-up calls must not re-record facts already on file, except these fields
    allow_rerecord: tuple[str, ...] = ()
    check_rerecord: bool = True
    kb: KbExpect | None = None  # set only in the knowledge scenarios
    # Set only in the frustration-note scenarios: "noted" (a note must have been sent, m1) or
    # "calm" (none may, m2).
    frustration: Literal["noted", "calm"] | None = None
    # Set only in the language-switch scenarios: the candidate asks to continue in the other
    # language, so Sofia must call switch_language once and speak the old language before it and
    # the new one after it (`check_language_switch`; the drift check splits at the switch).
    language_switch: bool = False


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    persona: str
    plan: tuple[CallPlan, ...]
    expect: Expect
    setup: setups.SetupFn | None = None
    # conditional judge rubric items to ask (llm.CONDITIONAL_ITEMS), e.g. l2: revealed_rejection
    judge_extra: tuple[str, ...] = ()
    kb: KbSpec | None = None  # the knowledge base the call gets (None: no knowledge tools)
    # Notes to Sofia on for the calls (needs the Cloudflare keys; the monitor is the app's own).
    frustration_notes: bool = False


_BOOK = ("list_onboarding_slots", "schedule_onboarding")
# The record tools other than record_start_date (a follow-up with every fact saved confirms
# the start date and nothing else).
_RECORD_OTHERS = (
    "record_subjects",
    "record_levels",
    "record_availability",
    "record_teaching_format",
    "record_work_authorization",
    "record_experience",
)

SCENARIOS: dict[str, Scenario] = {
    s.id: s
    for s in (
        Scenario(
            "a",
            "dropped right after interest, no facts: follow-up asks all five",
            "qualifying",
            (CallPlan(drop=AfterTurnsNoFacts(2)), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                must_call=(*RECORD_ALL, *_BOOK),
                check_rerecord=False,
            ),
        ),
        Scenario(
            "b",
            "dropped after 4 facts: follow-up skips them, completes and books",
            "qualifying",
            (CallPlan(drop=AfterFacts(4)), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                min_facts_at_start={2: 4},
                must_call=_BOOK,
            ),
        ),
        Scenario(
            "c",
            "dropped after availability, before teaching format",
            "qualifying",
            (CallPlan(drop=AvailabilityWithoutFormat()), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                must_call=("record_teaching_format", *_BOOK),
                must_not_call=("record_availability",),
            ),
        ),
        Scenario(
            "c2",
            "dropped after subjects, before levels",
            "qualifying",
            (CallPlan(drop=SubjectsWithoutLevels()), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                must_call=("record_levels", *_BOOK),
                must_not_call=("record_subjects",),
            ),
        ),
        Scenario(
            "d",
            "dropped right after record_experience: all facts, qualified, not booked",
            "qualifying",
            (CallPlan(drop=AfterTool("record_experience")), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                min_facts_at_start={2: 7},
                # every fact on file: the start date is confirmed first (README, lesson 18)
                must_call=("record_start_date", *_BOOK),
                must_not_call=_RECORD_OTHERS,
                allow_rerecord=("start_date",),
            ),
        ),
        Scenario(
            "e",
            "busy: asks to be called back tomorrow at 18:00, then the call-back books",
            "qualifying",
            (
                CallPlan(
                    instruction=(
                        "You are busy right now. After confirming who you are, say you cannot "
                        "talk now and ask to be called back tomorrow at 18:00. Do not answer "
                        "any screening question in this call."
                    )
                ),
                CallPlan(),
            ),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                call_outcomes={1: "callback_requested"},
                end_reasons={1: "end_call"},
                must_call=_BOOK,
                check_rerecord=False,
            ),
        ),
        Scenario(
            "f",
            "dropped after all facts; on the call-back the start date changes to January",
            "qualifying",
            (
                CallPlan(drop=AfterFacts(7)),
                CallPlan(
                    instruction=(
                        "Correct yourself at the first chance: you made a mistake about your "
                        "start date. You can only start on {date:in_60_days}; say it as a "
                        "date (day and month), not as a number of days."
                    )
                ),
            ),
            Expect(
                outcome="not_qualified",
                booked=False,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                corrected={"start_date": "in_60_days"},
                must_call=("record_start_date",),
                must_not_call=("schedule_onboarding",),
                allow_rerecord=("start_date",),
            ),
        ),
        Scenario(
            "g",
            "not authorized to work: no slots, not qualified, no booking",
            "not_authorized",
            (CallPlan(drop=AfterTool("record_work_authorization")), CallPlan()),
            Expect(
                outcome="not_qualified",
                booked=False,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                required_facts=("work_authorized",),
                must_not_call=("list_onboarding_slots", "schedule_onboarding"),
                check_rerecord=True,
            ),
        ),
        Scenario(
            "h",
            "a new call starts while the first is live (supersede) after 3 facts",
            "qualifying",
            (CallPlan(supersede=AfterFacts(3)), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                call_statuses={1: "failed"},
                end_reasons={1: "superseded"},
                min_facts_at_start={2: 3},
                must_call=_BOOK,
            ),
        ),
        Scenario(
            "i",
            "dropped after slots were offered: the next call lists them again before booking",
            "qualifying",
            (CallPlan(drop=AfterTool("list_onboarding_slots")), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2),
                modes=("fresh", "followup"),
                min_facts_at_start={2: 7},
                # every fact on file: the start date is confirmed first (README, lesson 18)
                must_call=("record_start_date", *_BOOK),
                must_not_call=_RECORD_OTHERS,
                allow_rerecord=("start_date",),
            ),
        ),
        Scenario(
            "j",
            "two drops: the third call continues with 5 facts and books",
            "qualifying",
            (CallPlan(drop=AfterFacts(3)), CallPlan(drop=AfterFacts(5)), CallPlan()),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(1, 2, 3),
                modes=("fresh", "followup", "followup"),
                min_facts_at_start={3: 5},
                must_call=_BOOK,
            ),
        ),
        Scenario(
            "k",
            "earlier dropped call has every fact but a start date that is now in the past",
            "qualifying",
            (CallPlan(),),
            Expect(
                outcome="scheduled",
                booked=True,
                attempts=(2,),
                modes=("followup",),
                min_facts_at_start={1: 6},
                must_call=("record_start_date", *_BOOK),
                allow_rerecord=("start_date",),
            ),
            setup=setups.failed_all_facts_stale_start,
        ),
        Scenario(
            "l1",
            "closed, booked: Sofia only informs; the booking is untouched",
            "qualifying",
            (
                CallPlan(
                    instruction=(
                        "Answer the phone. If the agent tells you about your onboarding "
                        "session, thank them. Do not ask to change anything."
                    )
                ),
            ),
            Expect(
                outcome="already_screened",
                booked=True,
                booking_unchanged=True,
                attempts=(2,),
                modes=("closed_booked",),
                required_facts=(),
                only_tools=("end_call",),
                check_rerecord=False,
            ),
            setup=setups.booked_candidate,
        ),
        Scenario(
            "l2",
            "closed, rejected: Sofia only informs and gives no reason",
            "not_authorized",
            (
                CallPlan(
                    instruction=(
                        "Answer the phone. If the agent tells you the decision, ask once why "
                        "(why was your application not successful). Accept any answer."
                    )
                ),
            ),
            Expect(
                outcome="already_screened",
                booked=False,
                attempts=(2,),
                modes=("closed_rejected",),
                required_facts=(),
                only_tools=("end_call",),
                check_rerecord=False,
            ),
            setup=setups.rejected_candidate,
            judge_extra=("revealed_rejection",),
        ),
        Scenario(
            "l3",
            "closed, booked, the session already took place: Sofia says so, no claims",
            "qualifying",
            (
                CallPlan(
                    instruction=(
                        "Answer the phone. If the agent tells you about your onboarding "
                        "session, thank them and ask once whether you can book another one. "
                        "Accept any answer."
                    )
                ),
            ),
            Expect(
                outcome="already_screened",
                booked=True,
                booking_unchanged=True,
                attempts=(2,),
                modes=("closed_booked",),
                required_facts=(),
                only_tools=("end_call",),
                check_rerecord=False,
            ),
            setup=setups.booked_candidate_session_passed,
            judge_extra=("claimed_upcoming",),
        ),
    )
}


# --- knowledge-base scenarios (README) ---------------------------------------------------------

KB_JUDGE = ("kb_faithful", "kb_regulation_caveats", "kb_spanish_terms", "kb_two_sentences")
REAL = KbSpec("real")
SLOW = KbSpec("slow", SLOW_DELAY_SECS)
DOWN = KbSpec("down")

POLICY = "pagos-y-tarifas"
Q_PAY = {  # golden en-pay-level / es-pay-level
    "en": "How much do you pay per hour for high school classes?",
    "es": "¿Cuánto pagáis la hora de clase de bachillerato?",
}
Q_PAYDAY = {  # golden en-payday / es-payday
    "en": "When do I actually get paid?",
    "es": "¿Qué día del mes se cobra?",
}
Q_VAT = {  # golden en-vat; the Spanish one is a paraphrase of it
    "en": "Do I have to charge VAT on private lessons?",
    "es": "¿Tengo que cobrar IVA en las clases particulares?",
}
Q_OUT_OF_SCOPE = {  # golden oos-en-competitor / oos-es-competitor
    "en": "How much does Superprof pay its tutors compared to you?",
    "es": "¿Cuánto paga la academia Cuadernos de Madrid a sus profesores?",
}
Q_DOCS = {  # golden en-docs; the Spanish one is a paraphrase of it
    "en": "What documents do I need to send you after the session?",
    "es": "¿Qué documentos tengo que enviaros después de la sesión?",
}
Q_ONBOARDING = {  # golden en-onboarding-what; the Spanish one is a paraphrase of it
    "en": "What exactly is the onboarding session?",
    "es": "¿Qué hacemos exactamente en la sesión de incorporación?",
}
C_PAY = (f"{POLICY}#tarifa-por-hora-segun-el-nivel",)
C_PAYDAY = (f"{POLICY}#como-se-registran-las-horas",)
C_VAT = ("iva-clases-particulares#la-exencion-de-las-clases-particulares",)
C_DOCS = ("documentacion-tras-onboarding#que-documentos-pedimos",)
C_ONBOARDING = ("onboarding-y-formacion#que-es-la-sesion-de-incorporacion",)


def ask_midway(*questions: Mapping[str, str], then: str = "") -> dict[str, str]:
    """The candidate asks `questions` (one per call language) when Sofia asks about the weekly
    availability, instead of answering, and then answers as usual."""
    out: dict[str, str] = {}
    for lang in ("en", "es"):
        asked = [q[lang] for q in questions]
        text = (
            "When Sofia asks about your weekly availability, do not answer yet. First ask her, "
            f'in your own words: "{asked[0]}"'
        )
        for follow in asked[1:]:
            text += (
                ". As soon as she has answered that, and before answering the availability "
                f'question, ask her this second question: "{follow}"'
            )
        text += (
            ". Ask nothing else in this call. After her answers, give your availability "
            f"and carry on with her screening questions as usual. {then}"
        )
        out[lang] = text.strip()
    return out


def _kb_fresh(kb: KbExpect) -> Expect:
    """A fresh call that screens, books and searches, with the knowledge expectations `kb`."""
    return Expect(
        outcome="scheduled",
        booked=True,
        attempts=(1,),
        modes=("fresh",),
        must_call=(*RECORD_ALL, *_BOOK, "search_knowledge"),
        kb=kb,
    )


SCENARIOS.update(
    {
        s.id: s
        for s in (
            Scenario(
                "k1",
                "policy question mid-screening (pay): searched once, answered, screening resumes",
                "curious",
                (CallPlan(instruction=ask_midway(Q_PAY)),),
                _kb_fresh(KbExpect(min_searches=1, max_searches=1, chunk_groups=(C_PAY,))),
                judge_extra=KB_JUDGE,
                kb=REAL,
            ),
            Scenario(
                "k2",
                "regulation question (IVA): answer carries the as_of date and the gestor line",
                "curious",
                (CallPlan(instruction=ask_midway(Q_VAT)),),
                _kb_fresh(KbExpect(min_searches=1, max_searches=1, chunk_groups=(C_VAT,))),
                judge_extra=KB_JUDGE,
                kb=REAL,
            ),
            Scenario(
                "k3",
                "two questions in a row: two searches, one at a time, screening resumes",
                "curious",
                (CallPlan(instruction=ask_midway(Q_PAY, Q_PAYDAY)),),
                _kb_fresh(KbExpect(min_searches=2, max_searches=3, chunk_groups=(C_PAY, C_PAYDAY))),
                judge_extra=KB_JUDGE,
                kb=REAL,
            ),
            Scenario(
                "k4",
                "slow knowledge base: the candidate keeps talking, the result arrives late",
                "curious",
                (
                    CallPlan(
                        instruction=ask_midway(
                            Q_PAY,
                            then=(
                                "She will say she is checking. Do not wait for the answer: in "
                                "your next line give your availability right away. If she then "
                                "tells you the answer to your question, thank her briefly."
                            ),
                        )
                    ),
                ),
                _kb_fresh(
                    KbExpect(min_searches=1, max_searches=1, chunk_groups=(C_PAY,), deferred=True)
                ),
                judge_extra=KB_JUDGE,
                kb=SLOW,
            ),
            Scenario(
                "k5",
                "knowledge base down: Sofia refers the question to a recruiter and carries on",
                "curious",
                (CallPlan(instruction=ask_midway(Q_PAY)),),
                Expect(
                    outcome="scheduled",
                    booked=True,
                    attempts=(1,),
                    modes=("fresh",),
                    must_call=(*RECORD_ALL, *_BOOK, "search_knowledge", "refer_to_recruiter"),
                    kb=KbExpect(
                        min_searches=1,
                        max_searches=2,
                        outcome="unavailable",
                        referred=True,
                    ),
                ),
                judge_extra=KB_JUDGE,
                kb=DOWN,
            ),
            Scenario(
                "k6",
                "out-of-scope question: no_match, nothing invented, referred to a recruiter",
                "curious",
                (CallPlan(instruction=ask_midway(Q_OUT_OF_SCOPE)),),
                Expect(
                    outcome="scheduled",
                    booked=True,
                    attempts=(1,),
                    modes=("fresh",),
                    must_call=(*RECORD_ALL, *_BOOK, "search_knowledge", "refer_to_recruiter"),
                    kb=KbExpect(
                        min_searches=1,
                        max_searches=2,
                        outcome="no_match",
                        referred=True,
                    ),
                ),
                judge_extra=KB_JUDGE,
                kb=REAL,
            ),
            Scenario(
                "k7",
                "closed, booked: the candidate calls back with a question; booking untouched",
                "curious",
                (
                    CallPlan(
                        instruction={
                            lang: (
                                "Answer the phone. After the agent tells you about your "
                                f'onboarding session, ask her: "{Q_DOCS[lang]}" Ask nothing '
                                "else; thank her for the answer. Do not ask to change anything."
                            )
                            for lang in ("en", "es")
                        }
                    ),
                ),
                Expect(
                    outcome="already_screened",
                    booked=True,
                    booking_unchanged=True,
                    attempts=(2,),
                    modes=("closed_booked",),
                    required_facts=(),
                    # refer_to_recruiter too: a retriever that misses (local provider) leads to
                    # the hand-off to a recruiter
                    only_tools=("search_knowledge", "refer_to_recruiter", "end_call"),
                    check_rerecord=False,
                    must_call=("search_knowledge",),
                    kb=KbExpect(
                        min_searches=1, max_searches=1, chunk_groups=(C_DOCS,), resume=False
                    ),
                ),
                setup=setups.booked_candidate,
                judge_extra=KB_JUDGE,
                kb=REAL,
            ),
            Scenario(
                "k8",
                "the candidate tries to end the call while a search runs: end_call waits",
                "curious",
                (
                    CallPlan(
                        instruction={
                            lang: (
                                "Do not ask anything until Sofia has booked your onboarding "
                                "session and read it back. Then, instead of saying goodbye, "
                                f'ask her: "{Q_ONBOARDING[lang]}" She will say she is '
                                "checking. Do not wait: in your very next line say thanks, "
                                "you have to go now, and goodbye. If she keeps talking, say "
                                "goodbye again."
                            )
                            for lang in ("en", "es")
                        }
                    ),
                ),
                _kb_fresh(
                    KbExpect(
                        min_searches=1,
                        max_searches=1,
                        chunk_groups=(C_ONBOARDING,),
                        search_pending=True,
                        resume=False,  # the question comes after the booking
                    )
                ),
                judge_extra=KB_JUDGE,
                kb=SLOW,
            ),
        )
    }
)


# --- frustration-note scenarios ------------------------------------------------------------

SCENARIOS.update(
    {
        s.id: s
        for s in (
            Scenario(
                "m1",
                "impatient candidate: Sofia is told, acknowledges briefly, stops re-asking",
                "impatient",
                (
                    CallPlan(
                        instruction={
                            "es": (
                                "Contesta bien, pero ten prisa desde el principio: di que no "
                                "tienes mucho tiempo y que la llamada se hace larga. Si te "
                                "preguntan algo que ya has dicho, responde 'ya te lo he dicho'. "
                                "Cada vez más seco, sin llegar a ser grosero."
                            ),
                            "en": (
                                "Answer correctly, but be in a hurry from the start: say you "
                                "have little time and the call is getting long. If you are "
                                "asked something you already said, answer 'I already told "
                                "you'. Sharper each time, never rude."
                            ),
                        }
                    ),
                ),
                Expect(
                    outcome="scheduled",
                    booked=True,
                    attempts=(1,),
                    modes=("fresh",),
                    must_call=(*RECORD_ALL, *_BOOK),
                    frustration="noted",
                ),
                judge_extra=("frustration_adapted",),
                frustration_notes=True,
            ),
            Scenario(
                "m2",
                "curt but calm candidate: no note (false-alarm control), the call books",
                "curt_calm",
                (CallPlan(),),
                Expect(
                    outcome="scheduled",
                    booked=True,
                    attempts=(1,),
                    modes=("fresh",),
                    must_call=(*RECORD_ALL, *_BOOK),
                    frustration="calm",
                ),
                frustration_notes=True,
            ),
        )
    }
)


# --- language-switch scenario --------------------------------------------------------------

_SWITCH_REQUEST = {
    # The language the run starts in -> what the candidate does (the other language is theirs
    # from then on; the simulator's "speak only one language" rule is lifted for this scenario).
    "es": (
        "This call has a twist. Answer the start date and subjects questions normally, in "
        "Spanish. When Sofia asks which levels you can teach, do not answer; say only: "
        '"Perdona, ¿podemos seguir la llamada en inglés?". Once Sofia agrees, answer her '
        "question and every later one in English only, with the facts on your card."
    ),
    "en": (
        "This call has a twist. Answer the start date and subjects questions normally, in "
        "English. When Sofia asks which levels you can teach, do not answer; say only: "
        '"Sorry, could we continue the call in Spanish?". Once Sofia agrees, answer her '
        "question and every later one in Spanish only, with the facts on your card."
    ),
}

SCENARIOS["n1"] = Scenario(
    "n1",
    "candidate asks to continue in the other language: switch_language once, then that language",
    "qualifying",
    (CallPlan(instruction=_SWITCH_REQUEST),),
    Expect(
        outcome="scheduled",
        booked=True,
        attempts=(1,),
        modes=("fresh",),
        must_call=(*RECORD_ALL, *_BOOK, "switch_language"),
        language_switch=True,
    ),
)
