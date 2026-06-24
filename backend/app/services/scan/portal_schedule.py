"""官方门户扫描调度 —— 间隔可经 API 覆盖（Redis）。"""

from __future__ import annotations

import json
from typing import Any

from app.core.redis_client import get_redis
from app.services.scan.schedule_config import load_worker_schedule

OFFICIAL_PORTAL_SCHEDULE_KEY = "iknow:official_portal_schedule"
_memory_schedule: dict[str, Any] | None = None


def default_interval_sec() -> int:
    cfg = load_worker_schedule()
    return int((cfg.get("official_portal") or {}).get("interval_sec") or 600)


async def get_official_portal_schedule() -> dict[str, Any]:
    global _memory_schedule
    default = {"interval_sec": default_interval_sec()}
    r = await get_redis()
    if r:
        raw = await r.get(OFFICIAL_PORTAL_SCHEDULE_KEY)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    out = {**default, **data}
                    out["interval_sec"] = max(60, int(out.get("interval_sec") or default["interval_sec"]))
                    return out
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return default
    if _memory_schedule:
        out = {**default, **_memory_schedule}
        out["interval_sec"] = max(60, int(out.get("interval_sec") or default["interval_sec"]))
        return out
    return default


async def set_official_portal_schedule(data: dict[str, Any]) -> dict[str, Any]:
    global _memory_schedule
    current = await get_official_portal_schedule()
    merged = {**current}
    if "interval_sec" in data:
        merged["interval_sec"] = max(60, int(data["interval_sec"]))
    r = await get_redis()
    if r:
        await r.set(OFFICIAL_PORTAL_SCHEDULE_KEY, json.dumps(merged, ensure_ascii=False))
    _memory_schedule = merged
    return merged


async def official_interval_sec() -> int:
    sched = await get_official_portal_schedule()
    return int(sched.get("interval_sec") or default_interval_sec())
