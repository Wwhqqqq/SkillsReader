"""判断入库条目是否为可收录/可推送的真实 Skill（排除文档门户锚点等）。"""

from __future__ import annotations

from app.adapters.base import RawSkillRecord
from app.models import Skill

BILI_PORTAL_URL_PREFIXES = (
    "https://open.bilibili.com",
    "https://openhome.bilibili.com",
)
BILI_PORTAL_EXTERNAL_IDS = frozenset(
    {
        "bilibili-open-platform",
        "bilibili-openhome",
        "bilibili-api-video",
        "bilibili-api-live",
        "bilibili-agent-skills-ecosystem",
    }
)


def _meta(skill_or_rec: Skill | RawSkillRecord) -> dict:
    if isinstance(skill_or_rec, RawSkillRecord):
        return skill_or_rec.metadata or {}
    meta = skill_or_rec.metadata_json
    return meta if isinstance(meta, dict) else {}


def _detail_url(skill_or_rec: Skill | RawSkillRecord) -> str:
    if isinstance(skill_or_rec, RawSkillRecord):
        return str(skill_or_rec.detail_url or "")
    return str(skill_or_rec.detail_url or "")


def _external_id(skill_or_rec: Skill | RawSkillRecord) -> str:
    if isinstance(skill_or_rec, RawSkillRecord):
        return str(skill_or_rec.external_id or "")
    return str(skill_or_rec.external_id or "")


def is_bilibili_portal_anchor(skill_or_rec: Skill | RawSkillRecord) -> bool:
    """B 站开放平台/开平管理中心等文档入口，不是 Agent Skill。"""
    eid = _external_id(skill_or_rec)
    if eid in BILI_PORTAL_EXTERNAL_IDS:
        return True
    url = _detail_url(skill_or_rec).rstrip("/").lower()
    if not url:
        return False
    if any(url.startswith(p.rstrip("/")) for p in BILI_PORTAL_URL_PREFIXES):
        if "skill.md" in url or "github.com" in url or "clawhub" in url or "skillsmp" in url:
            return False
        return True
    meta = _meta(skill_or_rec)
    if meta.get("recordType") == "portal_anchor":
        return True
    return False


def is_real_skill(skill_or_rec: Skill | RawSkillRecord) -> bool:
    if is_bilibili_portal_anchor(skill_or_rec):
        return False
    return True
