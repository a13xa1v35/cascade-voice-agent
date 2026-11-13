"""Admin password gate for a public deployment: HTTP Basic auth as a pure ASGI middleware, so
it sees websocket scopes too (BaseHTTPMiddleware does not). The demo pages and routes are
public (POST /demo/call and the results route check their own access code); the REST API,
which exposes candidate data, is behind the password."""

import base64
import binascii
import hmac

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Called by Twilio, which cannot send credentials: /twilio/status is signed, and /twilio/ws
# accepts only the one-time screening id from our TwiML. /health is the platform's probe.
# / and /demo are the public home page; routes under /demo/ are the demo flow (each checks
# its own access code).
OPEN_PATHS = frozenset({"/", "/demo", "/health", "/twilio/status", "/twilio/ws"})
OPEN_PREFIX = "/demo/"


def is_open(path: str) -> bool:
    return path in OPEN_PATHS or path.startswith(OPEN_PREFIX)


def password_matches(header: str, password: str) -> bool:
    """True when `Authorization: Basic ...` carries this password (any username)."""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        _, _, supplied = base64.b64decode(token, validate=True).decode().partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    return hmac.compare_digest(supplied.encode(), password.encode())


class PasswordGate:
    def __init__(self, app: ASGIApp, password: str) -> None:
        self.app = app
        self.password = password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or is_open(scope["path"]):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        if password_matches(headers.get("authorization", ""), self.password):
            await self.app(scope, receive, send)
        elif scope["type"] == "http":
            response = PlainTextResponse(
                "Password required",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Screening agent demo"'},
            )
            await response(scope, receive, send)
        else:  # websocket: refuse the handshake
            await send({"type": "websocket.close", "code": 1008})
