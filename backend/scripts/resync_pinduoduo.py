#!/usr/bin/env python3
"""Sync sources from yaml and resync pinduoduo into DB."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select, update

from app.core.database import async_session_factory
from app.models import Skill, Source
from app.services.scan.scanner import scan_source
from app.services.scan.source_sync import sync_sources_from_yaml

SOURCE_ID = "pinduoduo_skills"


async def main() -> None:
    async with async_session_factory() as session:
        await sync_sources_from_yaml(session)
        await session.commit()

    async with async_session_factory() as session:
        source = await session.get(Source, SOURCE_ID)
        if not source:
            print(f"ERROR: {SOURCE_ID} not found after sync")
            sys.exit(1)

        await session.execute(
            update(Skill).where(Skill.source_id == SOURCE_ID).values(status="archived")
        )
        run = await scan_source(session, source)
        await session.commit()

        active = await session.scalar(
            select(func.count())
            .select_from(Skill)
            .where(Skill.source_id == SOURCE_ID, Skill.status == "active")
        )
        result = {
            "source_id": SOURCE_ID,
            "vendor": source.vendor,
            "scan_status": run.status,
            "items_fetched": run.items_fetched,
            "items_new": run.items_new,
            "active_count": active or 0,
            "error": run.error_message,
        }
        print(result)
        if run.status != "success":
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
