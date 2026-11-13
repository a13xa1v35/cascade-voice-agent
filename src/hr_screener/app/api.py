"""FastAPI app: REST for candidates/screenings, WebRTC signaling, Twilio webhooks.

We build our own app instead of using `pipecat.runner.run.main` because this backend
owns the session state (SQL database). The WebRTC and prebuilt-UI wiring mirrors what pipecat's
runner does, so the stock browser client at /client works unchanged.
"""

import asyncio
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, RedirectResponse, Response
from loguru import logger
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)
from pipecat_ai_prebuilt.frontend import PipecatPrebuiltUI
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine
from twilio.request_validator import RequestValidator

from hr_screener import i18n
from hr_screener.app.demo import (
    MIN_FUTURE_SLOTS,
    DemoAccessIn,
    DemoCallIn,
    access_code_valid,
    demo_options,
)
from hr_screener.app.gate import PasswordGate
from hr_screener.app.seed import ensure_demo_data
from hr_screener.app.telephony import place_outbound_call
from hr_screener.config import Settings
from hr_screener.knowledge.service import open_knowledge_base
from hr_screener.knowledge.store import KnowledgeBase
from hr_screener.models import (
    Candidate,
    Channel,
    Opening,
    Outcome,
    Screening,
    ScreeningFacts,
    ScreeningStatus,
    Subject,
)
from hr_screener.pipeline.bot import run_screening_bot
from hr_screener.pipeline.providers import missing_keys
from hr_screener.pipeline.transports import make_twilio_transport, make_webrtc_transport
from hr_screener.screening.calls import LiveCalls, supersede_live_call
from hr_screener.screening.followup import (
    decisive_screening,
    default_candidate,
    local_today,
    new_screening,
)
from hr_screener.screening.qualification import evaluate, missing_questions
from hr_screener.storage.db import make_engine
from hr_screener.storage.store import ScreeningStore

DEMO_PAGE = Path(__file__).parent / "static" / "demo.html"


# --- dependencies ---------------------------------------------------------------


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_store(request: Request) -> ScreeningStore:
    store: ScreeningStore = request.app.state.store
    return store


SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[ScreeningStore, Depends(get_store)]


async def verify_twilio_signature(request: Request, settings: SettingsDep) -> None:
    """Reject webhooks that Twilio did not sign (skipped if no auth token is configured).

    Twilio signs the exact public URL it called. Behind ngrok `request.url` is the
    internal http://localhost URL, so rebuild the URL from PUBLIC_BASE_URL instead.
    """
    if not settings.twilio_auth_token:
        return
    url = settings.public_base_url.rstrip("/") + request.url.path
    if request.url.query:
        url += f"?{request.url.query}"
    form = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    if not RequestValidator(settings.twilio_auth_token).validate(url, dict(form), signature):
        logger.warning(f"invalid Twilio signature for {url}")
        raise HTTPException(status_code=403, detail="invalid Twilio signature")


# --- request bodies --------------------------------------------------------------


class CandidateIn(BaseModel):
    name: str
    phone: str  # E.164, e.g. +15551234567
    opening_id: str | None = None  # default: the first (oldest) opening
    location: str | None = None  # default: the opening's location
    subjects: list[Subject] = []  # the subjects declared when applying
    language: Literal["en", "es"] | None = None  # None: the app-wide LANGUAGE setting


class ScreeningIn(BaseModel):
    candidate_id: str
    channel: Literal[Channel.WEBRTC, Channel.PHONE] = Channel.WEBRTC  # text is not an API call
    resume: bool = True  # False forces a fresh call even if the last one is resumable


# --- app factory -----------------------------------------------------------------


