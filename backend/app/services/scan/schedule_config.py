"""Worker 调度配置 —— config/worker_schedule.yaml"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from app.core.config import CONFIG_DIR

CONFIG_PATH = CONFIG_DIR / "worker_schedule.yaml"


@lru_cache
def load_worker_schedule() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def official_interval_sec() -> int:
    cfg = load_worker_schedule()
    return int((cfg.get("official_portal") or {}).get("interval_sec") or 600)


def full_scan_interval_sec() -> int:
    cfg = load_worker_schedule()
    return int((cfg.get("full_scan") or {}).get("interval_sec") or 28800)


def per_source_scan_enabled() -> bool:
    cfg = load_worker_schedule()
    return bool(cfg.get("per_source_scan", False))


def startup_delay_sec() -> int:
    cfg = load_worker_schedule()
    return int(cfg.get("startup_delay_sec") or 180)
