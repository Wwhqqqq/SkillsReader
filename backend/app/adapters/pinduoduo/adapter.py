"""
拼多多 Agent Skill 社区 Adapter —— ClawHub、SkillsMP、GitHub、官方开放平台锚点。

yaml: adapter: pinduoduo_skills
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
    PDD_REPO_BLOCKLIST,
    is_dedicated_pinduoduo_repo,
    is_pinduoduo_relevant,
)
from app.adapters.pinduoduo.catalog import fetch_clawhub_pinduoduo, fetch_skillsmp_pinduoduo
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

PDD_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("TonyWang-hub/mcp-cn-commerce", ("packages/mcp-cn-pinduoduo", "packages/pinduoduo")),
    ("hhx465453939/mcp-cn-commerce", ("packages/mcp-cn-pinduoduo", "packages/pinduoduo")),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md pinduoduo",
    "filename:SKILL.md 拼多多",
    "filename:SKILL.md pdd-coupon",
    "filename:SKILL.md pdd ",
)

REPO_SEARCH_QUERIES = (
    "pinduoduo skill agent",
    "pinduoduo mcp skill",
    "拼多多 skill",
    "pdd coupon skill",
    "mcp-cn-pinduoduo",
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "pdd-open-platform",
        "name": "拼多多开放平台",
        "raw_description": "面向开发者与服务商：订单、商品、物流、售后、营销、店铺、多多进宝等 REST API（OAuth）",
        "detail_url": "https://open.pinduoduo.com/",
        "tags": ["拼多多", "官方", "开放平台"],
        "category": "官方平台",
    },
    {
        "external_id": "pdd-api-ddk",
        "name": "拼多多多多进宝 API",
        "raw_description": "推广位、商品查询、转链、佣金等多多进宝（PDD DDK）接口能力",
        "detail_url": "https://open.pinduoduo.com/application/document/api",
        "tags": ["拼多多", "官方", "多多进宝"],
        "category": "官方 API",
    },
    {
        "external_id": "pdd-api-mall",
        "name": "拼多多商家 API",
        "raw_description": "商家订单、商品、库存、物流、售后等店铺经营接口",
        "detail_url": "https://open.pinduoduo.com/",
        "tags": ["拼多多", "官方", "商家API"],
        "category": "官方 API",
    },
    {
        "external_id": "pdd-mcp-cn-commerce",
        "name": "mcp-cn-commerce 拼多多 MCP",
        "raw_description": "开源 MCP Server 套件中的拼多多模块（mcp-cn-pinduoduo），结构化访问订单/商品/推广工具",
        "detail_url": "https://github.com/TonyWang-hub/mcp-cn-commerce",
        "tags": ["拼多多", "MCP", "社区"],
        "category": "MCP生态",
    },
    {
        "external_id": "pdd-clawhub-coupon-bot",
        "name": "拼多多优惠券 Skill（ClawHub 社区）",
        "raw_description": "pdd-coupon-bot：ClawHub 社区 Skill，自动检索隐藏券/百亿补贴等（`clawhub install pdd-coupon-bot`）",
        "detail_url": "https://clawhub.ai/",
        "tags": ["拼多多", "社区", "ClawHub"],
        "category": "社区 Skill",
    },
    {
        "external_id": "pdd-agent-skills-ecosystem",
        "name": "拼多多 Agent Skill 社区生态",
        "raw_description": "拼多多无统一 SkillHub 公开列表；Skill 分布于 ClawHub、SkillsMP、GitHub（优惠券、电商 MCP、选品/进宝工具等）",
        "detail_url": "https://open.pinduoduo.com/",
        "tags": ["拼多多", "社区", "生态说明"],
        "category": "社区生态",
    },
]


class PinduoduoSkillsAdapter(SourceAdapter):
    source_id = "pinduoduo_skills"
    vendor = "拼多多"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        if not is_pinduoduo_relevant(rec):
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
            for rec in await fetch_clawhub_pinduoduo(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_pinduoduo(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=4
            ):
                self._add_record(records, seen, rec)

            for repo, known in PDD_GITHUB_REPOS:
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["拼多多", "GitHub"],
                        roots=("", "skills", "packages"),
                        known_prefixes=known,
                        category_default="社区",
                        record_filter=is_pinduoduo_relevant,
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
                    if not repo or "SKILL.md" not in path or repo in PDD_REPO_BLOCKLIST:
                        continue
                    blob = f"{repo} {path}".lower()
                    if not any(k in blob for k in ("pinduoduo", "拼多多", "pdd-", "pdd_", "/pdd")):
                        continue
                    prefix = path.replace("/SKILL.md", "")
                    key = f"{repo}:{prefix}"
                    if key in seen:
                        continue
                    skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                    text = await fetch_skill_md_text(client, repo, prefix, headers)
                    fallback_desc = f"拼多多相关 SKILL.md · {repo}"
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
                        tags=["拼多多", "SKILL.md", category],
                        metadata={
                            "repo": repo,
                            "path": path,
                            "categoryName": category,
                            "catalog": "github",
                        },
                    )
                    self._add_record(records, seen, rec)

            known_repos = {r for r, _ in PDD_GITHUB_REPOS}
            extra_repos: set[str] = set()
            for query in REPO_SEARCH_QUERIES:
                for item in await search_repositories(client, query, headers, per_page=8):
                    name = item.get("full_name", "")
                    if not name or name in known_repos or name in PDD_REPO_BLOCKLIST:
                        continue
                    if not is_dedicated_pinduoduo_repo(name):
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
                        tags=["拼多多", "GitHub"],
                        roots=("", "skills", "packages"),
                        record_filter=is_pinduoduo_relevant,
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
