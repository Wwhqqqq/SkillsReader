"""
每日精选 Top N API —— 预览、生成、推送、配置与历史。

路由前缀: /api/digest
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.helpers import to_digest_pick_items
from app.core.database import get_db
from app.core.redis_client import get_digest_schedule, set_digest_schedule
from app.models import DigestPickRun, PushLog, Skill
from app.schemas import (
    DigestConfigResponse,
    DigestGenerateResponse,
    DigestPreviewRequest,
    DigestPreviewResponse,
    DigestScheduleSettings,
    DigestSendRequest,
    DigestSendResponse,
)
from app.services.digest.config_loader import load_digest_config
from app.services.digest.engine import get_latest_digest_run, save_digest_run, select_daily_picks
from app.services.push.ruliu_notifier import send_digest

router = APIRouter(prefix="/api/digest", tags=["digest"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@router.get("/config", response_model=DigestConfigResponse)
async def get_digest_config():
    cfg = load_digest_config()
    schedule_raw = await get_digest_schedule()
    return DigestConfigResponse(
        version=str(cfg.get("version") or "1"),
        config=cfg,
        schedule=DigestScheduleSettings(**schedule_raw),
    )


@router.get("/schedule", response_model=DigestScheduleSettings)
async def get_schedule():
    data = await get_digest_schedule()
    return DigestScheduleSettings(**data)


@router.put("/schedule", response_model=DigestScheduleSettings)
async def update_schedule(body: DigestScheduleSettings):
    data = await set_digest_schedule(body.model_dump())
    return DigestScheduleSettings(**data)


@router.post("/preview", response_model=DigestPreviewResponse)
async def preview_digest(body: DigestPreviewRequest, session: AsyncSession = Depends(get_db)):
    ref = _parse_date(body.date)
    vendors = body.vendors or None
    result = await select_daily_picks(
        session,
        digest_date=ref,
        top_n=body.top_n,
        vendors=vendors,
        channel=body.channel,
    )
    return DigestPreviewResponse(
        digest_date=result.digest_date,
        top_n=result.top_n,
        items=to_digest_pick_items(result.items),
        content_md=result.content_md,
        char_count=len(result.content_md),
        config_version=result.config_version,
        meta=result.meta,
        needs_split=len(result.content_md) > 2048,
    )


@router.post("/generate", response_model=DigestGenerateResponse)
async def generate_digest(body: DigestPreviewRequest, session: AsyncSession = Depends(get_db)):
    ref = _parse_date(body.date)
    vendors = body.vendors or None
    result = await select_daily_picks(
        session,
        digest_date=ref,
        top_n=body.top_n,
        vendors=vendors,
        channel=body.channel,
    )
    run = await save_digest_run(session, result)
    await session.commit()
    return DigestGenerateResponse(
        run_id=run.id,
        digest_date=result.digest_date,
        top_n=result.top_n,
        skill_count=len(result.items),
        config_version=result.config_version,
    )


@router.get("/picks")
async def get_picks(
    digest_date: str | None = None,
    top_n: int = 10,
    regenerate: bool = False,
    vendors: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    ref = _parse_date(digest_date) or date.today()
    vendor_list = [v.strip() for v in vendors.split(",") if v.strip()] if vendors else None
    if not regenerate:
        run = await get_latest_digest_run(session, ref)
        if run and run.picks:
            skill_ids = [p.get("skill_id") for p in run.picks if p.get("skill_id")]
            skills = {
                s.id: s
                for s in (
                    await session.scalars(select(Skill).where(Skill.id.in_(skill_ids)))
                ).all()
            }
            items = []
            for p in run.picks:
                sid = p.get("skill_id")
                skill = skills.get(sid)
                if not skill:
                    continue
                items.append(
                    {
                        **p,
                        "skill": skill,
                    }
                )
            from app.services.digest.types import DigestPickItem

            digest_items = [
                DigestPickItem(
                    rank=p["rank"],
                    slot=p.get("slot", ""),
                    pool=p.get("pool", ""),
                    skill=skills[p["skill_id"]],
                    score=p.get("score", 0),
                    score_breakdown=p.get("score_breakdown") or {},
                    growth=p.get("growth") or {},
                    recommend_reason=p.get("recommend_reason") or "",
                    is_official=p.get("is_official", False),
                    is_new=p.get("is_new", False),
                )
                for p in run.picks
                if p.get("skill_id") in skills
            ]
            return {
                "digest_date": ref.isoformat(),
                "top_n": run.top_n,
                "run_id": run.id,
                "items": to_digest_pick_items(digest_items),
                "content_md": run.content_md,
                "config_version": run.config_version,
                "meta": run.selection_meta,
                "from_cache": True,
            }

    result = await select_daily_picks(
        session, digest_date=ref, top_n=top_n, vendors=vendor_list
    )
    return {
        "digest_date": result.digest_date.isoformat(),
        "top_n": result.top_n,
        "items": to_digest_pick_items(result.items),
        "content_md": result.content_md,
        "config_version": result.config_version,
        "meta": result.meta,
        "from_cache": False,
    }


@router.post("/push", response_model=DigestSendResponse)
async def push_digest(body: DigestSendRequest, session: AsyncSession = Depends(get_db)):
    ref = _parse_date(body.date)
    vendors = body.vendors or None
    result = await select_daily_picks(
        session,
        digest_date=ref,
        top_n=body.top_n,
        vendors=vendors,
        channel=body.channel,
    )
    run = await save_digest_run(session, result, push_status="pending")
    content = result.content_md

    push_type = "official_new_daily" if body.channel == "official_new" else "digest_top10"
    log = PushLog(
        push_type=push_type,
        target="ruliu_group" if body.target == "group" else "ruliu_dm",
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
            return DigestSendResponse(
                success=True,
                message="Preview only (dry_run)",
                push_log_id=log.id,
                digest_run_id=run.id,
                content_md=content,
            )
        await send_digest(content, dry_run=False, target=body.target)
        log.status = "sent"
        run.push_status = "sent"
        run.pushed_at = datetime.now()
        await session.commit()
        target_label = "群聊" if body.target == "group" else "单聊"
        return DigestSendResponse(
            success=True,
            message=f"精选 Top{result.top_n} 已推送到{target_label}",
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
        return DigestSendResponse(
            success=False,
            message=str(exc),
            push_log_id=log.id,
            digest_run_id=run.id,
        )


@router.get("/history")
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
