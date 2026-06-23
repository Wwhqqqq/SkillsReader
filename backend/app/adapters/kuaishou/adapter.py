"""
快手 Agent Skill 社区 Adapter —— ClawHub、SkillsMP、GitHub、官方开放平台锚点。

yaml: adapter: kuaishou_skills
"""

from __future__ import annotations

import httpx

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.adapters.common.github import (
    build_records_from_repo,
    fetch_skill_md_text,
    github_headers,
    parse_skill_md,
    search_code_skill_md,
    search_repositories,
)
from app.adapters.common.platform_filters import (
    KUAISHOU_REPO_BLOCKLIST,
    is_dedicated_kuaishou_repo,
    is_kuaishou_relevant,
)
from app.adapters.kuaishou.catalog import fetch_clawhub_kuaishou, fetch_skillsmp_kuaishou
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

KUAISHOU_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("XieWxx/maxhub-api-skills", ("maxhub-kuaishou",)),
    ("dreammis/social-auto-upload", ("skills/kuaishou-upload",)),
    ("httprunner/skills", ("resolve-kwai-cdn-url",)),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md kuaishou",
    "filename:SKILL.md 快手",
    "filename:SKILL.md kwai",
    "filename:SKILL.md kuaishou-upload",
)

REPO_SEARCH_QUERIES = (
    "kuaishou skill agent",
    "kuaishou mcp skill",
    "快手 skill",
    "maxhub-kuaishou skill",
    "kwai cdn skill",
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "kuaishou-open-platform",
        "name": "快手开放平台",
        "raw_description": "面向开发者与服务商：短视频、直播、电商、本地生活等开放 API 与 OAuth 授权能力",
        "detail_url": "https://open.kuaishou.com/",
        "tags": ["快手", "官方", "开放平台"],
        "category": "官方平台",
    },
    {
        "external_id": "kuaishou-miniprogram",
        "name": "快手小程序开放平台",
        "raw_description": "小程序接入、能力申请、发快手、挂载、支付与行业能力等开发者文档",
        "detail_url": "https://open.kuaishou.com/docs/introduction/abilityShow/abilityShowDetail",
        "tags": ["快手", "官方", "小程序"],
        "category": "开发者中心",
    },
    {
        "external_id": "kuaishou-api-video",
        "name": "快手短视频与直播 API",
        "raw_description": "开放平台视频发布、数据查询、直播互动等接口能力说明",
        "detail_url": "https://open.kuaishou.com/platform/openApi",
        "tags": ["快手", "官方", "视频API"],
        "category": "官方 API",
    },
    {
        "external_id": "kuaishou-api-ecommerce",
        "name": "快手电商与本地生活 API",
        "raw_description": "小店、分销、本地生活等业务开放接口与接入指引",
        "detail_url": "https://open.kuaishou.com/",
        "tags": ["快手", "官方", "电商"],
        "category": "官方 API",
    },
    {
        "external_id": "kuaishou-agent-skills-ecosystem",
        "name": "快手 Agent Skill 社区生态",
        "raw_description": "快手暂无统一 SkillHub 公开列表；社区 Skill 分布于 GitHub、ClawHub、SkillsMP（上传/数据查询/热榜分析/链接解析等）",
        "detail_url": "https://open.kuaishou.com/",
        "tags": ["快手", "社区", "生态说明"],
        "category": "社区生态",
    },
]


class KuaishouSkillsAdapter(SourceAdapter):
    source_id = "kuaishou_skills"
    vendor = "快手"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        if not is_kuaishou_relevant(rec):
            return
        if rec.external_id in seen:
            return
        seen.add(rec.external_id)
        records.append(rec)

    async def fetch(self) -> list[RawSkillRecord]:
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        headers = github_headers()
        timeout = httpx.Timeout(90.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for rec in await fetch_clawhub_kuaishou(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_kuaishou(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=4
            ):
                self._add_record(records, seen, rec)

            for repo, known in KUAISHOU_GITHUB_REPOS:
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["快手", "GitHub"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="社区",
                        record_filter=is_kuaishou_relevant,
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        meta.setdefault("catalog", "github")
                        rec.metadata = meta
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

            for query in CODE_SEARCH_QUERIES:
                for item in await search_code_skill_md(client, query, headers, per_page=20):
                    repo = item.get("repository", {}).get("full_name", "")
                    path = item.get("path", "")
                    if not repo or "SKILL.md" not in path or repo in KUAISHOU_REPO_BLOCKLIST:
                        continue
                    blob = f"{repo} {path}".lower()
                    if not any(k in blob for k in ("kuaishou", "快手", "kwai", "ks-")):
                        continue
                    prefix = path.replace("/SKILL.md", "")
                    key = f"{repo}:{prefix}"
                    if key in seen:
                        continue
                    skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                    text = await fetch_skill_md_text(client, repo, prefix, headers)
                    fallback_desc = f"快手相关 SKILL.md · {repo}"
                    if text:
                        skill_name, desc, category = parse_skill_md(text, skill_name, fallback_desc)
                    else:
                        desc, category = fallback_desc, "社区"
                    rec = RawSkillRecord(
                        external_id=key,
                        name=skill_name,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        raw_description=desc,
                        detail_url=item.get("html_url", ""),
                        tags=["快手", "SKILL.md", category],
                        metadata={
                            "repo": repo,
                            "path": path,
                            "categoryName": category,
                            "catalog": "github",
                        },
                    )
                    self._add_record(records, seen, rec)

            known_repos = {r for r, _ in KUAISHOU_GITHUB_REPOS}
            extra_repos: set[str] = set()
            for query in REPO_SEARCH_QUERIES:
                for item in await search_repositories(client, query, headers, per_page=8):
                    name = item.get("full_name", "")
                    if not name or name in known_repos or name in KUAISHOU_REPO_BLOCKLIST:
                        continue
                    if not is_dedicated_kuaishou_repo(name):
                        continue
                    extra_repos.add(name)

            for repo in sorted(extra_repos):
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["快手", "GitHub"],
                        roots=("", "skills"),
                        record_filter=is_kuaishou_relevant,
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        meta.setdefault("catalog", "github")
                        rec.metadata = meta
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

        for entry in OFFICIAL_ENTRIES:
            rec = RawSkillRecord(
                external_id=entry["external_id"],
                name=entry["name"],
                vendor=self.vendor,
                source_id=self.source_id,
                raw_description=entry["raw_description"],
                detail_url=entry["detail_url"],
                tags=entry["tags"],
                metadata={
                    "categoryName": entry.get("category", "社区"),
                    "official": True,
                    "catalog": "official",
                },
            )
            self._add_record(records, seen, rec)

        return await apply_vendor_relevance_split(self.vendor, records)

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        from app.adapters.common.official_entries import records_from_official_entries

        return records_from_official_entries(
            source_id=self.source_id, vendor=self.vendor, entries=OFFICIAL_ENTRIES
        )
