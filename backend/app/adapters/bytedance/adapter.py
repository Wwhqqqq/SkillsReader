"""
字节跳动 Skill 生态 Adapter —— 火山引擎 / 扣子 / GitHub 等多源聚合。

yaml: adapter: bytedance_skills 或 volcengine_find（见 volcengine_find.py 重导出）
"""

from __future__ import annotations

import re

import httpx

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.adapters.common.clawhub_search import fetch_clawhub_for_vendor
from app.adapters.common.github import (
    build_records_from_repo,
    github_headers,
    get_with_retry,
    search_code_skill_md,
    search_repositories,
)
from app.adapters.bytedance.agentkit import list_sharing_skills
from app.adapters.common.record_utils import preapprove_platform_record
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split
from app.adapters.common.official_github_config import vendor_github_scan_specs

# 官方文档入口（无公开 list API 时的锚点 Skill）
OFFICIAL_ENTRIES = [
    {
        "external_id": "volcengine-agentkit-skills-center",
        "name": "火山引擎 AgentKit Skills 中心",
        "raw_description": "字节火山引擎 AgentKit 官方 Skills 中心，含预置 Skill、Skills 空间与 ListSharingSkills API",
        "detail_url": "https://www.volcengine.com/docs/86681/2155845",
        "tags": ["字节", "火山引擎", "AgentKit", "官方"],
        "category": "AgentKit",
    },
    {
        "external_id": "volcengine-preset-skills",
        "name": "火山引擎预置 Skill",
        "raw_description": "AgentKit 平台预置/共享 Skill 目录，可通过 ListSharingSkills 批量查询",
        "detail_url": "https://www.volcengine.com/docs/86681/2214405",
        "tags": ["字节", "火山引擎", "预置Skill", "官方"],
        "category": "预置Skill",
    },
    {
        "external_id": "coze-open-platform",
        "name": "扣子 Coze 开放平台",
        "raw_description": "字节跳动扣子 AI Agent 开放平台，支持 Bot、插件与 Skill 工作流",
        "detail_url": "https://www.coze.cn/open",
        "tags": ["字节", "扣子", "Coze", "官方"],
        "category": "Coze",
    },
    {
        "external_id": "coze-studio",
        "name": "Coze Studio 开源版",
        "raw_description": "扣子 Coze 开源 Agent 开发框架，社区 Skill 与插件扩展",
        "detail_url": "https://github.com/coze-dev/coze-studio",
        "tags": ["字节", "扣子", "开源", "官方"],
        "category": "Coze",
    },
]

CODE_SEARCH_QUERIES = (
    "org:volcengine filename:SKILL.md",
    "org:coze-dev filename:SKILL.md",
    "coze skill filename:SKILL.md",
)

REPO_SEARCH_QUERIES = (
    "volcengine skill",
    "coze skill agent",
    "bytedance agent skill",
)


