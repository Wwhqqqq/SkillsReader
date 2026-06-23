"""Skill 详情链接解析 —— 修正聚合镜像页等无效 URL。"""

from __future__ import annotations

import re
from typing import Any

CLAWHUB_SKILLS_BASE = "https://clawhub-skills.com/skills"
CLAWHUB_AI_BASE = "https://clawhub.ai"

# RedSkill 目录把全部 136 个 skill 的 sourceUrl 指向同一篇 CSDN 盘点文章
AGGREGATE_MIRROR_PATTERNS = (
    re.compile(r"gitcode\.csdn\.net/69b97a480a2f6a37c5982b84", re.I),
    re.compile(r"gitcode\.csdn\.net/.+/69b97a480a2f6a37c5982b84", re.I),
)


def is_aggregate_mirror_url(url: str | None) -> bool:
    if not url:
        return False
    return any(p.search(url) for p in AGGREGATE_MIRROR_PATTERNS)


def clawhub_skills_url(slug: str) -> str:
    return f"{CLAWHUB_SKILLS_BASE}/{slug.strip().lstrip('/')}"


def clawhub_ai_url(slug: str) -> str:
    return f"{CLAWHUB_AI_BASE}/{slug.strip().lstrip('/')}"


def _meta_dict(skill: Any) -> dict[str, Any]:
    meta = getattr(skill, "metadata_json", None) or getattr(skill, "metadata", None) or {}
    return meta if isinstance(meta, dict) else {}


def extract_skill_slug(skill: Any) -> str | None:
    meta = _meta_dict(skill)
    slug = meta.get("slug")
    if slug:
        return str(slug).strip()

    external_id = str(getattr(skill, "external_id", "") or "")
    for prefix in ("redskill:", "clawhub:", "skillsh:"):
        if external_id.startswith(prefix):
            part = external_id[len(prefix) :].strip()
            return part or None

    install_cmd = meta.get("installCommand") or meta.get("install_command") or ""
    if isinstance(install_cmd, str) and "clawhub install" in install_cmd.lower():
        parts = install_cmd.strip().split()
        if parts:
            return parts[-1].strip()

    return None


def resolve_skill_detail_url(skill: Any, *, default: str = "") -> str:
    """推送/展示用详情链接：优先 per-skill ClawHub 页，跳过聚合盘点镜像。"""
    url = (getattr(skill, "detail_url", None) or "").strip()
    slug = extract_skill_slug(skill)
    meta = _meta_dict(skill)

    if slug and (not url or is_aggregate_mirror_url(url)):
        if meta.get("redskill") or meta.get("catalog") in ("redskill", "clawhub"):
            return clawhub_skills_url(slug)
        if (getattr(skill, "external_id", "") or "").startswith(("redskill:", "clawhub:")):
            return clawhub_skills_url(slug)

    if not url and slug:
        return clawhub_skills_url(slug)

    return url or default
