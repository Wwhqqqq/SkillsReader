"""Volcengine AgentKit OpenAPI client (ListSharingSkills).

volcenginesdkcore 不是 PyPI 公开包，需要从火山引擎官方安装。
未安装时该模块优雅降级，不影响其他功能。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SERVICE = "agentkit"
API_VERSION = "2025-10-30"
DEFAULT_REGION = "cn-beijing"
HOST = f"{SERVICE}.{DEFAULT_REGION}.volcengineapi.com"

_SignerV4 = None


def _get_signer():
    """延迟加载 volcenginesdkcore。未安装时返回 None。"""
    global _SignerV4
    if _SignerV4 is None:
        try:
            from volcenginesdkcore.signv4 import SignerV4  # type: ignore[import-not-found]
            _SignerV4 = SignerV4
        except ImportError:
            logger.warning(
                "volcenginesdkcore not installed — AgentKit scan disabled. "
                "Install with: pip install volcenginesdkcore"
            )
    return _SignerV4


def _sign_post(*, access_key: str, secret_key: str, query: dict[str, str], body: str, region: str) -> dict[str, str]:
    headers = {"Host": HOST, "Content-Type": "application/json"}
    SignerV4 = _get_signer()
    if SignerV4 is None:
        raise ImportError("volcenginesdkcore is required for AgentKit API")
    SignerV4.sign("/", "POST", headers, body, {}, query, access_key, secret_key, region, SERVICE)
    return headers


async def list_sharing_skills(*, page_size: int = 100, page_number: int = 1) -> list[dict[str, Any]]:
    """Fetch shared/preset skills from AgentKit. Returns [] if creds missing or call fails."""
    settings = get_settings()
    ak = settings.volcengine_access_key.strip()
    sk = settings.volcengine_secret_key.strip()
    if not ak or not sk:
        return []

    region = settings.volcengine_region or DEFAULT_REGION
    all_items: list[dict[str, Any]] = []
    page = page_number

    if _get_signer() is None:
        logger.info("Skipping AgentKit scan — volcenginesdkcore not available")
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                query = {
                    "Action": "ListSharingSkills",
                    "Version": API_VERSION,
                }
                body = json.dumps({"PageSize": page_size, "PageNumber": page}, separators=(",", ":"))
                headers = _sign_post(access_key=ak, secret_key=sk, query=query, body=body, region=region)
                resp = await client.post(f"https://{HOST}/", params=query, content=body, headers=headers)
                if resp.status_code != 200:
                    logger.warning("ListSharingSkills HTTP %s: %s", resp.status_code, resp.text[:500])
                    break
                data = resp.json()
                if data.get("ResponseMetadata", {}).get("Error"):
                    err = data["ResponseMetadata"]["Error"]
                    logger.warning("ListSharingSkills API error: %s", err)
                    break
                result = data.get("Result") or {}
                items = result.get("Items") or []
                if not isinstance(items, list):
                    break
                all_items.extend(items)

                total = int(result.get("TotalCount") or 0)
                if len(all_items) >= total or len(items) < page_size:
                    break
                page += 1
    except Exception as exc:
        logger.warning("ListSharingSkills failed: %s", exc)

    return all_items
