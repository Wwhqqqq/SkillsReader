"""官方新增 Skill 即时推送 —— 门户扫描 / 全量扫描共用。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill
from app.services.enrichment.skill_classification import is_official_publisher
from app.services.scan.events import emit_event
from app.services.scan.schedule_config import load_worker_schedule

logger = logging.getLogger(__name__)


async def filter_official_new_ids(session: AsyncSession, new_ids: list[int]) -> list[int]:
    if not new_ids:
        return []
    skills = list(
        (await session.scalars(select(Skill).where(Skill.id.in_(new_ids)))).all()
    )
    by_id = {s.id: s for s in skills}
    return [i for i in new_ids if i in by_id and is_official_publisher(by_id[i])]


async def push_official_new_skills(
    session: AsyncSession,
    skill_ids: list[int],
    *,
    source: str = "official_portal_scan",
    push_all: bool | None = None,
) -> str | None:
    """推送本轮官方新增；无官方新增则跳过。"""
    official_ids = await filter_official_new_ids(session, skill_ids)
    if not official_ids:
        return None
    try:
        from app.core.redis_client import get_digest_schedule
        from app.services.digest.engine import save_digest_run, select_official_new_from_scan_ids
        from app.services.push.push_targets import get_push_recipients
        from app.services.push.ruliu_notifier import send_digest

        sched = load_worker_schedule()
        portal_cfg = sched.get("official_portal") or {}
        target = str(portal_cfg.get("push_target") or "dm")
        recipients = await get_push_recipients()
        dm_users = recipients.get("official_new_dm_users") or recipients.get("dm_users") or []
        if push_all is None:
            push_all = bool(portal_cfg.get("push_all_new", True))
        top_n = len(official_ids) if push_all else int(
            ((await get_digest_schedule()).get("official_new_top_n") or 10)
        )
        result = await select_official_new_from_scan_ids(
            session, official_ids, top_n=top_n
        )
        if not result.items:
            return "skipped_empty"
        result.meta["source"] = source
        run = await save_digest_run(session, result, push_status="pending")
        await send_digest(
            result.content_md,
            dry_run=False,
            target=target,
            dm_users=dm_users if target != "group" else None,
        )
        run.push_status = "sent"
        run.pushed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        from app.core.redis_client import set_official_scan_state

        await set_official_scan_state(
            {"last_new_official_at": run.pushed_at.isoformat()}
        )
        await emit_event(
            session,
            event_type="official_new_push",
            message=f"官方新增已推送 {len(result.items)} 条 → {target}（{source}）",
            level="success",
            payload={
                "skill_count": len(result.items),
                "target": target,
                "source": source,
            },
        )
        return "sent"
    except Exception as exc:
        logger.exception("official new push failed")
        await emit_event(
            session,
            event_type="official_new_push_error",
            message=f"官方新增推送失败: {exc}",
            level="error",
        )
        return "failed"