class BytedanceSkillsAdapter(SourceAdapter):
    source_id = "bytedance_skills"
    vendor = "字节"

    async def fetch(self) -> list[RawSkillRecord]:
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        headers = github_headers()
        timeout = httpx.Timeout(90.0, connect=30.0)

        for item in await list_sharing_skills(page_size=100):
            skill_id = str(item.get("Id") or item.get("SkillId") or item.get("Name") or "")
            name = str(item.get("Name") or item.get("SkillName") or skill_id or "AgentKit Skill")
            if not skill_id and not name:
                continue
            ext_id = f"agentkit:{skill_id or name}"
            if ext_id in seen:
                continue
            seen.add(ext_id)
            desc = str(
                item.get("Description")
                or item.get("Summary")
                or item.get("Intro")
                or "火山引擎 AgentKit 共享/预置 Skill"
            )
            detail = str(item.get("Url") or item.get("DetailUrl") or "")
            if not detail:
                detail = "https://www.volcengine.com/docs/86681/2155845"
            category = str(item.get("Category") or item.get("Type") or "AgentKit")
            records.append(
                RawSkillRecord(
                    external_id=ext_id,
                    name=name,
                    vendor=self.vendor,
                    source_id=self.source_id,
                    raw_description=desc[:400],
                    detail_url=detail,
                    tags=["字节", "火山引擎", "AgentKit", category],
                    metadata={"categoryName": category, "official": True, "agentkit": True, "catalog": "official_api"},
                )
            )

        async with httpx.AsyncClient(timeout=timeout) as client:
            for repo, roots, known in vendor_github_scan_specs(self.vendor):
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["字节", "火山引擎"],
                        roots=roots,
                        known_prefixes=known,
                        category_default="云资源",
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        meta["catalog"] = "official_github"
                        meta["official"] = True
                        meta["repo"] = repo
                        rec.metadata = meta
                        if rec.external_id not in seen:
                            seen.add(rec.external_id)
                            records.append(rec)
                except Exception:
                    continue

            catalog_loaded = len(records) >= 20
            if not catalog_loaded:
                for query in CODE_SEARCH_QUERIES:
                    for item in await search_code_skill_md(client, query, headers, per_page=25):
                        repo = item.get("repository", {}).get("full_name", "")
                        path = item.get("path", "")
                        if not repo or not path.endswith("SKILL.md"):
                            continue
                        prefix = path[: -len("/SKILL.md")]
                        key = f"{repo}:{prefix}"
                        if key in seen:
                            continue
                        seen.add(key)
                        skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                        records.append(
                            preapprove_platform_record(
                                RawSkillRecord(
                                    external_id=key,
                                    name=skill_name,
                                    vendor=self.vendor,
                                    source_id=self.source_id,
                                    raw_description=f"GitHub SKILL.md · {repo}",
                                    detail_url=item.get("html_url", f"https://github.com/{repo}"),
                                    tags=["字节", "GitHub", "SKILL.md"],
                                    metadata={
                                        "repo": repo,
                                        "path": path,
                                        "categoryName": "社区",
                                        "catalog": "github",
                                    },
                                )
                            )
                        )

            if not catalog_loaded:
                discovered_repos: set[str] = set()
                for query in REPO_SEARCH_QUERIES:
                    for item in await search_repositories(client, query, headers, per_page=8):
                        full_name = item.get("full_name", "")
                        if full_name and full_name not in discovered_repos:
                            discovered_repos.add(full_name)
                    for repo in sorted(discovered_repos):
                        if repo in {r for r, _, _ in BYTE_GITHUB_REPOS}:
                            continue
                        try:
                            batch = await build_records_from_repo(
                                client,
                                repo,
                                vendor=self.vendor,
                                source_id=self.source_id,
                                headers=headers,
                                tags=["字节", "社区"],
                                roots=("", "skills"),
                                category_default="社区",
                            )
                            for rec in batch:
                                meta = dict(rec.metadata or {})
                                meta.setdefault("catalog", "github")
                                rec.metadata = meta
                                rec = preapprove_platform_record(rec)
                                if rec.external_id not in seen:
                                    seen.add(rec.external_id)
                                    records.append(rec)
                        except Exception:
                            continue

            for rec in await fetch_skillsmp_for_vendor(
                client,
                vendor=self.vendor,
                source_id=self.source_id,
                max_pages=3,
            ):
                rec = preapprove_platform_record(rec)
                if rec.external_id not in seen:
                    seen.add(rec.external_id)
                    records.append(rec)

            for rec in await fetch_clawhub_for_vendor(
                client,
                vendor=self.vendor,
                source_id=self.source_id,
                queries=("volcengine", "字节", "doubao", "扣子", "agentkit", "火山"),
            ):
                rec = preapprove_platform_record(rec)
                if rec.external_id not in seen:
                    seen.add(rec.external_id)
                    records.append(rec)

        for entry in OFFICIAL_ENTRIES:
            if entry["external_id"] in seen:
                continue
            seen.add(entry["external_id"])
            category = entry.get("category", "官方")
            records.append(
                RawSkillRecord(
                    external_id=entry["external_id"],
                    name=entry["name"],
                    vendor=self.vendor,
                    source_id=self.source_id,
                    raw_description=entry["raw_description"],
                    detail_url=entry["detail_url"],
                    tags=entry["tags"],
                    metadata={"categoryName": category, "official": True, "catalog": "official"},
                )
            )

        return await apply_vendor_relevance_split(self.vendor, records)

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        """火山 AgentKit 官方 API + 官方文档入口，不含 GitHub/SkillsMP。"""
        from app.adapters.common.official_entries import records_from_official_entries

        records: list[RawSkillRecord] = []
        seen: set[str] = set()

        for item in await list_sharing_skills(page_size=100):
            skill_id = str(item.get("Id") or item.get("SkillId") or item.get("Name") or "")
            name = str(item.get("Name") or item.get("SkillName") or skill_id or "AgentKit Skill")
            if not skill_id and not name:
                continue
            ext_id = f"agentkit:{skill_id or name}"
            if ext_id in seen:
                continue
            seen.add(ext_id)
            desc = str(
                item.get("Description")
                or item.get("Summary")
                or item.get("Intro")
                or "火山引擎 AgentKit 共享/预置 Skill"
            )
            detail = str(item.get("Url") or item.get("DetailUrl") or "")
            if not detail:
                detail = "https://www.volcengine.com/docs/86681/2155845"
            category = str(item.get("Category") or item.get("Type") or "AgentKit")
            records.append(
                RawSkillRecord(
                    external_id=ext_id,
                    name=name,
                    vendor=self.vendor,
                    source_id=self.source_id,
                    raw_description=desc[:400],
                    detail_url=detail,
                    tags=["字节", "火山引擎", "AgentKit", category],
                    metadata={
                        "categoryName": category,
                        "official": True,
                        "agentkit": True,
                        "catalog": "official_api",
                    },
                )
            )

        for rec in records_from_official_entries(
            source_id=self.source_id,
            vendor=self.vendor,
            entries=OFFICIAL_ENTRIES,
        ):
            if rec.external_id not in seen:
                seen.add(rec.external_id)
                records.append(rec)
        return records


# Backward-compatible alias
class VolcengineFindAdapter(BytedanceSkillsAdapter):
    source_id = "volcengine_find"
