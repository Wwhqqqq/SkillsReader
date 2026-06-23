"""
扫描事件服务 —— 写 DB + Redis 广播，驱动前端 /live 实时日志。

数据流:
    emit_event() → scan_events 表 + publish_scan_event()
    → Redis 频道 iknow:scan_events
    → api/scan.py WebSocket 推给浏览器
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import publish_scan_event
from app.models import ScanEvent


async def emit_event(
    session: AsyncSession,
    *,
    event_type: str,
    message: str,
    level: str = "info",
    source_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> ScanEvent:
    """
    记录一条扫描事件。

    参数里带 * 的 keyword-only:
        必须写 emit_event(session, event_type="...", message="...")
        不能写 emit_event(session, "scan_start", "...")  positional

    payload:
        任意 JSON 可序列化 dict，如 {"new": 3, "duration_ms": 1200}
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    event = ScanEvent(
        source_id=source_id,
        level=level,
        event_type=event_type,
        message=message,
        payload=payload or {},
        created_at=now,
    )
    session.add(event)
    await session.flush()  # 拿到 event.id

    # 实时推送（Redis 或内存队列）
    await publish_scan_event(
        {
            "id": event.id,
            "source_id": source_id,
            "level": level,
            "event_type": event_type,
            "message": message,
            "payload": payload or {},
            "created_at": now.isoformat(),  # ISO 8601 字符串，前端易解析
        }
    )
    return event
