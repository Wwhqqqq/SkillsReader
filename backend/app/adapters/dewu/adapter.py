"""
得物 Agent Skill 社区 Adapter —— ClawHub、SkillsMP、GitHub、官方开放平台锚点。

yaml: adapter: dewu_skills
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
    DEWU_REPO_BLOCKLIST,
    is_dedicated_dewu_repo,
    is_dewu_relevant,
)
from app.adapters.dewu.catalog import fetch_clawhub_dewu, fetch_skillsmp_dewu
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

DEWU_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("wxkingstar/SpecFusion", ("specfusion",)),
    ("LiangNiang/OpenMantis", (".agents/skills/specfusion",)),
    ("xzyhahaha/dw-skills", ("dewu-seeding-copywriter",)),
    ("jiaxianh/skill_l10n", None),
    ("sydical/Clawde-skills", ("skills/honny-social-publisher",)),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md dewu",
    "filename:SKILL.md 得物",
    "filename:SKILL.md poizon-l10n",
    "filename:SKILL.md specfusion dewu",
    "filename:SKILL.md dewu-seeding",
    "filename:SKILL.md honny-social-publisher",
)

REPO_SEARCH_QUERIES = (
    "dewu skill agent",
    "poizon skill agent",
    "得物 skill",
    "dw-skills dewu",
    "specfusion dewu",
    "dewu mcp",
    "poizon mcp",
)

OFFICIAL_PLATFORM_IDS = frozenset(
    {
        "dewu-open-platform",
        "poizon-open-platform",
        "dewu-merchant-console",
        "dewu-consumer-app",
        "dewu-tech-blog",
    }
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "dewu-open-platform",
        "name": "得物开放平台 (DOP)",
        "raw_description": "商家/合作伙伴 REST API：商品、订单、售后、出价、入仓、物流、对账等；需 appKey/appSecret 授权，无公开 Skill 列表 API",
        "detail_url": "https://open.dewu.com/#/api",
        "tags": ["得物", "官方", "开放平台"],
        "category": "官方开放平台",
    },
    {
        "external_id": "poizon-open-platform",
        "name": "Poizon Open Platform",
        "raw_description": "得物国际版开发者门户，与 open.dewu.com 并行",
        "detail_url": "https://open.poizon.com/",
        "tags": ["得物", "官方", "开放平台", "Poizon"],
        "category": "官方开放平台",
    },
    {
        "external_id": "dewu-merchant-console",
        "name": "得物商家后台",
        "raw_description": "B2B 商家运营控制台",
        "detail_url": "https://global.dewu.com/",
        "tags": ["得物", "官方", "商家"],
        "category": "官方产品",
    },
    {
        "external_id": "dewu-consumer-app",
        "name": "得物 App / 官网",
        "raw_description": "消费者端 App 与官网（社区 Skill 常引用公开页面与规则）",
        "detail_url": "https://www.dewu.com/",
        "tags": ["得物", "官方", "消费者"],
        "category": "官方产品",
    },
    {
        "external_id": "dewu-tech-blog",
        "name": "得物技术博客",
        "raw_description": "内部 AI/MCP 工程实践文章，非对外 Skill 注册中心",
        "detail_url": "https://tech.dewu.com/",
        "tags": ["得物", "官方", "技术"],
        "category": "官方技术",
    },
    {
        "external_id": "clawhub-dewu-community",
        "name": "ClawHub: dewu（社区）",
        "raw_description": "mikeclaw007/dewu：整理得物公开入驻/活动/规则/帮助页，非官方后端操作",
        "detail_url": "https://clawhub.ai/dewu",
        "tags": ["得物", "社区", "ClawHub"],
        "category": "社区 Skill",
        "catalog": "community",
    },
    {
        "external_id": "specfusion-dewu-source",
        "name": "SpecFusion 得物文档源（社区）",
        "raw_description": "wxkingstar/SpecFusion：多平台 API 文档检索，source=dewu 约 260 条得物开放平台文档",
        "detail_url": "https://github.com/wxkingstar/SpecFusion/tree/main/specfusion",
        "tags": ["得物", "社区", "API文档"],
        "category": "社区 Skill",
        "catalog": "community",
    },
    {
        "external_id": "open-poizon-api-mcp",
        "name": "Open Poizon Api MCP（第三方）",
        "raw_description": "xpack.ai 第三方商品搜索/详情 MCP，非得物官方",
        "detail_url": "https://xpack.ai/server/open-poizon-api",
        "tags": ["得物", "第三方", "MCP"],
        "category": "第三方 MCP",
        "catalog": "third_party",
    },
    {
        "external_id": "dewu-agent-skills-ecosystem",
        "name": "得物 Agent Skill 社区生态",
        "raw_description": "无官方 SkillHub；社区 Skill 稀少（ClawHub dewu、SpecFusion、种草文案、poizon-l10n 等），poizon/得物 检索噪声大需强过滤",
        "detail_url": "https://open.dewu.com/",
        "tags": ["得物", "社区", "生态说明"],
        "category": "社区生态",
        "catalog": "community",
    },
]


class DewuSkillsAdapter(SourceAdapter):
    source_id = "dewu_skills"
    vendor = "得物"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        if not is_dewu_relevant(rec):
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
            for rec in await fetch_clawhub_dewu(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_dewu(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=4
            ):
                self._add_record(records, seen, rec)

            for repo, known in DEWU_GITHUB_REPOS:
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["得物", "GitHub"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="社区",
                        record_filter=is_dewu_relevant,
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
                    if not repo or "SKILL.md" not in path or repo in DEWU_REPO_BLOCKLIST:
                        continue
                    blob = f"{repo} {path}".lower()
                    if not any(
                        k in blob
                        for k in (
                            "dewu",
                            "得物",
                            "poizon",
                            "specfusion",
                            "dewu-seeding",
                            "honny-social",
                        )
                    ):
                        continue
                    prefix = path.replace("/SKILL.md", "")
                    key = f"{repo}:{prefix}"
                    if key in seen:
                        continue
                    skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                    text = await fetch_skill_md_text(client, repo, prefix, headers)
                    fallback_desc = f"得物相关 SKILL.md · {repo}"
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
                        tags=["得物", "SKILL.md", category],
                        metadata={
                            "repo": repo,
                            "path": path,
                            "categoryName": category,
                            "catalog": "github",
                        },
                    )
                    self._add_record(records, seen, rec)

            known_repos = {r for r, _ in DEWU_GITHUB_REPOS}
            extra_repos: set[str] = set()
            for query in REPO_SEARCH_QUERIES:
                for item in await search_repositories(client, query, headers, per_page=8):
                    name = item.get("full_name", "")
                    if not name or name in known_repos or name in DEWU_REPO_BLOCKLIST:
                        continue
                    if not is_dedicated_dewu_repo(name):
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
                        tags=["得物", "GitHub"],
                        roots=("", "skills"),
                        record_filter=is_dewu_relevant,
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        meta.setdefault("catalog", "github")
                        rec.metadata = meta
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

        for entry in OFFICIAL_ENTRIES:
            eid = entry["external_id"]
            is_official = eid in OFFICIAL_PLATFORM_IDS
            rec = RawSkillRecord(
                external_id=eid,
                name=entry["name"],
                vendor=self.vendor,
                source_id=self.source_id,
                raw_description=entry["raw_description"],
                detail_url=entry["detail_url"],
                tags=entry["tags"],
                metadata={
                    "categoryName": entry.get("category", "社区"),
                    "official": is_official,
                    "catalog": entry.get("catalog", "official" if is_official else "community"),
                },
            )
            self._add_record(records, seen, rec)

        return await apply_vendor_relevance_split(self.vendor, records)

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        from app.adapters.common.official_entries import records_from_official_entries

        return records_from_official_entries(
            source_id=self.source_id, vendor=self.vendor, entries=OFFICIAL_ENTRIES
        )
