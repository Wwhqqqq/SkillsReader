"""官方 Skill 门户配置 —— 仅各公司官网/API，不含 GitHub 等外部源。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source

CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "official_portals.yaml"


@lru_cache
def load_official_portals_config() -> list[dict[str, Any]]:
    if not CONFIG_PATH.is_file():
        return []
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    portals = data.get("portals") or []
    return [p for p in portals if isinstance(p, dict) and p.get("source_id")]


def official_portal_source_ids() -> tuple[str, ...]:
    return tuple(p["source_id"] for p in load_official_portals_config())


def official_portals_table() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p in load_official_portals_config():
        rows.append(
            {
                "vendor": str(p.get("vendor") or ""),
                "name": str(p.get("name") or ""),
                "url": str(p.get("url") or ""),
                "source_id": str(p.get("source_id") or ""),
            }
        )
    return rows


async def list_official_portal_sources(session: AsyncSession) -> list[Source]:
    """官方一键扫描仅扫 config/official_portals.yaml 中的门户源。"""
    ids = official_portal_source_ids()
    if not ids:
        return []
    rows = await session.scalars(
        select(Source)
        .where(Source.enabled.is_(True))
        .where(Source.id.in_(ids))
        .order_by(Source.priority, Source.id)
    )
    by_id = {s.id: s for s in rows.all()}
    return [by_id[sid] for sid in ids if sid in by_id]
