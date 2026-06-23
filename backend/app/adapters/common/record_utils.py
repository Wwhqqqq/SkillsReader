"""Adapter 侧 record 追加工具。"""

from __future__ import annotations

from collections.abc import Callable

from app.adapters.base import RawSkillRecord
from app.services.enrichment.vendor_relevance import PROMPT_VERSION


def preapprove_platform_record(rec: RawSkillRecord) -> RawSkillRecord:
    """platform_filters 已通过时跳过 vendor relevance LLM 二次审核。"""
    meta = rec.metadata or {}
    if meta.get("official") or (meta.get("vendorRelevance") or {}).get("relevant"):
        return rec
    meta = dict(meta)
    meta["vendorRelevance"] = {
        "relevant": True,
        "prompt_version": PROMPT_VERSION,
        "source": "platform_filter",
    }
    return RawSkillRecord(
        external_id=rec.external_id,
        name=rec.name,
        vendor=rec.vendor,
        source_id=rec.source_id,
        raw_description=rec.raw_description,
        detail_url=rec.detail_url,
        tags=rec.tags,
        install_count=rec.install_count,
        publish_date=rec.publish_date,
        metadata=meta,
    )


def add_platform_record(
    records: list[RawSkillRecord],
    seen: set[str],
    rec: RawSkillRecord,
    is_relevant: Callable[[RawSkillRecord], bool],
) -> None:
    if not is_relevant(rec):
        return
    if rec.external_id in seen:
        return
    rec = preapprove_platform_record(rec)
    seen.add(rec.external_id)
    records.append(rec)
