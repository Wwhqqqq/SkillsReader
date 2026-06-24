"""
后台扫描 Worker —— 生产调度：
  - 每 10 分钟：官方门户扫描，有新增则推送单聊
  - 每 8 小时：全量扫描所有 enabled 源
  - 可选：按 sources.yaml interval_sec 逐源轮询（默认关闭）

启动: cd backend && python -m app.worker.scan_loop
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.redis_client import (
    WORKER_LAST_FULL_KEY,
    WORKER_LAST_OFFICIAL_KEY,
    close_redis,
    get_worker_last_run,
    is_scan_globally_enabled,
    set_worker_last_run,
)
from app.init_db import init_db
from app.models import Source
from app.services.scan.full_scan import run_full_scan_batch
from app.services.scan.official_scan import run_official_scan_batch
from app.services.scan.portal_schedule import official_interval_sec
from app.services.scan.schedule_config import (
    full_scan_interval_sec,
    per_source_scan_enabled,
    startup_delay_sec,
)
from app.services.scan.scanner import scan_source
from app.services.scan.source_sync import sync_sources_from_yaml

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("iknow.worker")

_worker_started_at: float = 0.0


def _past_startup_delay() -> bool:
    delay = startup_delay_sec()
    if delay <= 0:
        return True
    return (time.time() - _worker_started_at) >= delay


async def _due(last_ts: float | None, interval_sec: int) -> bool:
    if not _past_startup_delay():
        return False
    if last_ts is None:
        return True
    return (time.time() - last_ts) >= interval_sec


async def _run_official_portal_if_due() -> bool:
    interval = await official_interval_sec()
    last = await get_worker_last_run(WORKER_LAST_OFFICIAL_KEY)
    if not await _due(last, interval):
        return False
    logger.info("Running scheduled official portal scan (interval=%ss)", interval)
    async with async_session_factory() as session:
        try:
            await run_official_scan_batch(session, push_after=True)
            await session.commit()
            await set_worker_last_run(WORKER_LAST_OFFICIAL_KEY, time.time())
            return True
        except Exception:
            await session.rollback()
            raise


async def _run_full_scan_if_due() -> bool:
    interval = full_scan_interval_sec()
    last = await get_worker_last_run(WORKER_LAST_FULL_KEY)
    if not await _due(last, interval):
        return False
    logger.info("Running scheduled full scan (interval=%ss)", interval)
    async with async_session_factory() as session:
        try:
            await run_full_scan_batch(session)
            await session.commit()
            await set_worker_last_run(WORKER_LAST_FULL_KEY, time.time())
            return True
        except Exception:
            await session.rollback()
            raise


async def _run_per_source_scans(session) -> None:
    if not per_source_scan_enabled():
        return
    sources = list(
        (
            await session.scalars(
                select(Source).where(Source.enabled.is_(True)).order_by(Source.priority)
            )
        ).all()
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for source in sources:
        last = source.last_run_at
        interval = source.interval_sec or 300
        if last and (now - last).total_seconds() < interval:
            continue
        logger.info("Scanning source: %s", source.id)
        await scan_source(session, source)


async def run_scan_loop() -> None:
    global _worker_started_at
    _worker_started_at = time.time()
    await init_db()
    delay = startup_delay_sec()
    logger.info(
        "Worker started — official every %ss, full every %ss, per_source=%s, startup_delay=%ss",
        await official_interval_sec(),
        full_scan_interval_sec(),
        per_source_scan_enabled(),
        delay,
    )

    while True:
        try:
            if not await is_scan_globally_enabled():
                await asyncio.sleep(5)
                continue

            async with async_session_factory() as session:
                await sync_sources_from_yaml(session)
                await session.commit()

            await _run_official_portal_if_due()
            await _run_full_scan_if_due()

            if per_source_scan_enabled() and _past_startup_delay():
                async with async_session_factory() as session:
                    await _run_per_source_scans(session)
                    await session.commit()

            await asyncio.sleep(10)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)
            await asyncio.sleep(30)


def main() -> None:
    try:
        asyncio.run(run_scan_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped")
    finally:
        asyncio.run(close_redis())


if __name__ == "__main__":
    main()
