"""
采集源管理 API —— 列表、开关、扫描间隔、全局扫描开关。

路由前缀: /api/sources
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import is_scan_globally_enabled, set_scan_globally_enabled
from app.models import Source
from app.schemas import GlobalScanToggle, SourceOut, SourceUpdate

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
async def list_sources(session: AsyncSession = Depends(get_db)):
    """返回所有采集源及运行状态（last_run_at、last_error 等）。"""
    from sqlalchemy import select

    sources = (await session.scalars(select(Source).order_by(Source.priority))).all()
    return [SourceOut.model_validate(s) for s in sources]


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: str, body: SourceUpdate, session: AsyncSession = Depends(get_db)
):
    """
    PATCH 部分更新：只改 body 里非 None 的字段。

    HTTPException(404): FastAPI 抛 HTTP 错误的标准方式
    """
    source = await session.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    if body.enabled is not None:
        source.enabled = body.enabled
    if body.interval_sec is not None:
        source.interval_sec = body.interval_sec
    await session.flush()
    return SourceOut.model_validate(source)


@router.get("/scan/global", response_model=GlobalScanToggle)
async def get_global_scan():
    """读取 Worker 是否在扫描（Redis 或 .env 默认值）。"""
    return GlobalScanToggle(enabled=await is_scan_globally_enabled())


@router.put("/scan/global", response_model=GlobalScanToggle)
async def set_global_scan(body: GlobalScanToggle):
    """前端总开关：暂停/恢复所有 Worker 扫描。"""
    await set_scan_globally_enabled(body.enabled)
    return body
