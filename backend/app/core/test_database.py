"""测试平台独立数据库 —— 与生产库同结构、数据隔离。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import Base

settings = get_settings()

test_engine = create_async_engine(
    settings.test_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)

test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_test_db() -> None:
    """建库（若不存在）+ 建表。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = get_settings()
    base_url = settings.test_database_url.rsplit("/", 1)[0]
    db_name = settings.test_database_url.rsplit("/", 1)[-1]

    bootstrap = create_async_engine(base_url, echo=False)
    async with bootstrap.begin() as conn:
        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4"))
    await bootstrap.dispose()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_test_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
