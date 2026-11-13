"""Twilio helpers: placing the outbound call and building the TwiML that connects it."""

import asyncio
from urllib.parse import urlencode

from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from hr_screener.config import Settings
from hr_screener.models import Candidate, Screening


def ws_url_for(settings: Settings) -> str:
    """wss:// URL of our media-stream endpoint, derived from the public https URL."""
    base = settings.public_base_url.rstrip("/")
    return base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/twilio/ws"


def build_stream_twiml(ws_url: str, screening_id: str) -> str:
    """TwiML that opens a bidirectional media stream and passes the screening id along.

    Twilio forwards <Parameter> values in the websocket's `start` message, which is how
    the websocket handler knows which screening this call belongs to.
    """
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=ws_url)
    stream.parameter(name="screening_id", value=screening_id)
    connect.append(stream)
    response.append(connect)
    return str(response)


async def place_outbound_call(
    screening: Screening, candidate: Candidate, settings: Settings
) -> str:
    """Start the call and return its CallSid. Twilio's client is sync, so use a thread."""
    twiml = build_stream_twiml(ws_url_for(settings), screening.id)
    status_url = f"{settings.public_base_url.rstrip('/')}/twilio/status?" + urlencode(
        {"screening_id": screening.id}
    )

    def _create() -> str:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        call = client.calls.create(
            to=candidate.phone,
            from_=settings.twilio_from_number,
            twiml=twiml,
            status_callback=status_url,
            status_callback_method="POST",
            time_limit=settings.call_time_limit_secs,
        )
        return str(call.sid)

    return await asyncio.to_thread(_create)
