"""每日精选流水线编排。

入口函数 `select_daily_picks` 完成从候选构建 -> 结构化选择 -> Markdown 格式化的完整过程，
并返回 `DigestResult`。其他辅助函数实现持久化（`save_digest_run`）与读取最新记录。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DigestPickRun
from app.services.digest.config_loader import config_version, load_digest_config
from app.services.digest.formatter import format_digest_markdown
from app.services.digest.push_desc import polish_push_descriptions
from app.services.digest.pools import build_candidates, build_candidates_from_skill_ids
from app.services.digest.selector import select_official_new_picks, select_structured_picks
from app.services.digest.types import DigestPickItem, DigestResult


def _primary_pool(ctx) -> str:
    order = ("official", "trend", "discovery", "popularity")
    for p in order:
        if p in ctx.pools:
            return p
    return next(iter(ctx.pools), "unknown")


def _build_items(picks) -> list[DigestPickItem]:
    items: list[DigestPickItem] = []
    for i, ctx in enumerate(picks, start=1):
        items.append(
            DigestPickItem(
                rank=i,
                slot=ctx.slot,
                pool=_primary_pool(ctx),
                skill=ctx.skill,
                score=ctx.score_total,
                score_breakdown=dict(ctx.score_breakdown),
                growth=ctx.growth.to_dict(),
                recommend_reason=ctx.recommend_reason,
                is_official=ctx.is_official,
                is_new=ctx.is_new,
            )
        )
    return items


async def finalize_digest_content(result: DigestResult, cfg: dict[str, Any]) -> None:
    push_cfg = dict(cfg.get("push") or {})
    channel = (result.meta or {}).get("channel") or "digest"
    if channel == "official_new":
        push_cfg = {**push_cfg, **(push_cfg.get("official_new") or {})}
    if push_cfg.get("polish_description", True):
        result.meta["push_descriptions"] = await polish_push_descriptions(result.items, push_cfg)
    result.content_md = format_digest_markdown(result, cfg)


async def select_daily_picks(
    session: AsyncSession,
    *,
    digest_date: date | None = None,
    top_n: int | None = None,
    vendors: list[str] | None = None,
    channel: str = "digest",
    cfg: dict[str, Any] | None = None,
) -> DigestResult:
    # 加载配置、确定参考日期与 top_n
    cfg = cfg or load_digest_config()
    ref = digest_date or datetime.utcnow().date()
    top_n = top_n or int((cfg.get("selection") or {}).get("default_top_n") or 10)
    channel = channel or "digest"

    candidates = await build_candidates(session, cfg, vendors=vendors, ref_date=ref)
    if channel == "official_new":
        picks = select_official_new_picks(candidates, cfg, top_n=top_n, ref_date=ref)
    else:
        picks = select_structured_picks(candidates, cfg, top_n=top_n)
    items = _build_items(picks)

    result = DigestResult(
        digest_date=ref,
        top_n=top_n,
        items=items,
        config_version=config_version(cfg),
        meta={
            "channel": channel,
            "candidate_count": len(candidates),
            "selected_count": len(items),
            "vendors": vendors or [],
            "pool_distribution": {
                slot: sum(1 for it in items if it.slot == slot)
                for slot in ("official", "trend", "discovery", "fill", "official_new")
            },
        },
    )
    await finalize_digest_content(result, cfg)
    return result


async def select_official_new_from_scan_ids(
    session: AsyncSession,
    skill_ids: list[int],
    *,
    top_n: int | None = None,
    cfg: dict[str, Any] | None = None,
) -> DigestResult:
    """官方门户扫描完成后，基于本轮新增 skill id 生成推送内容。"""
    cfg = cfg or load_digest_config()
    ref = datetime.utcnow().date()
    top_n = top_n or int(
        ((cfg.get("push") or {}).get("official_new") or {}).get("top_n") or 10
    )
    candidates = await build_candidates_from_skill_ids(
        session, skill_ids, cfg, ref_date=ref
    )
    picks = select_official_new_picks(
        candidates, cfg, top_n=top_n, ref_date=ref,
        skip_recency_filter=True, skip_official_filter=True,
    )
    items = _build_items(picks)
    result = DigestResult(
        digest_date=ref,
        top_n=top_n,
        items=items,
        config_version=config_version(cfg),
        meta={
            "channel": "official_new",
            "candidate_count": len(candidates),
            "selected_count": len(items),
            "source": "official_portal_scan",
            "skill_ids": skill_ids,
        },
    )
    await finalize_digest_content(result, cfg)
    return result


async def save_digest_run(
    session: AsyncSession,
    result: DigestResult,
    *,
    push_status: str = "pending",
) -> DigestPickRun:
    run = DigestPickRun(
        digest_date=result.digest_date,
        top_n=result.top_n,
        picks=[item.to_dict() for item in result.items],
        content_md=result.content_md,
        config_version=result.config_version,
        selection_meta=result.meta,
        push_status=push_status,
    )
    session.add(run)
    await session.flush()
    return run


async def get_latest_digest_run(
    session: AsyncSession,
    digest_date: date,
) -> DigestPickRun | None:
    return await session.scalar(
        select(DigestPickRun)
        .where(DigestPickRun.digest_date == digest_date)
        .order_by(desc(DigestPickRun.created_at))
        .limit(1)
    )
