# -*- coding: utf-8 -*-
"""
Remote access (mobile-remote-control, spec B — Tailscale-based).

Lets a phone on the customer's tailnet drive this PC's engine. Security model:
  * Local (loopback) requests always pass — the desktop UI never needs a token.
  * Remote requests are blocked entirely unless remote access is explicitly enabled
    AND they carry a valid access token (constant-time compared).
  * /api/remote/* is LOCAL-ONLY — the token/config is configured from the desktop and
    never exposed to an unauthenticated remote caller.

The server binds 0.0.0.0 only when remote access is enabled (see server.run()); the
default stays loopback-only, so enabling remote is an explicit, opt-in action.
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
import subprocess
from typing import Optional

from aiohttp import web

from .database import SessionLocal
from .models import AppState

logger = logging.getLogger(__name__)

_ENABLED_KEY = "remote_enabled"
_TOKEN_KEY = "remote_access_token"

_REMOTE_PREFIX = "/api/remote/"
_TOKEN_HEADER = "X-Access-Token"


# ── persistence (AppState key/value) ───────────────────────────────────────────
def _state_get(key: str) -> Optional[str]:
    with SessionLocal() as db:
        row = db.get(AppState, key)
        return row.value if row else None


def _state_set(key: str, value: str) -> None:
    with SessionLocal() as db:
        row = db.get(AppState, key)
        if row:
            row.value = value
        else:
            db.add(AppState(key=key, value=value))
        db.commit()


# ── config API ─────────────────────────────────────────────────────────────────
def is_remote_enabled() -> bool:
    return _state_get(_ENABLED_KEY) == "1"


def set_remote_enabled(enabled: bool) -> None:
    _state_set(_ENABLED_KEY, "1" if enabled else "0")


def get_or_create_token() -> str:
    tok = _state_get(_TOKEN_KEY)
    if not tok:
        tok = secrets.token_urlsafe(32)
        _state_set(_TOKEN_KEY, tok)
    return tok


def regenerate_token() -> str:
    tok = secrets.token_urlsafe(32)
    _state_set(_TOKEN_KEY, tok)
    return tok


def verify_token(provided: Optional[str]) -> bool:
    if not provided:
        return False
    expected = _state_get(_TOKEN_KEY)
    if not expected:
        return False
    return hmac.compare_digest(provided, expected)


def get_tailscale_ip() -> Optional[str]:
    """The PC's tailnet IPv4 (100.64.0.0/10), used to build the phone URL/QR."""
    candidates = [
        ["tailscale", "ip", "-4"],
        [r"C:\Program Files\Tailscale\tailscale.exe", "ip", "-4"],
        ["/Applications/Tailscale.app/Contents/MacOS/Tailscale", "ip", "-4"],
    ]
    for cmd in candidates:
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=8
            ).stdout.strip()
            for line in out.splitlines():
                ip = line.strip()
                if ip.startswith("100."):
                    return ip
        except Exception:  # noqa: BLE001
            continue
    return None


# ── request helpers ─────────────────────────────────────────────────────────────
def _is_local_request(request: web.Request) -> bool:
    peername = (
        request.transport.get_extra_info("peername") if request.transport else None
    )
    host = peername[0] if peername else None
    return host in ("127.0.0.1", "::1", "::ffff:127.0.0.1")


def _extract_token(request: web.Request) -> Optional[str]:
    return request.headers.get(_TOKEN_HEADER) or request.query.get("token")


# ── middleware ──────────────────────────────────────────────────────────────────
@web.middleware
async def access_token_middleware(request: web.Request, handler):
    """Gate remote requests. Runs BEFORE the license gate."""
    path = request.path

    # Static assets (the PWA shell itself) load without a token so the phone can boot
    # the UI; all data lives behind /api and /ws which are gated below.
    if not path.startswith("/api/") and path != "/ws":
        return await handler(request)

    # Genuine desktop UI (loopback) bypasses the token. Requests the relay client replays
    # are ALSO loopback but carry X-Relay-Forwarded — those are remote-origin, so they fall
    # through to the token check below (a guessed pairing code must still present a token).
    if _is_local_request(request) and not request.headers.get("X-Relay-Forwarded"):
        return await handler(request)

    # ---- remote request from here on ----
    # Config endpoints are local-only; never expose the token to a remote caller.
    if path.startswith(_REMOTE_PREFIX):
        return web.json_response(
            {"error": "local_only", "message": "Remote config is desktop-only"},
            status=403,
        )

    if not is_remote_enabled():
        return web.json_response(
            {"error": "remote_disabled", "message": "Remote access is turned off"},
            status=403,
        )

    if not verify_token(_extract_token(request)):
        return web.json_response(
            {"error": "invalid_token", "message": "Missing or invalid access token"},
            status=401,
        )

    return await handler(request)


# ── routes (/api/remote/*) — local-only by the middleware above ─────────────────
async def _status(request: web.Request):
    from . import relay_client

    return web.json_response(
        {
            "enabled": is_remote_enabled(),
            "token": get_or_create_token(),
            "pairing_code": relay_client.get_pairing_code(),  # zero-config relay path
            "relay_host": relay_client.get_relay_host(),
            "tailscale_ip": get_tailscale_ip(),  # legacy/advanced path
            "port": int(os.environ.get("PORT", 3080)),
        }
    )


async def _enable(request: web.Request):
    # FR-7: remote requires an active license.
    from . import license_client, relay_client

    status = await license_client.get_status_for_gate()
    if not status.valid:
        return web.json_response(
            {"error": "license_required", "message": "Activate a license first"},
            status=402,
        )
    set_remote_enabled(True)
    get_or_create_token()
    relay_client.start()  # dial out to the relay so a phone can reach this PC
    return web.json_response({"enabled": True})


async def _disable(request: web.Request):
    from . import relay_client

    set_remote_enabled(False)
    relay_client.stop()
    return web.json_response({"enabled": False})


async def _regenerate(request: web.Request):
    return web.json_response({"token": regenerate_token()})


def setup_routes(app: web.Application, cors) -> None:
    resources = [
        ("GET", "/api/remote/status", _status),
        ("POST", "/api/remote/enable", _enable),
        ("POST", "/api/remote/disable", _disable),
        ("POST", "/api/remote/regenerate-token", _regenerate),
    ]
    for method, path, handler in resources:
        res = cors.add(app.router.add_resource(path))
        cors.add(res.add_route(method, handler))
