"""
aiohttp REST API server for FBGroupPosterPro.
Runs on localhost:3080.
"""

import logging
import os
from pathlib import Path

import aiohttp_cors
from aiohttp import WSMsgType, web

from .database import init_db
from .selenium_engine import selenium_engine
from .routes import accounts, groups, posts, schedule, report
from .routes import ai as ai_routes

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "out"
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


def create_app() -> web.Application:
    init_db()

    app = web.Application()

    # CORS — localhost only
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "http://localhost:3080": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*",
            ),
            "http://127.0.0.1:3080": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
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
    for router_module in [accounts, groups, posts, schedule, report, ai_routes]:
        router_module.setup_routes(app, cors)

    # Static frontend (Next.js export)
    if FRONTEND_DIR.exists():
        app.router.add_static("/", FRONTEND_DIR, show_index=True)

    return app


def run():
    app = create_app()
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    run()
