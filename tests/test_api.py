import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from twilio.request_validator import RequestValidator

from hr_screener.app.api import create_app
from hr_screener.config import Settings
from hr_screener.models import (
    Channel,
    OnboardingSlot,
    Opening,
    Outcome,
    Screening,
    ScreeningStatus,
    SlotMode,
)
from hr_screener.storage.store import ScreeningStore

CANDIDATE = {"name": "Jo Doe", "phone": "+15550001111"}


@pytest.fixture
def client(redis: Redis, engine, settings: Settings, opening: Opening):
    # `with` runs the app's lifespan (startup/shutdown). `opening` exists before the app starts.
    with TestClient(create_app(redis=redis, settings=settings, engine=engine)) as c:
        yield c


@pytest.mark.parametrize("outcome", ["scheduled", "not_qualified"])
def test_phone_screening_refuses_a_closed_candidate(
    client: TestClient, store: ScreeningStore, outcome: str
):
    """Outbound calls never dial a booked or rejected candidate (409, nothing created); the
    browser still connects them, to a closed-mode call."""
    candidate = client.post("/candidates", json=CANDIDATE).json()

    async def decide() -> str:
        screening = await store.create_screening(
            Screening(
                candidate_id=candidate["id"],
                channel=Channel.WEBRTC,
                status=ScreeningStatus.IN_PROGRESS,
            )
        )
        if outcome == "scheduled":
            slot = await store.create_slot(
                OnboardingSlot(
                    starts_at=datetime.now(UTC) + timedelta(days=2),
                    mode=SlotMode.ONLINE,
                    capacity=1,
                )
            )
            await store.book_slot(screening.id, slot.id)
        await store.finish_screening(
            screening.id, ScreeningStatus.COMPLETED, Outcome(outcome), None
        )
        return screening.id

    decided_id = asyncio.run(decide())
    before = asyncio.run(store.list_screenings(candidate["id"]))

    response = client.post(
        "/screenings", json={"candidate_id": candidate["id"], "channel": "phone"}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "error": "candidate_closed",
        "screening_id": decided_id,
        "outcome": outcome,
    }
    assert asyncio.run(store.list_screenings(candidate["id"])) == before  # nothing dialed

    web = client.post("/screenings", json={"candidate_id": candidate["id"]})
    assert web.status_code == 201  # the browser path still answers them (closed mode)


def test_twilio_webhook_signature_is_validated_against_public_url(redis: Redis, engine):
    settings = Settings(
        _env_file=None, twilio_auth_token="secret", public_base_url="https://abc.ngrok.app"
    )
    form = {"CallStatus": "completed"}
    # Twilio signs the public URL, not the http://testserver URL the app sees.
    signature = RequestValidator("secret").compute_signature(
        "https://abc.ngrok.app/twilio/status?screening_id=s1", form
    )
    with TestClient(create_app(redis=redis, settings=settings, engine=engine)) as client:
        url = "/twilio/status?screening_id=s1"
        assert client.post(url, data=form).status_code == 403
        assert client.post(url, data=form, headers={"X-Twilio-Signature": "bad"}).status_code == 403
        assert (
            client.post(url, data=form, headers={"X-Twilio-Signature": signature}).status_code
            == 200
        )


def test_demo_password_gates_the_api_but_not_the_demo(redis: Redis, engine):
    """With DEMO_PASSWORD set the REST API (candidate PII) needs the password; the public
    demo pages, the platform probe, Twilio's status webhook and the media stream stay open."""
    settings = Settings(_env_file=None, demo_password="s3cret", web_ui_enabled=False)
    with TestClient(create_app(redis=redis, settings=settings, engine=engine)) as client:
        for path in ("/", "/demo", "/demo/options", "/health"):
            assert client.get(path).status_code == 200, path
        for path in ("/openings", "/screenings/x", "/docs", "/openapi.json", "/candidates/x"):
            denied = client.get(path)
            assert denied.status_code == 401, path
            assert denied.headers["www-authenticate"].startswith("Basic")
            assert client.get(path, auth=("anyone", "wrong")).status_code == 401, path
        assert client.get("/openings", auth=("anyone", "s3cret")).status_code == 200
        assert client.get("/screenings/x", auth=("anyone", "s3cret")).status_code == 404
        # a look-alike path is not under /demo/
        assert client.get("/demonstration").status_code == 401
        # no auth token configured, so the status webhook skips the signature and answers
        assert client.post("/twilio/status?screening_id=s1", data={}).status_code == 200
        # the gate lets the websocket handshake through (the handler authenticates the stream)
        with client.websocket_connect("/twilio/ws"):
            pass


