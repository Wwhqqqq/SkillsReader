"""如流推送收件人配置 —— Redis 持久化，支持增量维护名单。"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.core.redis_client import get_redis

PUSH_RECIPIENTS_KEY = "iknow:push_recipients"

_memory_recipients: dict[str, Any] | None = None


def _defaults() -> dict[str, Any]:
    settings = get_settings()
    dm = settings.ruliu_dm_user or "wangheqiao"
    gid = settings.ruliu_group_id or "13038971"
    return {
        "dm_users": [dm],
        "group_ids": [gid],
        "official_new_dm_users": [dm],
    }


async def get_push_recipients() -> dict[str, Any]:
    global _memory_recipients
    default = _defaults()
    r = await get_redis()
    if r:
        raw = await r.get(PUSH_RECIPIENTS_KEY)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    merged = {**default, **data}
                    for key in ("dm_users", "group_ids", "official_new_dm_users"):
                        vals = merged.get(key)
                        if isinstance(vals, list):
                            merged[key] = [str(x).strip() for x in vals if str(x).strip()]
                    return merged
            except json.JSONDecodeError:
                pass
        return default
    if _memory_recipients:
        return {**default, **_memory_recipients}
    return default


async def set_push_recipients(data: dict[str, Any]) -> dict[str, Any]:
    global _memory_recipients
    current = await get_push_recipients()
    merged = {**current}
    for key in ("dm_users", "group_ids", "official_new_dm_users"):
        if key in data and isinstance(data[key], list):
            merged[key] = [str(x).strip() for x in data[key] if str(x).strip()]
    r = await get_redis()
    if r:
        await r.set(PUSH_RECIPIENTS_KEY, json.dumps(merged, ensure_ascii=False))
    _memory_recipients = merged
    return merged


async def add_push_recipient(kind: str, value: str) -> dict[str, Any]:
    value = value.strip()
    if not value:
        raise ValueError("empty value")
    key_map = {
        "dm": "dm_users",
        "group": "group_ids",
        "official_new": "official_new_dm_users",
    }
    field = key_map.get(kind)
    if not field:
        raise ValueError("invalid kind")
    current = await get_push_recipients()
    items = list(current.get(field) or [])
    if value not in items:
        items.append(value)
    return await set_push_recipients({field: items})


async def remove_push_recipient(kind: str, value: str) -> dict[str, Any]:
    value = value.strip()
    key_map = {
        "dm": "dm_users",
        "group": "group_ids",
        "official_new": "official_new_dm_users",
    }
    field = key_map.get(kind)
    if not field:
        raise ValueError("invalid kind")
    current = await get_push_recipients()
    items = [x for x in (current.get(field) or []) if x != value]
    return await set_push_recipients({field: items})


def primary_dm_user(recipients: dict[str, Any] | None = None) -> str:
    rec = recipients or {}
    users = rec.get("dm_users") or _defaults()["dm_users"]
    return users[0] if users else _defaults()["dm_users"][0]


def primary_group_id(recipients: dict[str, Any] | None = None) -> str:
    rec = recipients or {}
    groups = rec.get("group_ids") or _defaults()["group_ids"]
    return groups[0] if groups else _defaults()["group_ids"][0]
