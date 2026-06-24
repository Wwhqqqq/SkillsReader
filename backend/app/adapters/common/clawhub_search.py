"""ClawHub 关键词搜索 —— 各公司全量扫描共用。"""

from __future__ import annotations

import logging
from collections.abc import Callable

import httpx

from app.adapters.base import RawSkillRecord
from app.adapters.common.clawhub import CLAWHUB_SEARCH_URL, record_from_clawhub
from app.services.enrichment.vendor_relevance import filter_records_by_vendor_relevance

logger = logging.getLogger(__name__)


async def fetch_clawhub_for_vendor(
    client: httpx.AsyncClient,
    *,
    vendor: str,
    source_id: str,
    queries: tuple[str, ...],
    limit: int = 50,
    record_filter: Callable[[RawSkillRecord], bool] | None = None,
) -> list[RawSkillRecord]:
    records: list[RawSkillRecord] = []
    seen: set[str] = set()
    for query in queries:
        try:
            resp = await client.get(
                CLAWHUB_SEARCH_URL,
                params={"q": query, "limit": limit, "nonSuspiciousOnly": "true"},
                headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
                timeout=60.0,
            )
            if resp.status_code != 200:
                logger.warning("ClawHub search failed vendor=%s q=%s status=%s", vendor, query, resp.status_code)
                continue
            for item in resp.json().get("results") or []:
                slug = str(item.get("slug") or "")
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                rec = record_from_clawhub(item, source_id=source_id, vendor=vendor)
                if record_filter and not record_filter(rec):
                    continue
                records.append(rec)
        except Exception as exc:
            logger.warning("ClawHub search error vendor=%s q=%s: %s", vendor, query, exc)
    return await filter_records_by_vendor_relevance(vendor, records)
