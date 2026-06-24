"""Skill 发布类型与数据来源分类 —— 官方发布 vs 个人创作者。"""

from __future__ import annotations

from typing import Any

from app.models import Skill

PUBLISHER_OFFICIAL = "官方发布"
PUBLISHER_CREATOR = "个人创作者"

OFFICIAL_PORTAL_SOURCES = frozenset({"meituan_ai_hub", "aliyun_skills_portal"})
CREATOR_CATALOGS = frozenset({"skillsmp", "clawhub", "github"})
OFFICIAL_CATALOGS = frozenset({"official", "official_api", "official_github"})


def _is_official_repo_mirror(meta: dict[str, Any], external_id: str) -> bool:
    """SkillsMP/ClawHub 镜像的官方仓库 SKILL.md，应视为官方发布。"""
    from app.adapters.common.official_github_config import all_official_repo_names, is_official_github_repo

    repo = str(meta.get("repo") or "")
    if is_official_github_repo(repo):
        return True
    eid = external_id.lower()
    for official_repo in all_official_repo_names():
        slug = official_repo.lower().replace("/", "-")
        if slug in eid:
            return True
    return False


def _meta_dict(skill_or_meta: Skill | dict[str, Any]) -> dict[str, Any]:
    if isinstance(skill_or_meta, dict):
        return skill_or_meta
    meta = getattr(skill_or_meta, "metadata_json", None)
    return meta if isinstance(meta, dict) else {}


def _source_id(skill_or_meta: Skill | dict[str, Any], meta: dict[str, Any]) -> str:
    if isinstance(skill_or_meta, dict):
        return str(meta.get("source_id") or "")
    return str(getattr(skill_or_meta, "source_id", None) or meta.get("source_id") or "")


def _external_id(skill_or_meta: Skill | dict[str, Any], meta: dict[str, Any]) -> str:
    if isinstance(skill_or_meta, dict):
        return str(meta.get("external_id") or "")
    return str(getattr(skill_or_meta, "external_id", None) or meta.get("external_id") or "")


def publisher_type_for(skill_or_meta: Skill | dict[str, Any]) -> str:
    meta = _meta_dict(skill_or_meta)
    catalog = str(meta.get("catalog") or "")

    if (
        meta.get("official")
        or meta.get("agentkit")
        or catalog in OFFICIAL_CATALOGS
    ):
        return PUBLISHER_OFFICIAL

    external_id = _external_id(skill_or_meta, meta)
    owner = str(meta.get("owner") or "").strip()
    if owner and _is_official_repo_mirror({"repo": owner}, owner):
        return PUBLISHER_OFFICIAL
    if _is_official_repo_mirror(meta, external_id):
        return PUBLISHER_OFFICIAL

    if catalog in CREATOR_CATALOGS:
        return PUBLISHER_CREATOR

    if external_id.startswith(("skillsmp:", "clawhub:", "redskill:")):
        return PUBLISHER_CREATOR

    source_id = _source_id(skill_or_meta, meta)
    if source_id in OFFICIAL_PORTAL_SOURCES and catalog != "skillsmp":
        return PUBLISHER_OFFICIAL

    return PUBLISHER_CREATOR


def is_official_publisher(skill_or_meta: Skill | dict[str, Any]) -> bool:
    return publisher_type_for(skill_or_meta) == PUBLISHER_OFFICIAL


def data_source_for(skill_or_meta: Skill | dict[str, Any]) -> str:
    meta = _meta_dict(skill_or_meta)
    if meta.get("dataSource"):
        return str(meta["dataSource"])

    catalog = str(meta.get("catalog") or "")
    source_id = _source_id(skill_or_meta, meta)
    external_id = _external_id(skill_or_meta, meta)

    if catalog == "skills_sh" or source_id == "skills_sh":
        return "skills.sh"
    if catalog == "skillsmp" or external_id.startswith("skillsmp:"):
        return "SkillsMP"
    if catalog == "clawhub" or external_id.startswith("clawhub:"):
        return "ClawHub"
    if catalog == "redskill" or meta.get("redskill_catalog") or meta.get("redskill"):
        return "RedSkill目录"
    if meta.get("agentkit"):
        return "AgentKit API"
    if catalog == "official_github":
        return "官方GitHub"
    if catalog == "github" or "GitHub" in (meta.get("tags") or []):
        return "GitHub社区"

    portal_labels = {
        "meituan_ai_hub": "美团AI Hub API",
        "aliyun_skills_portal": "阿里Skills门户",
        "volcengine_find": "火山/扣子生态",
        "zhihu_skills": "知乎开发者/社区",
        "xiaohongshu_red_skill": "小红书RED Skill",
        "bilibili_skills": "B站开发者/社区",
        "kuaishou_skills": "快手开发者/社区",
        "didi_skills": "滴滴 MCP/官方Skill",
        "pinduoduo_skills": "拼多多开发者/社区",
        "ctrip_skills": "携程开发者/社区",
        "dewu_skills": "得物开发者/社区",
        "wechat_skillhub": "微信开发者文档",
        "skills_sh": "skills.sh",
        "github_watch": "GitHub监控",
    }
    if source_id in portal_labels:
        if catalog == "official_api":
            return portal_labels[source_id]
        if catalog == "official":
            return f"{portal_labels[source_id]}·官方说明"
        if source_id in OFFICIAL_PORTAL_SOURCES:
            return portal_labels[source_id]

    if catalog == "official_api":
        return "官方API"
    if catalog == "official":
        return "官方说明"
    return "社区发现"


def enrich_metadata(
    metadata: dict[str, Any] | None,
    *,
    vendor: str,
    source_id: str,
    external_id: str = "",
) -> dict[str, Any]:
    """Normalize publisherType / dataSource on ingest."""
    meta = dict(metadata or {})
    meta.setdefault("vendor", vendor)
    meta.setdefault("source_id", source_id)
    meta.setdefault("external_id", external_id)
    meta.pop("publisherType", None)
    meta.pop("dataSource", None)
    meta["publisherType"] = publisher_type_for(meta)
    meta["dataSource"] = data_source_for(meta)
    return meta
