"""
采集源配置同步 —— 把 config/sources.yaml 同步到 MySQL sources 表。

为何 YAML + DB 双份:
    YAML 是「声明式配置」，方便 Git 管理、改 adapter 名
    DB 存「运行态」：last_run_at、enabled 开关（前端可改）、last_error

调用时机:
    - API 启动 lifespan
    - Worker 每轮扫描前
    - init_db
"""

from __future__ import annotations

from pathlib import Path

import yaml  # 解析 YAML 配置文件
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source

# parents[4]: scan → services → app → backend → 项目根
CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "sources.yaml"


def load_sources_yaml() -> list[dict]:
    """读取 YAML 文件，返回 sources 列表（每个元素是一个 dict）。"""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}  # safe_load 避免执行任意代码
    return data.get("sources", [])


async def sync_sources_from_yaml(session: AsyncSession) -> None:
    """
    逐条 sync：存在则更新部分字段，不存在则 INSERT。

    session.get(Source, source_id):
        按主键查一行，无则 None（比 select 简便）
    item.get("url", ""):
        键不存在时返回 ""，不抛 KeyError
    """
    for item in load_sources_yaml():
        source_id = item["id"]  # yaml 必填字段，无则 KeyError
        existing = await session.get(Source, source_id)

        if existing:
            # 已存在：更新元数据（不覆盖 enabled / last_run_at 等运行态）
            existing.vendor = item["vendor"]
            existing.name = item["name"]
            existing.url = item.get("url", "")
            existing.category = item.get("category", "")
            existing.adapter = item["adapter"]
            existing.priority = item.get("priority", 5)
            existing.supplemental = item.get("supplemental", False)
            # 仅当 DB 里仍是默认 300 秒且 yaml 有值时才改 interval（保护前端手动修改）
            if existing.interval_sec == 300 and item.get("interval_sec"):
                existing.interval_sec = item["interval_sec"]
        else:
            session.add(
                Source(
                    id=source_id,
                    vendor=item["vendor"],
                    name=item["name"],
                    url=item.get("url", ""),
                    category=item.get("category", ""),
                    enabled=item.get("enabled", True),
                    interval_sec=item.get("interval_sec", 300),
                    adapter=item["adapter"],
                    priority=item.get("priority", 5),
                    supplemental=item.get("supplemental", False),
                )
            )
    await session.flush()
