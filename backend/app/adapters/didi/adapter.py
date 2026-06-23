"""
滴滴 Agent Skill 社区 Adapter —— ClawHub、SkillsMP、GitHub、官方 MCP 锚点。

yaml: adapter: didi_skills
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
    DIDI_REPO_BLOCKLIST,
    is_dedicated_didi_repo,
    is_didi_relevant,
)
from app.adapters.didi.catalog import fetch_clawhub_didi, fetch_skillsmp_didi
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

DIDI_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("didi/didi-ride-skill", None),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md didi-ride",
    "filename:SKILL.md 滴滴",
    "filename:SKILL.md didichuxing",
    "filename:SKILL.md DIDI_MCP",
)

REPO_SEARCH_QUERIES = (
    "didi ride skill agent",
    "didi mcp skill",
    "滴滴 skill",
    "didichuxing mcp skill",
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "didi-mcp-platform",
        "name": "滴滴 MCP 服务",
        "raw_description": "面向 AI Agent 的出行 MCP 服务：网约车预估/下单/订单查询/取消、地图 POI/路线规划（Beta/Pro/Pro+）",
        "detail_url": "https://mcp.didichuxing.com/",
        "tags": ["滴滴", "官方", "MCP"],
        "category": "官方平台",
    },
    {
        "external_id": "didi-mcp-api-docs",
        "name": "DiDi MCP Server 开发者文档",
        "raw_description": "13 个 MCP 工具：taxi_estimate/create_order/query_order、maps_textsearch、路线规划等接入指南",
        "detail_url": "https://mcp.didichuxing.com/api",
        "tags": ["滴滴", "官方", "API文档"],
        "category": "官方 API",
    },
    {
        "external_id": "didi-ride-skill-clawhub",
        "name": "滴滴官方打车 Skill（ClawHub）",
        "raw_description": "didi-ride-skill-official：OpenClaw 一键安装，覆盖叫车/预约/查价/路线规划/订单跟踪全流程",
        "detail_url": "https://clawhub.ai/didi/didi-ride-skill-official",
        "tags": ["滴滴", "官方", "Skill"],
        "category": "官方 Skill",
    },
    {
        "external_id": "didi-ride-skill-github",
        "name": "滴滴官方打车 Skill（GitHub）",
        "raw_description": "didi/didi-ride-skill 开源仓库，基于 DiDi MCP Server 封装 Agent Skill",
        "detail_url": "https://github.com/didi/didi-ride-skill",
        "tags": ["滴滴", "官方", "GitHub"],
        "category": "官方 Skill",
    },
    {
        "external_id": "didi-open-platform",
        "name": "滴滴开放平台",
        "raw_description": "企业级出行开放能力与合作伙伴接入（与 MCP 服务互补）",
        "detail_url": "https://open.didi.cn/",
        "tags": ["滴滴", "官方", "开放平台"],
        "category": "开发者中心",
    },
    {
        "external_id": "didi-agent-skills-ecosystem",
        "name": "滴滴 Agent Skill 生态",
        "raw_description": "核心为官方 didi-ride-skill + MCP；无公开 Skill 列表 API，社区 Fork/衍生 Skill 分布于 ClawHub、SkillsMP、GitHub",
        "detail_url": "https://mcp.didichuxing.com/",
        "tags": ["滴滴", "社区", "生态说明"],
        "category": "社区生态",
    },
]


class DidiSkillsAdapter(SourceAdapter):
    source_id = "didi_skills"
    vendor = "滴滴"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        if not is_didi_relevant(rec):
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
            for rec in await fetch_clawhub_didi(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_didi(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=4
            ):
                self._add_record(records, seen, rec)

            for repo, known in DIDI_GITHUB_REPOS:
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["滴滴", "GitHub", "官方"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="官方",
                        record_filter=is_didi_relevant,
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        meta.setdefault("catalog", "official_github")
                        meta["official"] = True
                        rec.metadata = meta
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

            for query in CODE_SEARCH_QUERIES:
                for item in await search_code_skill_md(client, query, headers, per_page=20):
                    repo = item.get("repository", {}).get("full_name", "")
                    path = item.get("path", "")
                    if not repo or "SKILL.md" not in path or repo in DIDI_REPO_BLOCKLIST:
                        continue
                    blob = f"{repo} {path}".lower()
                    if not any(k in blob for k in ("didi", "滴滴", "didichuxing", "didi-ride")):
                        continue
                    prefix = path.replace("/SKILL.md", "")
                    key = f"{repo}:{prefix}"
                    if key in seen:
                        continue
                    skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                    text = await fetch_skill_md_text(client, repo, prefix, headers)
                    fallback_desc = f"滴滴相关 SKILL.md · {repo}"
                    if text:
                        skill_name, desc, category = parse_skill_md(text, skill_name, fallback_desc)
                    else:
                        desc, category = fallback_desc, "社区"
                    catalog = "official_github" if repo.lower().startswith("didi/") else "github"
                    rec = RawSkillRecord(
                        external_id=key,
                        name=skill_name,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        raw_description=desc,
                        detail_url=item.get("html_url", ""),
                        tags=["滴滴", "SKILL.md", category],
                        metadata={
                            "repo": repo,
                            "path": path,
                            "categoryName": category,
                            "catalog": catalog,
                            "official": repo.lower().startswith("didi/"),
                        },
                    )
                    self._add_record(records, seen, rec)

            known_repos = {r for r, _ in DIDI_GITHUB_REPOS}
            extra_repos: set[str] = set()
            for query in REPO_SEARCH_QUERIES:
                for item in await search_repositories(client, query, headers, per_page=8):
                    name = item.get("full_name", "")
                    if not name or name in known_repos or name in DIDI_REPO_BLOCKLIST:
                        continue
                    if not is_dedicated_didi_repo(name):
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
                        tags=["滴滴", "GitHub"],
                        roots=("", "skills"),
                        record_filter=is_didi_relevant,
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
