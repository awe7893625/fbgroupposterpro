# -*- coding: utf-8 -*-
"""
FBGroupPosterPro license backend (hosted, e.g. https://license.konggoo.uk).

Minimal but real: trial issuance + key verification with one-device binding. SQLite store.
Matches the desktop client contract (backend/license_client.py):
  POST /api/create-trial   {email}                     -> {license_key, plan, expires_at, valid}
  POST /api/verify-license {license_key, device_id}    -> {valid, plan, expires_at, activated_at, error?}
  POST /api/create-order   {plan, email}               -> {checkout_url}   (payment link; wire later)

Run:  python license_server.py     # binds 0.0.0.0:8798 (front with Cloudflare Tunnel)
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from aiohttp import web

PORT = int(os.environ.get("LICENSE_PORT", 8798))
DB = os.environ.get("LICENSE_DB", os.path.expanduser("~/.fbgp-license.db"))
TRIAL_DAYS = 14
PURCHASE_LINK = os.environ.get("FBGP_PURCHASE_LINK", "https://konggoo.uk")  # wire real payment later
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _db():
    conn = sqlite3.connect(DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY, email TEXT, plan TEXT,
            expires_at TEXT, device_id TEXT, activated_at TEXT, created_at TEXT
        )"""
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS trials_by_email (email TEXT PRIMARY KEY, license_key TEXT)"
    )
    conn.commit()
    return conn


def _gen_key() -> str:
    grp = lambda: "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"FBGP-{grp()}-{grp()}-{grp()}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def create_trial(request: web.Request):
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return web.json_response({"error": "bad request"}, status=400)
    email = (data.get("email") or "").strip().lower()
    if "@" not in email:
        return web.json_response({"error": "Valid email required"}, status=400)
    conn = _db()
    # One trial per email — return the existing key if already issued.
    row = conn.execute(
        "SELECT license_key, plan, expires_at FROM licenses WHERE license_key="
        "(SELECT license_key FROM trials_by_email WHERE email=?)",
        (email,),
    ).fetchone()
    if row:
        conn.close()
        return web.json_response(
            {"license_key": row[0], "plan": row[1], "expires_at": row[2], "valid": True,
             "note": "existing trial"}
        )
    key = _gen_key()
    now = datetime.now(timezone.utc)
    expires = _iso(now + timedelta(days=TRIAL_DAYS))
    conn.execute(
        "INSERT INTO licenses (license_key,email,plan,expires_at,device_id,activated_at,created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (key, email, "trial", expires, None, None, _iso(now)),
    )
    conn.execute("INSERT OR REPLACE INTO trials_by_email (email,license_key) VALUES (?,?)", (email, key))
    conn.commit()
    conn.close()
    return web.json_response({"license_key": key, "plan": "trial", "expires_at": expires, "valid": True})


async def verify_license(request: web.Request):
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return web.json_response({"valid": False, "error": "bad request"}, status=400)
    key = (data.get("license_key") or "").strip().upper()
    device_id = (data.get("device_id") or "").strip()
    if not key:
        return web.json_response({"valid": False, "error": "license_key required"})
    conn = _db()
    row = conn.execute(
        "SELECT plan, expires_at, device_id, activated_at FROM licenses WHERE license_key=?",
        (key,),
    ).fetchone()
    if not row:
        conn.close()
        return web.json_response({"valid": False, "error": "Invalid license key"})
    plan, expires_at, bound_device, activated_at = row
    # expiry
    try:
        exp = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            conn.close()
            return web.json_response(
                {"valid": False, "plan": plan, "expires_at": expires_at, "error": "License expired"}
            )
    except Exception:  # noqa: BLE001
        pass
    # one-device binding
    if bound_device and device_id and bound_device != device_id:
        conn.close()
        return web.json_response(
            {"valid": False, "plan": plan, "expires_at": expires_at,
             "error": "此授權已綁定其他裝置（請聯絡客服解綁）"}
        )
    if not bound_device and device_id:
        activated_at = _iso(datetime.now(timezone.utc))
        conn.execute(
            "UPDATE licenses SET device_id=?, activated_at=? WHERE license_key=?",
            (device_id, activated_at, key),
        )
        conn.commit()
    conn.close()
    return web.json_response(
        {"valid": True, "plan": plan, "expires_at": expires_at, "activated_at": activated_at}
    )


async def create_order(request: web.Request):
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        data = {}
    plan = (data.get("plan") or "pro")
    return web.json_response({"checkout_url": f"{PURCHASE_LINK}?plan={plan}"})


async def health(request: web.Request):
    conn = _db()
    n = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    conn.close()
    return web.json_response({"status": "ok", "licenses": n})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post("/api/create-trial", create_trial)
    app.router.add_post("/api/verify-license", verify_license)
    app.router.add_post("/api/create-order", create_order)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=PORT)
