from aiohttp import web
from ..database import SessionLocal
from ..models import Group

VALID_PLATFORMS = {"fb", "threads", "x", "instagram"}


def setup_routes(app, cors):
    r1 = cors.add(app.router.add_resource("/api/groups"))
    cors.add(r1.add_route("GET", list_groups))
    cors.add(r1.add_route("POST", create_group))

    r2 = cors.add(app.router.add_resource("/api/groups/{id}"))
    cors.add(r2.add_route("DELETE", delete_group))


async def list_groups(request):
    account_id = request.rel_url.query.get("account_id")
    with SessionLocal() as db:
        q = db.query(Group)
        if account_id:
            q = q.filter(Group.account_id == int(account_id))
        groups = q.all()
        return web.json_response(
            [
                {
                    "id": g.id,
                    "name": g.name,
                    "url": g.url,
                    "tag": g.tag,
                    "platform": g.platform,
                    "platform_entity_id": g.platform_entity_id,
                    "join_status": g.join_status,
                    "post_count": g.post_count,
                    "last_post_at": g.last_post_at.isoformat()
                    if g.last_post_at
                    else None,
                }
                for g in groups
            ]
        )


async def create_group(request):
    data = await request.json()
    account_id = data.get("account_id")
    url = data.get("url", "").strip()
    name = data.get("name", url).strip()
    if not account_id or not url:
        raise web.HTTPBadRequest(reason="account_id and url required")

    platform = data.get("platform", "fb")
    if platform not in VALID_PLATFORMS:
        raise web.HTTPBadRequest(
            reason=f"Invalid platform '{platform}'. Must be one of: {sorted(VALID_PLATFORMS)}"
        )

    with SessionLocal() as db:
        g = Group(
            account_id=account_id,
            url=url,
            name=name,
            fb_group_id=url.split("/")[-1] or url,
            tag=data.get("tag"),
            platform=platform,
            platform_entity_id=data.get("platform_entity_id"),
        )
        db.add(g)
        db.commit()
        db.refresh(g)
        return web.json_response(
            {
                "id": g.id,
                "name": g.name,
                "url": g.url,
                "platform": g.platform,
                "platform_entity_id": g.platform_entity_id,
            },
            status=201,
        )


async def delete_group(request):
    try:
        gid = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid group id")
    with SessionLocal() as db:
        g = db.get(Group, gid)
        if not g:
            raise web.HTTPNotFound()
        db.delete(g)
        db.commit()
        return web.json_response({"success": True})
