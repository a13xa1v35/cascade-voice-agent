"""Run one scenario conversation: real Sofia (the call pipeline over text) against a simulated
candidate, with the harness controlling drops.

Per conversation: a fresh SQLite file in the results directory (schema created from the
metadata, the same schema the Alembic migrations build, see tests/test_migrations.py; seeded
with the demo opening, the persona as candidate and onboarding slots), a store on the eval
Redis, one `LiveCalls`. Calls are created exactly like the browser path
(`calls.start_screening`). Nothing here reads or writes the configured DATABASE_URL/REDIS_URL.
"""

import asyncio
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Literal, Protocol

import anthropic
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.pool import NullPool

from evals.common.language import detect
from evals.common.usage import Usage, add_agent_usage, add_usage
from evals.e2e.checks import exercised_problem, run_checks
from evals.e2e.drops import DropCondition, ObservedStore, fact_fields, snapshot
from evals.e2e.kb import KbHub, down_knowledge_base, settings_for
from evals.e2e.llm import evidence_found, judge_run, simulate_line, simulator_system
from evals.e2e.persona import Persona, load_persona, render_instruction, resolve_date
from evals.e2e.records import (
    CallRecord,
    DriftTurn,
    JudgeVerdict,
    RunRecord,
    ToolCallRecord,
    Turn,
    events_of,
    mark_switch_drift,
    other_language,
)
from evals.e2e.scenarios import CallPlan, Scenario
from evals.e2e.setups import SetupContext
from hr_screener.app.seed import seed
from hr_screener.config import Settings
from hr_screener.i18n import Lang, search_holding_line
from hr_screener.knowledge.store import KnowledgeBase
from hr_screener.models import Candidate, Channel, ScreeningStatus
from hr_screener.pipeline.textcall import TextCall
from hr_screener.screening.calls import LiveCalls, start_screening
from hr_screener.screening.followup import load_call_context, local_today
from hr_screener.screening.summary import summarize_call
from hr_screener.storage.db import make_engine, metadata

POLL_SECS = 0.1
# The knowledge events kept in a call's record (the rest of the Redis timeline is not needed).
KB_EVENT_TYPES = frozenset(
    {"kb_search", "kb_result_delivered", "kb_holding_line", "question_referred"}
)


def keeps_event(scenario: Scenario, event_type: str) -> bool:
    """Whether the call record keeps this event of the Redis timeline (the rest is not needed).
    Knowledge scenarios keep the knowledge events; frustration-note scenarios keep the
    `frustration.*` events and the tool events (to order tool calls against the notes);
    language-switch scenarios keep `language_switched`."""
    if scenario.expect.language_switch and event_type == "language_switched":
        return True
    if scenario.kb is not None and event_type in KB_EVENT_TYPES:
        return True
    return scenario.frustration_notes and (
        event_type.startswith("frustration.") or event_type == "tool.event"
    )


@dataclass
class EvalConfig:
    results_dir: Path
    redis_url: str
    client: anthropic.AsyncAnthropic
    summary: bool = True
    judge: bool = True
    max_turns: int = 30  # candidate lines per call before "did not finish"
    reply_timeout_secs: float = 120.0
    finalize_timeout_secs: float = 180.0
    # Knowledge-base scenarios: after the holding line, how long to wait for the answer reply
    # (the inline path) before the candidate carries on and the result is delivered late.
    answer_wait_secs: float = 30.0
    kb: KbHub | None = None  # the real index, built once per run (None: no kb scenario selected)


class ReplySource(Protocol):
    async def next_reply(self) -> str | None: ...


Wait = Literal["reply", "ended", "triggered", "timeout", "provider_quota"]


async def read_reply(
    call: ReplySource,
    store: ObservedStore,
    screening_id: str,
    cond: DropCondition | None,
    candidate_turns: int,
    wait_secs: float,
    failed: Callable[[], bool] = lambda: False,
) -> tuple[Wait, str | None]:
    """Sofia's next reply, polling the drop condition while she is busy (a tool can save the
    fact that makes the candidate hang up long before her reply is done). `failed()` is polled
    too: once it holds, stop waiting for a reply that will not come ("provider_quota")."""
    task = asyncio.ensure_future(call.next_reply())
    deadline = asyncio.get_running_loop().time() + wait_secs
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=POLL_SECS)
            if done:
                reply = task.result()
                return ("ended", None) if reply is None else ("reply", reply)
            if failed():
                return "provider_quota", None
            if cond is not None and cond.satisfied(
                await snapshot(store, screening_id, candidate_turns)
            ):
                return "triggered", None
            if asyncio.get_running_loop().time() > deadline:
                return "timeout", None
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def meter_summary_client(client: Any, usage: Usage) -> None:
    """Count the tokens of the summary's `parse` calls (summarize_call does not return them)."""
    for resource in (client.messages, client.beta.messages):
        original = resource.parse

        async def wrapped(*args: Any, _original: Any = original, **kwargs: Any) -> Any:
            response = await _original(*args, **kwargs)
            add_usage(usage, response.usage)
            return response

        setattr(resource, "parse", wrapped)  # noqa: B010