def _demo_settings(tmp_path, **overrides) -> Settings:
    key = "k"
    return Settings(
        _env_file=None,
        timezone="UTC",
        call_log_dir=str(tmp_path),
        public_base_url="https://x.example",
        twilio_account_sid="AC1",
        twilio_auth_token="t",
        twilio_from_number="+15550000000",
        anthropic_api_key=key,
        assemblyai_api_key=key,
        cloudflare_account_id=key,
        cloudflare_api_token=key,
        **overrides,
    )


def test_demo_call_needs_an_access_code_and_respects_the_daily_cap(
    redis: Redis, engine, tmp_path, monkeypatch
):
    """The access code and the per-day cap protect against runaway telephony cost: a refused
    request creates no candidate and places no call. The results route needs the code too and
    never returns the phone number."""
    dialed = []

    async def fake_place(*args):
        dialed.append(args)
        return "CA1"

    monkeypatch.setattr("hr_screener.app.api.place_outbound_call", fake_place)
    settings = _demo_settings(
        tmp_path, demo_max_calls_per_day=1, demo_access_codes="c1, c2", demo_password="pw"
    )
    admin = ("admin", "pw")
    with TestClient(create_app(redis=redis, settings=settings, engine=engine)) as client:
        body = {"name": "Jo", "phone": "+34 600 111 222", "language": "es", "consent": True}
        wrong = client.post("/demo/call", json={**body, "access_code": "nope"})
        assert wrong.status_code == 403
        assert "www-authenticate" not in wrong.headers
        assert client.post("/demo/call", json=body).status_code == 403
        assert client.post("/demo/call?access_code=c1", json=body).status_code == 403
        assert dialed == []
        assert client.get("/openings", auth=admin).status_code == 200  # app is alive, gate is on

        first = client.post("/demo/call", json={**body, "access_code": "c2"})
        assert first.status_code == 201, first.text
        assert client.post("/demo/call", json={**body, "access_code": "c1"}).status_code == 429
        assert len(dialed) == 1

        url = f"/demo/screenings/{first.json()['screening_id']}"
        assert client.post(url, json={"access_code": "nope"}).status_code == 403
        assert client.post(url, json={}).status_code == 403
        missing = client.post("/demo/screenings/missing", json={"access_code": "c1"})
        assert missing.status_code == 404
        shown = client.post(url, json={"access_code": "c1"})
        assert shown.status_code == 200, shown.text
        assert "status" in shown.json()
        assert "600111222" not in shown.text


def test_demo_call_fails_closed_without_access_codes(redis: Redis, engine, tmp_path, monkeypatch):
    dialed = []

    async def fake_place(*args):
        dialed.append(args)
        return "CA1"

    monkeypatch.setattr("hr_screener.app.api.place_outbound_call", fake_place)
    settings = _demo_settings(tmp_path, demo_access_codes=" , ")
    with TestClient(create_app(redis=redis, settings=settings, engine=engine)) as client:
        body = {"name": "Jo", "phone": "+34600111222", "language": "es", "consent": True}
        for code in ("", "anything", " "):
            response = client.post("/demo/call", json={**body, "access_code": code})
            assert response.status_code == 403
        assert client.post("/demo/screenings/x", json={"access_code": ""}).status_code == 403
        assert dialed == []
