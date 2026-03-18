from datetime import datetime

from aiohttp import web

from ..database import SessionLocal
from ..models import PostRecord


def setup_routes(app, cors):
    r = cors.add(app.router.add_resource("/api/report"))
    cors.add(r.add_route("GET", get_report))


async def get_report(request):
    from_str = request.rel_url.query.get("from")
    to_str = request.rel_url.query.get("to")
    account_id_str = request.rel_url.query.get("account_id")

    account_id = None
    if account_id_str:
        try:
            account_id = int(account_id_str)
        except ValueError:
            raise web.HTTPBadRequest(reason="Invalid account_id")

    from_dt = None
    if from_str:
        try:
            from_dt = datetime.fromisoformat(from_str)
        except ValueError:
            raise web.HTTPBadRequest(reason="Invalid from date (ISO 8601)")

    to_dt = None
    if to_str:
        try:
            to_dt = datetime.fromisoformat(to_str)
        except ValueError:
            raise web.HTTPBadRequest(reason="Invalid to date (ISO 8601)")

    with SessionLocal() as db:
        q = db.query(PostRecord)
        if account_id:
            q = q.filter(PostRecord.account_id == account_id)
        if from_dt:
            q = q.filter(PostRecord.posted_at >= from_dt)
        if to_dt:
            q = q.filter(PostRecord.posted_at <= to_dt)
        records = q.order_by(PostRecord.posted_at.desc()).limit(500).all()

        total = len(records)
        success = sum(1 for r in records if r.status == "active")
        failed = sum(1 for r in records if r.status == "failed")
        deleted = sum(1 for r in records if r.status == "deleted")

        return web.json_response(
            {
                "records": [
                    {
                        "id": r.id,
                        "group_name": r.group_name,
                        "status": r.status,
                        "fb_post_url": r.fb_post_url,
                        "posted_at": r.posted_at.isoformat() if r.posted_at else None,
                        "deleted_at": r.deleted_at.isoformat()
                        if r.deleted_at
                        else None,
                        "error_msg": r.error_msg,
                    }
                    for r in records
                ],
                "summary": {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "deleted": deleted,
                    "success_rate": round(success / total * 100) if total > 0 else 0,
                },
            }
        )
