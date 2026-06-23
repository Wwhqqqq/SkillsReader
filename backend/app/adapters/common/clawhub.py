"""ClawHub 目录抓取共用工具。"""

from __future__ import annotations

from typing import Any

from app.adapters.base import RawSkillRecord

CLAWHUB_SEARCH_URL = "https://clawhub.ai/api/v1/search"


def record_from_clawhub(item: dict[str, Any], *, source_id: str, vendor: str) -> RawSkillRecord:
    slug = str(item.get("slug") or "").strip()
    name = str(item.get("displayName") or slug or "ClawHub Skill")
    summary = str(item.get("summary") or item.get("description") or "")[:400]
    stats = item.get("stats") or {}
    installs = int(stats.get("installsCurrent") or stats.get("downloads") or 0)
    return RawSkillRecord(
        external_id=f"clawhub:{slug}",
        name=name,
        vendor=vendor,
        source_id=source_id,
        raw_description=summary or f"ClawHub {vendor} Skill · {slug}",
        detail_url=f"https://clawhub.ai/{slug}",
        tags=[vendor, "ClawHub", "社区"],
        install_count=installs,
        metadata={
            "categoryName": "ClawHub",
            "catalog": "clawhub",
            "slug": slug,
            "clawhub": True,
            "stars": stats.get("stars"),
            "downloads": stats.get("downloads"),
        },
    )
