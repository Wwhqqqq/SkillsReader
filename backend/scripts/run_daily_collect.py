#!/usr/bin/env python3
"""全量采集入库 —— 扫描所有 enabled 源，充实候选池（指定快照日）。"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime

from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.init_db import init_db
from app.models import Skill, Source
from app.services.digest.metrics import record_snapshots_for_skills
from app.services.scan.scanner import scan_source
from app.services.scan.source_sync import sync_sources_from_yaml

SNAPSHOT_DATE = date(2026, 6, 23)
SCAN_TIMEOUT_SEC = 240
PARALLEL_SOURCES = 4


async def _scan_one(
    source: Source, snap: date, sem: asyncio.Semaphore, timeout_sec: int
) -> dict:
    async with sem:
        async with async_session_factory() as session:
            src = await session.get(Source, source.id)
            if not src:
                return {"source": source.id, "status": "missing"}
            print(f"扫描 {src.vendor} / {src.id} ...", flush=True)
            try:
                run = await asyncio.wait_for(scan_source(session, src), timeout=timeout_sec)
                if run.status == "success":
                    rows = (
                        await session.scalars(
                            select(Skill.id).where(
                                Skill.source_id == src.id,
                                Skill.status == "active",
                                Skill.last_seen_at >= datetime.combine(snap, datetime.min.time()),
                            )
                        )
                    ).all()
                    if rows:
                        await record_snapshots_for_skills(session, list(rows), snapshot_date=snap)
                await session.commit()
                active = await session.scalar(
                    select(func.count())
                    .select_from(Skill)
                    .where(Skill.source_id == src.id, Skill.status == "active")
                )
                row = {
                    "source": src.id,
                    "vendor": src.vendor,
                    "status": run.status,
                    "fetched": run.items_fetched,
                    "new": run.items_new,
                    "updated": run.items_updated,
                    "active": active,
                }
                print(
                    f"  OK {src.id} fetched={run.items_fetched} new={run.items_new} "
                    f"updated={run.items_updated} active={active}",
                    flush=True,
                )
                return row
            except asyncio.TimeoutError:
                print(f"  TIMEOUT {source.id} after {timeout_sec}s", flush=True)
                return {"source": source.id, "status": "timeout"}
            except Exception as exc:
                print(f"  FAIL {source.id} {exc}", flush=True)
                return {"source": source.id, "status": "error", "error": str(exc)}


async def run_collect(
    *,
    snapshot_date: date | None = None,
    source_ids: list[str] | None = None,
    parallel: int = PARALLEL_SOURCES,
    timeout_sec: int = SCAN_TIMEOUT_SEC,
) -> None:
    snap = snapshot_date or SNAPSHOT_DATE
    await init_db(dispose=False)

    async with async_session_factory() as session:
        await sync_sources_from_yaml(session)
        await session.commit()

    async with async_session_factory() as session:
        q = select(Source).where(Source.enabled.is_(True)).order_by(Source.priority)
        if source_ids:
            q = q.where(Source.id.in_(source_ids))
        sources = list((await session.scalars(q)).all())

    print(
        f"=== 全量采集 {len(sources)} 个源 · 快照日 {snap.isoformat()} · "
        f"并发 {parallel} · 超时 {timeout_sec}s ==="
    )
    sem = asyncio.Semaphore(max(1, parallel))
    summary = await asyncio.gather(
        *[_scan_one(src, snap, sem, timeout_sec) for src in sources]
    )

    async with async_session_factory() as session:
        total_active = await session.scalar(
            select(func.count()).select_from(Skill).where(Skill.status == "active")
        )
        skills_sh = await session.scalar(
            select(func.count())
            .select_from(Skill)
            .where(Skill.source_id == "skills_sh", Skill.status == "active")
        )
        bad_xhs = await session.scalar(
            select(func.count())
            .select_from(Skill)
            .where(
                Skill.source_id == "xiaohongshu_red_skill",
                Skill.status == "active",
                Skill.detail_url.like("%gitcode.csdn.net%"),
            )
        )

    print("\n=== 汇总 ===")
    print(f"active skills: {total_active}")
    print(f"skills_sh active: {skills_sh}")
    print(f"xiaohongshu gitcode mirror urls remaining: {bad_xhs}")
    for row in summary:
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="全量 Skill 采集入库")
    parser.add_argument("snapshot_date", nargs="?", help="快照日 YYYY-MM-DD")
    parser.add_argument(
        "--sources",
        help="逗号分隔 source id，仅扫描指定源（如 wechat_skillhub,zhihu_skills）",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=PARALLEL_SOURCES,
        help=f"并发扫描源数量（默认 {PARALLEL_SOURCES}）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=SCAN_TIMEOUT_SEC,
        help=f"单源扫描超时秒数（默认 {SCAN_TIMEOUT_SEC}）",
    )
    args = parser.parse_args()

    snap = SNAPSHOT_DATE
    if args.snapshot_date:
        snap = date.fromisoformat(args.snapshot_date)
    source_ids = [s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else None
    asyncio.run(
        run_collect(
            snapshot_date=snap,
            source_ids=source_ids,
            parallel=args.parallel,
            timeout_sec=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
