"""
数据库初始化脚本 —— 建表 + 同步 sources.yaml。

使用方式:
    cd backend && .venv/bin/python -m app.init_db

setup_local.sh 也会调用此脚本。
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text  # 本文件未直接用 text，保留供 raw SQL 扩展

from app.core.database import Base, engine
from app.core.database import async_session_factory
from app.services.scan.source_sync import sync_sources_from_yaml


async def init_db(*, dispose: bool = False) -> None:
    """
    初始化数据库。

    dispose=True 时关闭 engine（CLI 一次性运行用，避免 hanging 连接）。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_schema(conn)

    async with async_session_factory() as session:
        await sync_sources_from_yaml(session)
        await session.commit()


async def _migrate_schema(conn) -> None:
    """轻量 schema 迁移（create_all 不会 ALTER 已有表）。"""
    stmts = [
        "ALTER TABLE skill_metric_snapshots ADD COLUMN recorded_at DATETIME NULL",
    ]
    for sql in stmts:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass
    try:
        await conn.execute(
            text("ALTER TABLE skill_metric_snapshots DROP INDEX ix_skill_metric_snapshots_skill_date")
        )
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(init_db(dispose=True))
    print("Database initialized.")
