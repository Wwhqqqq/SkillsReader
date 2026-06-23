"""
入库管道 —— 把 Adapter 抓到的 RawSkillRecord 写入 skills 表。

职责:
    1. 跳过空名称
    2. 计算 fingerprint 判断新/旧
    3. 新记录 INSERT，旧记录 UPDATE last_seen_at 等
    4. 返回 IngestResult 供 scanner 统计和触发 LLM
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import RawSkillRecord
from app.models import Skill
from app.adapters.common.record_dedup import (
    canonical_dedup_key,
    canonical_key_for_skill,
    dedupe_vendor_records,
)
from app.services.scan.normalizer import (
    compute_fingerprint,
    compute_quality_score,
    parse_publish_date,
)
from app.services.enrichment.skill_classification import enrich_metadata
from app.services.digest.metrics import record_snapshots_for_skills


class IngestResult:
    """ingest_records 的返回值，汇总本次入库统计。"""

    def __init__(self) -> None:
        self.new_ids: list[int] = []       # 新 Skill 的数据库 id，供 LLM 批量处理
        self.updated_ids: list[int] = []
        self.new_count = 0
        self.updated_count = 0


async def ingest_records(
    session: AsyncSession, records: list[RawSkillRecord]
) -> IngestResult:
    """
    逐条处理抓取结果。

    session.scalar(select(...)):
        执行查询返回单个标量（第一行第一列），无结果则 None
    session.flush():
        把 pending 的 INSERT 发到 DB 拿到自增 id，但未 commit
    """
    result = IngestResult()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = dedupe_vendor_records(records)

    canonical_index: dict[str, Skill] = {}
    if records:
        source_ids = {r.source_id for r in records}
        existing_skills = (
            await session.scalars(
                select(Skill).where(
                    Skill.source_id.in_(source_ids),
                    Skill.status == "active",
                )
            )
        ).all()
        for skill in existing_skills:
            key = canonical_key_for_skill(skill)
            if key and key not in canonical_index:
                canonical_index[key] = skill

    for record in records:
        if not record.name or not record.name.strip():
            continue

        fp = compute_fingerprint(
            record.vendor, record.source_id, record.external_id, record.name
        )
        quality = compute_quality_score(record)
        status = "active" if quality >= 40 else "filtered"  # 低质量可过滤

        metadata = enrich_metadata(
            record.metadata,
            vendor=record.vendor,
            source_id=record.source_id,
            external_id=record.external_id,
        )

        existing = await session.scalar(select(Skill).where(Skill.fingerprint == fp))
        if existing is None:
            canon_key = canonical_dedup_key(record)
            if canon_key:
                existing = canonical_index.get(canon_key)
        if existing:
            # ── 已存在：更新字段，保留 first_seen_at ──
            existing.raw_description = record.raw_description or existing.raw_description
            existing.detail_url = record.detail_url or existing.detail_url
            existing.install_count = max(existing.install_count, record.install_count)
            existing.quality_score = max(existing.quality_score, quality)
            existing.last_seen_at = now
            existing.tags = record.tags or existing.tags
            parsed_pub = parse_publish_date(record.publish_date)
            if parsed_pub:
                existing.publish_date = parsed_pub
            if metadata:
                meta = dict(existing.metadata_json or {})
                meta.update(metadata)  # 合并 metadata，不覆盖旧键
                existing.metadata_json = enrich_metadata(
                    meta,
                    vendor=existing.vendor,
                    source_id=existing.source_id,
                    external_id=existing.external_id,
                )
            if status == "active":
                existing.status = "active"
            canon_key = canonical_dedup_key(record)
            if canon_key:
                canonical_index[canon_key] = existing
            result.updated_ids.append(existing.id)
            result.updated_count += 1
        else:
            # ── 新 Skill：INSERT ──
            skill = Skill(
                fingerprint=fp,
                vendor=record.vendor,
                source_id=record.source_id,
                external_id=record.external_id,
                name=record.name.strip(),
                raw_description=record.raw_description,
                detail_url=record.detail_url,
                tags=record.tags,
                install_count=record.install_count,
                quality_score=quality,
                first_seen_at=now,
                last_seen_at=now,
                publish_date=parse_publish_date(record.publish_date),
                status=status,
                metadata_json=metadata,
            )
            session.add(skill)
            await session.flush()  # 获取 skill.id
            canon_key = canonical_dedup_key(record)
            if canon_key:
                canonical_index[canon_key] = skill
            result.new_ids.append(skill.id)
            result.new_count += 1

    touched_ids = result.new_ids + result.updated_ids
    if touched_ids:
        await record_snapshots_for_skills(session, touched_ids)

    return result
