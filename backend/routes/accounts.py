from aiohttp import web
from ..database import SessionLocal
from ..models import Account
from ..crypto import encrypt


def setup_routes(app, cors):
    resource = cors.add(app.router.add_resource("/api/accounts"))
    cors.add(resource.add_route("GET", list_accounts))
    cors.add(resource.add_route("POST", create_account))

    resource2 = cors.add(app.router.add_resource("/api/accounts/{id}"))
    cors.add(resource2.add_route("DELETE", delete_account))
    cors.add(resource2.add_route("GET", get_account))


async def list_accounts(request):
    with SessionLocal() as db:
        accounts = db.query(Account).all()
        return web.json_response(
            [
                {
                    "id": a.id,
                    "name": a.name,
                    "email": a.email,
                    "status": a.status,
                    "proxy": a.proxy,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in accounts
            ]
        )


async def get_account(request):
    acc_id = int(request.match_info["id"])
    with SessionLocal() as db:
        a = db.get(Account, acc_id)
        if not a:
            raise web.HTTPNotFound(reason="Account not found")
        return web.json_response(
            {
                "id": a.id,
                "name": a.name,
                "email": a.email,
                "status": a.status,
                "proxy": a.proxy,
            }
        )


async def create_account(request):
    data = await request.json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    proxy = data.get("proxy")

    if not name or not email or not password:
        raise web.HTTPBadRequest(reason="name, email, password required")

    with SessionLocal() as db:
        existing = db.query(Account).filter(Account.email == email).first()
        if existing:
            raise web.HTTPConflict(reason="Email already exists")

        account = Account(
            name=name,
            email=email,
            password_enc=encrypt(password),
            proxy=proxy,
            status="active",
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return web.json_response(
            {"id": account.id, "name": account.name, "status": account.status},
            status=201,
        )


async def delete_account(request):
    acc_id = int(request.match_info["id"])
    with SessionLocal() as db:
        a = db.get(Account, acc_id)
        if not a:
            raise web.HTTPNotFound()
        db.delete(a)
        db.commit()
        return web.json_response({"success": True})
