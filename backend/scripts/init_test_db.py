#!/usr/bin/env python3
"""初始化测试平台独立数据库 iknow_test。"""

from __future__ import annotations

import asyncio

from app.core.test_database import init_test_db, test_session_factory
from app.services.testbench.service import ensure_sim_platforms


async def main() -> None:
    await init_test_db()
    async with test_session_factory() as session:
        platforms = await ensure_sim_platforms(session)
        await session.commit()
    print(f"Test database initialized with {len(platforms)} simulation platforms.")


if __name__ == "__main__":
    asyncio.run(main())
