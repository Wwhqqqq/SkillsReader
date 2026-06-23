"""
携程 Agent Skill 社区 Adapter —— ClawHub、SkillsMP、GitHub、官方 OpenClaw 锚点。

yaml: adapter: ctrip_skills
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
    CTRIP_REPO_BLOCKLIST,
    is_ctrip_relevant,
    is_dedicated_ctrip_repo,
)
from app.adapters.ctrip.catalog import fetch_clawhub_ctrip, fetch_skillsmp_ctrip
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

CTRIP_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("yflaz/ctrip-skill", None),
    ("ovesorg/workbuddy-config", ("connectors/ctrip-wendao/skills",)),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md ctrip",
    "filename:SKILL.md 携程",
    "filename:SKILL.md wendao-skill",
    "filename:SKILL.md tripgenie",
    "filename:SKILL.md ctrip-flight",
    "filename:SKILL.md ctrip-hotel",
)

REPO_SEARCH_QUERIES = (
    "ctrip skill agent",
    "ctrip mcp skill",
    "携程 skill",
    "wendao-skill openclaw",
    "tripgenie skill",
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "ctrip-wendao-openclaw",
        "name": "携程问道 OpenClaw Skill（官方）",
        "raw_description": "trips-ai/wendao-skill：面向 Ctrip 的 Agent Skill，Token 申请 https://www.ctrip.com/wendao/openclaw，API wendao-skill-prod.ctrip.com",
        "detail_url": "https://www.ctrip.com/wendao/openclaw",
        "tags": ["携程", "官方", "Skill"],
        "category": "官方 Skill",
    },
    {
        "external_id": "trip-tripgenie-openclaw",
        "name": "TripGenie OpenClaw Skill（官方）",
        "raw_description": "tcom-tripgenie-skill：Trip.com AI 助手 OpenClaw 接入，Token https://www.trip.com/tripgenie/openclaw",
        "detail_url": "https://www.trip.com/tripgenie/openclaw",
        "tags": ["携程", "官方", "Skill", "TripGenie"],
        "category": "官方 Skill",
    },
    {
        "external_id": "ctrip-tripplanner",
        "name": "携程 AI 行程助手 Trip.Planner",
        "raw_description": "携程 App/Web 内 AI 行程规划产品（非独立 Skill 包，作为官方能力锚点）",
        "detail_url": "https://www.ctrip.com/tripplanner/",
        "tags": ["携程", "官方", "行程规划"],
        "category": "官方产品",
    },
    {
        "external_id": "ctrip-connect",
        "name": "Trip.com Connect 开放平台",
        "raw_description": "Trip.com 酒店/供应商 OTA 接入与合作伙伴 API（B2B，与 Agent Skill 生态互补）",
        "detail_url": "https://connect.trip.com/",
        "tags": ["携程", "官方", "开放平台"],
        "category": "开发者中心",
    },
    {
        "external_id": "ctrip-business-travel-ai",
        "name": "携程商旅 AI 开放平台",
        "raw_description": "企业商旅 MCP/Agent 能力（差标、机票酒店火车、行程规划等），需商务对接，无公开个人开发者 Skill 列表",
        "detail_url": "https://ct.ctrip.com/thinktanks/235566117077549",
        "tags": ["携程", "官方", "商旅", "MCP"],
        "category": "企业平台",
    },
    {
        "external_id": "ctrip-agent-skills-ecosystem",
        "name": "携程 Agent Skill 社区生态",
        "raw_description": "无统一 SkillHub 公开列表；官方 Wendao/TripGenie OpenClaw + 社区 ClawHub/SkillsMP/GitHub（机票监控、酒店比价、热榜等）",
        "detail_url": "https://www.ctrip.com/wendao/openclaw",
        "tags": ["携程", "社区", "生态说明"],
        "category": "社区生态",
    },
]


class CtripSkillsAdapter(SourceAdapter):
    source_id = "ctrip_skills"
    vendor = "携程"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        if not is_ctrip_relevant(rec):
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
            for rec in await fetch_clawhub_ctrip(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_ctrip(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=4
            ):
                self._add_record(records, seen, rec)

            for repo, known in CTRIP_GITHUB_REPOS:
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["携程", "GitHub"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="社区",
                        record_filter=is_ctrip_relevant,
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        meta.setdefault("catalog", "github")
                        if repo.lower().startswith(("trips-ai/", "ovesorg/workbuddy-config")):
                            meta["official"] = True
                            meta["catalog"] = "official_github"
                        rec.metadata = meta
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

            for query in CODE_SEARCH_QUERIES:
                for item in await search_code_skill_md(client, query, headers, per_page=20):
                    repo = item.get("repository", {}).get("full_name", "")
                    path = item.get("path", "")
                    if not repo or "SKILL.md" not in path or repo in CTRIP_REPO_BLOCKLIST:
                        continue
                    blob = f"{repo} {path}".lower()
                    if not any(
                        k in blob
                        for k in (
                            "ctrip",
                            "携程",
                            "wendao",
                            "tripgenie",
                            "ctrip-flight",
                            "ctrip-hotel",
                        )
                    ):
                        continue
                    prefix = path.replace("/SKILL.md", "")
                    key = f"{repo}:{prefix}"
                    if key in seen:
                        continue
                    skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                    text = await fetch_skill_md_text(client, repo, prefix, headers)
                    fallback_desc = f"携程相关 SKILL.md · {repo}"
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
                        tags=["携程", "SKILL.md", category],
                        metadata={
                            "repo": repo,
                            "path": path,
                            "categoryName": category,
                            "catalog": "github",
                        },
                    )
                    self._add_record(records, seen, rec)

            known_repos = {r for r, _ in CTRIP_GITHUB_REPOS}
            extra_repos: set[str] = set()
            for query in REPO_SEARCH_QUERIES:
                for item in await search_repositories(client, query, headers, per_page=8):
                    name = item.get("full_name", "")
                    if not name or name in known_repos or name in CTRIP_REPO_BLOCKLIST:
                        continue
                    if not is_dedicated_ctrip_repo(name):
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
                        tags=["携程", "GitHub"],
                        roots=("", "skills"),
                        record_filter=is_ctrip_relevant,
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
