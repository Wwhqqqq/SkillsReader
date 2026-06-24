"""
Redis 客户端与 Pub/Sub —— 扫描事件实时推送 + 全局扫描开关。

设计要点:
    - Redis 不可用时自动降级到内存（MemoryPubSub + 模块级变量）
    - 本地开发没装 Redis 也能跑，但 /live WebSocket 仅本进程内有效

频道与键:
    SCAN_EVENTS_CHANNEL     — 扫描事件广播，WebSocket 订阅
    SCAN_GLOBAL_KEY         — "1"/"0" 表示全局扫描开/关
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis  # redis 库的异步接口

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 模块级单例状态（进程内共享）
_redis: aioredis.Redis | None = None       # Redis 连接实例
_redis_ok: bool | None = None              # None=未试, True=可用, False=不可用
_memory_scan_enabled: bool | None = None   # 无 Redis 时的扫描开关内存值
_memory_subscribers: list = []             # 无 Redis 时的订阅者队列列表

SCAN_EVENTS_CHANNEL = "iknow:scan_events"
SCAN_GLOBAL_KEY = "iknow:scan_global_enabled"
AUTO_PUSH_MODE_KEY = "iknow:auto_push_mode"
DIGEST_SCHEDULE_KEY = "iknow:digest_schedule"
DIGEST_PUSH_MARKER_PREFIX = "iknow:digest_pushed:"
OFFICIAL_SCAN_KEY = "iknow:official_scan:last"
WORKER_LAST_OFFICIAL_KEY = "iknow:worker:last_official_portal"
WORKER_LAST_FULL_KEY = "iknow:worker:last_full_scan"


async def get_redis() -> aioredis.Redis | None:
    """
    懒加载 Redis 连接。
    首次 ping 失败则标记 _redis_ok=False，之后直接返回 None 走内存降级。
    """
    global _redis, _redis_ok
    if _redis_ok is False:
        return None
    if _redis is None:
        try:
            _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
            # decode_responses=True: 返回 str 而非 bytes
            await _redis.ping()
            _redis_ok = True
        except Exception as exc:
            logger.warning("Redis unavailable, using in-memory fallback: %s", exc)
            _redis_ok = False
            _redis = None
            return None
    return _redis


async def close_redis() -> None:
    """应用/Worker 退出时关闭连接。"""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def publish_scan_event(event: dict[str, Any]) -> None:
    """
    发布扫描事件。
    Worker/API 在 emit_event 里调用 → 前端 WebSocket 收到。
    """
    payload = json.dumps(event, ensure_ascii=False, default=str)
    r = await get_redis()
    if r:
        await r.publish(SCAN_EVENTS_CHANNEL, payload)
    else:
        # 内存降级：逐个放入订阅者的 asyncio.Queue
        for sub in _memory_subscribers:
            await sub.put(payload)


async def is_scan_globally_enabled() -> bool:
    """Worker 每轮开头调用，判断是否允许扫描。"""
    global _memory_scan_enabled
    r = await get_redis()
    if r:
        val = await r.get(SCAN_GLOBAL_KEY)
        if val is None:
            return get_settings().scan_global_enabled  # Redis 无键则用 .env 默认
        return val == "1"
    if _memory_scan_enabled is not None:
        return _memory_scan_enabled
    return get_settings().scan_global_enabled


async def set_scan_globally_enabled(enabled: bool) -> None:
    """API /api/sources/scan/global 调用，前端切换全局扫描开关。"""
    global _memory_scan_enabled
    r = await get_redis()
    if r:
        await r.set(SCAN_GLOBAL_KEY, "1" if enabled else "0")
    else:
        _memory_scan_enabled = enabled


_memory_auto_push_mode: str | None = None


async def get_auto_push_mode() -> str:
    """off | dm | group — 新 Skill 自动推送模式。"""
    global _memory_auto_push_mode
    r = await get_redis()
    if r:
        val = await r.get(AUTO_PUSH_MODE_KEY)
        if val in ("off", "dm", "group"):
            return val
        return get_settings().auto_push_mode
    if _memory_auto_push_mode in ("off", "dm", "group"):
        return _memory_auto_push_mode
    default = get_settings().auto_push_mode
    return default if default in ("off", "dm", "group") else "dm"


async def set_auto_push_mode(mode: str) -> None:
    global _memory_auto_push_mode
    if mode not in ("off", "dm", "group"):
        raise ValueError("mode must be off, dm, or group")
    r = await get_redis()
    if r:
        await r.set(AUTO_PUSH_MODE_KEY, mode)
    _memory_auto_push_mode = mode


_memory_digest_schedule: dict[str, Any] | None = None
_memory_digest_pushed: set[str] = set()
_memory_official_scan: dict[str, Any] | None = None
_memory_worker_last_run: dict[str, float] = {}


async def get_worker_last_run(key: str) -> float | None:
    """上次调度任务完成时间（Unix timestamp）。"""
    global _memory_worker_last_run
    r = await get_redis()
    if r:
        raw = await r.get(key)
        if raw is not None:
            try:
                return float(raw)
            except ValueError:
                pass
        return None
    return _memory_worker_last_run.get(key)


async def set_worker_last_run(key: str, ts: float) -> None:
    global _memory_worker_last_run
    r = await get_redis()
    if r:
        await r.set(key, str(ts))
    _memory_worker_last_run[key] = ts


async def get_official_scan_state() -> dict[str, Any]:
    """最近一次官方一键扫描的状态与新增 Skill ID 列表。"""
    global _memory_official_scan
    default: dict[str, Any] = {
        "status": "idle",
        "started_at": None,
        "finished_at": None,
        "sources_total": 0,
        "sources_ok": 0,
        "sources_error": 0,
        "new_count": 0,
        "new_official_count": 0,
        "new_skill_ids": [],
        "new_official_skill_ids": [],
        "vendor_new_counts": {},
        "push_status": None,
        "error_message": None,
        "last_new_official_at": None,
    }
    r = await get_redis()
    if r:
        raw = await r.get(OFFICIAL_SCAN_KEY)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return {**default, **data}
            except json.JSONDecodeError:
                pass
        return default
    if _memory_official_scan:
        return {**default, **_memory_official_scan}
    return default


async def set_official_scan_state(data: dict[str, Any]) -> dict[str, Any]:
    global _memory_official_scan
    current = await get_official_scan_state()
    merged = {**current, **data}
    r = await get_redis()
    if r:
        await r.set(OFFICIAL_SCAN_KEY, json.dumps(merged, ensure_ascii=False, default=str))
    _memory_official_scan = merged
    return merged


class MemoryPubSub:
    """
    无 Redis 时的最小 Pub/Sub 实现。
    接口与 redis.client.PubSub 类似，供 api/scan.py WebSocket 统一调用。
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        _memory_subscribers.append(self._queue)

    async def subscribe(self, channel: str) -> None:
        pass  # 内存模式不需要真正订阅

    async def unsubscribe(self, channel: str) -> None:
        if self._queue in _memory_subscribers:
            _memory_subscribers.remove(self._queue)

    async def get_message(self, **kwargs) -> dict | None:
        timeout = kwargs.get("timeout", 1.0)
        try:
            data = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return {"type": "message", "data": data}
        except asyncio.TimeoutError:
            return None  # 超时无消息，WebSocket 循环继续

    async def aclose(self) -> None:
        await self.unsubscribe(SCAN_EVENTS_CHANNEL)


