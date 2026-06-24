"""全量扫国内各公司（含 ClawHub/GitHub）并导出近 24h 新发现。"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session_factory
from app.init_db import init_db
from app.models import Source
from app.services.export.skill_export import (
    fetch_skills_for_export,
    rows_to_xlsx,
)
from app.services.scan.scanner import scan_source


async def main() -> None:
    await init_db()
    sources: list[Source] = []
    async with async_session_factory() as session:
        sources = list(
            (
                await session.scalars(
                    select(Source)
                    .where(Source.enabled.is_(True))
                    .where(Source.supplemental.is_(False))
                    .order_by(Source.priority, Source.id)
                )
            ).all()
        )

    print(f"Scanning {len(sources)} domestic sources (full fetch, ClawHub+GitHub)...")
    total_new = 0
    for i, source in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] {source.vendor} / {source.id} ...", flush=True)
        async with async_session_factory() as session:
            src = await session.get(Source, source.id)
            if not src:
                continue
            result = await scan_source(session, src)
            n = len(result.new_skill_ids)
            total_new += n
            await session.commit()
            print(f"  -> {result.run.status}, +{n} new", flush=True)

    async with async_session_factory() as session:
        skills = await fetch_skills_for_export(session, recent_only=True)

    out = ROOT / f"domestic_recent_24h_{datetime.now(ZoneInfo('Asia/Shanghai')).date()}.xlsx"
    out.write_bytes(rows_to_xlsx(skills))

    by_vendor = Counter(s.vendor for s in skills)
    print(f"\nDone. Scan new this run: {total_new}")
    print(f"24h new in DB (exportable): {len(skills)}")
    for v, c in sorted(by_vendor.items(), key=lambda x: -x[1]):
        print(f"  {v}: {c}")
    print(f"Excel: {out}")


if __name__ == "__main__":
    asyncio.run(main())
