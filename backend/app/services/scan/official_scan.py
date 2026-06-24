"""各公司官方门户一键扫描 —— 仅官网/API，不含 GitHub 等外部源。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_official_scan_state, set_official_scan_state
from app.models import Skill
from app.services.scan.events import emit_event
from app.services.scan.official_new_push import filter_official_new_ids, push_official_new_skills
from app.services.scan.official_portals import list_official_portal_sources
from app.services.scan.scanner import scan_source

logger = logging.getLogger(__name__)


@dataclass
class OfficialScanBatchResult:
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    sources_total: int = 0
    sources_ok: int = 0
    sources_error: int = 0
    new_skill_ids: list[int] = field(default_factory=list)
    new_official_skill_ids: list[int] = field(default_factory=list)
    vendor_new_counts: dict[str, int] = field(default_factory=dict)
    push_status: str | None = None
    error_message: str | None = None


async def _official_ids_from_new(
    session: AsyncSession, new_ids: list[int]
) -> list[int]:
    return await filter_official_new_ids(session, new_ids)


async def run_official_scan_batch(
    session: AsyncSession,
    *,
    push_after: bool = True,
) -> OfficialScanBatchResult:
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    batch = OfficialScanBatchResult(started_at=started_at, status="running")
    sources = await list_official_portal_sources(session)
    batch.sources_total = len(sources)

    await set_official_scan_state(
        {
            "status": "running",
            "started_at": started_at.isoformat(),
            "finished_at": None,
            "sources_total": batch.sources_total,
            "new_count": 0,
            "new_official_count": 0,
            "new_skill_ids": [],
            "new_official_skill_ids": [],
            "vendor_new_counts": {},
        }
    )
    await emit_event(
        session,
        event_type="official_scan_start",
        message=f"开始官方门户扫描（{batch.sources_total} 个官网源，不含 GitHub/SkillsMP）",
        level="info",
    )

    all_new_ids: list[int] = []
    vendor_counts: dict[str, int] = {}

    try:
        for source in sources:
            try:
                result = await scan_source(
                    session, source, official_portal_only=True
                )
                run = result.run
                new_ids = list(result.new_skill_ids)
                if run.status == "success":
                    batch.sources_ok += 1
                else:
                    batch.sources_error += 1
                if new_ids:
                    all_new_ids.extend(new_ids)
                    official_new = await _official_ids_from_new(session, new_ids)
                    if official_new:
                        vendor_counts[source.vendor] = (
                            vendor_counts.get(source.vendor, 0) + len(official_new)
                        )
            except Exception as exc:
                batch.sources_error += 1
                logger.exception("official portal scan failed for %s", source.id)
                await emit_event(
                    session,
                    event_type="official_scan_source_error",
                    message=f"[{source.vendor}] 官方门户扫描失败: {exc}",
                    source_id=source.id,
                    level="error",
                )

        batch.new_skill_ids = list(dict.fromkeys(all_new_ids))
        batch.new_official_skill_ids = await _official_ids_from_new(
            session, batch.new_skill_ids
        )
        batch.vendor_new_counts = vendor_counts
        batch.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        batch.status = "done"
        last_new_at = None
        if batch.new_official_skill_ids:
            last_new_at = batch.finished_at.isoformat()

        if push_after and batch.new_skill_ids:
            batch.push_status = await push_official_new_skills(
                session,
                batch.new_skill_ids,
                source="official_portal_scan",
                push_all=True,
            )

        await emit_event(
            session,
            event_type="official_scan_done",
            message=(
                f"官方门户扫描完成：新增官方 {len(batch.new_official_skill_ids)} 条"
                f"（共发现 {len(batch.new_skill_ids)} 条）"
                + (f"，推送 {batch.push_status}" if batch.push_status else "")
            ),
            level="success",
            payload={
                "new_official_count": len(batch.new_official_skill_ids),
                "new_count": len(batch.new_skill_ids),
                "vendor_new_counts": vendor_counts,
                "sources_ok": batch.sources_ok,
                "sources_error": batch.sources_error,
                "push_status": batch.push_status,
            },
        )
    except Exception as exc:
        batch.status = "error"
        batch.error_message = str(exc)
        batch.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await emit_event(
            session,
            event_type="official_scan_error",
            message=f"官方门户扫描失败: {exc}",
            level="error",
        )

    await set_official_scan_state(
        {
            "status": batch.status,
            "started_at": batch.started_at.isoformat(),
            "finished_at": batch.finished_at.isoformat() if batch.finished_at else None,
            "sources_total": batch.sources_total,
            "sources_ok": batch.sources_ok,
            "sources_error": batch.sources_error,
            "new_count": len(batch.new_skill_ids),
            "new_official_count": len(batch.new_official_skill_ids),
            "new_skill_ids": batch.new_official_skill_ids,
            "new_official_skill_ids": batch.new_official_skill_ids,
            "vendor_new_counts": batch.vendor_new_counts,
            "error_message": batch.error_message,
            "push_status": batch.push_status,
            **({"last_new_official_at": last_new_at} if last_new_at else {}),
        }
    )
    return batch
