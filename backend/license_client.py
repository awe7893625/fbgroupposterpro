"""
License client — talks to Vercel proxy at fbgroupposter.vercel.app.

Responsibilities:
- Generate / persist a stable install_uuid (device_id) — never derived from MAC.
- Cache the latest verify-license response so we can survive offline.
- Background heartbeat: re-verify every HEARTBEAT_INTERVAL_SEC, with OFFLINE_GRACE_SEC slack.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Optional

import aiohttp

from .database import SessionLocal
from .models import AppState

logger = logging.getLogger(__name__)

VERCEL_BASE_URL = os.environ.get(
    "FBP_LICENSE_BASE_URL", "https://fbgroupposter.vercel.app"
)
VERIFY_URL = f"{VERCEL_BASE_URL}/api/verify-license"
TRIAL_URL = f"{VERCEL_BASE_URL}/api/create-trial"
ORDER_URL = f"{VERCEL_BASE_URL}/api/create-order"

HEARTBEAT_INTERVAL_SEC = 6 * 3600  # re-verify every 6h when online
OFFLINE_GRACE_SEC = 72 * 3600  # 72h offline grace period
HTTP_TIMEOUT_SEC = 15

INSTALL_UUID_KEY = "install_uuid"
LICENSE_CACHE_KEY = "license_cache"


@dataclass
class LicenseStatus:
    valid: bool
    plan: Optional[str] = None
    expires_at: Optional[str] = None
    activated_at: Optional[str] = None
    license_key: Optional[str] = None
    error: Optional[str] = None
    last_verified_at: Optional[float] = None  # unix seconds
    source: str = "remote"  # remote | cache | none

    def to_dict(self) -> dict:
        return asdict(self)


def _get_state(key: str) -> Optional[str]:
    with SessionLocal() as db:
        row = db.get(AppState, key)
        return row.value if row else None


def _set_state(key: str, value: str) -> None:
    with SessionLocal() as db:
        row = db.get(AppState, key)
        if row:
            row.value = value
        else:
            db.add(AppState(key=key, value=value))
        db.commit()


def get_install_uuid() -> str:
    """Stable per-installation UUID. Created on first call, persisted in DB."""
    existing = _get_state(INSTALL_UUID_KEY)
    if existing:
        return existing
    new_uuid = str(uuid.uuid4())
    _set_state(INSTALL_UUID_KEY, new_uuid)
    logger.info(f"Generated new install_uuid: {new_uuid[:8]}...")
    return new_uuid


def _load_cache() -> Optional[LicenseStatus]:
    raw = _get_state(LICENSE_CACHE_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return LicenseStatus(**data)
    except Exception:
        return None


def _save_cache(status: LicenseStatus) -> None:
    _set_state(LICENSE_CACHE_KEY, json.dumps(status.to_dict()))


def _clear_cache() -> None:
    _set_state(LICENSE_CACHE_KEY, "")


async def verify_remote(license_key: str, device_id: str) -> LicenseStatus:
    """Call Vercel verify-license endpoint. Network errors raise; protocol errors return invalid."""
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            VERIFY_URL, json={"license_key": license_key, "device_id": device_id}
        ) as resp:
            data = await resp.json()
            now = time.time()
            if data.get("valid"):
                return LicenseStatus(
                    valid=True,
                    plan=data.get("plan"),
                    expires_at=data.get("expires_at"),
                    activated_at=data.get("activated_at"),
                    license_key=license_key,
                    last_verified_at=now,
                    source="remote",
                )
            return LicenseStatus(
                valid=False,
                plan=data.get("plan"),
                expires_at=data.get("expires_at"),
                license_key=license_key,
                error=data.get("error", "Unknown error"),
                last_verified_at=now,
                source="remote",
            )


async def get_current_status() -> LicenseStatus:
    """
    Return current license state.
    Order:
      1. No license_key in cache → not activated
      2. Try remote verify with cached key
      3. On network failure within OFFLINE_GRACE_SEC of last successful verify → return cached valid
      4. Beyond grace → return invalid with error="Offline grace expired"
    """
    cache = _load_cache()
    if not cache or not cache.license_key:
        return LicenseStatus(valid=False, error="Not activated", source="none")

    device_id = get_install_uuid()
    try:
        fresh = await verify_remote(cache.license_key, device_id)
        _save_cache(fresh)
        return fresh
    except Exception as e:
        logger.warning(f"Remote verify failed, falling back to cache: {e}")
        if cache.valid and cache.last_verified_at:
            age = time.time() - cache.last_verified_at
            if age <= OFFLINE_GRACE_SEC:
                cache.source = "cache"
                return cache
        return LicenseStatus(
            valid=False,
            license_key=cache.license_key,
            error=f"Offline grace expired ({int((time.time() - (cache.last_verified_at or 0)) / 3600)}h)",
            source="cache",
        )


async def activate(license_key: str) -> LicenseStatus:
    """Activate with a license key. Calls remote, persists cache on success."""
    license_key = license_key.strip().upper()
    device_id = get_install_uuid()
    status = await verify_remote(license_key, device_id)
    if status.valid:
        _save_cache(status)
        logger.info(
            f"License activated: plan={status.plan} expires={status.expires_at}"
        )
    _invalidate_memo()
    return status


async def deactivate() -> None:
    """Local-only deactivate (does NOT release device binding on server — that requires support)."""
    _clear_cache()
    _invalidate_memo()


async def request_trial(email: str) -> dict:
    """Request a trial license via Vercel proxy. Returns the raw response."""
    email = email.strip().lower()
    if "@" not in email:
        return {"error": "Valid email required"}
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(TRIAL_URL, json={"email": email}) as resp:
            try:
                return await resp.json()
            except Exception:
                return {"error": f"Trial endpoint returned {resp.status}"}


def get_purchase_url(plan: str = "pro", email: str = "") -> str:
    """Build a URL the frontend can open in the user's browser to start checkout."""
    from urllib.parse import urlencode

    return f"{ORDER_URL}?{urlencode({'plan': plan, 'email': email})}"


