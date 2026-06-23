"""
扫描相关 API —— 手动触发、历史事件、WebSocket 实时推送。

路由前缀: /api（router.prefix）

前端 /live 页:
    WebSocket 连接 ws://host/api/ws/scan-events
    先收最近 50 条历史，再收 Redis 实时事件
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db
from app.core.redis_client import SCAN_EVENTS_CHANNEL, create_pubsub, get_official_scan_state
from app.models import ScanEvent, Source
from app.schemas import OfficialPortalOut, OfficialScanStatusOut, ScanEventOut, ScanTriggerRequest
from app.services.scan.official_portals import official_portals_table
from app.services.scan.official_scan import run_official_scan_batch
from app.services.scan.scanner import scan_source

router = APIRouter(prefix="/api", tags=["scan"])


@router.post("/scan/trigger")
async def trigger_scan(body: ScanTriggerRequest):
    """
    手动触发扫描（前端「立即扫描」按钮）。

    不 await 扫描完成，而是用 asyncio.create_task 放后台跑，
    立即返回 {"status": "triggered"}，避免 HTTP 超时。
    """
    async def _run():
        async with async_session_factory() as session:
            try:
                q = select(Source).where(Source.enabled.is_(True))
                if body.source_ids:
                    q = q.where(Source.id.in_(body.source_ids))  # IN 查询
                if body.vendors:
                    q = q.where(Source.vendor.in_(body.vendors))
                sources = list((await session.scalars(q)).all())
                for source in sources:
                    await scan_source(session, source)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    asyncio.create_task(_run())
    return {"status": "triggered", "message": "Scan started in background"}


@router.get("/scan/official/status", response_model=OfficialScanStatusOut)
async def official_scan_status():
    """最近一次官方门户扫描的状态。"""
    state = await get_official_scan_state()
    return OfficialScanStatusOut.model_validate(state)


@router.get("/scan/official/portals", response_model=list[OfficialPortalOut])
async def official_scan_portals():
    """各公司官方 Skill 门户链接（仅官网，不含 GitHub/SkillsMP）。"""
    return [OfficialPortalOut.model_validate(row) for row in official_portals_table()]


@router.post("/scan/official")
async def trigger_official_scan():
    """一键扫描各公司官方门户（仅官网/API），比对入库、推送官方新增。"""
    state = await get_official_scan_state()
    if state.get("status") == "running":
        return {"status": "running", "message": "官方扫描进行中，请稍候"}

    async def _run():
        async with async_session_factory() as session:
            try:
                await run_official_scan_batch(session)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    asyncio.create_task(_run())
    return {"status": "triggered", "message": "Official scan started in background"}


@router.get("/scan/events", response_model=list[ScanEventOut])
async def list_events(
    session: AsyncSession = Depends(get_db),  # FastAPI 依赖注入 DB session
    limit: int = Query(100, ge=1, le=500),    # 查询参数，限制 1-500
    source_id: str | None = None,
    level: str | None = None,
):
    """GET 历史扫描事件，供 /live 页初始加载或分页。"""
    q = select(ScanEvent).order_by(ScanEvent.created_at.desc()).limit(limit)
    if source_id:
        q = q.where(ScanEvent.source_id == source_id)
    if level:
        q = q.where(ScanEvent.level == level)
    events = (await session.scalars(q)).all()
    # model_validate: Pydantic v2 从 ORM 对象转 Schema
    return [ScanEventOut.model_validate(e) for e in events]


@router.websocket("/ws/scan-events")
async def ws_scan_events(websocket: WebSocket):
    """
    WebSocket 实时事件流。

    WebSocket 与 HTTP 不同：长连接，服务端可主动 push 消息。
    """
    await websocket.accept()  # 完成握手
    pubsub = await create_pubsub()
    await pubsub.subscribe(SCAN_EVENTS_CHANNEL)
    try:
        # 连接后先推送最近 50 条（reversed 按时间正序）
        async with async_session_factory() as session:
            recent = (
                await session.scalars(
                    select(ScanEvent).order_by(ScanEvent.created_at.desc()).limit(50)
                )
            ).all()
            for ev in reversed(recent):
                await websocket.send_text(
                    json.dumps(
                        {
                            "id": ev.id,
                            "source_id": ev.source_id,
                            "level": ev.level,
                            "event_type": ev.event_type,
                            "message": ev.message,
                            "payload": ev.payload,
                            "created_at": ev.created_at.isoformat() if ev.created_at else None,
                        },
                        ensure_ascii=False,  # 中文不转 \uXXXX
                    )
                )

        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                await websocket.send_text(msg["data"])
            await asyncio.sleep(0.1)  # 避免 tight loop 占 CPU
    except WebSocketDisconnect:
        pass  # 客户端关闭连接，正常退出
    finally:
        await pubsub.unsubscribe(SCAN_EVENTS_CHANNEL)
        await pubsub.aclose()
