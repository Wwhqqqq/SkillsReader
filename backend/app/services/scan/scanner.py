"""
扫描编排服务 —— 执行「单个采集源」的完整一次扫描。

被谁调用:
    - worker/scan_loop.py  （定时自动扫）
    - api/scan.py          （前端手动触发）
    - api/debug.py         （重同步某源）

一次 scan_source 的流程:
    1. 创建 ScanRun 记录（status=running）
    2. 发 scan_start 事件（前端 /live 可见）
    3. get_adapter → adapter.fetch() 抓取
    4. ingest_records() 入库去重
    5. 若有新 Skill → enrich_skills_batch() 调 LLM
    6. 更新 ScanRun / Source 状态，发 scan_done 或 scan_error 事件
"""

from __future__ import annotations

import time  # time.time() 计算耗时毫秒
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession  # 异步数据库会话类型

from app.adapters import get_adapter
from app.adapters.base import RawSkillRecord
from app.models import ScanRun, Skill, Source
from app.services.scan.events import emit_event
from app.services.enrichment.llm_enricher import enrich_skills_batch
from app.services.scan.pipeline import ingest_records


@dataclass
class ScanSourceResult:
    run: ScanRun
    new_skill_ids: list[int]


async def archive_stale_skills(
    session: AsyncSession,
    source_id: str,
    records: list[RawSkillRecord],
) -> int:
    """Archive active skills for this source that no longer appear in the latest fetch."""
    fetched_ids = {rec.external_id for rec in records if rec.external_id}
    if not fetched_ids:
        return 0
    result = await session.execute(
        update(Skill)
        .where(
            Skill.source_id == source_id,
            Skill.status == "active",
            Skill.external_id.notin_(fetched_ids),
        )
        .values(status="archived")
    )
    return int(result.rowcount or 0)


async def scan_source(
    session: AsyncSession,
    source: Source,
    *,
    official_portal_only: bool = False,
) -> ScanSourceResult:
    """
    扫描单个 Source。

    参数:
        session: 数据库会话，调用方负责 commit
        source:  ORM 对象，来自 sources 表的一行

    返回:
        ScanRun 对象（成功或失败都会写入 finished_at 等字段）
    """
    # ① 创建本次扫描运行记录
    run = ScanRun(source_id=source.id, status="running")
    session.add(run)       # 加入 session 待写入
    await session.flush()  # 立即 INSERT 拿到 run.id，但未 commit

    source.last_status = "scanning"
    await emit_event(
        session,
        event_type="scan_start",  # 事件类型，前端可过滤
        message=f"[{source.vendor}] 开始扫描 {source.name}",
        source_id=source.id,
        level="info",  # info | success | error
    )

    new_skill_ids: list[int] = []
    start = time.time()
    try:
        # ② 根据 source.adapter 字段（如 "meituan"）实例化对应 Adapter
        adapter = get_adapter(source.adapter)
        if official_portal_only:
            records = await adapter.fetch_official_portal()
        else:
            records = await adapter.fetch()
        result = await ingest_records(session, records)
        new_skill_ids = list(result.new_ids)
        if not official_portal_only:
            archived_stale = await archive_stale_skills(session, source.id, records)
        else:
            archived_stale = 0
        duration_ms = int((time.time() - start) * 1000)

        # ⑤ 仅对新发现的 Skill 调 LLM（最多 20 条，见 llm_enricher）
        if result.new_ids:
            await enrich_skills_batch(session, result.new_ids)

        # ⑥ 更新 ScanRun 为成功
        run.status = "success"
        run.items_fetched = len(records)       # 抓取条数
        run.items_new = result.new_count       # 新入库条数
        run.items_updated = result.updated_count
        run.duration_ms = duration_ms
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # 更新 Source 运行状态，供 Dashboard 展示
        source.last_run_at = run.finished_at
        source.last_status = "ok"
        source.last_error = None
        source.items_total = (source.items_total or 0) + result.new_count

        await emit_event(
            session,
            event_type="scan_done",
            message=(
                f"[{source.vendor}] +{result.new_count} new · "
                f"↑{result.updated_count} updated · {duration_ms}ms"
            ),
            source_id=source.id,
            level="success",
            payload={  # 结构化数据，前端可做图表
                "new": result.new_count,
                "updated": result.updated_count,
                "fetched": len(records),
                "archived_stale": archived_stale,
                "duration_ms": duration_ms,
            },
        )
    except Exception as exc:
        # 任意环节失败：记录错误但不抛出，让 Worker 继续扫下一个源
        duration_ms = int((time.time() - start) * 1000)
        run.status = "error"
        run.duration_ms = duration_ms
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        source.last_status = "error"
        source.last_error = str(exc)
        await emit_event(
            session,
            event_type="scan_error",
            message=f"[{source.vendor}] 扫描失败: {exc}",
            source_id=source.id,
            level="error",
            payload={"error": str(exc)},
        )

    return ScanSourceResult(run=run, new_skill_ids=new_skill_ids)
