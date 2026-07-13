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
    PushRecipientAddRequest,
    PushRecipientsUpdate,
    PushSendRequest,
    PushSendResponse,
)
from app.services.push.push_targets import (
    add_push_recipient,
    get_push_recipients,
    remove_push_recipient,
    set_push_recipients,
)
from app.services.digest.engine import save_digest_run, select_daily_picks
from app.services.digest.self_media_picker import (
    mark_self_media_pushed,
    select_self_media_picks,
)
from app.services.digest.push_desc import polish_push_descriptions
from app.services.push.ruliu_notifier import send_digest

router = APIRouter(prefix="/api/push", tags=["push"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@router.get("/targets")
async def push_targets():
    rec = await get_push_recipients()
    settings = get_settings()
    return {
        "dm_users": rec.get("dm_users") or [],
        "group_ids": rec.get("group_ids") or [],
        "official_new_dm_users": rec.get("official_new_dm_users") or [],
        "dm": {
            "label": "单聊",
            "default_user": settings.ruliu_dm_user or "wangheqiao",
        },
        "group": {
            "label": "群聊",
            "default_group_id": settings.ruliu_group_id or "13038971",
        },
    }


@router.put("/targets")
async def update_push_targets(body: PushRecipientsUpdate):
    data = body.model_dump(exclude_none=True)
    if not data:
        return await push_targets()
    return await set_push_recipients(data)


@router.post("/targets/add")
async def add_push_target(body: PushRecipientAddRequest):
    try:
        await add_push_recipient(body.kind, body.value)
        return await push_targets()
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/targets/remove")
async def remove_push_target(body: PushRecipientAddRequest):
    try:
        await remove_push_recipient(body.kind, body.value)
        return await push_targets()
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/preview", response_model=PushPreviewResponse)
async def preview_push(body: PushPreviewRequest, session: AsyncSession = Depends(get_db)):
    vendors = body.vendors or None
    if body.channel == "self_media":
        picks = await select_self_media_picks(session, top_n=body.top_n, ref_date=_parse_date(body.date))
        items = _build_self_media_items(picks)
        descs = await polish_push_descriptions(items, {"description_max_len": 20})
        content_md = _render_self_media_md(items, descs)
        return PushPreviewResponse(
            content_md=content_md,
            char_count=len(content_md),
            skill_count=len(items),
            items=items,
            needs_split=len(content_md) > 2048,
            config_version="self_media_v1",
            meta={"channel": "self_media", "platforms": _count_platforms(picks)},
            digest_date=body.date and date.fromisoformat(body.date) or date.today(),
            top_n=body.top_n,
        )

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
    target_key = "ruliu_group" if body.target == "group" else "ruliu_dm"
    target_label = "群聊" if body.target == "group" else "单聊"

    if body.channel == "self_media":
        picks = await select_self_media_picks(session, top_n=body.top_n, ref_date=_parse_date(body.date))
        items = _build_self_media_items(picks)
        descs = await polish_push_descriptions(items, {"description_max_len": 20})
        content = _render_self_media_md(items, descs)
        skill_count = len(items)
        skill_ids = [p.skill.id for p in picks]
        push_type = "self_media"
        label = f"自媒体定向推送 Top{body.top_n}"
    else:
        result = await select_daily_picks(
            session,
            digest_date=_parse_date(body.date),
            top_n=body.top_n,
            vendors=vendors,
            channel=body.channel,
        )
        run = await save_digest_run(session, result, push_status="pending")
        content = result.content_md
        skill_count = len(result.items)
        push_type = "official_new_daily" if body.channel == "official_new" else "digest_top10"
        label = "官方发布新增日报" if body.channel == "official_new" else f"精选 Top{result.top_n}"

    log = PushLog(
        push_type=push_type,
        target=target_key,
        vendors=body.vendors,
        skill_count=skill_count,
        content_md=content,
        status="pending",
    )
    session.add(log)
    await session.flush()

    try:
        if body.dry_run:
            log.status = "dry_run"
            if body.channel != "self_media":
                run.push_status = "dry_run"
            await session.commit()
            return PushSendResponse(
                success=True,
                message="Preview only (dry_run)",
                push_log_id=log.id,
                digest_run_id=run.id if body.channel != "self_media" else None,
                content_md=content,
            )
        resp = await send_digest(content, dry_run=False, target=body.target)
        log.status = "sent"
        log.response = resp
        if body.channel != "self_media":
            run.push_status = "sent"
            run.pushed_at = datetime.now()
        await session.commit()

        # 自媒体推送后标记为已推送
        if body.channel == "self_media":
            await mark_self_media_pushed(skill_ids)

        return PushSendResponse(
            success=True,
            message=f"{label} 已推送到{target_label}",
            push_log_id=log.id,
            digest_run_id=run.id if body.channel != "self_media" else None,
            content_md=content,
        )
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)
        if body.channel != "self_media":
            run.push_status = "failed"
            run.push_error = str(exc)
        await session.commit()
        return PushSendResponse(
            success=False,
            message=str(exc),
            push_log_id=log.id,
            digest_run_id=run.id if body.channel != "self_media" else None,
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


# ── 自媒体推送辅助函数 ──

def _build_self_media_items(picks) -> list:
    """将 CandidateContext 列表转成 DigestPickItemOut 格式。"""
    from app.api.helpers import skill_to_out
    from app.schemas import DigestPickItemOut, GrowthMetricsOut, ScoreBreakdownOut

    items = []
    for i, ctx in enumerate(picks, 1):
        g = ctx.growth
        growth_out = GrowthMetricsOut(
            metric_value=g.metric_value if hasattr(g, 'metric_value') else (ctx.skill.install_count or 0),
            metric_kind=getattr(g, 'metric_kind', 'install') or 'install',
            value_1d_ago=getattr(g, 'value_1d_ago', None),
            value_3d_ago=getattr(g, 'value_3d_ago', None),
            value_7d_ago=getattr(g, 'value_7d_ago', None),
            growth_1d_pct=getattr(g, 'growth_1d_pct', 0.0) or 0.0,
            growth_3d_pct=getattr(g, 'growth_3d_pct', 0.0) or 0.0,
            growth_7d_pct=getattr(g, 'growth_7d_pct', 0.0) or 0.0,
            growth_score=getattr(g, 'growth_score', 0.0) or 0.0,
        )
        items.append(
            DigestPickItemOut(
                rank=i,
                slot=ctx.slot or "self_media",
                pool="self_media",
                skill=skill_to_out(ctx.skill),
                score=round(ctx.score_total or 0, 1),
                score_breakdown=ScoreBreakdownOut(
                    trend=0,
                    official=1 if ctx.is_official else 0,
                    quality=0,
                    diversity=0,
                    total=round(ctx.score_total or 0, 1),
                ),
                growth=growth_out,
                recommend_reason=ctx.recommend_reason or "",
                is_official=ctx.is_official,
                is_new=ctx.is_new,
            )
        )
    return items


def _render_self_media_md(items, descs: dict[int, str] | None = None) -> str:
    """渲染自媒体定向推送 Markdown 表格。"""
    descs = descs or {}
    today = date.today().isoformat()
    lines = [
        f"##### 自媒体 Skill 定向推送 Top{len(items)} · {today}",
        "",
        "| Skill名称 | 公司 | Skill简介 | 是否曾推送 | 链接 |",
        "|------------|------|-----------|------------|------|",
    ]

    for item in items:
        skill = item.skill
        link = skill.detail_url or "#"
        name = (skill.name or "-").replace("|", "/").strip()
        vendor = (skill.vendor or "-").replace("|", "/").strip()
        desc = _skill_brief(skill, polished=descs.get(skill.id))
        pushed = "否" if "曾推送" not in (item.recommend_reason or "") else "是"

        row = (
            f"| [{name}]({link}) | {vendor} | {desc} | {pushed} | [查看]({link}) |"
        )
        lines.append(row)

    return "\n".join(lines)


def _skill_brief(skill, polished: str | None = None) -> str:
    """Skill 简介（优先 DeepSeek 概括，其次 LLM 摘要，最后 raw_description 截断）。"""
    if polished:
        desc = polished.strip()
    else:
        desc = (skill.llm_summary or skill.raw_description or "-").strip()
    desc = desc.replace("|", "/").replace("\n", " ")
    if len(desc) > 20:
        desc = desc[:19] + "…"
    return desc if desc else "-"


def _count_platforms(picks) -> dict[str, int]:
    """统计各平台 Skill 数量。"""
    from collections import Counter
    cnt = Counter()
    for ctx in picks:
        reason = ctx.recommend_reason or ""
        for plat in ("小红书", "微信/公众号", "抖音", "快手", "B站", "知乎", "微博", "通用自媒体"):
            if plat in reason:
                cnt[plat] += 1
                break
    return dict(cnt)
