"""Transport builders: how audio gets in and out of the pipeline.

The pipeline itself is identical for both; only the transport differs.
"""

from fastapi import WebSocket
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

from hr_screener.config import Settings


def make_webrtc_transport(connection: SmallWebRTCConnection) -> BaseTransport:
    return SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )


def make_twilio_transport(
    websocket: WebSocket, stream_sid: str, call_sid: str, settings: Settings
) -> BaseTransport:
    # The serializer converts Twilio's 8 kHz mu-law frames to PCM and back. With account
    # credentials it also hangs up the call through the REST API when the pipeline ends
    # (that is how end_call really terminates the phone call).
    has_credentials = bool(settings.twilio_account_sid and settings.twilio_auth_token)
    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        params=TwilioFrameSerializer.InputParams(auto_hang_up=has_credentials),
    )
    return FastAPIWebsocketTransport(
        websocket,
        FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,  # raw audio only; Twilio does not want WAV headers
            serializer=serializer,
        ),
    )
