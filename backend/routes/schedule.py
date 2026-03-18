from aiohttp import web


def setup_routes(app, cors):
    r = cors.add(app.router.add_resource("/api/schedule"))
    cors.add(r.add_route("GET", list_jobs))


async def list_jobs(request):
    # APScheduler integration to be added in scheduler.py
    return web.json_response({"jobs": []})
