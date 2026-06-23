"""
知乎 Agent Skill 社区 Adapter —— 多源聚合：ClawHub、SkillsMP、GitHub、官方开发者入口。

yaml: adapter: zhihu_skills
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
    ZHIHU_REPO_BLOCKLIST,
    is_dedicated_zhihu_repo,
    is_zhihu_relevant,
)
from app.adapters.common.record_utils import add_platform_record
from app.adapters.zhihu.catalog import fetch_clawhub_zhihu, fetch_skillsmp_zhihu
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

ZHIHU_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("handsomestWei/zhihu-fetch-skill", ("",)),
    (
        "liyxianren/zhihu",
        (
            "skills/zhihu-auto-publisher",
            "skills/zhihu-content-writer",
            "skills/zhihu-social-publisher",
            "skills/zhihu-topic-ideator",
        ),
    ),
    ("liuboacean/zhihu-automation-skill", None),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md zhihu",
    "filename:SKILL.md 知乎",
)

REPO_SEARCH_QUERIES = (
    "zhihu skill",
    "zhihu-fetch skill",
    "知乎 skill agent",
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "zhihu-dev-platform",
        "name": "知乎数据开放平台",
        "raw_description": "面向开发者与 AI 应用：知乎搜索、热榜、直答 Agent；支持 REST API、Skill、MCP 接入",
        "detail_url": "https://developer.zhihu.com",
        "tags": ["知乎", "官方", "开发者平台"],
        "category": "官方平台",
    },
    {
        "external_id": "zhihu-dev-docs",
        "name": "知乎开发者文档中心",
        "raw_description": "API / Skill / MCP 接入文档与效果测试入口",
        "detail_url": "https://developer.zhihu.com/docs",
        "tags": ["知乎", "官方", "文档"],
        "category": "官方文档",
    },
    {
        "external_id": "zhihu-dev-hotlist",
        "name": "知乎热榜 API",
        "raw_description": "知乎热榜数据接口，供 Agent 获取实时热点",
        "detail_url": "https://developer.zhihu.com/hotlist",
        "tags": ["知乎", "官方", "热榜"],
        "category": "官方 API",
    },
    {
        "external_id": "zhihu-dev-answer",
        "name": "知乎问答搜索 API",
        "raw_description": "知乎问答/内容检索接口，结构化返回可溯源结果",
        "detail_url": "https://developer.zhihu.com/answer",
        "tags": ["知乎", "官方", "搜索"],
        "category": "官方 API",
    },
    {
        "external_id": "zhihu-openapi-bot",
        "name": "知乎 AI Bot OpenAPI",
        "raw_description": "圈子发布、点赞、评论等 Bot 能力（openapi.zhihu.com，需 app_key/app_secret）",
        "detail_url": "https://openapi.zhihu.com/",
        "tags": ["知乎", "官方", "Bot API"],
        "category": "官方 API",
    },
    {
        "external_id": "zhihu-agent-skills-ecosystem",
        "name": "知乎 Agent Skills 社区生态",
        "raw_description": "知乎暂无统一 SkillHub；创作者在专栏/社区分发 SKILL.md，扣子/ClawHub 等亦上架知乎相关 Skill",
        "detail_url": "https://zhuanlan.zhihu.com/p/1997469097856890798",
        "tags": ["知乎", "社区", "官方生态"],
        "category": "社区生态",
    },
]


class ZhihuSkillsAdapter(SourceAdapter):
    source_id = "zhihu_skills"
    vendor = "知乎"
# 添加记录到列表中，并去重
    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        add_platform_record(records, seen, rec, is_zhihu_relevant)

    async def fetch(self) -> list[RawSkillRecord]:
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        headers = github_headers()
        timeout = httpx.Timeout(90.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for rec in await fetch_clawhub_zhihu(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_zhihu(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=5
            ):
                self._add_record(records, seen, rec)

            for repo, known in ZHIHU_GITHUB_REPOS:
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["知乎", "GitHub"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="社区",
                        record_filter=is_zhihu_relevant,
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
                    if not repo or "SKILL.md" not in path:
                        continue
                    if repo in ZHIHU_REPO_BLOCKLIST:
                        continue
                    if (
                        "zhihu" not in repo.lower()
                        and "zhihu" not in path.lower()
                        and "知乎" not in path
                    ):
                        continue
                    prefix = path.replace("/SKILL.md", "")
                    key = f"{repo}:{prefix}"
                    if key in seen:
                        continue
                    skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                    text = await fetch_skill_md_text(client, repo, prefix, headers)
                    fallback_desc = f"知乎相关 SKILL.md · {repo}"
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
                        tags=["知乎", "SKILL.md", category],
                        metadata={
                            "repo": repo,
                            "path": path,
                            "categoryName": category,
                            "catalog": "github",
                        },
                    )
                    self._add_record(records, seen, rec)

            known_repos = {r for r, _ in ZHIHU_GITHUB_REPOS}
            extra_repos: set[str] = set()
            for query in REPO_SEARCH_QUERIES:
                for item in await search_repositories(client, query, headers, per_page=8):
                    name = item.get("full_name", "")
                    if not name or name in known_repos or name in ZHIHU_REPO_BLOCKLIST:
                        continue
                    if not is_dedicated_zhihu_repo(name):
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
                        tags=["知乎", "GitHub"],
                        roots=("", "skills"),
                        record_filter=is_zhihu_relevant,
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
