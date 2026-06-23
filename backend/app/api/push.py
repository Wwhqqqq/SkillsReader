"""
如流推送 API —— 每日精选 Top N 预览与发送。

路由前缀: /api/push
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.helpers import to_digest_pick_items
from app.core.config import get_settings
from app.core.database import get_db
from app.models import DigestPickRun, PushLog
from app.schemas import (
    PushPreviewRequest,
    PushPreviewResponse,
    PushSendRequest,
    PushSendResponse,
)
from app.services.digest.engine import save_digest_run, select_daily_picks
from app.services.push.ruliu_notifier import send_digest

router = APIRouter(prefix="/api/push", tags=["push"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@router.get("/targets")
async def push_targets():
    settings = get_settings()
    return {
        "dm": {
            "label": "单聊",
            "default_user": settings.ruliu_dm_user or "wangheqiao",
        },
        "group": {
            "label": "群聊",
            "default_group_id": settings.ruliu_group_id or "13038971",
        },
    }


@router.post("/preview", response_model=PushPreviewResponse)
async def preview_push(body: PushPreviewRequest, session: AsyncSession = Depends(get_db)):
    vendors = body.vendors or None
    result = await select_daily_picks(
        session,
        digest_date=_parse_date(body.date),
        top_n=body.top_n,
        vendors=vendors,
        channel=body.channel,
    )
    return PushPreviewResponse(
        content_md=result.content_md,
        char_count=len(result.content_md),
        skill_count=len(result.items),
        items=to_digest_pick_items(result.items),
        needs_split=len(result.content_md) > 2048,
        config_version=result.config_version,
        meta=result.meta,
        digest_date=result.digest_date,
        top_n=result.top_n,
    )


@router.post("/send", response_model=PushSendResponse)
async def send_push(body: PushSendRequest, session: AsyncSession = Depends(get_db)):
    vendors = body.vendors or None
    result = await select_daily_picks(
        session,
        digest_date=_parse_date(body.date),
        top_n=body.top_n,
        vendors=vendors,
        channel=body.channel,
    )
    run = await save_digest_run(session, result, push_status="pending")
    content = result.content_md

    target_key = "ruliu_group" if body.target == "group" else "ruliu_dm"
    push_type = "official_new_daily" if body.channel == "official_new" else "digest_top10"
    log = PushLog(
        push_type=push_type,
        target=target_key,
        vendors=body.vendors,
        skill_count=len(result.items),
        content_md=content,
        status="pending",
    )
    session.add(log)
    await session.flush()

    try:
        if body.dry_run:
            log.status = "dry_run"
            run.push_status = "dry_run"
            await session.commit()
            return PushSendResponse(
                success=True,
                message="Preview only (dry_run)",
                push_log_id=log.id,
                digest_run_id=run.id,
                content_md=content,
            )
        resp = await send_digest(content, dry_run=False, target=body.target)
        log.status = "sent"
        log.response = resp
        run.push_status = "sent"
        run.pushed_at = datetime.now()
        await session.commit()
        target_label = "群聊" if body.target == "group" else "单聊"
        label = "官方发布新增日报" if body.channel == "official_new" else f"精选 Top{result.top_n}"
        return PushSendResponse(
            success=True,
            message=f"{label} 已推送到{target_label}",
            push_log_id=log.id,
            digest_run_id=run.id,
            content_md=content,
        )
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)
        run.push_status = "failed"
        run.push_error = str(exc)
        await session.commit()
        return PushSendResponse(
            success=False,
            message=str(exc),
            push_log_id=log.id,
            digest_run_id=run.id,
        )


@router.get("/history")
async def push_history(session: AsyncSession = Depends(get_db), limit: int = 20):
    logs = (
        await session.scalars(
            select(PushLog).order_by(PushLog.created_at.desc()).limit(limit)
        )
    ).all()
    return [
        {
            "id": l.id,
            "push_type": l.push_type,
            "target": l.target,
            "status": l.status,
            "skill_count": l.skill_count,
            "vendors": l.vendors,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "error": l.error_message,
        }
        for l in logs
    ]


@router.get("/digest-history")
async def digest_history(session: AsyncSession = Depends(get_db), limit: int = 30):
    runs = (
        await session.scalars(
            select(DigestPickRun).order_by(desc(DigestPickRun.created_at)).limit(limit)
        )
    ).all()
    return [
        {
            "id": r.id,
            "digest_date": r.digest_date.isoformat(),
            "top_n": r.top_n,
            "skill_count": len(r.picks or []),
            "push_status": r.push_status,
            "config_version": r.config_version,
            "pushed_at": r.pushed_at.isoformat() if r.pushed_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "meta": r.selection_meta,
        }
        for r in runs
    ]