def create_app(
    redis: Redis | None = None,
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
    knowledge: KnowledgeBase | None = None,
) -> FastAPI:
    """Build the app. Tests inject a fakeredis client, an engine and a knowledge base;
    production builds them from REDIS_URL and DATABASE_URL (the schema comes from `make
    migrate`) and opens the knowledge base once at startup (syncing KB_DIR into Qdrant first
    when KB_SYNC_ON_STARTUP is on), closing it on shutdown. It never fails the app: without a
    usable knowledge base the search tool reports `kb_unavailable`."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        client = redis or Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.settings = settings
        db = engine or make_engine(settings.database_url)
        app.state.store = ScreeningStore(db, client)
        app.state.webrtc_handler = SmallWebRTCRequestHandler()
        app.state.bot_tasks = set()
        app.state.live_calls = LiveCalls()  # per process, see calls.py
        kb = knowledge or await open_knowledge_base(settings, redis=client)
        app.state.knowledge = kb
        yield
        for task in list(app.state.bot_tasks):
            task.cancel()
        await asyncio.gather(*app.state.bot_tasks, return_exceptions=True)
        await app.state.webrtc_handler.close()
        if knowledge is None:  # only close what we created
            await kb.close()
        if redis is None:  # only close what we created
            await client.aclose()
        if engine is None:
            await db.dispose()

    app = FastAPI(title="HR Screener", lifespan=lifespan)

    def spawn(coro: Coroutine[Any, Any, None]) -> None:
        """Run a bot in the background, holding a reference so it is not garbage collected."""
        task = asyncio.create_task(coro)
        app.state.bot_tasks.add(task)
        task.add_done_callback(app.state.bot_tasks.discard)

    async def supersede(store: ScreeningStore, settings: Settings, candidate_id: str) -> None:
        """Call before creating a candidate's new screening: ends their still-running call."""
        await supersede_live_call(
            store, app.state.live_calls, candidate_id, settings.supersede_wait_secs
        )

    # --- health ---

    @app.get("/health")
    async def health(store: StoreDep) -> dict[str, Any]:
        for name, ping in (("database", store.ping_db), ("redis", store.ping_redis)):
            try:
                await ping()
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"{name} unavailable: {exc}") from exc
        return {"status": "ok", "db": True, "redis": True}

    # --- candidates ---

    @app.post("/candidates", status_code=201)
    async def create_candidate(body: CandidateIn, store: StoreDep) -> Candidate:
        if body.opening_id:
            opening = await store.get_opening(body.opening_id)
            if opening is None:
                raise HTTPException(status_code=404, detail="opening not found")
        else:
            found = await store.list_openings()
            if not found:
                raise HTTPException(
                    status_code=409, detail="no opening to apply to: run `make seed` first"
                )
            opening = found[0]
        candidate = Candidate(
            name=body.name,
            phone=body.phone,
            location=body.location or opening.location,
            opening_id=opening.id,
            subjects=list(dict.fromkeys(body.subjects)),
            language=body.language,
        )
        return await store.create_candidate(candidate)

    @app.get("/candidates/{candidate_id}")
    async def get_candidate(candidate_id: str, store: StoreDep) -> Candidate:
        candidate = await store.get_candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        return candidate

    # --- openings ---

    @app.get("/openings")
    async def list_openings(store: StoreDep) -> list[Opening]:
        return await store.list_openings()

    # --- slots ---

    @app.get("/slots")
    async def list_slots(store: StoreDep, settings: SettingsDep, limit: int = 20) -> list[dict]:
        tz = ZoneInfo(settings.timezone)
        slots = await store.list_open_slots(datetime.now(tz), limit=limit)
        return [
            {
                **s.model_dump(mode="json"),
                "when": i18n.format_slot_time(s.starts_at, tz, settings.language),
                "location": i18n.render_location(s, settings.language),
            }
            for s in slots
        ]

    # --- screenings ---

    async def dial_candidate(
        store: ScreeningStore, settings: Settings, candidate: Candidate, *, resume: bool = True
    ) -> dict[str, Any]:
        """Place the outbound call to the candidate (shared by POST /screenings and the demo)."""
        # Phone: never dial a candidate whose case is decided (booked or not qualified). If
        # they get in touch themselves (browser), Sofia tells them where they stand instead.
        if decided := await decisive_screening(store, candidate.id):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "candidate_closed",
                    "screening_id": decided.id,
                    "outcome": decided.outcome,
                },
            )

        # Fail fast on configuration problems, before we create anything.
        problems = missing_keys(settings)
        for name, value in {
            "PUBLIC_BASE_URL": settings.public_base_url,
            "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
            "TWILIO_FROM_NUMBER": settings.twilio_from_number,
        }.items():
            if not value:
                problems.append(name)
        if problems:
            raise HTTPException(status_code=503, detail=f"missing settings: {', '.join(problems)}")

        await supersede(store, settings, candidate.id)
        # Status must be `dialing` BEFORE the call is placed: the media-stream websocket
        # can arrive as soon as the callee answers and only accepts `dialing` screenings.
        screening = await new_screening(
            store,
            candidate,
            Channel.PHONE,
            today=local_today(settings.timezone),
            resume=resume,
            status=ScreeningStatus.DIALING,
        )
        try:
            call_sid = await place_outbound_call(screening, candidate, settings)
        except Exception as exc:
            logger.exception("failed to place call")
            await store.finish_screening(screening.id, ScreeningStatus.FAILED, None, str(exc))
            raise HTTPException(status_code=502, detail=f"Twilio call failed: {exc}") from exc
        await store.update_screening(screening.id, call_sid=call_sid)
        return {
            "screening": await store.get_screening(screening.id),
            "previous_screening_id": screening.previous_screening_id,
            "attempt": screening.attempt,
            "call_sid": call_sid,
        }

    @app.post("/screenings", status_code=201)
    async def create_screening(
        body: ScreeningIn, store: StoreDep, settings: SettingsDep
    ) -> dict[str, Any]:
        candidate = await store.get_candidate(body.candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="candidate not found")

        if body.channel is Channel.WEBRTC:
            await supersede(store, settings, candidate.id)
            screening = await new_screening(
                store,
                candidate,
                Channel.WEBRTC,
                today=local_today(settings.timezone),
                resume=body.resume,
            )
            return {
                "screening": screening,
                "previous_screening_id": screening.previous_screening_id,
                "attempt": screening.attempt,
                "session_id": screening.id,
                "open": "/client/",
                "note": (
                    "Open /client/ and click connect: the web UI starts its own session via "
                    "POST /start (DEMO_CANDIDATE_ID, else the most recent candidate). Custom "
                    "clients can pass {'screening_id': session_id} to POST /start to "
                    "attach to this screening."
                ),
            }

        return await dial_candidate(store, settings, candidate, resume=body.resume)

    def qualification_for(
        facts: ScreeningFacts, opening: Opening | None, settings: Settings
    ) -> dict[str, Any]:
        """Whether the facts are complete and, when they are, the deterministic verdict."""
        missing = missing_questions(facts)
        qualification: dict[str, Any] = {
            "complete": not missing,
            "missing": [q.value for q in missing],
        }
        if not missing and opening is not None:
            today = datetime.now(ZoneInfo(settings.timezone)).date()
            qualified, reasons = evaluate(facts, opening, today)
            qualification |= {"qualified": qualified, "reasons": reasons}
        return qualification

    @app.get("/screenings/{screening_id}")
    async def get_screening(
        screening_id: str, store: StoreDep, settings: SettingsDep
    ) -> dict[str, Any]:
        screening = await store.get_screening(screening_id)
        if screening is None:
            raise HTTPException(status_code=404, detail="screening not found")

        facts = await store.get_facts(screening_id)
        opening = await store.opening_for_screening(screening_id)
        qualification = qualification_for(facts, opening, settings)

        slot = await store.get_slot(screening.slot_id) if screening.slot_id else None
        return {
            "screening": screening,
            "candidate": await store.get_candidate(screening.candidate_id),
            "opening": opening,
            "facts": facts,
            "qualification": qualification,
            "slot": slot,
            "transcript": await store.get_transcript(screening_id),
            "summary": await store.get_summary(screening_id),
            "referred_questions": await store.list_referred_questions(screening_id=screening_id),
            "previous_screenings": [
                s.id
                for s in await store.list_screenings(screening.candidate_id)
                if s.id != screening.id and s.created_at < screening.created_at
            ],
            "metrics_url": f"/screenings/{screening_id}/metrics",
        }

    @app.get("/screenings/{screening_id}/metrics")
    async def get_screening_metrics(screening_id: str, store: StoreDep) -> dict[str, Any]:
        """The scorecard: computed from the event timeline while Redis still has it; after
        the events expire, rebuilt from call_metrics + tool_calls (`exchanges_expired`);
        else the task section only with `partial: true`."""
        card = await store.load_scorecard(screening_id)
        if card is None:
            raise HTTPException(status_code=404, detail="screening not found")
        return card

    # --- WebRTC (browser) ---

    webrtc = APIRouter()  # only included when WEB_UI_ENABLED

    async def _resolve_webrtc_screening(
        store: ScreeningStore, settings: Settings, screening_id: str | None, resume: bool = True
    ) -> Screening:
        """Load the given screening, or start a new one for the demo candidate."""
        if screening_id:
            screening = await store.get_screening(screening_id)
            if screening is None:
                raise HTTPException(status_code=404, detail="unknown session")
            return screening

        candidate = await default_candidate(store, settings)
        if candidate is None:
            raise HTTPException(
                status_code=409,
                detail="no candidate to call: run `make seed` or POST /candidates first",
            )
        await supersede(store, settings, candidate.id)
        return await new_screening(
            store, candidate, Channel.WEBRTC, today=local_today(settings.timezone), resume=resume
        )

    @webrtc.post("/start")
    async def start(request: Request, store: StoreDep, settings: SettingsDep) -> dict[str, Any]:
        """What the prebuilt UI calls first. We use the screening id as the session id."""
        try:
            data = await request.json()
        except Exception:
            data = {}
        # The prebuilt UI nests custom data under "body"; accept either place.
        options = {**data, **(data.get("body") or {})} if isinstance(data, dict) else {}

        resume = options.get("resume") is not False
        if candidate_id := options.get("candidate_id"):
            candidate = await store.get_candidate(candidate_id)
            if candidate is None:
                raise HTTPException(status_code=404, detail="candidate not found")
            await supersede(store, settings, candidate.id)
            screening = await new_screening(
                store,
                candidate,
                Channel.WEBRTC,
                today=local_today(settings.timezone),
                resume=resume,
            )
        else:
            screening = await _resolve_webrtc_screening(
                store, settings, options.get("screening_id"), resume
            )
        return {
            "sessionId": screening.id,
            "previous_screening_id": screening.previous_screening_id,
            "attempt": screening.attempt,
        }

    async def _handle_offer(
        offer: SmallWebRTCRequest, store: ScreeningStore, settings: Settings, session_id: str | None
    ) -> dict[str, Any] | None:
        session_id = session_id or (offer.request_data or {}).get("screening_id")
        if session_id is None:
            raise HTTPException(status_code=400, detail="missing session id")

        claimed = False
        if offer.pc_id is None:  # a brand-new connection (not a renegotiation)
            if problems := missing_keys(settings):
                raise HTTPException(
                    status_code=503, detail=f"missing settings: {', '.join(problems)}"
                )
            screening = await _resolve_webrtc_screening(store, settings, session_id)
            # Claim the screening so one session cannot start two bots.
            claimed = await store.transition_status(
                screening.id, ScreeningStatus.PENDING, ScreeningStatus.IN_PROGRESS
            )
            if not claimed:
                raise HTTPException(status_code=409, detail="session already used")

        async def on_connection(connection: SmallWebRTCConnection) -> None:
            if not claimed:
                return
            spawn(
                run_screening_bot(
                    make_webrtc_transport(connection),
                    screening_id=session_id,
                    store=store,
                    settings=settings,
                    channel=Channel.WEBRTC,
                    live_calls=app.state.live_calls,
                    knowledge=app.state.knowledge,
                )
            )

        try:
            answer: dict[str, Any] | None = await app.state.webrtc_handler.handle_web_request(
                request=offer, webrtc_connection_callback=on_connection
            )
        except Exception:
            if claimed:  # signaling failed, so no bot will ever run: don't leave it hanging
                await store.finish_screening(
                    session_id, ScreeningStatus.FAILED, None, "webrtc signaling failed"
                )
            raise
        return answer

    @webrtc.post("/api/offer")
    async def offer_direct(
        offer: SmallWebRTCRequest,
        store: StoreDep,
        settings: SettingsDep,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        return await _handle_offer(offer, store, settings, session_id)

    @webrtc.post("/sessions/{session_id}/api/offer")
    async def offer_for_session(
        session_id: str, offer: SmallWebRTCRequest, store: StoreDep, settings: SettingsDep
    ) -> dict[str, Any] | None:
        return await _handle_offer(offer, store, settings, session_id)

    @webrtc.patch("/api/offer")
    @webrtc.patch("/sessions/{session_id}/api/offer")
    async def ice_candidates(patch: SmallWebRTCPatchRequest, session_id: str | None = None) -> dict:
        await app.state.webrtc_handler.handle_patch_request(patch)
        return {"status": "success"}

    # --- Twilio (phone) ---

    @app.websocket("/twilio/ws")
    async def twilio_media_stream(websocket: WebSocket) -> None:
        # Media-stream websockets carry no Twilio signature, so the screening id (an
        # unguessable value that exists only in our TwiML) acts as a one-time capability
        # token: it must belong to a screening that is `dialing`, and is consumed here.
        store: ScreeningStore = websocket.app.state.store
        settings: Settings = websocket.app.state.settings
        await websocket.accept()
        try:
            transport_type, call_data = await parse_telephony_websocket(websocket)
        except ValueError:
            await websocket.close(code=1008)
            return

        screening_id = (call_data.body or {}).get("screening_id")
        if transport_type != "twilio" or not screening_id:
            logger.warning("rejecting media stream: not a Twilio stream with a screening id")
            await websocket.close(code=1008)
            return
        if not await store.transition_status(
            screening_id, ScreeningStatus.DIALING, ScreeningStatus.IN_PROGRESS
        ):
            logger.warning(f"rejecting media stream for screening {screening_id!r}")
            await websocket.close(code=1008)
            return

        transport = make_twilio_transport(
            websocket, call_data.stream_id or "", call_data.call_id or "", settings
        )
        await run_screening_bot(
            transport,
            screening_id=screening_id,
            store=store,
            settings=settings,
            channel=Channel.PHONE,
            live_calls=websocket.app.state.live_calls,
            knowledge=websocket.app.state.knowledge,
        )

    @app.post("/twilio/status", dependencies=[Depends(verify_twilio_signature)])
    async def twilio_status(request: Request, screening_id: str, store: StoreDep) -> dict[str, str]:
        """Twilio's end-of-call callback. Only matters if the call never reached the bot."""
        form = await request.form()
        call_status = str(form.get("CallStatus", ""))
        logger.info(f"twilio status screening={screening_id} status={call_status}")

        # Still `dialing` at the end of the call means the callee never connected.
        terminal = {"busy", "no-answer", "failed", "canceled", "completed"}
        if call_status in terminal and await store.transition_status(
            screening_id, ScreeningStatus.DIALING, ScreeningStatus.FAILED
        ):
            unanswered = call_status in {"busy", "no-answer"}
            await store.update_screening(
                screening_id, outcome=Outcome.NO_ANSWER.value if unanswered else None
            )
        return {"status": "ok"}

    # --- demo page and browser UI ---

    @app.get("/demo", include_in_schema=False)
    async def demo_page() -> FileResponse:
        return FileResponse(DEMO_PAGE)

    @app.get("/demo/options", include_in_schema=False)
    async def get_demo_options(settings: SettingsDep) -> dict[str, object]:
        return demo_options(settings)

    def require_access_code(settings: Settings, code: str) -> None:
        """403 unless `code` is a configured access code (fails closed with none configured).
        The code is never logged."""
        if not settings.demo_access_codes.strip():
            raise HTTPException(status_code=403, detail="The demo is not open for calls.")
        if not access_code_valid(settings, code):
            raise HTTPException(status_code=403, detail="That access code is not valid.")

    @app.post("/demo/call", status_code=201)
    async def demo_call(body: DemoCallIn, store: StoreDep, settings: SettingsDep) -> dict[str, Any]:
        """The demo page's "Call me": a fresh candidate, then the agent phones them."""
        require_access_code(settings, body.access_code)
        cap = settings.demo_max_calls_per_day
        if cap > 0:
            since = datetime.now(UTC) - timedelta(hours=24)
            if await store.count_screenings_since(Channel.PHONE, since) >= cap:
                raise HTTPException(
                    status_code=429,
                    detail=f"The demo is limited to {cap} calls per day and today's are used "
                    "up. Please try again tomorrow.",
                )
        opening = await ensure_demo_data(store, settings, MIN_FUTURE_SLOTS)
        candidate = await store.create_candidate(
            Candidate(
                name=body.name,
                phone=body.phone,
                location=opening.location,
                opening_id=opening.id,
                subjects=list(dict.fromkeys(body.subjects)),
                language=body.language,
            )
        )
        result = await dial_candidate(store, settings, candidate)
        return {"screening_id": result["screening"].id}

    @app.post("/demo/screenings/{screening_id}")
    async def demo_screening(
        screening_id: str, body: DemoAccessIn, store: StoreDep, settings: SettingsDep
    ) -> dict[str, Any]:
        """What the demo page shows about a demo call, and nothing else (no phone, candidate
        record or transcript text). POST so the access code travels in the body."""
        require_access_code(settings, body.access_code)
        screening = await store.get_screening(screening_id)
        if screening is None or screening.channel is not Channel.PHONE:
            raise HTTPException(status_code=404, detail="screening not found")
        facts = await store.get_facts(screening_id)
        opening = await store.opening_for_screening(screening_id)
        qualification = qualification_for(facts, opening, settings)
        slot = await store.get_slot(screening.slot_id) if screening.slot_id else None
        summary = await store.get_summary(screening_id)
        outcome = screening.outcome
        transcript = await store.get_transcript(screening_id)
        return {
            "status": screening.status,
            "outcome": outcome,
            "reached": outcome != Outcome.NO_ANSWER and bool(transcript),
            "facts": {
                "subjects": facts.subjects,
                "levels": facts.levels,
                "availability": facts.availability,
                "teaching_format": facts.teaching_format,
                "work_authorized": facts.work_authorized,
                "start_date": facts.start_date,
                "experience": facts.experience,
            },
            "qualification": {
                k: qualification[k] for k in ("qualified", "reasons") if k in qualification
            },
            "slot": (
                {"starts_at": slot.starts_at, "mode": slot.mode, "address": slot.address}
                if slot
                else None
            ),
            "summary": (
                {"key_points": summary.key_points, "next_step": summary.next_step}
                if summary
                else None
            ),
        }

    if settings.web_ui_enabled:
        app.include_router(webrtc)
        app.mount("/client", PipecatPrebuiltUI)

    @app.get("/", include_in_schema=False)
    async def root() -> Response:
        if settings.web_ui_enabled:
            return RedirectResponse(url="/client/")
        return FileResponse(DEMO_PAGE)

    if settings.demo_password:
        app.add_middleware(PasswordGate, password=settings.demo_password)

    return app


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "hr_screener.app.api:create_app", factory=True, host=settings.host, port=settings.port
    )
