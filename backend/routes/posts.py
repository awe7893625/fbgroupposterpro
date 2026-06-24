import asyncio
import json
from datetime import datetime

from aiohttp import web

from ..database import SessionLocal
from ..models import Group, Post, PostRecord
from ..selenium_engine import selenium_engine

POST_TIMEOUT_SEC = 3600  # 1 hour max per post run

# Per-platform Selenium timeout (Ray M5)
PLATFORM_TIMEOUT = {"fb": 300, "threads": 180, "x": 240, "instagram": 300}


def setup_routes(app, cors):
    r1 = cors.add(app.router.add_resource("/api/posts"))
    cors.add(r1.add_route("GET", list_posts))
    cors.add(r1.add_route("POST", create_post))

    r2 = cors.add(app.router.add_resource("/api/posts/{id}"))
    cors.add(r2.add_route("DELETE", delete_post))

    r3 = cors.add(app.router.add_resource("/api/posts/{id}/start"))
    cors.add(r3.add_route("POST", start_post))


async def list_posts(request):
    status = request.rel_url.query.get("status")
    with SessionLocal() as db:
        q = db.query(Post)
        if status:
            q = q.filter(Post.status == status)
        posts = q.order_by(Post.created_at.desc()).limit(100).all()
        return web.json_response(
            [
                {
                    "id": p.id,
                    "content": p.content[:100] + "..."
                    if len(p.content) > 100
                    else p.content,
                    "status": p.status,
                    "total_groups": p.total_groups,
                    "success_count": p.success_count,
                    "fail_count": p.fail_count,
                    "scheduled_at": p.scheduled_at.isoformat()
                    if p.scheduled_at
                    else None,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in posts
            ]
        )


async def create_post(request):
    data = await request.json()
    account_id = data.get("account_id")
    content = data.get("content", "").strip()
    group_ids = data.get("group_ids", [])
    if not account_id or not content:
        raise web.HTTPBadRequest(reason="account_id and content required")

    scheduled_at = None
    if data.get("scheduled_at"):
        try:
            scheduled_at = datetime.fromisoformat(data["scheduled_at"])
        except ValueError:
            raise web.HTTPBadRequest(reason="Invalid scheduled_at format (ISO 8601)")

    with SessionLocal() as db:
        post = Post(
            account_id=account_id,
            content=content,
            images_json=json.dumps(data.get("images", [])),
            group_ids_json=json.dumps(group_ids),
            interval_sec=data.get("interval_seconds", 90),
            auto_delete_days=data.get("auto_delete_days"),
            scheduled_at=scheduled_at,
            total_groups=len(group_ids),
            status="queued",
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id

    return web.json_response({"post_id": post_id, "status": "queued"}, status=201)


async def start_post(request):
    try:
        post_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid post id")
    asyncio.create_task(_run_post_with_timeout(post_id))
    return web.json_response({"success": True, "message": "Post started"})


async def _run_post_with_timeout(post_id: int):
    """Wrap _run_post with a timeout. Marks post as failed on timeout."""
    try:
        await asyncio.wait_for(_run_post(post_id), timeout=POST_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        with SessionLocal() as db:
            post_obj = db.get(Post, post_id)
            if post_obj and post_obj.status == "running":
                post_obj.status = "failed"
                post_obj.completed_at = datetime.utcnow()
                db.commit()


async def _run_post(post_id: int):
    """Run post in background, only posting to the group_ids selected by the user."""
    with SessionLocal() as db:
        post = db.get(Post, post_id)
        if not post:
            return
        account_id = post.account_id
        content = post.content
        interval_sec = post.interval_sec or 90

        # Respect the user-selected group_ids, falling back to all joined groups
        selected_ids = json.loads(post.group_ids_json or "[]")
        q = db.query(Group).filter(
            Group.account_id == account_id, Group.join_status == "joined"
        )
        if selected_ids:
            q = q.filter(Group.id.in_(selected_ids))
        groups = q.limit(500).all()
        groups_data = [
            {"id": g.id, "url": g.url, "name": g.name, "platform": g.platform}
            for g in groups
        ]

        post.status = "running"
        post.started_at = datetime.utcnow()
        db.commit()

    await selenium_engine.start_browser(account_id)

    if not groups_data:
        with SessionLocal() as db:
            post_obj = db.get(Post, post_id)
            if post_obj:
                post_obj.status = "failed"
                post_obj.completed_at = datetime.utcnow()
                db.commit()
        return

    # Load images from DB (post object was closed with the earlier session)
    with SessionLocal() as db:
        _post_obj = db.get(Post, post_id)
        images = json.loads(_post_obj.images_json or "[]") if _post_obj else []

    for g in groups_data:
        platform = g.get("platform", "fb")

        # Ray M3: Instagram requires at least one image — skip and record failure early
        if platform == "instagram" and not images:
            with SessionLocal() as db:
                db.add(
                    PostRecord(
                        post_id=post_id,
                        group_id=g["id"],
                        group_name=g["name"],
                        account_id=account_id,
                        status="failed",
                        error_msg="Instagram requires at least one image",
                        posted_at=datetime.utcnow(),
                    )
                )
                db.commit()
                post_obj = db.get(Post, post_id)
                if post_obj:
                    post_obj.fail_count += 1
                    db.commit()
            continue

        try:
            timeout = PLATFORM_TIMEOUT.get(platform, 300)
            result = await asyncio.wait_for(
                selenium_engine.post_to_group(
                    account_id, g["url"], content, images=images, platform=platform
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            result = {"success": False, "error": f"Timeout after {timeout}s"}
        except Exception as exc:
            result = {"success": False, "error": str(exc)}

        with SessionLocal() as db:
            _post_url = result.get("post_url")
            record = PostRecord(
                post_id=post_id,
                group_id=g["id"],
                group_name=g["name"],
                account_id=account_id,
                fb_post_url=_post_url if platform == "fb" else None,
                fb_post_id=result.get("post_id") if platform == "fb" else None,
                post_url=_post_url,  # generic field for all platforms
                status="active" if result["success"] else "failed",
                error_msg=result.get("error"),
                posted_at=datetime.utcnow() if result["success"] else None,
            )
            db.add(record)
            db.commit()

            post_obj = db.get(Post, post_id)
            if post_obj:
                if result["success"]:
                    post_obj.success_count += 1
                else:
                    post_obj.fail_count += 1
                db.commit()

        if result["success"]:
            await asyncio.sleep(interval_sec)

    with SessionLocal() as db:
        post_obj = db.get(Post, post_id)
        if post_obj:
            post_obj.status = "completed"
            post_obj.completed_at = datetime.utcnow()
            db.commit()


async def delete_post(request):
    try:
        post_id = int(request.match_info["id"])
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid post id")
    with SessionLocal() as db:
        p = db.get(Post, post_id)
        if not p:
            raise web.HTTPNotFound()
        db.delete(p)
        db.commit()
        return web.json_response({"success": True})