@dataclass
class _Live:
    """A started call and what the harness knows about it so far."""

    call: TextCall
    record: CallRecord
    ended_by: str = ""


class Conversation:
    """One scenario run. `run()` always returns a RunRecord (errors become harness_status)."""

    def __init__(
        self,
        scenario: Scenario,
        language: Lang,
        run_index: int,
        cfg: EvalConfig,
    ) -> None:
        self.scenario = scenario
        self.language = language
        self.cfg = cfg
        self.key = f"{scenario.id}_{language}_{run_index}"
        results = cfg.results_dir
        (results / "db").mkdir(parents=True, exist_ok=True)
        self.db_file = results / "db" / f"{self.key}.db"
        self.settings = settings_for(
            scenario.kb,
            Settings(
                language=language,
                database_url=f"sqlite+aiosqlite:///{self.db_file}",
                redis_url=cfg.redis_url,
                call_log_dir=str(results / "logs"),
                summary_enabled=cfg.summary,
                debug_pipeline=True,  # the per-call log keeps the LLM requests: the evidence
                # Set explicitly (not left to .env): a scenario either has the notes or not.
                frustration_check_enabled=True,
                frustration_notes_enabled=scenario.frustration_notes,
            ),
        )
        self.holding_line = search_holding_line(language)
        self.persona: Persona = load_persona(scenario.persona)
        self.today = local_today(self.settings.timezone)
        self.record = RunRecord(
            scenario=scenario.id,
            language=language,
            run=run_index,
            persona=scenario.persona,
            today=self.today.isoformat(),
            agent_model=self.settings.agent_model,
            agent_provider=self.settings.llm_provider,
            summary_enabled=cfg.summary,
            kb_mode=scenario.kb.mode if scenario.kb else "",
        )

    async def run(self) -> RunRecord:
        started = time.monotonic()
        engine = make_engine(self.settings.database_url, poolclass=NullPool)
        redis: Redis = Redis.from_url(self.cfg.redis_url, decode_responses=True)
        store = ObservedStore(engine, redis)
        screening_ids: list[str] = []
        try:
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            await self._play(store, screening_ids)
        except Exception as exc:
            logger.exception(f"[{self.key}] harness error")
            self._invalid("error", f"{type(exc).__name__}: {exc}")
        finally:
            # Delete exactly the event timelines this run created, nothing else.
            with contextlib.suppress(Exception):
                keys = [f"screening:{sid}:events" for sid in screening_ids]
                if keys:
                    await redis.delete(*keys)
            await redis.aclose()
            await engine.dispose()
        self.record.seconds = round(time.monotonic() - started, 1)
        return self.record

    def _invalid(self, status: str, detail: str) -> None:
        # Keep the first reason, except that a provider quota error wins: the other reasons
        # (no reply in time, ...) are then just how it showed up.
        if self.record.harness_status == "ok" or (
            status == "provider_quota" and self.record.harness_status != "provider_quota"
        ):
            self.record.harness_status = status
            self.record.harness_detail = detail

    async def _play(self, store: ObservedStore, screening_ids: list[str]) -> None:
        rec, scenario, settings = self.record, self.scenario, self.settings
        candidate = await seed(store, settings, self.persona.name, settings.demo_candidate_phone)
        if scenario.setup is not None:
            await scenario.setup(SetupContext(store, settings, candidate, self.persona, self.today))
        before = await store.list_screenings(candidate.id)
        screening_ids.extend(s.id for s in before)
        rec.bookings_before = [
            {"screening_id": s.id, "slot_id": s.slot_id} for s in reversed(before) if s.slot_id
        ]

        summarizer = summarize_call
        if self.cfg.summary and settings.anthropic_api_key:
            summary_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            meter_summary_client(summary_client, rec.usage["summary"])
            summarizer = partial(summarize_call, client=summary_client)

        live_calls = LiveCalls()
        pending: _Live | None = None  # a call that is being superseded by the next one
        for index, plan in enumerate(scenario.plan, start=1):
            live = await self._start_call(index, store, candidate, live_calls, summarizer)
            screening_ids.append(live.record.screening_id)
            if pending is not None:  # start_screening ended it and waited for its final status
                await self._finish(store, pending)
                pending = None
            rec.calls.append(live.record)
            outcome = await self._talk(store, live, plan)
            if outcome == "superseded":
                pending = live
                continue
            await self._finish(store, live)
            if (
                rec.harness_status != "ok"
                or live.record.unresponsive
                or live.record.end_reason == "llm_error"
            ):
                break  # later calls would only continue a conversation Sofia did not hold
        if pending is not None:  # defensive: the last plan entry cannot supersede
            await self._finish(store, pending)

        screenings = list(reversed(await store.list_screenings(candidate.id)))
        rec.screenings = [
            {
                "id": s.id,
                "status": s.status.value,
                "outcome": s.outcome.value if s.outcome else None,
                "attempt": s.attempt,
                "previous_screening_id": s.previous_screening_id,
                "slot_id": s.slot_id,
            }
            for s in screenings
        ]
        rec.bookings = [
            {"screening_id": s.id, "slot_id": s.slot_id} for s in screenings if s.slot_id
        ]
        expected = self.persona.expected_facts(self.today)
        for name, spec in scenario.expect.corrected.items():
            expected[name] = resolve_date(spec, self.today).isoformat()
        rec.expected_facts = expected
        if rec.calls:
            rec.final_facts = rec.calls[-1].facts_end
        if scenario.kb is not None and self.cfg.kb is not None:
            ids = {
                cid
                for c in rec.calls
                for e in events_of(c, "kb_search")
                for cid in e["data"].get("chunk_ids") or []
            }
            rec.kb_chunks = self.cfg.kb.chunk_info(ids)
        if rec.valid and (why := exercised_problem(rec, scenario.expect)):
            self._invalid("trigger_missed", why)
        rec.checks = run_checks(rec, scenario.expect)
        if self.cfg.judge and rec.valid:
            await self._judge()

    async def _start_call(
        self,
        index: int,
        store: ObservedStore,
        candidate: Candidate,
        live_calls: LiveCalls,
        summarizer: Any,
    ) -> _Live:
        settings = self.settings
        screening = await start_screening(
            store,
            live_calls,
            candidate,
            channel=Channel.TEXT,
            timezone=settings.timezone,
            supersede_wait_secs=settings.supersede_wait_secs,
        )
        facts = await store.get_facts(screening.id)
        context = await load_call_context(store, screening)
        record = CallRecord(
            index=index,
            screening_id=screening.id,
            attempt=screening.attempt,
            previous_screening_id=screening.previous_screening_id,
            mode=context.mode.value,
            facts_at_start=facts.model_dump(mode="json", exclude_none=True),
            fields_at_start=sorted(fact_fields(facts)),
        )
        call = TextCall(
            screening.id,
            store=store,
            settings=settings,
            summarizer=summarizer,
            live_calls=live_calls,
            knowledge=await self._knowledge(),
        )
        store.live.add(screening.id)
        call.start()
        return _Live(call, record)

    async def _knowledge(self) -> KnowledgeBase | None:
        """The call's knowledge base: none, one that is down, or the shared index (slow or not)."""
        spec = self.scenario.kb
        if spec is None:
            return None
        if spec.mode == "down":
            return down_knowledge_base()
        if self.cfg.kb is None:
            raise RuntimeError(f"scenario {self.scenario.id} needs the knowledge index (KbHub)")
        return await self.cfg.kb.knowledge(spec)

    def _take(self, record: CallRecord, transcript: list[tuple[str, str]], reply: str) -> bool:
        """Record one reply of Sofia's. True when it is (or carries) the holding line, which
        the text channel delivers as a reply of its own: the answer follows as another."""
        transcript.append(("agent", reply))
        record.transcript.append(Turn("agent", reply))
        self._note_drift(record, reply)
        return self.scenario.kb is not None and self.holding_line in reply

    async def _drain(
        self, call: TextCall, record: CallRecord, transcript: list[tuple[str, str]]
    ) -> bool:
        """Take the replies that arrived while the candidate was thinking (a result delivered
        late can make Sofia speak on her own). True when the call has ended."""
        while True:
            try:
                reply = await call.next_reply(0.05)
            except TimeoutError:
                return False
            if reply is None:
                return True
            self._take(record, transcript, reply)

    async def _talk(
        self, store: ObservedStore, live: _Live, plan: CallPlan
    ) -> Literal["done", "superseded"]:
        """Play the call until Sofia ends it, the drop condition holds or something fails.
        Returns "superseded" when the call is left running for the next call to end."""
        call, record = live.call, live.record
        cond = plan.drop or plan.supersede
        system = simulator_system(
            self.language,
            self.persona.card_text(self.today),
            render_instruction(plan.text(self.language), self.today),
            other_language(self.language) if self.scenario.expect.language_switch else None,
        )
        transcript: list[tuple[str, str]] = []
        answered = 0  # candidate lines Sofia has fully replied to
        sent = 0
        while True:
            state, reply = await read_reply(
                call,
                store,
                record.screening_id,
                cond,
                answered,
                self.cfg.reply_timeout_secs,
                failed=lambda: call.quota_error is not None,
            )
            if call.quota_error is not None:
                return await self._provider_refused(live, record)
            while state == "reply" and reply is not None:
                holding = self._take(record, transcript, reply)
                if sent and not holding:
                    answered = sent
                screening = await store.get_screening(record.screening_id)
                if cond is not None and cond.satisfied(
                    await snapshot(store, record.screening_id, answered)
                ):
                    state = "triggered"
                elif call.ending or (screening and screening.status is ScreeningStatus.COMPLETED):
                    # The reply was Sofia's fixed apology (her LLM kept failing), or end_call
                    # finished the screening before the reply flushed: nothing more to say.
                    state = "ended"
                if state != "reply" or not holding or self.scenario.kb is None:
                    break
                if self.scenario.kb.mode == "slow":
                    break  # the candidate keeps talking: the result is delivered late
                # Inline path: the answer is the next reply. If it does not come in time the
                # search is slow after all: carry on (the result is delivered late).
                state, reply = await read_reply(
                    call,
                    store,
                    record.screening_id,
                    cond,
                    answered,
                    self.cfg.answer_wait_secs,
                    failed=lambda: call.quota_error is not None,
                )
                if state == "timeout":
                    state = "reply"
                    break
            if call.quota_error is not None:
                return await self._provider_refused(live, record)
            if state == "ended":
                live.ended_by = "agent"
                if cond is not None and not await self._gave_up(call):
                    self._invalid(
                        "trigger_missed",
                        f"call {record.index} ended on its own before the condition "
                        f"'{cond.description}' held",
                    )
                return "done"
            if state == "triggered" and cond is not None:
                if await self._already_complete(store, record.screening_id):
                    # Sofia finished the screening (end_call) in the same breath as the fact
                    # that fires the condition: dropping now would not drop a dropped call.
                    live.ended_by = "agent"
                    self._invalid(
                        "trigger_missed",
                        f"call {record.index}: Sofia ended the call as the condition "
                        f"'{cond.description}' became true",
                    )
                    return "done"
                live.ended_by = cond.description
                if plan.supersede is not None:
                    live.ended_by = f"superseded: {cond.description}"
                    return "superseded"
                await call.drop()
                return "done"
            if state == "timeout":
                # Silence is Sofia's failure, so the run stays valid and `responsive` fails (a
                # stalled LLM request nobody recovered is a bug of the app). Unlike the turn
                # limit below: a call that never ends cannot be pinned on Sofia rather than on
                # the simulated candidate, but silence in the middle of a turn can.
                live.ended_by = "timeout"
                record.unresponsive = True
                await call.drop()
                return "done"
            if sent >= self.cfg.max_turns:
                # Invalid, not a failure: the call keeps going because either side may be
                # keeping it going (a looping simulated candidate looks the same).
                live.ended_by = "max_turns"
                kind = "trigger_missed" if cond is not None else "did_not_finish"
                self._invalid(kind, f"call {record.index}: {sent} candidate turns, not finished")
                await call.drop()
                return "done"
            line = await simulate_line(
                self.cfg.client,
                system,
                transcript,
                self.persona.name,
                self.record.usage["simulator"],
            )
            if self.scenario.kb is not None and await self._drain(call, record, transcript):
                continue  # the call ended while the candidate was thinking
            transcript.append(("candidate", line))
            record.transcript.append(Turn("candidate", line))
            # (A language-switch scenario has the candidate change language on purpose.)
            if not self.scenario.expect.language_switch and detect(line).drifted(self.language):
                # The simulator left the call language: the run no longer tests a call in
                # that language, so it is invalid (a harness problem, not a Sofia failure).
                self._invalid(
                    "simulator_drift",
                    f"call {record.index}: the simulated candidate spoke another language: "
                    f"{line[:80]!r}",
                )
            sent += 1
            await call.send(line)

    async def _provider_refused(self, live: _Live, record: CallRecord) -> Literal["done"]:
        """The provider refused Sofia's request after the SDK's retries (rate limit or quota):
        the run says nothing about Sofia, so it is invalid, not a failure."""
        live.ended_by = "provider_quota"
        self._invalid(
            "provider_quota",
            f"call {record.index}: {self.settings.llm_provider} refused Sofia's request "
            f"(rate limit / quota): {live.call.quota_error}",
        )
        await live.call.drop()
        return "done"

    async def _gave_up(self, call: TextCall) -> bool:
        """The call ended because Sofia's LLM kept failing (she apologized and hung up). That
        is a Sofia failure (check `responsive`), not a condition the harness missed."""
        try:
            await asyncio.wait_for(call.wait_done(), self.cfg.finalize_timeout_secs)
        except TimeoutError:
            return False
        return await call.end_reason() == "llm_error"

    @staticmethod
    async def _already_complete(store: ObservedStore, screening_id: str) -> bool:
        screening = await store.get_screening(screening_id)
        return screening is not None and screening.status is ScreeningStatus.COMPLETED

    def _note_drift(self, record: CallRecord, text: str) -> None:
        det = detect(text)
        record.drift.append(
            DriftTurn(
                turn=len([t for t in record.transcript if t.role == "agent"]) - 1,
                lang=det.lang,
                es_hits=det.es_hits,
                en_hits=det.en_hits,
                drifted=det.drifted(self.language),
                text=text,
                at=time.time(),
            )
        )

    async def _finish(self, store: ObservedStore, live: _Live) -> None:
        """Wait for finalize and copy the call's stored state into its record."""
        call, record = live.call, live.record
        try:
            await asyncio.wait_for(call.wait_done(), self.cfg.finalize_timeout_secs)
        except TimeoutError:
            self._invalid("error", f"call {record.index}: finalize did not finish")
        store.live.discard(record.screening_id)
        sid = record.screening_id
        record.ended_by = live.ended_by
        screening = await store.get_screening(sid)
        if screening is not None:
            record.status = screening.status.value
            record.outcome = screening.outcome.value if screening.outcome else None
            record.slot_id = screening.slot_id
        record.end_reason = await call.end_reason()
        record.llm_errors = list(call.llm_errors)
        record.saved_transcript = await store.get_transcript(sid)
        record.tool_calls = [
            ToolCallRecord(t.name, t.args, t.result, t.status, t.ok)
            for t in await store.get_tool_calls(sid)
        ]
        record.facts_end = (await store.get_facts(sid)).model_dump(mode="json")
        if (
            self.scenario.kb is not None
            or self.scenario.frustration_notes
            or self.scenario.expect.language_switch
        ):
            # These events are only in the Redis timeline (deleted when the run ends).
            record.events = [
                e for e in await store.get_events(sid) if keeps_event(self.scenario, e["type"])
            ]
        if self.scenario.expect.language_switch:
            mark_switch_drift(record, self.language)
        if self.scenario.kb is not None:
            record.referred_questions = [
                r.model_dump(mode="json")
                for r in await store.list_referred_questions(screening_id=sid)
            ]
        if (summary := await store.get_summary(sid)) is not None:
            record.summary_source = summary.source
        if (card := await store.get_call_metrics(sid)) and card.cost:
            record.llm_retries = card.cost.llm_retries
            add_agent_usage(
                self.record.usage["agent"],
                self.settings.llm_provider,
                calls=card.cost.llm_calls,
                prompt_tokens=card.cost.prompt_tokens,
                completion_tokens=card.cost.completion_tokens,
                cache_read_tokens=card.cost.cache_read_tokens,
                reasoning_tokens=card.cost.reasoning_tokens,
            )
        # Every request's time to first byte, from the event timeline (the Redis keys are
        # deleted only when the run ends, so they are still there).
        self.record.llm_ttfb_secs.extend(
            float(e["data"]["seconds"])
            for e in await store.get_events(sid)
            if e["type"] == "llm.ttfb"
        )

    async def _judge(self) -> None:
        rec = self.record
        try:
            items = await judge_run(
                self.cfg.client,
                self.language,
                rec.calls,
                rec.final_facts,
                self.scenario.judge_extra,
                rec.usage["judge"],
                kb_chunks=rec.kb_chunks,
                switched_to=(
                    other_language(self.language) if self.scenario.expect.language_switch else None
                ),
            )
        except Exception as exc:
            logger.exception(f"[{self.key}] judge failed")
            rec.judge_error = f"{type(exc).__name__}: {exc}"
            return
        rec.judge = []
        for i in items:
            dropped = bool(i.evidence.strip()) and not evidence_found(i.evidence, rec.calls, i.call)
            evidence = "" if dropped else i.evidence
            rec.judge.append(JudgeVerdict(i.id, i.answer, evidence, i.call, dropped))
