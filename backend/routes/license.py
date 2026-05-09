"""
License REST API.

Public endpoints (always reachable, even when not activated):
  GET  /api/license/status       — current license state + install_uuid
  POST /api/license/activate     — activate with {license_key}
  POST /api/license/trial        — request trial with {email}
  POST /api/license/refresh      — force re-verify
  POST /api/license/deactivate   — local clear (does NOT free device binding upstream)
  GET  /api/license/purchase_url — returns checkout URL for a given plan
"""

from aiohttp import web

from .. import license_client


def setup_routes(app, cors):
    r1 = cors.add(app.router.add_resource("/api/license/status"))
    cors.add(r1.add_route("GET", get_status))

    r2 = cors.add(app.router.add_resource("/api/license/activate"))
    cors.add(r2.add_route("POST", activate))

    r3 = cors.add(app.router.add_resource("/api/license/trial"))
    cors.add(r3.add_route("POST", trial))

    r4 = cors.add(app.router.add_resource("/api/license/refresh"))
    cors.add(r4.add_route("POST", refresh))

    r5 = cors.add(app.router.add_resource("/api/license/deactivate"))
    cors.add(r5.add_route("POST", deactivate))

    r6 = cors.add(app.router.add_resource("/api/license/purchase_url"))
    cors.add(r6.add_route("GET", purchase_url))


async def get_status(request):
    status = await license_client.get_current_status()
    return web.json_response(
        {
            **status.to_dict(),
            "device_id": license_client.get_install_uuid(),
        }
    )


async def activate(request):
    data = await request.json()
    key = (data.get("license_key") or "").strip()
    if not key:
        raise web.HTTPBadRequest(reason="license_key required")
    status = await license_client.activate(key)
    return web.json_response(status.to_dict(), status=200 if status.valid else 400)


async def trial(request):
    data = await request.json()
    email = (data.get("email") or "").strip()
    if "@" not in email:
        raise web.HTTPBadRequest(reason="Valid email required")
    result = await license_client.request_trial(email)
    return web.json_response(result)


async def refresh(request):
    status = await license_client.get_current_status()
    return web.json_response(status.to_dict())


async def deactivate(request):
    await license_client.deactivate()
    return web.json_response({"ok": True})


async def purchase_url(request):
    plan = request.rel_url.query.get("plan", "pro")
    email = request.rel_url.query.get("email", "")
    return web.json_response({"url": license_client.get_purchase_url(plan, email)})
