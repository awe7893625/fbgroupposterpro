"""
Listing scraper REST endpoints.

POST /api/scrape
    Body: {url: string, account_id: int}
    Response (success): {success: true, platform: "591"|"housebox", data: {...}}
    Response (failure): {success: false, error: "..."}
"""

from aiohttp import web

from ..scrapers.realestate import scrape_realestate


def setup_routes(app, cors):
    r = cors.add(app.router.add_resource("/api/scrape"))
    cors.add(r.add_route("POST", scrape_handler))


async def scrape_handler(request):
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON body")

    url = (data.get("url") or "").strip()
    account_id = data.get("account_id")

    if not url:
        raise web.HTTPBadRequest(reason="url required")
    if account_id is None:
        raise web.HTTPBadRequest(reason="account_id required")

    try:
        account_id = int(account_id)
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(reason="account_id must be an integer")

    result = await scrape_realestate(account_id, url)
    if result.get("success"):
        return web.json_response(result)
    return web.json_response(result, status=400)
