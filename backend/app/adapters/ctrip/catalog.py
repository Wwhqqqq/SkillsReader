"""
携程 Skill 多源目录抓取 —— ClawHub、SkillsMP。
"""

from __future__ import annotations

import logging

import httpx

from app.adapters.base import RawSkillRecord
from app.adapters.common.clawhub import CLAWHUB_SEARCH_URL, record_from_clawhub
from app.adapters.common.platform_filters import is_ctrip_relevant
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor
from app.services.enrichment.vendor_relevance import filter_records_by_vendor_relevance

logger = logging.getLogger(__name__)

CLAWHUB_SEARCH_QUERIES = (
    "ctrip",
    "携程",
    "wendao",
    "wendao-skill",
    "tripgenie",
    "tcom-tripgenie",
    "ctrip-flight",
    "ctrip-hotel",
    "ctrip-hot-trend",
    "trip-coupon",
)

# ClawHub UI 对 ctrip 检索不稳定，API 可命中；额外按 slug 拉取官方包
CLAWHUB_DIRECT_SLUGS = (
    "wendao-skill",
    "tcom-tripgenie-skill",
    "wendao-partner-qclaw-skill",
    "ctrip-skill",
    "ctrip-flights",
    "ctrip-hotel-search",
    "ctrip-hot-trend",
    "ctrip-compare",
    "ctrip-points",
    "flight-monitor",
)


async def fetch_clawhub_ctrip(
    client: httpx.AsyncClient,
    *,
    source_id: str,
    vendor: str,
    limit: int = 50,
) -> list[RawSkillRecord]:
    records: list[RawSkillRecord] = []
    seen: set[str] = set()

    async def _ingest_item(item: dict) -> None:
        slug = str(item.get("slug") or "")
        if not slug or slug in seen:
            return
        seen.add(slug)
        rec = record_from_clawhub(item, source_id=source_id, vendor=vendor)
        meta = dict(rec.metadata or {})
        meta["categoryName"] = "ClawHub"
        rec.metadata = meta
        rec.tags = [vendor, "ClawHub", "社区"]
        if is_ctrip_relevant(rec):
            records.append(rec)

    for query in CLAWHUB_SEARCH_QUERIES:
        try:
            resp = await client.get(
                CLAWHUB_SEARCH_URL,
                params={"q": query, "limit": limit, "nonSuspiciousOnly": "true"},
                headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
                timeout=60.0,
            )
            if resp.status_code != 200:
                logger.warning("ClawHub ctrip search failed q=%s status=%s", query, resp.status_code)
                continue
            for item in resp.json().get("results") or []:
                await _ingest_item(item)
        except Exception as exc:
            logger.warning("ClawHub ctrip search error q=%s: %s", query, exc)

    for slug in CLAWHUB_DIRECT_SLUGS:
        if slug in seen:
            continue
        try:
            resp = await client.get(
                f"https://clawhub.ai/api/v1/skills/{slug}",
                headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
                timeout=30.0,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            item = data.get("skill") or data
            if isinstance(item, dict):
                item.setdefault("slug", slug)
                await _ingest_item(item)
        except Exception:
            continue

    return await filter_records_by_vendor_relevance(vendor, records)


async def fetch_skillsmp_ctrip(
    client: httpx.AsyncClient,
    *,
    source_id: str,
    vendor: str,
    max_pages: int = 4,
    limit: int = 50,
) -> list[RawSkillRecord]:
    return await fetch_skillsmp_for_vendor(
        client,
        vendor=vendor,
        source_id=source_id,
        max_pages=max_pages,
        limit=limit,
        record_filter=is_ctrip_relevant,
    )
