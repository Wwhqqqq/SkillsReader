"""
Skill 列表 API —— 分页、筛选、搜索。

路由前缀: /api/skills
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote

from app.api.helpers import skill_to_out
from app.core.database import get_db
from app.models import Skill
from app.schemas import SkillListResponse
from app.services.export.skill_export import (
    build_bundle_filename,
    build_export_filename,
    build_vendor_csv_bundle,
    fetch_skills_for_export,
    rows_to_csv,
    rows_to_xlsx,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=SkillListResponse)
async def list_skills(
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),              # 页码从 1 开始
    page_size: int = Query(20, ge=1, le=100),
    vendor: str | None = None,               # 按厂商过滤
    source_id: str | None = None,
    q: str | None = None,                    # 名称模糊搜索
    today_only: bool = False,                # 仅今日 first_seen_at
):
    query = select(Skill).where(Skill.status == "active")
    if vendor:
        query = query.where(Skill.vendor == vendor)
    if source_id:
        query = query.where(Skill.source_id == source_id)
    if q:
        query = query.where(Skill.name.contains(q))  # SQL LIKE %q%
    if today_only:
        today_start = datetime.combine(datetime.now().date(), datetime.min.time())
        query = query.where(Skill.first_seen_at >= today_start)

    # 子查询计数总数（分页用）
    count_q = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_q) or 0

    items = (
        await session.scalars(
            query.order_by(Skill.first_seen_at.desc())
            .offset((page - 1) * page_size)  # SQL OFFSET
            .limit(page_size)
        )
    ).all()
    return SkillListResponse(
        items=[skill_to_out(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_skills(
    session: AsyncSession = Depends(get_db),
    fmt: str = Query("csv", alias="format", pattern="^(csv|xlsx)$"),
    vendor: str | None = None,
    today_only: bool = False,
    recent_only: bool = False,
    last_official_scan: bool = False,
):
    """Download skills; last_official_scan=skills new in latest official batch scan."""
    skills = await fetch_skills_for_export(
        session,
        vendor=vendor,
        today_only=today_only,
        recent_only=recent_only,
        last_official_scan=last_official_scan,
    )
    if not skills:
        return Response(content="no exportable skills".encode(), media_type="text/plain", status_code=404)
    filename = build_export_filename(
        fmt=fmt,
        vendor=vendor,
        today_only=today_only,
        recent_only=recent_only,
        last_official_scan=last_official_scan,
    )
    ascii_name = filename.encode("ascii", "ignore").decode() or "skills.csv"
    if not ascii_name.endswith((".csv", ".xlsx")):
        ascii_name += ".csv" if fmt == "csv" else ".xlsx"

    if fmt == "xlsx":
        content = rows_to_xlsx(skills)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = rows_to_csv(skills)
        media_type = "text/csv; charset=utf-8"

    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


@router.get("/export/bundle")
async def export_skills_bundle(
    session: AsyncSession = Depends(get_db),
    today_only: bool = False,
    recent_only: bool = False,
    scope: str = Query("domestic", pattern="^(domestic|all)$"),
):
    """Download a ZIP containing one CSV per vendor (domestic vendors by default)."""
    content, vendors = await build_vendor_csv_bundle(
        session,
        today_only=today_only,
        recent_only=recent_only,
        scope=scope,
    )
    if not vendors:
        return Response(content=b"", media_type="text/plain", status_code=404)

    filename = build_bundle_filename(
        today_only=today_only,
        scope=scope,
        recent_only=recent_only,
    )
    ascii_name = filename.encode("ascii", "ignore").decode() or "skills_bundle.zip"
    if not ascii_name.endswith(".zip"):
        ascii_name = "skills_bundle.zip"

    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )
