"""
知乎 Skill 多源目录抓取 —— ClawHub、SkillsMP、官方开发者入口。
"""

from __future__ import annotations

import logging

import httpx

from app.adapters.base import RawSkillRecord
from app.adapters.common.clawhub import CLAWHUB_SEARCH_URL, record_from_clawhub
from app.adapters.common.platform_filters import is_zhihu_relevant
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor
from app.services.enrichment.vendor_relevance import filter_records_by_vendor_relevance

logger = logging.getLogger(__name__)

CLAWHUB_SEARCH_QUERIES = ("zhihu", "知乎", "zhihu hot", "zhihu publish")

async def fetch_clawhub_zhihu(
    client: httpx.AsyncClient,
    *,
    source_id: str,
    vendor: str,
    limit: int = 50,
) -> list[RawSkillRecord]:
    records: list[RawSkillRecord] = []
    seen: set[str] = set()
    for query in CLAWHUB_SEARCH_QUERIES:
        try:
            resp = await client.get(
                CLAWHUB_SEARCH_URL,
                params={"q": query, "limit": limit, "nonSuspiciousOnly": "true"},
                headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
                timeout=60.0,
            )
            if resp.status_code != 200:
                logger.warning("ClawHub search failed q=%s status=%s", query, resp.status_code)
                continue
            payload = resp.json()
            for item in payload.get("results") or []:
                slug = str(item.get("slug") or "")
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                rec = record_from_clawhub(item, source_id=source_id, vendor=vendor)
                if is_zhihu_relevant(rec):
                    records.append(rec)
        except Exception as exc:
            logger.warning("ClawHub search error q=%s: %s", query, exc)
    return await filter_records_by_vendor_relevance(vendor, records)


async def fetch_skillsmp_zhihu(
    client: httpx.AsyncClient,
    *,
    source_id: str,
    vendor: str,
    max_pages: int = 5,
    limit: int = 50,
) -> list[RawSkillRecord]:
    return await fetch_skillsmp_for_vendor(
        client,
        vendor=vendor,
        source_id=source_id,
        max_pages=max_pages,
        limit=limit,
        record_filter=is_zhihu_relevant,
    )