async def get_digest_schedule() -> dict[str, Any]:
    """每日精选推送调度配置（Redis 可覆盖 YAML 默认）。"""
    global _memory_digest_schedule
    from app.services.digest.config_loader import load_digest_config

    cfg = load_digest_config()
    default = {
        "enabled": True,
        "times": list((cfg.get("schedule") or {}).get("times") or ["09:00", "18:00"]),
        "timezone": (cfg.get("schedule") or {}).get("timezone") or "Asia/Shanghai",
        "target": "dm",
        "top_n": int((cfg.get("selection") or {}).get("default_top_n") or 10),
        "official_new_enabled": bool(
            ((cfg.get("schedule") or {}).get("official_new") or {}).get("enabled", False)
        ),
        "official_new_time": (
            (cfg.get("schedule") or {}).get("official_new") or {}
        ).get("time")
        or "08:30",
        "official_new_top_n": int(
            ((cfg.get("schedule") or {}).get("official_new") or {}).get("top_n") or 10
        ),
    }
    r = await get_redis()
    if r:
        raw = await r.get(DIGEST_SCHEDULE_KEY)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return {**default, **data}
            except json.JSONDecodeError:
                pass
        return default
    if _memory_digest_schedule:
        return {**default, **_memory_digest_schedule}
    return default


async def set_digest_schedule(data: dict[str, Any]) -> dict[str, Any]:
    global _memory_digest_schedule
    current = await get_digest_schedule()
    merged = {**current, **data}
    r = await get_redis()
    if r:
        await r.set(DIGEST_SCHEDULE_KEY, json.dumps(merged, ensure_ascii=False))
    _memory_digest_schedule = merged
    return merged


async def mark_digest_slot_pushed(slot_key: str) -> bool:
    """返回 True 表示首次标记成功，False 表示该 slot 今日已推送。"""
    global _memory_digest_pushed
    r = await get_redis()
    key = f"{DIGEST_PUSH_MARKER_PREFIX}{slot_key}"
    if r:
        ok = await r.set(key, "1", nx=True, ex=86400 * 2)
        return bool(ok)
    if slot_key in _memory_digest_pushed:
        return False
    _memory_digest_pushed.add(slot_key)
    return True


async def create_pubsub():
    """WebSocket 连接时调用，返回 Redis PubSub 或 MemoryPubSub。"""
    r = await get_redis()
    if r:
        return r.pubsub()
    return MemoryPubSub()