# ────────────────────────────────────────────────────────────
# In-memory memo for the request hot-path
#
# The license_gate middleware runs on every protected request. Calling
# get_current_status() each time hits SQLite + a 15-second remote timeout, so a
# slow Vercel response would stall every request. We keep a short-lived memo
# (60s) populated by both the heartbeat and on-demand refreshes.
# ────────────────────────────────────────────────────────────

GATE_MEMO_TTL_SEC = 60

_memo: Optional[LicenseStatus] = None
_memo_set_at: float = 0.0
_memo_lock: Optional[asyncio.Lock] = None


def _get_memo_lock() -> asyncio.Lock:
    """Lazily create the lock so we don't bind it to a loop at import time."""
    global _memo_lock
    if _memo_lock is None:
        _memo_lock = asyncio.Lock()
    return _memo_lock


async def get_status_for_gate() -> LicenseStatus:
    """Cheap call for the request-hot-path middleware. ≤1 remote roundtrip per
    GATE_MEMO_TTL_SEC. Concurrent callers share the in-flight verify."""
    global _memo, _memo_set_at
    now = time.time()
    if _memo is not None and (now - _memo_set_at) < GATE_MEMO_TTL_SEC:
        return _memo
    async with _get_memo_lock():
        # Double-check after acquiring the lock — another caller may have refreshed.
        now = time.time()
        if _memo is not None and (now - _memo_set_at) < GATE_MEMO_TTL_SEC:
            return _memo
        fresh = await get_current_status()
        _memo = fresh
        _memo_set_at = time.time()
        return fresh


def _invalidate_memo() -> None:
    """Force the next gate call to refetch — used after activate/deactivate."""
    global _memo, _memo_set_at
    _memo = None
    _memo_set_at = 0.0


# ────────────────────────────────────────────────────────────
# Background heartbeat
# ────────────────────────────────────────────────────────────

_heartbeat_task: Optional[asyncio.Task] = None


async def _heartbeat_loop():
    """Re-verify periodically. Cache always reflects last known state."""
    global _memo, _memo_set_at
    while True:
        try:
            fresh = await get_current_status()
            _memo = fresh
            _memo_set_at = time.time()
        except Exception as e:
            logger.error(f"heartbeat error: {e}")
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)


def start_heartbeat() -> None:
    global _heartbeat_task
    if _heartbeat_task and not _heartbeat_task.done():
        return
    loop = asyncio.get_event_loop()
    _heartbeat_task = loop.create_task(_heartbeat_loop())


def stop_heartbeat() -> None:
    global _heartbeat_task
    if _heartbeat_task and not _heartbeat_task.done():
        _heartbeat_task.cancel()
    _heartbeat_task = None
