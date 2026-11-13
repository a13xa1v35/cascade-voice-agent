"""The pipeline for one screening call.

Voice (browser, phone):

    transport.input -> STT -> user aggregator -> LLM (+tools) -> TTS -> transport.output
                                                                        -> assistant aggregator

The assistant aggregator sits after transport.output so the context records what was
actually spoken (important when the caller interrupts).

Text (`Channel.TEXT`, see textcall.py): the same pipeline without audio. The transport's
input injects typed turns, its output collects Sofia's replies, and there is no STT, TTS, VAD,
audio watchdog or hang-up controller:

    transport.input -> user aggregator -> LLM (+tools) -> transport.output -> assistant aggregator

`channel` is the one switch between the three; everything else (prompt, tools, context,
observers, `_finalize`) is shared.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, ErrorFrame, LLMRunFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import NOT_GIVEN, LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregator,
    LLMContextAggregatorPair,
    LLMUserAggregator,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.llm_service import LLMService
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_turn_strategies import ExternalUserTurnStrategies, UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from hr_screener import i18n
from hr_screener.agent.prompt_text import PROMPT, TOOLS, fmt
from hr_screener.agent.prompts import SystemPrompt, build_system_prompt_parts
from hr_screener.agent.tools import (
    CallLanguage,
    SearchState,
    ToolDeps,
    build_tools,
    knowledge_offered,
)
from hr_screener.config import Settings
from hr_screener.llm.recovery import LLMRecovery
from hr_screener.models import (
    Candidate,
    Channel,
    Outcome,
    ReferredQuestion,
    Screening,
    ScreeningStatus,
)
from hr_screener.observability.metrics import compute_scorecard
from hr_screener.observability.observers import CallObservers
from hr_screener.pipeline.frames import HoldingLineFrame, NoteEchoGuard
from hr_screener.pipeline.frustration import make_frustration_monitor, notes_available
from hr_screener.pipeline.hangup import HangupController
from hr_screener.pipeline.providers import make_llm, make_stt, make_tts, require_keys
from hr_screener.pipeline.watchdog import AudioWatchdog
from hr_screener.screening.calls import LiveCall, LiveCalls
from hr_screener.screening.followup import (
    CallContext,
    CallMode,
    ClosedContext,
    FollowUpContext,
    load_call_context,
)
from hr_screener.screening.qualification import evaluate, missing_questions
from hr_screener.screening.summary import Summarizer, fallback_summary, summarize_call
from hr_screener.storage.store import ScreeningStore
from hr_screener.turn_taking.design import SYSTEM_ONE_DESIGN, design_sha, system_one_hooks
from hr_screener.turn_taking.events import recording_sink
from hr_screener.turn_taking.policy import question_set_sha

if TYPE_CHECKING:
    from hr_screener.knowledge.store import KnowledgeBase

# Stored as the screening's notes when the call history could not be loaded.
CONTEXT_UNAVAILABLE_NOTE = "context_unavailable"
# Stored as the notes of a screening whose call ended because Sofia's LLM kept failing. Its
# status is inferred like a dropped call's (see `_finish_status`), so it stays resumable.
LLM_ERROR_NOTE = "llm_error"
IDLE_TIMEOUT_SECS = 120  # end the session if nobody speaks or is spoken to for this long
# A typing human is slower than a speaking one; the text channel's owner can always drop().
TEXT_IDLE_TIMEOUT_SECS = 900


def extract_transcript(messages: list[Any]) -> list[dict[str, str]]:
    """Keep only what was said: user/assistant turns that have text content. Consecutive
    turns from the same role are merged into one (joined with a space): the STT often splits
    one utterance into several short user messages ("Pues hace años", "Para", ...)."""
    turns: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
            continue
        content = message.get("content")
        if isinstance(content, list):  # content parts: keep the text ones
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not isinstance(content, str) or not content.strip():
            continue
        text = content.strip()
        if turns and turns[-1]["role"] == message["role"]:
            turns[-1]["text"] += " " + text
        else:
            turns.append({"role": message["role"], "text": text})
    return turns


def _add_call_log(screening_id: str, settings: Settings) -> int | None:
    """Per-call log file: every loguru line tagged with this screening id goes to it."""
    try:
        path = Path(settings.call_log_dir) / f"{screening_id}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        return logger.add(
            path,
            level="DEBUG" if settings.debug_pipeline else "INFO",
            filter=lambda record: record["extra"].get("screening_id") == screening_id,
        )
    except Exception:
        logger.exception(f"[{screening_id}] could not open the per-call log file")
        return None


@dataclass
class ConversationPipeline:
    """Everything a runner needs from the conversation pipeline builder."""

    pipeline: Pipeline
    params: PipelineParams
    context: LLMContext
    user_agg: LLMUserAggregator
    assistant_agg: LLMAssistantAggregator
    llm: LLMService[Any] | None = None  # None without a system prompt (the apology path)
    note_guard: NoteEchoGuard | None = None  # right after the LLM (see frames.py)


def build_conversation_pipeline(
    transport: BaseTransport,
    settings: Settings,
    *,
    system_prompt: str | None,
    tools: Any,
    telephony: bool,
    text: bool = False,
    tool_handlers: Mapping[str, Any] | None = None,
    tool_options: Mapping[str, Mapping[str, Any]] | None = None,
    processors_after_input: Sequence[FrameProcessor] = (),
    user_turn_strategies: Callable[[LLMContext], UserTurnStrategies] | None = None,
    processors_before_aggregator: Callable[[LLMContext], list[FrameProcessor]] | None = None,
    user_params_overrides: Mapping[str, Any] | None = None,
    fixed_prefix: str | None = None,
) -> ConversationPipeline:
    """The turn-taking configuration in ONE place (VAD, aggregator params, processor
    order, sample rates). Shared by production calls (voice and text) and the
    Full-Duplex-Bench harness.

    `tools` goes into the LLM context (a ToolsSchema or direct functions); `tool_handlers`
    are registered on the LLM by name (needed when `tools` is a schema, as in production), with
    `tool_options[name]` as extra `register_function` arguments (the async knowledge search).
    `system_prompt=None` builds the pipeline without an LLM (the fixed apology of a call whose
    context is unavailable). `fixed_prefix` is the start of `system_prompt` that is the same for
    every call (`SystemPrompt.fixed`), which Anthropic caches under its own breakpoint.
    `text` drops audio: no STT, TTS or VAD, and turns are committed by the proposal frames the
    text transport sends, never interrupting.

    Variant hooks: production always passes the system-one design's (`system_one_hooks`) for voice
    calls and none for text. Without them, the pipeline keeps pipecat's default strategies (Silero
    VAD + Smart Turn) and the processor order unchanged: that is Sofia's turn-taking before
    2026-11-11, kept for the eval's `baseline` variant. The callables are factories
    because they need the context, which is created here:
    - `processors_after_input`: processors right after `transport.input()` (the audio watchdog).
    - `user_turn_strategies(context)` -> strategies for the user aggregator's params.
    - `processors_before_aggregator(context)` -> processors inserted between STT and the
      user aggregator.
    - `user_params_overrides`: extra `LLMUserAggregatorParams` fields to set by name (e.g.
      `user_turn_stop_timeout`, `empty_user_turn`)."""
    llm = (
        make_llm(settings, system_prompt, fixed_prefix=fixed_prefix)
        if system_prompt is not None
        else None
    )
    if llm is not None:
        for tool_name, handler in (tool_handlers or {}).items():
            llm.register_function(tool_name, handler, **(tool_options or {}).get(tool_name, {}))
    context = LLMContext(tools=tools)
    if text:
        # No audio, so no VAD and no turn analyzer. No interruptions: a text turn is only sent
        # once Sofia has finished.
        user_params = LLMUserAggregatorParams(
            user_turn_strategies=ExternalUserTurnStrategies(enable_interruptions=False)
        )
    else:
        user_params = LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())
    if user_turn_strategies is not None:
        user_params.user_turn_strategies = user_turn_strategies(context)
    for name, value in (user_params_overrides or {}).items():
        setattr(user_params, name, value)
    user_agg, assistant_agg = LLMContextAggregatorPair(context, user_params=user_params)
    extra = processors_before_aggregator(context) if processors_before_aggregator else []
    note_guard = NoteEchoGuard() if llm else None
    pipeline = Pipeline(
        [
            transport.input(),
            *processors_after_input,
            *([] if text else [make_stt(settings)]),
            *extra,
            user_agg,
            *([llm, note_guard] if llm and note_guard else []),
            *([] if text else [make_tts(settings)]),
            transport.output(),
            assistant_agg,
        ]
    )
    if text:
        params = PipelineParams(enable_metrics=True, enable_usage_metrics=True)
    else:
        # Twilio media streams are 8 kHz mu-law; match it end to end on the phone.
        # Web keeps pipecat's defaults (16 kHz in, 24 kHz out).
        params = PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=8000 if telephony else 16000,
            audio_out_sample_rate=8000 if telephony else 24000,
        )
    return ConversationPipeline(pipeline, params, context, user_agg, assistant_agg, llm, note_guard)


async def run_screening_bot(
    transport: BaseTransport,
    *,
    screening_id: str,
    store: ScreeningStore,
    settings: Settings,
    channel: Channel,
    summarizer: Summarizer = summarize_call,
    live_calls: LiveCalls | None = None,
    on_llm_error: Callable[[ErrorFrame, bool], None] | None = None,
    knowledge: "KnowledgeBase | None" = None,
) -> None:
    """Run one call to completion. The caller must already have claimed the screening
    (status -> in_progress); this function owns everything after that, including
    always leaving the screening in a final state.

    With `live_calls` the call is registered for its whole life, so a newer call for the same
    candidate can end it (end reason "superseded") and wait for its final status.

    `on_llm_error(error, is_quota)` is called for every error the LLM service reports (the
    eval uses it to tell a provider rate limit from a failure of Sofia's).

    With a `knowledge` base the call offers the knowledge tools (search_knowledge,
    refer_to_recruiter) in every mode but closed_rejected; without one it runs exactly as before."""
    settings = await _settings_for_candidate(store, screening_id, settings)
    observers = CallObservers(
        screening_id,
        debug=settings.debug_pipeline,
        redis=store.redis,
        events_ttl_secs=settings.events_ttl_days * 86400,
        on_llm_error=on_llm_error,
    )
    log_sink = _add_call_log(screening_id, settings)
    contexts: list[LLMContext] = []
    search = SearchState()  # shared by the tools and _finalize
    language = CallLanguage(settings.language)  # likewise: the tools can switch it
    live = live_calls.register(screening_id) if live_calls else None
    # contextualize() is a contextvar: tasks created inside it (pipecat's) inherit it.
    with logger.contextualize(screening_id=screening_id):
        try:
            await _run_call(
                transport,
                screening_id,
                store,
                settings,
                channel,
                observers,
                contexts,
                live,
                knowledge,
                search,
                language,
            )
        except Exception:
            logger.exception(f"[{screening_id}] bot crashed")
            observers.set_end_reason("error")
        finally:
            observers.log_summary()
            try:
                await _finalize(
                    screening_id,
                    store,
                    settings,
                    contexts[0] if contexts else None,
                    observers,
                    log_sink,
                    summarizer,
                    live.status_final.set if live else None,
                    search,
                    language,
                )
            finally:
                if live_calls:
                    live_calls.unregister(screening_id)


async def _settings_for_candidate(
    store: ScreeningStore, screening_id: str, settings: Settings
) -> Settings:
    """The settings of this call: the candidate's own language, when set, replaces the
    app-wide one. Everything after this (providers, prompt, tools, turn-taking, summary)
    reads the returned copy, never the app's settings."""
    screening = await store.get_screening(screening_id)
    candidate = await store.get_candidate(screening.candidate_id) if screening else None
    if candidate is not None and candidate.language:
        return settings.model_copy(update={"language": candidate.language})
    return settings


def opening_message(
    candidate: Candidate,
    followup: FollowUpContext | None,
    closed: ClosedContext | None = None,
    now: datetime | None = None,
) -> str:
    """The developer message that makes the bot speak first once the candidate is there.
    English like the rest of the context.
    `now` (aware, default the real clock) decides whether a booked session is past; pass the
    same one as to `build_system_prompt_parts`."""
    if closed is not None:
        if closed.outcome is not Outcome.SCHEDULED:
            key = "opening_closed_rejected"
        elif closed.session_passed(now or datetime.now(UTC)):
            key = "opening_closed_booked_past"
        else:
            key = "opening_closed_booked"
    else:
        key = "opening_followup" if followup else "opening"
    return fmt(PROMPT[key], first_name=candidate.first_name)


async def load_call_context_safe(store: ScreeningStore, screening: Screening) -> CallContext | None:
    """The call mode and its context, or None when the lookup fails. Callers must fail
    closed (see `_run_context_unavailable`): guessing "fresh" would re-screen, and maybe
    book, a candidate who is already booked or was rejected."""
    try:
        return await load_call_context(store, screening)
    except Exception:
        logger.exception(f"[{screening.id}] could not load the call context")
        return None


def _add_holding_line(
    llm: LLMService[Any],
    search_tool: str,
    search: SearchState,
    language: CallLanguage,
    observers: CallObservers,
) -> None:
    """Say a fixed line when a knowledge lookup starts, so the call does not go quiet.

    A fixed line (see i18n.search_holding_line), not one the model writes: text written
    around a tool call is spoken as it is, and that is where reasoning leaks. It is pushed
    with `append_to_context=False`: the model is told in the prompt that the line is played
    for it, and keeping it out of the context stops the history ending in an assistant
    message after the tool result (the Anthropic adapter would add a "." user turn), makes
    the voice and text channels build the same context, and leaves the transcript to what
    the model said. The recorder keeps a `kb_holding_line` event instead. A second search
    while one runs is refused, so it gets no line.
    """

    async def on_function_calls_started(service: Any, function_calls: list[Any]) -> None:
        if search.in_flight or not any(c.function_name == search_tool for c in function_calls):
            return
        line = i18n.search_holding_line(language.current)
        observers.recorder.record("kb_holding_line", text=line)
        await service.push_frame(HoldingLineFrame(line, append_to_context=False))

    llm.add_event_handler("on_function_calls_started", on_function_calls_started)


async def _run_call(
    transport: BaseTransport,
    screening_id: str,
    store: ScreeningStore,
    settings: Settings,
    channel: Channel,
    observers: CallObservers,
    contexts: list[LLMContext],
    live: LiveCall | None = None,
    knowledge: "KnowledgeBase | None" = None,
    search: SearchState | None = None,
    language: CallLanguage | None = None,
) -> None:
    text = channel is Channel.TEXT
    search = search or SearchState()
    language = language or CallLanguage(settings.language)
    require_keys(settings, text_only=text)
    screening = await store.get_screening(screening_id)
    candidate = await store.get_candidate(screening.candidate_id) if screening else None
    if screening is None or candidate is None:
        raise RuntimeError(f"screening {screening_id} or its candidate not found")

    opening = await store.get_opening(candidate.opening_id)
    if opening is None:
        raise RuntimeError(f"opening {candidate.opening_id} of candidate {candidate.id} not found")

    call = await load_call_context_safe(store, screening)
    now = datetime.now(ZoneInfo(settings.timezone))  # one clock reading for the whole call
    apology: str | None = None  # set when the call cannot run as a screening
    recovery: LLMRecovery | None = None  # set when the call has an LLM
    mode = CallMode.FRESH
    followup = closed = None
    if call is None:
        # Fail closed: without the history we cannot tell a new candidate from one who is
        # booked or rejected, so no screening runs and no LLM is involved. The pipeline
        # only speaks a fixed apology and ends. The screening stays resumable (FAILED, no
        # outcome), so the next call retries the lookup.
        apology = i18n.context_unavailable_apology(settings.language)
        observers.set_end_reason("context_unavailable")
        await store.finish_screening(
            screening_id, ScreeningStatus.FAILED, None, CONTEXT_UNAVAILABLE_NOTE
        )
        logger.error(f"[{screening_id}] call context unavailable: apologizing and ending")
    else:
        followup, closed, mode = call.followup, call.closed, call.mode
    if closed:
        logger.info(
            f"[{screening_id}] closed-mode call ({mode.value}): decided by "
            f"{closed.decided_screening_id} ({closed.outcome.value})"
        )
    if followup:
        logger.info(
            f"[{screening_id}] follow-up call: attempt {followup.attempt} of "
            f"{followup.previous_screening_id} ({followup.ended.value})"
        )
    prompt: SystemPrompt | None = None  # None: no LLM (the apology path)
    tools_schema: Any = NOT_GIVEN
    handlers: Mapping[str, Any] = {}
    with_knowledge = False
    search_tool = TOOLS["search_knowledge"].name
    tool_options: dict[str, Mapping[str, Any]] = {}  # extra register_function kwargs by tool
    if call is not None:
        with_knowledge = knowledge is not None and knowledge_offered(mode)
        prompt = build_system_prompt_parts(
            candidate,
            opening,
            settings,
            now=now,
            followup=followup,
            closed=closed,
            knowledge=with_knowledge,
            # Same value the monitor gets: the rules are in the prompt exactly when notes can come.
            frustration_notes=notes_available(settings),
        )
        tools_schema, handlers = build_tools(
            mode, knowledge=with_knowledge, kb_language=settings.kb_language
        )
        if with_knowledge:
            # Async tool: the conversation goes on while the lookup runs, a barge-in does not
            # cancel it, and Pipecat cancels a handler that hangs (`timeout_secs`, see
            # the README's knowledge base design).
            tool_options[search_tool] = {
                "cancel_on_interruption": False,
                "timeout_secs": settings.kb_tool_timeout_secs,
            }
    design_hooks: dict[str, Any] = {}
    if not text:
        # Every voice call is turn-taken by the system-one design, the same hooks the eval's
        # system_one variant uses; its events land in the call's recorder.
        design_hooks = system_one_hooks(
            settings,
            SYSTEM_ONE_DESIGN,
            recording_sink(
                observers.recorder.record, screening_id, keep_state=settings.debug_pipeline
            ),
            lang=lambda: language.current,
            agent_name=settings.agent_name,
        )
        questions_sha, design_id = question_set_sha(), design_sha()
        observers.recorder.record(
            "system1.config",
            language=settings.language,
            question_set_sha=questions_sha,
            design_sha=design_id,
        )
        logger.info(
            f"[{screening_id}] turn design: system_one design={design_id} "
            f"language={settings.language} questions_sha={questions_sha}"
        )
    # Browser only: end the call when the audio stops arriving (see watchdog.py).
    watchdog: AudioWatchdog | None = None
    if not text:
        watchdog = AudioWatchdog(
            0 if channel is Channel.PHONE else settings.audio_lost_secs,
            on_lost=lambda: end_call_now("connection_lost"),
            is_muted=lambda: _input_track_disabled(transport),
        )
    built = build_conversation_pipeline(
        transport,
        settings,
        system_prompt=prompt.text if prompt else None,
        fixed_prefix=prompt.fixed if prompt else None,
        tools=tools_schema,
        tool_handlers=handlers,
        tool_options=tool_options,
        telephony=channel is Channel.PHONE,
        text=text,
        processors_after_input=[watchdog] if watchdog else [],
        **design_hooks,
    )
    pipeline, params, context = built.pipeline, built.params, built.context
    user_agg, assistant_agg = built.user_agg, built.assistant_agg
    contexts.append(context)
    observers.attach_aggregators(user_agg, assistant_agg)
    # Voice and text; absent without the Cloudflare keys. Notes to Sofia only with the setting on.
    frustration = (
        make_frustration_monitor(
            settings, context, observers.recorder.record, lambda: observers.recorder.events
        )
        if apology is None
        else None
    )
    if frustration is not None:
        frustration.record_config()
        user_agg.add_event_handler("on_user_turn_stopped", frustration.on_user_turn_stopped)
    if built.note_guard is not None:
        built.note_guard.record = observers.recorder.record
    if built.llm is not None:
        observers.attach_llm(built.llm)
        if with_knowledge:
            _add_holding_line(built.llm, search_tool, search, language, observers)
        # A failed request is asked again once, then the call ends with an apology. Attached
        # before `observers.build()` (the worker below) so the observer list includes it.
        recovery = LLMRecovery(
            built.llm, observers, lambda: i18n.llm_error_apology(language.current)
        )
        observers.attach_recovery(recovery)
    # Voice: end_call arms this instead of closing the line; it hangs up after the goodbye
    # has played plus a grace window, unless the candidate speaks first (see hangup.py).
    # Text has no speech to wait for: end_call ends the pipeline directly (EndWorkerFrame)
    # and the end reason is inferred from the end_call tool event.
    hangup: HangupController | None = None
    if not text and apology is None:  # the apology path ends with an EndFrame, no end_call
        hangup = HangupController(
            record=observers.recorder.record,
            grace_secs=settings.hangup_grace_secs,
            on_fire=lambda: observers.set_end_reason("end_call"),
        )
        observers.attach_hangup(hangup)
    worker = PipelineWorker(
        pipeline,
        params=params,
        idle_timeout_secs=TEXT_IDLE_TIMEOUT_SECS if text else IDLE_TIMEOUT_SECS,
        observers=[*observers.build(), *([hangup] if hangup else [])],
        app_resources=ToolDeps(
            store=store,
            screening_id=screening_id,
            settings=settings,
            hangup=hangup,
            mode=mode,
            knowledge=knowledge,
            search=search,
            record=observers.recorder.record,
            confirm_start_date=followup is not None and not missing_questions(followup.facts),
            language=language,
            voice=not text,
        ),
    )
    if hangup is not None:
        # Graceful EndFrame only if the bot is still speaking; otherwise cancel at once so
        # late user speech cannot trigger a reply that would be cut off (see hangup.py).
        hangup.bind_end(worker.stop_when_done, immediate=lambda: worker.cancel(reason="hangup"))
        user_agg.add_event_handler("on_user_turn_started", hangup.on_user_turn_started)
        user_agg.add_event_handler("on_user_turn_stopped", hangup.on_user_turn_stopped)
    if recovery is not None:
        recovery.bind(worker.queue_frames)
    if frustration is not None:
        frustration.bind(worker.queue_frames)
    # The worker runs a TurnTrackingObserver by default; reuse it for turn logs.
    observers.attach_turn_tracking(worker.turn_tracking_observer)
    worker.add_event_handler("on_idle_timeout", observers.on_idle_timeout)
    # handle_sigint=False: uvicorn owns signal handling, not the runner.
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    async def end_call_now(reason: str) -> None:
        if recovery is not None:
            recovery.stop()
        observers.set_end_reason(reason)
        await runner.cancel()

    if live is not None:
        live.bind_stop(lambda: end_call_now("superseded"))

    async def kick_off() -> None:
        # The moment common to both channels (web waits for the client to be ready),
        # and the anchor for first-greeting latency.
        observers.call_connected()
        if watchdog is not None:
            watchdog.start()
        if apology is not None:
            # TTSSpeakFrame then EndFrame: the TTS service holds the EndFrame until the
            # utterance's audio contexts are closed, and the output transport drains its
            # audio before stopping, so the apology is heard before the line closes.
            # append_to_context=False: not a conversation turn, it must not become the
            # transcript (the next call would read it as a dropped conversation).
            await worker.queue_frames([TTSSpeakFrame(apology, append_to_context=False), EndFrame()])
            return
        context.add_message(
            {
                "role": "developer",
                "content": opening_message(candidate, followup, closed, now),
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    if channel is not Channel.WEBRTC:
        # Phone: the call is already live when the media stream connects. Text: the
        # transport reports "connected" once its pipeline has started.
        @transport.event_handler("on_client_connected")
        async def on_connected(transport: BaseTransport, client: Any) -> None:
            logger.info(f"[{screening_id}] {channel.value} client connected")
            await kick_off()
    else:
        # Browser: wait until the RTVI client says its audio is ready, or the
        # greeting would be spoken into the void.
        @worker.rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi: Any) -> None:
            logger.info(f"[{screening_id}] web client ready")
            await kick_off()

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport: BaseTransport, client: Any) -> None:
        logger.info(f"[{screening_id}] client disconnected")
        if recovery is not None:
            recovery.stop()
        observers.set_end_reason("hangup")
        await runner.cancel()

    if live is not None and live.end_requested:  # superseded before the pipeline started
        observers.set_end_reason("superseded")
        return
    observers.recorder.start()
    try:
        await runner.run()
    finally:
        if watchdog is not None:
            await watchdog.stop()
        if frustration is not None:  # before _finalize computes the scorecard
            await frustration.stop()


async def _finalize(
    screening_id: str,
    store: ScreeningStore,
    settings: Settings,
    context: LLMContext | None,
    observers: CallObservers,
    log_sink: int | None = None,
    summarizer: Summarizer = summarize_call,
    on_status_final: Callable[[], None] | None = None,
    search: SearchState | None = None,
    language: CallLanguage | None = None,
) -> None:
    """Persist the transcript, close the event timeline, make sure the screening ends in
    a final status, adopt the confirmed subjects, compute and store the call metrics and tool
    calls, then summarize the call.
    Removes the per-call log sink last.

    Everything stored here is in the language the call ended in (`language`, which the
    candidate may have switched), not the one it started in."""
    if language is not None and language.current != settings.language:
        settings = settings.model_copy(update={"language": language.current})
    try:
        if context is not None:
            await store.save_transcript(screening_id, extract_transcript(context.messages))

        await observers.hangup_close()  # no timer may call a stopped worker
        # End reason: with a hang-up controller it decides (see CallObservers.end_call);
        # without one, a screening that end_call already completed is the end_call path.
        before = await store.get_screening(screening_id)
        by_tool = bool(
            before and before.status is ScreeningStatus.COMPLETED and before.outcome is not None
        )
        reason = observers.end_call(ended_by_tool=by_tool)
        if search is not None:  # before the final flush, so the event reaches the timeline
            await _record_lost_questions(screening_id, store, settings, observers, search)
        await observers.recorder.stop()  # final flush
        logger.info(f"[{screening_id}] call ended: {reason}")

        await _finish_status(
            screening_id, store, settings, note=LLM_ERROR_NOTE if reason == "llm_error" else None
        )
        if on_status_final:  # a superseding call may now read the final status
            on_status_final()
        await _store_metrics(screening_id, store, observers)
        await _summarize(screening_id, store, settings, summarizer)
        # After the summary, so it still sees what the candidate declared on applying.
        await _confirm_candidate_subjects(screening_id, store)
    finally:
        if on_status_final:  # also when finalize failed early: never leave a waiter hanging
            on_status_final()
        if log_sink is not None:
            logger.remove(log_sink)


def _input_track_disabled(transport: BaseTransport) -> bool:
    """True while the browser reports its mic track as disabled (muted). Reads SmallWebRTC
    internals; if they change this returns False and the watchdog just stays armed."""
    try:
        track = getattr(getattr(transport.input(), "_client", None), "_audio_input_track", None)
        return track is not None and not track.is_enabled()
    except Exception:
        return False


async def _finish_status(
    screening_id: str, store: ScreeningStore, settings: Settings, note: str | None = None
) -> None:
    screening = await store.get_screening(screening_id)
    if screening is None or screening.status is not ScreeningStatus.IN_PROGRESS:
        return  # end_call already finished it (or it never started)

    # The call ended without end_call (hang-up, idle timeout, crash): infer what we can.
    facts = await store.get_facts(screening_id)
    opening = await store.opening_for_screening(screening_id)
    outcome: Outcome | None = None
    if screening.slot_id:
        outcome = Outcome.SCHEDULED
    elif opening is not None and not missing_questions(facts):
        today = datetime.now(ZoneInfo(settings.timezone)).date()
        qualified, _ = evaluate(facts, opening, today)
        outcome = None if qualified else Outcome.NOT_QUALIFIED

    status = ScreeningStatus.COMPLETED if outcome else ScreeningStatus.FAILED
    await store.finish_screening(
        screening_id, status, outcome, note or "call ended without end_call"
    )
    logger.info(f"[{screening_id}] finalized status={status.value} outcome={outcome}")


async def _record_lost_questions(
    screening_id: str,
    store: ScreeningStore,
    settings: Settings,
    observers: CallObservers,
    search: SearchState,
) -> None:
    """Every search that did not answer the candidate and that Sofia did not pass to a
    recruiter (`no_match`, `kb_unavailable`, a cancelled handler, a lookup still running when
    the call ended) leaves an automatic referred question, so no candidate question is lost.
    Best effort: it must never break finalize."""
    for query in search.unresolved():
        try:
            await store.create_referred_question(
                ReferredQuestion(
                    screening_id=screening_id,
                    # The model's Spanish search query (the only text the tool sees), not the
                    # candidate's own words.
                    question=query,
                    automatic=True,
                    language=settings.language,
                )
            )
            observers.recorder.record("question_referred", question=query, automatic=True)
            logger.info(f"[{screening_id}] unanswered question left to a recruiter: {query!r}")
        except Exception:
            logger.exception(f"[{screening_id}] could not save the referred question {query!r}")


async def _confirm_candidate_subjects(screening_id: str, store: ScreeningStore) -> None:
    """The candidate's subjects were declared when applying; if the call confirmed a
    different set, the confirmed one replaces it. The screening keeps what was said. Best
    effort: it must never break finalize."""
    try:
        screening = await store.get_screening(screening_id)
        candidate = await store.get_candidate(screening.candidate_id) if screening else None
        if candidate is None:
            return
        confirmed = (await store.get_facts(screening_id)).subjects
        if confirmed and set(confirmed) != set(candidate.subjects):
            await store.set_candidate_subjects(candidate.id, confirmed)
            logger.info(f"[{screening_id}] candidate subjects updated to the confirmed ones")
    except Exception:
        logger.exception(f"[{screening_id}] candidate subjects update failed")


async def _store_metrics(
    screening_id: str, store: ScreeningStore, observers: CallObservers
) -> None:
    """Compute from the in-memory timeline (complete, unlike the LTRIMmed Redis copy) and
    store the typed call_metrics row and the tool_calls. A metrics failure must never break
    finalize."""
    try:
        screening = await store.get_screening(screening_id)
        if screening is None:
            return
        facts = await store.get_facts(screening_id)
        card = compute_scorecard(observers.recorder.events, screening, facts)
        await store.save_call_metrics(screening_id, card)
        await store.save_tool_calls(screening_id, card.tool_calls)
        logger.info(f"[{screening_id}] call metrics stored ({card.event_count} events)")
    except Exception:
        logger.exception(f"[{screening_id}] call metrics failed (call data is unaffected)")


async def _summarize(
    screening_id: str, store: ScreeningStore, settings: Settings, summarizer: Summarizer
) -> None:
    """Runs last, once status, outcome, transcript and metrics are final and the pipeline
    is down. The summary is a direct API call (bounded by summary_timeout_secs); it is best
    effort and must never break finalize."""
    try:
        screening = await store.get_screening(screening_id)
        candidate = await store.get_candidate(screening.candidate_id) if screening else None
        opening = await store.opening_for_screening(screening_id)
        if screening is None or candidate is None or opening is None:
            return
        facts = await store.get_facts(screening_id)
        transcript = await store.get_transcript(screening_id)
        try:
            summary = await summarizer(settings, candidate, opening, screening, facts, transcript)
        except Exception:
            logger.exception(f"[{screening_id}] summary failed, using the facts-based fallback")
            summary = fallback_summary(settings, screening, facts, opening)
        await store.save_summary(screening_id, summary)
        logger.info(f"[{screening_id}] summary stored (source={summary.source})")
    except Exception:
        logger.exception(f"[{screening_id}] summary failed (call data is unaffected)")
