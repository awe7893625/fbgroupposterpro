# -*- coding: utf-8 -*-
"""
FBGroupPosterPro mobile relay (hosted, e.g. https://relay.konggoo.uk).

Zero-config phone→PC bridge for the general public (no Tailscale, no port-forwarding):
  * The customer's PC app dials OUT to this relay over a WebSocket (/agent/ws) and
    registers, receiving a short pairing CODE.
  * The phone opens https://<relay>/p/<CODE>/ — the relay forwards every request over the
    agent WebSocket to that PC's local server (127.0.0.1:3080) and streams the reply back.
    So the phone loads the PC's own UI through the relay; same-origin API calls just work.

Security: the relay only ROUTES by pairing code; the PC app's access-token gate still
authenticates every /api call end-to-end (the phone carries X-Access-Token), so a guessed
code alone controls nothing. Pairing codes are short-lived per PC connection.

Run:  python relay_server.py            # binds 0.0.0.0:8799 (front it with Cloudflare Tunnel)
"""

from __future__ import annotations

import asyncio
import base64
import os
import secrets

from aiohttp import WSMsgType, web

PORT = int(os.environ.get("RELAY_PORT", 8799))
REQUEST_TIMEOUT = 60  # seconds to wait for the PC to answer a proxied request
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars (0/O, 1/I)

# code -> {"ws": WebSocketResponse, "pending": {req_id: Future}}
_AGENTS: dict = {}


def _new_code() -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        if code not in _AGENTS:
            return code


async def agent_ws(request: web.Request):
    """A customer PC connects here and stays connected, serving forwarded requests."""
    ws = web.WebSocketResponse(heartbeat=30, max_msg_size=64 * 1024 * 1024)
    await ws.prepare(request)
    code = _new_code()
    _AGENTS[code] = {"ws": ws, "pending": {}}
    await ws.send_json({"type": "registered", "code": code})
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                import json

                data = json.loads(msg.data)
                if data.get("type") == "response":
                    fut = _AGENTS[code]["pending"].pop(data.get("req_id"), None)
                    if fut and not fut.done():
                        fut.set_result(data)
            elif msg.type == WSMsgType.ERROR:
                break
    finally:
        agent = _AGENTS.pop(code, None)
        if agent:
            for fut in agent["pending"].values():
                if not fut.done():
                    fut.set_exception(ConnectionError("agent disconnected"))
    return ws


async def proxy(request: web.Request):
    """Phone request: /p/<code>/<tail> -> forward over the agent ws -> return reply."""
    code = request.match_info["code"].upper()
    tail = request.match_info.get("tail", "")
    agent = _AGENTS.get(code)
    if not agent or agent["ws"].closed:
        return web.json_response(
            {
                "error": "pc_offline",
                "message": "找不到電腦或電腦未開啟（請確認 PC 端 App 運行中）",
            },
            status=502,
        )
    body = await request.read()
    req_id = secrets.token_hex(8)
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    agent["pending"][req_id] = fut
    path = "/" + tail
    if request.query_string:
        path += "?" + request.query_string
    try:
        await agent["ws"].send_json(
            {
                "type": "request",
                "req_id": req_id,
                "method": request.method,
                "path": path,
                "headers": dict(request.headers),
                "body_b64": base64.b64encode(body).decode() if body else "",
            }
        )
        data = await asyncio.wait_for(fut, timeout=REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        agent["pending"].pop(req_id, None)
        return web.json_response({"error": "timeout"}, status=504)
    except ConnectionError:
        return web.json_response({"error": "pc_offline"}, status=502)

    raw = base64.b64decode(data.get("body_b64", "")) if data.get("body_b64") else b""
    headers = data.get("headers", {})
    # strip hop-by-hop / length headers the relay re-derives
    for h in ("Content-Length", "Transfer-Encoding", "Content-Encoding", "Connection"):
        headers.pop(h, None)
    resp = web.Response(status=data.get("status", 200), body=raw)
    for k, v in headers.items():
        try:
            resp.headers[k] = v
        except Exception:  # noqa: BLE001
            pass
    return resp


async def root(request: web.Request):
    return web.json_response({"service": "fbgp-relay", "agents_online": len(_AGENTS)})


async def health(request: web.Request):
    return web.json_response({"status": "ok", "agents": len(_AGENTS)})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    app.router.add_get("/agent/ws", agent_ws)
    app.router.add_route("*", "/p/{code}/{tail:.*}", proxy)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=PORT)
