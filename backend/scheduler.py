"""
Auto-delete scheduler for FBGroupPosterPro.

定時掃描過期貼文並自動下架（對標 EZup 的「7天自動下架」）。
刪除動作抽象成可注入的 _deleter，方便不靠真 FB 帳號就能測排程邏輯。

Public API:
    set_deleter(fn)                          # 注入刪文實作（測試用 mock）
    await sweep_expired_once() -> dict        # 跑一次掃描，回 {checked, deleted, failed}
    start_auto_delete_scheduler(interval_minutes=30)
    stop_auto_delete_scheduler()
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

_scheduler = None  # AsyncIOScheduler singleton


async def _default_deleter(account_id: int, url: str, post_id: str = None) -> bool:
    """預設刪文：呼叫 selenium_engine.delete_post（尚未實作時回 False，不崩）。"""
    try:
        from .selenium_engine import selenium_engine

        fn = getattr(selenium_engine, "delete_post", None)
        if fn is None:
            logger.warning("selenium_engine.delete_post 尚未實作，跳過刪除 %s", url)
            return False
        return bool(await fn(account_id, url, post_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("default deleter failed for %s: %s", url, e)
        return False


# Injectable deleter — async (account_id, url, post_id=None) -> bool
_deleter: Callable[..., Awaitable[bool]] = _default_deleter


def set_deleter(fn: Callable[..., Awaitable[bool]]) -> None:
    """Inject a custom deleter (used by tests to avoid touching real FB)."""
    global _deleter
    _deleter = fn


def _deleter_accepts_post_id() -> bool:
    """Whether the current deleter accepts a 3rd (post_id) arg, decided by signature so we
    never have to guess from a caught TypeError."""
    import inspect

    try:
        params = inspect.signature(_deleter).parameters.values()
        if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
            return True  # *args
        positional = [
            p
            for p in params
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        return len(positional) >= 3
    except (ValueError, TypeError):
        return False


async def sweep_expired_once() -> dict:
    """
    掃描所有 status="active" 的 PostRecord，將已過 auto_delete_days 的貼文刪除。
    回傳 {"checked": n, "deleted": d, "failed": f}。整個函式絕不向外拋例外。
    """
    from .database import SessionLocal
    from .models import Post, PostRecord

    checked = deleted = failed = 0
    now = datetime.utcnow()

    try:
        with SessionLocal() as db:
            actives = db.query(PostRecord).filter(PostRecord.status == "active").all()
            for record in actives:
                post = db.get(Post, record.post_id)
                if (
                    post is None
                    or not post.auto_delete_days
                    or post.auto_delete_days <= 0
                ):
                    continue
                if record.posted_at is None:
                    continue
                expiry = record.posted_at + timedelta(days=post.auto_delete_days)
                if expiry > now:
                    continue  # 未到期

                checked += 1
                record.status = "pending_delete"
                db.commit()

                url = record.fb_post_url or record.post_url
                if not url:
                    record.status = "delete_failed"
                    record.error_msg = "no post url to delete"
                    failed += 1
                    db.commit()
                    continue

                fb_post_id = getattr(record, "fb_post_id", None)
                try:
                    # Decide arity up-front (NOT via catching TypeError, which would also
                    # swallow a TypeError raised *inside* the deleter and silently re-run it).
                    if _deleter_accepts_post_id():
                        ok = await _deleter(record.account_id, url, fb_post_id)
                    else:
                        ok = await _deleter(record.account_id, url)
                except Exception as e:  # noqa: BLE001
                    record.status = "delete_failed"
                    record.error_msg = str(e)
                    failed += 1
                    db.commit()
                    continue

                if ok:
                    record.status = "deleted"
                    record.deleted_at = now
                    deleted += 1
                else:
                    record.status = "delete_failed"
                    failed += 1
                db.commit()
    except Exception as e:  # noqa: BLE001 - sweep must never crash the scheduler
        logger.exception("sweep_expired_once failed: %s", e)

    if checked:
        logger.info(
            "auto-delete sweep: checked=%d deleted=%d failed=%d",
            checked,
            deleted,
            failed,
        )
    return {"checked": checked, "deleted": deleted, "failed": failed}


def _run_sweep_job() -> None:
    """APScheduler job — schedule the async sweep on the running loop."""
    try:
        asyncio.create_task(sweep_expired_once())
    except RuntimeError as e:
        logger.warning("could not schedule sweep task: %s", e)


def start_auto_delete_scheduler(interval_minutes: int = 30) -> None:
    """啟動定時自動刪除排程器（idempotent）。"""
    global _scheduler
    if _scheduler is not None:
        return
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    sched = AsyncIOScheduler()
    sched.add_job(
        _run_sweep_job,
        "interval",
        minutes=max(1, int(interval_minutes)),
        id="auto_delete",
        replace_existing=True,
    )
    sched.start()
    _scheduler = sched
    logger.info("auto-delete scheduler started (every %d min)", interval_minutes)


def stop_auto_delete_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
        except Exception as e:  # noqa: BLE001
            logger.warning("scheduler shutdown error: %s", e)
        _scheduler = None
