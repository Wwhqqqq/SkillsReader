#!/usr/bin/env python3
"""Sync sources from yaml and resync dewu into DB."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select, update

from app.core.database import async_session_factory
from app.models import Skill, Source
from app.services.scan.scanner import scan_source
from app.services.scan.source_sync import sync_sources_from_yaml

SOURCE_ID = "dewu_skills"


async def resync_one(source_id: str) -> dict:
    async with async_session_factory() as session:
        await sync_sources_from_yaml(session)
        await session.commit()

    async with async_session_factory() as session:
        source = await session.get(Source, source_id)
        if not source:
            return {"source_id": source_id, "error": "source not found after sync"}

        archived = await session.execute(
            update(Skill).where(Skill.source_id == source_id).values(status="archived")
        )
        run = await scan_source(session, source)
        await session.commit()

        active = await session.scalar(
            select(func.count())
            .select_from(Skill)
            .where(Skill.source_id == source_id, Skill.status == "active")
        )
        return {
            "source_id": source_id,
            "vendor": source.vendor,
            "archived_rows": archived.rowcount,
            "scan_status": run.status,
            "items_fetched": run.items_fetched,
            "items_new": run.items_new,
            "active_count": active or 0,
            "error": run.error_message,
        }


async def main() -> None:
    print(f"\n=== Resync {SOURCE_ID} ===", flush=True)
    try:
        result = await resync_one(SOURCE_ID)
        print(result, flush=True)
        if result.get("scan_status") != "success":
            sys.exit(1)
    except Exception as exc:
        print(f"FAILED {SOURCE_ID}: {exc}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
