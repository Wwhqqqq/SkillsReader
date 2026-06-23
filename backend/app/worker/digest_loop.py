"""
每日精选推送 Worker —— 按 schedule 定时生成并推送 Top N。

启动: cd backend && python -m app.worker.digest_loop
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.redis_client import close_redis, get_digest_schedule, mark_digest_slot_pushed
from app.init_db import init_db
from app.services.digest.engine import save_digest_run, select_daily_picks
from app.services.push.ruliu_notifier import send_digest

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("iknow.digest_worker")


async def _push_digest(
    *,
    slot_key: str,
    digest_date,
    top_n: int,
    target: str,
    channel: str,
) -> None:
    async with async_session_factory() as session:
        result = await select_daily_picks(
            session,
            digest_date=digest_date,
            top_n=top_n,
            channel=channel,
        )
        run = await save_digest_run(session, result, push_status="pending")
        try:
            await send_digest(result.content_md, dry_run=False, target=target)
            run.push_status = "sent"
            run.pushed_at = datetime.now()
            logger.info(
                "Digest push sent channel=%s slot=%s skills=%s",
                channel,
                slot_key,
                len(result.items),
            )
        except Exception as exc:
            run.push_status = "failed"
            run.push_error = str(exc)
            logger.exception("Digest push failed channel=%s slot=%s: %s", channel, slot_key, exc)
        await session.commit()


async def _maybe_push_scheduled() -> None:
    schedule = await get_digest_schedule()
    if not schedule.get("enabled", True):
        return

    tz_name = schedule.get("timezone") or "Asia/Shanghai"
    try:
        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.now()

    current_hm = now.strftime("%H:%M")
    target = schedule.get("target") or "dm"

    if schedule.get("official_new_enabled") and current_hm == (
        schedule.get("official_new_time") or "08:30"
    ):
        slot_key = f"{now.date().isoformat()}:official_new:{current_hm}"
        if await mark_digest_slot_pushed(slot_key):
            logger.info(
                "Running scheduled official portal scan + push slot=%s target=%s",
                slot_key,
                target,
            )
            async with async_session_factory() as session:
                try:
                    from app.services.scan.official_scan import run_official_scan_batch

                    await run_official_scan_batch(session, push_after=True)
                    await session.commit()
                except Exception as exc:
                    await session.rollback()
                    logger.exception("Scheduled official scan failed: %s", exc)
        return

    times = schedule.get("times") or []
    if current_hm not in times:
        return

    slot_key = f"{now.date().isoformat()}:digest:{current_hm}"
    if not await mark_digest_slot_pushed(slot_key):
        return

    top_n = int(schedule.get("top_n") or 10)
    logger.info("Running scheduled digest push slot=%s top_n=%s target=%s", slot_key, top_n, target)
    await _push_digest(
        slot_key=slot_key,
        digest_date=now.date(),
        top_n=top_n,
        target=target,
        channel="digest",
    )


async def run_digest_loop() -> None:
    await init_db()
    logger.info("Digest worker started")
    while True:
        try:
            await _maybe_push_scheduled()
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Digest worker error: %s", exc)
            await asyncio.sleep(60)


def main() -> None:
    try:
        asyncio.run(run_digest_loop())
    except KeyboardInterrupt:
        logger.info("Digest worker stopped")
    finally:
        asyncio.run(close_redis())


if __name__ == "__main__":
    main()
