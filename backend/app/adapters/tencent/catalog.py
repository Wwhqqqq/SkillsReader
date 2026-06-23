"""
腾讯 Skill 多源目录抓取 —— ClawHub、SkillsMP。
"""

from __future__ import annotations

import logging

import httpx

from app.adapters.base import RawSkillRecord
from app.adapters.common.clawhub import CLAWHUB_SEARCH_URL, record_from_clawhub
from app.adapters.common.platform_filters import is_tencent_relevant
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor
from app.services.enrichment.vendor_relevance import filter_records_by_vendor_relevance

logger = logging.getLogger(__name__)

CLAWHUB_SEARCH_QUERIES = (
    "wechat",
    "weixin",
    "微信",
    "tencent",
    "腾讯",
    "wecom",
    "wework",
    "企业微信",
    "hunyuan",
    "混元",
    "miniprogram",
    "小程序",
    "openclaw-weixin",
    "cloudbase",
    "mp-skills",
    "tencent-docs",
    "tencent-meeting",
    "qqmap",
)

CLAWHUB_DIRECT_SLUGS = (
    "wechat",
    "openclaw-weixin",
    "openclaw-wecom-channel",
    "wecom",
    "tencent",
    "tencent-docs",
    "tencent-cos-skill",
    "tencent-meeting-export",
    "hunyuan",
    "hunyuan-image",
    "webhook-robot",
)

SKILLSMP_SEARCH_QUERIES = (
    "wechat",
    "tencent",
    "wecom",
    "wework",
    "微信",
    "腾讯",
    "企业微信",
    "hunyuan",
    "混元",
    "miniprogram",
    "TencentCloudBase",
    "WecomTeam",
    "openclaw-weixin",
    "cloudbase",
)

SKILLSMP_MAX_PAGES = 4
SKILLSMP_PAGE_LIMIT = 50


async def fetch_clawhub_tencent(
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
        if is_tencent_relevant(rec):
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
                logger.warning("ClawHub tencent search failed q=%s status=%s", query, resp.status_code)
                continue
            for item in resp.json().get("results") or []:
                await _ingest_item(item)
        except Exception as exc:
            logger.warning("ClawHub tencent search error q=%s: %s", query, exc)

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


async def fetch_skillsmp_tencent(
    client: httpx.AsyncClient,
    *,
    source_id: str,
    vendor: str,
    max_pages: int = SKILLSMP_MAX_PAGES,
    limit: int = SKILLSMP_PAGE_LIMIT,
) -> list[RawSkillRecord]:
    return await fetch_skillsmp_for_vendor(
        client,
        vendor=vendor,
        source_id=source_id,
        queries=SKILLSMP_SEARCH_QUERIES,
        max_pages=max_pages,
        limit=limit,
        record_filter=is_tencent_relevant,
    )
