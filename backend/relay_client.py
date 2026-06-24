# -*- coding: utf-8 -*-
"""
PC-side relay client (mobile-remote, zero-config path).

When remote access is enabled, the app dials OUT to the hosted relay
(wss://relay.konggoo.uk/agent/ws), registers, and gets a short pairing CODE. It then
serves requests the relay forwards (from the customer's phone) by replaying them against
the local server (127.0.0.1:3080) and sending the response back.

Outbound-only: works behind any NAT/firewall with no customer network setup.

SECURITY: forwarded requests reach the local server over loopback, which would normally
bypass the access-token gate. The client tags every replay with `X-Relay-Forwarded: 1` so
the gate KNOWS it is remote-origin and still enforces the token (carried from the phone as
X-Access-Token). A guessed pairing code alone therefore controls nothing.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

RELAY_URL = os.environ.get("FBGP_RELAY_URL", "wss://relay.konggoo.uk/agent/ws")
LOCAL_BASE = os.environ.get("FBGP_LOCAL_BASE", "http://127.0.0.1:3080")

_pairing_code: Optional[str] = None
_relay_host: Optional[str] = None  # https origin of the relay, for the phone URL
_task: Optional[asyncio.Task] = None


def get_pairing_code() -> Optional[str]:
    return _pairing_code


def get_relay_host() -> Optional[str]:
    return _relay_host


async def _handle_request(session: aiohttp.ClientSession, ws, data: dict):
    req_id = data.get("req_id")
    method = data.get("method", "GET")
    path = data.get("path", "/")
    headers = dict(data.get("headers", {}))
    body = base64.b64decode(data["body_b64"]) if data.get("body_b64") else None
    # Force the gate to treat this as remote-origin (token still required).
    headers["X-Relay-Forwarded"] = "1"
    for h in ("Host", "Content-Length", "Connection", "Accept-Encoding"):
        headers.pop(h, None)
        headers.pop(h.lower(), None)
    try:
        async with session.request(
            method,
            LOCAL_BASE + path,
            headers=headers,
            data=body,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=55),
        ) as resp:
            raw = await resp.read()
            out = {
                "type": "response",
                "req_id": req_id,
                "status": resp.status,
                "headers": {k: v for k, v in resp.headers.items()},
                "body_b64": base64.b64encode(raw).decode() if raw else "",
            }
    except Exception as e:  # noqa: BLE001
        msg = json.dumps({"error": "local_fetch_failed", "message": str(e)[:120]})
        out = {
            "type": "response",
            "req_id": req_id,
            "status": 502,
            "headers": {"Content-Type": "application/json"},
            "body_b64": base64.b64encode(msg.encode()).decode(),
        }
    try:
        await ws.send_json(out)
    except Exception:  # noqa: BLE001
        pass


async def _run_once():
    global _pairing_code, _relay_host
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(
            RELAY_URL, heartbeat=30, max_msg_size=64 * 1024 * 1024
        ) as ws:
            _relay_host = (
                RELAY_URL.replace("wss://", "https://")
                .replace("ws://", "http://")
                .rsplit("/agent/ws", 1)[0]
            )
            logger.info("relay connected: %s", RELAY_URL)
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                t = data.get("type")
                if t == "registered":
                    _pairing_code = data.get("code")
                    logger.info("relay pairing code: %s", _pairing_code)
                elif t == "request":
                    asyncio.create_task(_handle_request(session, ws, data))


async def _loop():
    global _pairing_code
    backoff = 2
    while True:
        try:
            await _run_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("relay connection lost: %s (retry in %ss)", e, backoff)
        _pairing_code = None
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise
        backoff = min(backoff * 2, 30)


def start() -> None:
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop())
    logger.info("relay client started")


def stop() -> None:
    global _task, _pairing_code
    if _task and not _task.done():
        _task.cancel()
    _task = None
    _pairing_code = None
