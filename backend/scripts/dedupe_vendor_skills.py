#!/usr/bin/env python3
"""Archive duplicate active skills grouped by canonical dedup key."""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.adapters.common.record_dedup import canonical_key_for_skill, dedupe_vendor_records
from app.adapters.base import RawSkillRecord
from app.core.database import async_session_factory
from app.models import Skill


def _priority(skill: Skill) -> tuple[int, int, int]:
    meta = skill.metadata_json or {}
    catalog = str(meta.get("catalog") or "")
    pri = {"official": 100, "official_github": 90, "github": 70, "clawhub": 60, "skillsmp": 50}.get(
        catalog, 40
    )
    if meta.get("official"):
        pri = max(pri, 95)
    return (pri, skill.install_count or 0, len(skill.raw_description or ""))


async def archive_duplicates(*, vendor: str | None, source_id: str | None) -> int:
    async with async_session_factory() as session:
        query = select(Skill).where(Skill.status == "active")
        if vendor:
            query = query.where(Skill.vendor == vendor)
        if source_id:
            query = query.where(Skill.source_id == source_id)
        skills = (await session.scalars(query)).all()

        groups: dict[str, list[Skill]] = {}
        for skill in skills:
            key = canonical_key_for_skill(skill)
            if not key:
                continue
            groups.setdefault(key, []).append(skill)

        archived = 0
        for group in groups.values():
            if len(group) <= 1:
                continue
            group.sort(key=_priority, reverse=True)
            keeper = group[0]
            for dup in group[1:]:
                dup.status = "archived"
                meta = dict(dup.metadata_json or {})
                meta["archivedReason"] = "canonical_dedup"
                meta["dedupKeptFingerprint"] = keeper.fingerprint
                dup.metadata_json = meta
                archived += 1

        await session.commit()
        return archived


async def main() -> None:
    parser = argparse.ArgumentParser(description="Archive duplicate vendor skills")
    parser.add_argument("--vendor", help="e.g. 快手")
    parser.add_argument("--source-id", help="e.g. kuaishou_skills")
    args = parser.parse_args()

    n = await archive_duplicates(vendor=args.vendor, source_id=args.source_id)
    print(f"archived {n} duplicate skills")


if __name__ == "__main__":
    asyncio.run(main())
