"""
aiohttp REST API server for FBGroupPosterPro.
Runs on localhost:3080.
"""

import logging
import os
import sys
from pathlib import Path

import aiohttp_cors
from aiohttp import WSMsgType, web

from .database import init_db
from .selenium_engine import selenium_engine
from . import license_client
from . import remote_access
from .routes import (
    accounts,
    groups,
    posts,
    schedule,
    report,
    license as license_routes,
    onboard,
    scrape,
)
from .routes import ai as ai_routes
from .routes import image as image_routes

# Paths reachable before license activation. Anything else returns 402.
LICENSE_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/license/",
    "/api/vault/",  # vault unlock available pre-activation if user wants to migrate
    "/api/remote/",  # remote-access config (local-only; enable() checks license itself)
    "/ws",
)

logger = logging.getLogger(__name__)


def _resolve_frontend_dir() -> Path:
    """Locate the Next.js static export.

    - Dev: <project>/frontend/out
    - PyInstaller frozen (one-folder): sys._MEIPASS/frontend/out
    """
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = meipass / "frontend" / "out"
        if candidate.exists():
            return candidate
    return Path(__file__).parent.parent / "frontend" / "out"


FRONTEND_DIR = _resolve_frontend_dir()
PORT = int(os.environ.get("PORT", 3080))

# WebSocket clients registry
ws_clients: set = set()


async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)

    async def send_to_ws(msg: dict):
        if not ws.closed:
            await ws.send_json(msg)

    selenium_engine.register_ws_callback(send_to_ws)

    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
    finally:
        ws_clients.discard(ws)
        selenium_engine.unregister_ws_callback(send_to_ws)

    return ws


async def health_handler(request):
    engine_status = await selenium_engine.get_status()
    return web.json_response(
        {
            "status": "ok",
            "version": "1.0.0",
            "sessions": len(engine_status),
            "selenium_sessions": engine_status,
        }
    )


@web.middleware
async def license_gate_middleware(request, handler):
    """Block API access when license is not valid. Static assets + license endpoints stay open."""
    path = request.path

    # Static / non-API requests pass through.
    if not path.startswith("/api/") and path != "/ws":
        return await handler(request)

    # Always-public API paths.
    if any(path.startswith(p) for p in LICENSE_PUBLIC_PREFIXES):
        return await handler(request)

    status = await license_client.get_status_for_gate()
    if not status.valid:
        return web.json_response(
            {
                "error": "license_required",
                "message": status.error or "License not activated",
                "license_status": status.to_dict(),
            },
            status=402,  # Payment Required
        )
    return await handler(request)


def create_app() -> web.Application:
    init_db()

    # Token gate runs BEFORE the license gate so remote callers are authenticated first.
    app = web.Application(
        middlewares=[remote_access.access_token_middleware, license_gate_middleware]
    )

    # CORS — any origin is allowed because the access TOKEN (X-Access-Token header) is the
    # real authentication; the phone PWA may be served from a different origin/IP. Cookies
    # are not used for auth, so credentials stay off (required when origin is "*").
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=False,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*",
            ),
        },
    )

    # Core routes
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/health", health_handler)

    # Register route modules
    for router_module in [
        accounts,
        groups,
        posts,
        schedule,
        report,
        ai_routes,
        image_routes,
        license_routes,
        onboard,
        scrape,
        remote_access,
    ]:
        router_module.setup_routes(app, cors)

    # Static frontend (Next.js export)
    if FRONTEND_DIR.exists():
        app.router.add_static("/", FRONTEND_DIR, show_index=True)

    # Start license heartbeat after the loop is running.
    async def _on_startup(_app):
        license_client.start_heartbeat()
        from .scheduler import start_auto_delete_scheduler

        start_auto_delete_scheduler(interval_minutes=30)

    async def _on_cleanup(_app):
        license_client.stop_heartbeat()
        from .scheduler import stop_auto_delete_scheduler

        stop_auto_delete_scheduler()

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app


def run():
    app = create_app()
    logging.basicConfig(level=logging.INFO)
    # Bind beyond loopback only when the user has opted into remote access; otherwise the
    # engine stays reachable from this PC alone (safe default). BIND_HOST can override.
    host = os.environ.get("BIND_HOST")
    if not host:
        host = "0.0.0.0" if remote_access.is_remote_enabled() else "127.0.0.1"
    logging.getLogger(__name__).info(
        "binding %s:%s (remote=%s)", host, PORT, remote_access.is_remote_enabled()
    )
    web.run_app(app, host=host, port=PORT)


if __name__ == "__main__":
    run()
