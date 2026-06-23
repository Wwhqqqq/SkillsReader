"""从各 Adapter 的 OFFICIAL_ENTRIES 构建轻量官方门户记录。"""

from __future__ import annotations

from typing import Any

from app.adapters.base import RawSkillRecord

OFFICIAL_PORTAL_CATALOGS = frozenset({"official", "official_api"})


def records_from_official_entries(
    *,
    source_id: str,
    vendor: str,
    entries: list[dict[str, Any]],
    official_ids: frozenset[str] | None = None,
) -> list[RawSkillRecord]:
    """仅收录官方门户说明/API 锚点，跳过 community/github 链接。"""
    records: list[RawSkillRecord] = []
    for entry in entries:
        eid = str(entry.get("external_id") or "")
        url = str(entry.get("detail_url") or "")
        catalog = str(entry.get("catalog") or "official")
        if url.startswith("https://github.com") or url.startswith("http://github.com"):
            continue
        is_official = (
            eid in (official_ids or frozenset())
            or catalog in OFFICIAL_PORTAL_CATALOGS
            or entry.get("official") is True
        )
        if not is_official:
            continue
        records.append(
            RawSkillRecord(
                external_id=eid,
                name=str(entry.get("name") or eid),
                vendor=vendor,
                source_id=source_id,
                raw_description=str(entry.get("raw_description") or ""),
                detail_url=url,
                tags=list(entry.get("tags") or [vendor, "官方"]),
                metadata={
                    "categoryName": entry.get("category", "官方"),
                    "official": True,
                    "catalog": catalog if catalog in OFFICIAL_PORTAL_CATALOGS else "official",
                },
            )
        )
    return records
