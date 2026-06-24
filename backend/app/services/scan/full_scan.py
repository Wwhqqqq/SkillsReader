"""全量扫描 —— 遍历所有 enabled 源，执行完整 fetch()。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source
from app.services.scan.events import emit_event
from app.services.scan.official_new_push import filter_official_new_ids, push_official_new_skills
from app.services.scan.schedule_config import full_scan_push_official_new
from app.services.scan.scanner import scan_source

logger = logging.getLogger(__name__)


@dataclass
class FullScanBatchResult:
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    sources_total: int = 0
    sources_ok: int = 0
    sources_error: int = 0
    new_skill_ids: list[int] = field(default_factory=list)
    new_official_skill_ids: list[int] = field(default_factory=list)
    push_status: str | None = None
    error_message: str | None = None


async def run_full_scan_batch(session: AsyncSession) -> FullScanBatchResult:
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    batch = FullScanBatchResult(started_at=started_at, status="running")
    sources = list(
        (
            await session.scalars(
                select(Source)
                .where(Source.enabled.is_(True))
                .order_by(Source.priority, Source.id)
            )
        ).all()
    )
    batch.sources_total = len(sources)

    await emit_event(
        session,
        event_type="full_scan_start",
        message=f"开始全量扫描（{batch.sources_total} 个源）",
        level="info",
    )

    all_new: list[int] = []
    try:
        for source in sources:
            try:
                result = await scan_source(session, source)
                if result.run.status == "success":
                    batch.sources_ok += 1
                else:
                    batch.sources_error += 1
                if result.new_skill_ids:
                    all_new.extend(result.new_skill_ids)
            except Exception as exc:
                batch.sources_error += 1
                logger.exception("full scan failed for %s", source.id)
                await emit_event(
                    session,
                    event_type="full_scan_source_error",
                    message=f"[{source.vendor}] 全量扫描失败: {exc}",
                    source_id=source.id,
                    level="error",
                )

        batch.new_skill_ids = list(dict.fromkeys(all_new))
        batch.new_official_skill_ids = await filter_official_new_ids(
            session, batch.new_skill_ids
        )
        batch.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if batch.new_official_skill_ids:
            from app.core.redis_client import set_official_scan_state

            await set_official_scan_state(
                {"last_new_official_at": batch.finished_at.isoformat()}
            )
        if full_scan_push_official_new() and batch.new_official_skill_ids:
            batch.push_status = await push_official_new_skills(
                session,
                batch.new_official_skill_ids,
                source="full_scan",
            )
        batch.status = "done"
        await emit_event(
            session,
            event_type="full_scan_done",
            message=(
                f"全量扫描完成：{batch.sources_ok}/{batch.sources_total} 成功，"
                f"新增 {len(batch.new_skill_ids)} 条"
                + (
                    f"，官方新增 {len(batch.new_official_skill_ids)} 条"
                    if batch.new_official_skill_ids
                    else ""
                )
                + (f"，推送 {batch.push_status}" if batch.push_status else "")
            ),
            level="success",
            payload={
                "sources_ok": batch.sources_ok,
                "sources_error": batch.sources_error,
                "new_count": len(batch.new_skill_ids),
                "new_official_count": len(batch.new_official_skill_ids),
                "push_status": batch.push_status,
            },
        )
    except Exception as exc:
        batch.status = "error"
        batch.error_message = str(exc)
        batch.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await emit_event(
            session,
            event_type="full_scan_error",
            message=f"全量扫描失败: {exc}",
            level="error",
        )
    return batch
