"""加载并缓存 `config/digest_pick.yaml` 的工具函数。

提供 `load_digest_config`（有缓存）、`reload_digest_config`（清缓存后重新加载）、
`config_version` 与 `domestic_vendors` 等便捷接口，供 digest 各模块使用配置。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from app.core.config import CONFIG_DIR

CONFIG_PATH = CONFIG_DIR / "digest_pick.yaml"


@lru_cache
def load_digest_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def reload_digest_config() -> dict[str, Any]:
    load_digest_config.cache_clear()
    return load_digest_config()


def config_version(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_digest_config()
    return str(cfg.get("version") or "1")


def domestic_vendors(cfg: dict[str, Any] | None = None) -> frozenset[str]:
    # 返回一个不可变集合，表示配置中定义的 "超级公司" 列表，用于官方加权判定
    cfg = cfg or load_digest_config()
    vendors = cfg.get("pools", {}).get("domestic_vendors") or []
    return frozenset(str(v) for v in vendors)
