"""
First-time login wizard.

POST /api/onboard/login/{account_id}?platform=fb
  Opens a visible Chrome window for the user to log in manually. Polls for the
  platform-specific login-marker cookie. On success, encrypts cookies and stores in DB.

GET  /api/onboard/status/{account_id}
  Returns whether the account has stored cookies (i.e., is "logged in").
"""

from datetime import datetime

from aiohttp import web

from ..crypto import encrypt
from ..database import SessionLocal
from ..models import Account
from ..selenium_engine import selenium_engine

DEFAULT_LOGIN_TIMEOUT = 600  # 10 minutes for the user to complete login + 2FA


def setup_routes(app, cors):
    r1 = cors.add(app.router.add_resource("/api/onboard/login/{id}"))
    cors.add(r1.add_route("POST", start_login))

    r2 = cors.add(app.router.add_resource("/api/onboard/status/{id}"))
    cors.add(r2.add_route("GET", get_status))


async def start_login(request):
    try:
        account_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid account id")

    platform = request.rel_url.query.get("platform", "fb")
    # Cap user-provided timeout at DEFAULT_LOGIN_TIMEOUT (10 min) so a caller can't
    # pin a Chrome process and an executor thread indefinitely.
    try:
        requested = int(request.rel_url.query.get("timeout", DEFAULT_LOGIN_TIMEOUT))
    except ValueError:
        requested = DEFAULT_LOGIN_TIMEOUT
    timeout = max(30, min(requested, DEFAULT_LOGIN_TIMEOUT))

    with SessionLocal() as db:
        account = db.get(Account, account_id)
        if not account:
            raise web.HTTPNotFound(reason="Account not found")

    result = await selenium_engine.interactive_login(account_id, platform, timeout)

    if result.get("success"):
        with SessionLocal() as db:
            account = db.get(Account, account_id)
            if account:
                account.cookies_json = encrypt(result["cookies_json"])
                account.last_used_at = datetime.utcnow()
                account.status = "active"
                db.commit()
        # Close the visible browser; subsequent post runs reuse the persisted profile dir.
        await selenium_engine.close_session(account_id)
        return web.json_response(
            {
                "success": True,
                "platform": platform,
                "cookie_count": result["cookie_count"],
            }
        )

    return web.json_response(
        {"success": False, "error": result.get("error", "Unknown error")},
        status=400,
    )


async def get_status(request):
    try:
        account_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid account id")
    with SessionLocal() as db:
        account = db.get(Account, account_id)
        if not account:
            raise web.HTTPNotFound()
        return web.json_response(
            {
                "id": account.id,
                "logged_in": bool(account.cookies_json),
                "last_used_at": account.last_used_at.isoformat()
                if account.last_used_at
                else None,
            }
        )
