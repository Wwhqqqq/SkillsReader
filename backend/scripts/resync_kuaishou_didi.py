#!/usr/bin/env python3
"""Sync sources from yaml and resync kuaishou + didi into DB."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select, update

from app.core.database import async_session_factory
from app.models import Skill, Source
from app.services.scan.scanner import scan_source
from app.services.scan.source_sync import sync_sources_from_yaml


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
    targets = ("kuaishou_skills", "didi_skills")
    results = []
    for sid in targets:
        print(f"\n=== Resync {sid} ===", flush=True)
        try:
            result = await resync_one(sid)
            results.append(result)
            print(result, flush=True)
        except Exception as exc:
            print(f"FAILED {sid}: {exc}", flush=True)
            results.append({"source_id": sid, "error": str(exc)})

    print("\n=== Summary ===", flush=True)
    for r in results:
        print(r, flush=True)

    failed = [r for r in results if r.get("error") and r.get("scan_status") != "success"]
    if any(r.get("scan_status") != "success" for r in results if "scan_status" in r):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
