"""
跨数据源 Skill 去重 —— 同一社区 Skill 在 ClawHub / SkillsMP / GitHub 多次出现时合并为一条。

官方锚点（metadata.official）按 external_id 独立保留，不参与合并。
"""

from __future__ import annotations

import re
from typing import Any

from app.adapters.base import RawSkillRecord
from app.adapters.common.skillsmp_catalog import _github_repo_from_url

_CATALOG_PRIORITY: dict[str, int] = {
    "official": 100,
    "official_github": 90,
    "official_api": 85,
    "github": 70,
    "clawhub": 60,
    "skillsmp": 50,
    "redskill": 55,
}

_GITHUB_URL_RE = re.compile(r"github\.com/[^/\s]+/[^/\s]+", re.I)


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _meta_dict(obj: RawSkillRecord | Any) -> dict[str, Any]:
    if isinstance(obj, RawSkillRecord):
        return dict(obj.metadata or {})
    meta = getattr(obj, "metadata_json", None)
    return dict(meta) if isinstance(meta, dict) else {}


def _skill_slug(rec: RawSkillRecord | Any, *, external_id: str = "", name: str = "") -> str:
    meta = _meta_dict(rec)
    eid = external_id or getattr(rec, "external_id", None) or ""
    if eid.startswith("clawhub:"):
        slug = eid.split(":", 1)[1].strip().lower()
        if slug:
            return slug
    slug = str(meta.get("slug") or "").strip().lower()
    if slug:
        return slug
    path = str(meta.get("path") or "").strip("/")
    if path:
        return path.split("/")[-1].lower()
    if ":" in eid and not eid.startswith(("skillsmp:", "github-case:", "redskill:")):
        tail = eid.split(":", 1)[1].strip("/")
        if tail:
            return tail.split("/")[-1].lower()
    nm = _normalize_name(name or getattr(rec, "name", None) or "")
    if len(nm) >= 5:
        return nm.replace(" ", "-")
    return ""


def canonical_dedup_key(rec: RawSkillRecord | Any) -> str | None:
    """同一 vendor 下社区 Skill 的合并键；官方锚点每条独立。"""
    meta = _meta_dict(rec)
    vendor = getattr(rec, "vendor", None) or ""
    external_id = getattr(rec, "external_id", None) or ""

    if meta.get("official") or external_id.startswith("github-case:"):
        return f"official:{vendor}:{external_id}"

    slug = _skill_slug(rec, external_id=external_id, name=getattr(rec, "name", "") or "")
    if slug and len(slug) >= 4:
        return f"skill:{vendor}:{slug}"

    repo = str(meta.get("repo") or "").strip()
    path = str(meta.get("path") or "").strip("/").lower()
    if not repo and ":" in external_id and not external_id.startswith(("clawhub:", "skillsmp:")):
        head, tail = external_id.split(":", 1)
        if "/" in head:
            repo, path = head, tail.strip("/").lower()

    if repo:
        return f"gh:{vendor}:{repo.lower()}:{path}"

    github_url = str(meta.get("githubUrl") or "").strip()
    if github_url:
        repo_from_url = _github_repo_from_url(github_url)
        if repo_from_url:
            return f"gh:{vendor}:{repo_from_url.lower()}:"

    if external_id.startswith("skillsmp:"):
        return f"skillsmp:{vendor}:{external_id}"

    detail = str(getattr(rec, "detail_url", None) or "")
    if detail and _GITHUB_URL_RE.search(detail):
        repo_from_url = _github_repo_from_url(detail)
        if repo_from_url:
            return f"gh:{vendor}:{repo_from_url.lower()}:"

    return None


def _record_priority(rec: RawSkillRecord) -> tuple[int, int, int, int]:
    meta = rec.metadata or {}
    catalog = str(meta.get("catalog") or "")
    pri = _CATALOG_PRIORITY.get(catalog, 40)
    if meta.get("official"):
        pri = max(pri, 95)
    desc_len = len(rec.raw_description or "")
    return (pri, rec.install_count, desc_len, len(rec.detail_url or ""))


def _merge_record(primary: RawSkillRecord, other: RawSkillRecord) -> RawSkillRecord:
    """保留 priority 更高的一条为主，合并描述/链接/标签。"""
    if _record_priority(other) > _record_priority(primary):
        primary, other = other, primary

    meta = dict(primary.metadata or {})
    other_meta = dict(other.metadata or {})
    for key, val in other_meta.items():
        if key not in meta or not meta[key]:
            meta[key] = val
    aliases = set(meta.get("dedupAliases") or [])
    if other.external_id:
        aliases.add(other.external_id)
    if primary.external_id:
        aliases.add(primary.external_id)
    if aliases:
        meta["dedupAliases"] = sorted(aliases)

    primary.metadata = meta
    if other.raw_description and len(other.raw_description or "") > len(primary.raw_description or ""):
        primary.raw_description = other.raw_description
    if not primary.detail_url and other.detail_url:
        primary.detail_url = other.detail_url
    if other.install_count > primary.install_count:
        primary.install_count = other.install_count
    if other.tags:
        merged_tags = list(dict.fromkeys((primary.tags or []) + other.tags))
        primary.tags = merged_tags
    return primary


def dedupe_vendor_records(records: list[RawSkillRecord]) -> list[RawSkillRecord]:
    """按 canonical 键合并 fetch 结果，减少跨源重复。"""
    best: dict[str, RawSkillRecord] = {}
    passthrough: list[RawSkillRecord] = []

    for rec in records:
        key = canonical_dedup_key(rec)
        if not key:
            passthrough.append(rec)
            continue
        prev = best.get(key)
        if prev is None:
            best[key] = rec
        else:
            best[key] = _merge_record(prev, rec)

    return passthrough + list(best.values())


def canonical_key_for_skill(skill: Any) -> str | None:
    """从已入库 Skill ORM 行计算 canonical 键（供 pipeline 匹配历史重复）。"""
    pseudo = RawSkillRecord(
        external_id=skill.external_id or "",
        name=skill.name or "",
        vendor=skill.vendor or "",
        source_id=skill.source_id or "",
        raw_description=skill.raw_description or "",
        detail_url=skill.detail_url or "",
        tags=skill.tags or [],
        install_count=skill.install_count or 0,
        metadata=_meta_dict(skill),
    )
    return canonical_dedup_key(pseudo)
