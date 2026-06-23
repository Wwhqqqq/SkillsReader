"""
调试与诊断 API —— Adapter 探针、指纹计算、排行榜诊断、LLM 测试。

路由前缀: /api/debug
前端对应 /debug 页面。
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import get_adapter
from app.core.database import get_db
from app.models import Skill, Source
from app.schemas import AdapterProbeRequest, AdapterProbeResponse
from app.services.enrichment.llm_enricher import enrich_skill
from app.services.scan.normalizer import compute_fingerprint
from app.services.scan.scanner import scan_source
from sqlalchemy import update

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.post("/adapter-probe", response_model=AdapterProbeResponse)
async def adapter_probe(body: AdapterProbeRequest, session: AsyncSession = Depends(get_db)):
    """
    测试某个 source 的 Adapter 能否正常 fetch。
    不写入库，只返回条数和前 5 条 sample。
    """
    source = await session.get(Source, body.source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    start = time.time()
    try:
        adapter = get_adapter(source.adapter)
        records = await adapter.fetch()
        duration = int((time.time() - start) * 1000)
        sample = [
            {
                "name": r.name,
                "vendor": r.vendor,
                "description": r.raw_description[:100] if r.raw_description else "",
                "detail_url": r.detail_url,
            }
            for r in records[:5]
        ]
        return AdapterProbeResponse(
            source_id=body.source_id,
            success=True,
            count=len(records),
            duration_ms=duration,
            sample=sample,
        )
    except Exception as exc:
        duration = int((time.time() - start) * 1000)
        return AdapterProbeResponse(
            source_id=body.source_id,
            success=False,
            count=0,
            duration_ms=duration,
            sample=[],
            error=str(exc),
        )


@router.get("/fingerprint")
async def calc_fingerprint(vendor: str, source_id: str, external_id: str, name: str):
    """调试 fingerprint 计算，URL 查询参数传四个字段。"""
    return {
        "fingerprint": compute_fingerprint(vendor, source_id, external_id, name),
    }


@router.get("/digest-diagnosis")
async def digest_diagnosis(session: AsyncSession = Depends(get_db)):
    """输出精选候选池与各 Skill 得分，排查「为何没入选」。"""
    from app.services.digest.engine import select_daily_picks

    result = await select_daily_picks(session)
    return {
        "meta": result.meta,
        "selected_count": len(result.items),
        "config_version": result.config_version,
        "selected": [
            {
                "rank": item.rank,
                "slot": item.slot,
                "name": item.skill.name,
                "vendor": item.skill.vendor,
                "score": item.score,
                "score_breakdown": item.score_breakdown,
                "growth": item.growth,
                "recommend_reason": item.recommend_reason,
            }
            for item in result.items
        ],
    }


@router.post("/llm-enrich/{skill_id}")
async def debug_llm_enrich(skill_id: int, session: AsyncSession = Depends(get_db)):
    """对指定 Skill 手动触发 LLM enrichment。"""
    summary = await enrich_skill(session, skill_id)
    return {"skill_id": skill_id, "summary": summary}


@router.post("/resync-source/{source_id}")
async def resync_source(source_id: str, session: AsyncSession = Depends(get_db)):
    """
    归档旧数据并重新扫描指定源（用于修正脏数据）。

    update(Skill).where(...).values(status="archived"): 批量 UPDATE
    """
    source = await session.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    await session.execute(
        update(Skill)
        .where(Skill.source_id == source_id)
        .values(status="archived")
    )
    scan_result = await scan_source(session, source)
    run = scan_result.run
    await session.flush()
    return {
        "source_id": source_id,
        "archived_previous": True,
        "scan_status": run.status,
        "items_fetched": run.items_fetched,
        "items_new": run.items_new,
    }
