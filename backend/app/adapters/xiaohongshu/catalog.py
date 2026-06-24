"""小红书 ClawHub 目录抓取。"""

from __future__ import annotations

import httpx

from app.adapters.base import RawSkillRecord
from app.adapters.common.clawhub_search import fetch_clawhub_for_vendor
from app.adapters.common.platform_filters import is_xhs_relevant

CLAWHUB_SEARCH_QUERIES = (
    "xiaohongshu",
    "小红书",
    "redbook",
    "red skill",
    "xhs-note-gen",
    "xhs note",
    "rednote",
)


async def fetch_clawhub_xiaohongshu(
    client: httpx.AsyncClient,
    *,
    source_id: str,
    vendor: str,
    limit: int = 50,
) -> list[RawSkillRecord]:
    return await fetch_clawhub_for_vendor(
        client,
        vendor=vendor,
        source_id=source_id,
        queries=CLAWHUB_SEARCH_QUERIES,
        limit=limit,
        record_filter=is_xhs_relevant,
    )
