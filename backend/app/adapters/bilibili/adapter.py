"""
哔哩哔哩 Agent Skill 社区 Adapter —— ClawHub、SkillsMP、GitHub、官方开放平台锚点。

yaml: adapter: bilibili_skills
"""

from __future__ import annotations

import httpx

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.adapters.bilibili.catalog import fetch_clawhub_bilibili, fetch_skillsmp_bilibili
from app.adapters.common.github import (
    build_records_from_repo,
    fetch_skill_md_text,
    github_headers,
    parse_skill_md,
    search_code_skill_md,
    search_repositories,
)
from app.adapters.common.platform_filters import (
    BILI_REPO_BLOCKLIST,
    is_bilibili_relevant,
    is_dedicated_bilibili_repo,
)
from app.adapters.common.record_utils import add_platform_record
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

BILI_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("222wcnm/BiliStalkerMCP", ("skills/bili-content-analysis",)),
    ("dreammis/social-auto-upload", ("skills/bilibili-upload",)),
    ("yutto-dev/yutto", ("skills/bilibili-video-download",)),
    ("LeoYeAI/openclaw-master-skills", ("skills/bilibili-cc-to-notion",)),
    ("dongsheng123132/u-claw", ("portable/skills-cn/bilibili-helper",)),
    ("XZXZZX-Ai/bilibili-mcp", None),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md bilibili",
    "filename:SKILL.md 哔哩哔哩",
    "filename:SKILL.md bili-",
)

REPO_SEARCH_QUERIES = (
    "bilibili skill agent",
    "bilibili mcp skill",
    "哔哩哔哩 skill",
    "bili-content-analysis skill",
)


class BilibiliSkillsAdapter(SourceAdapter):
    source_id = "bilibili_skills"
    vendor = "哔哩哔哩"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        add_platform_record(records, seen, rec, is_bilibili_relevant)

    async def fetch(self) -> list[RawSkillRecord]:
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        headers = github_headers()
        timeout = httpx.Timeout(90.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for rec in await fetch_clawhub_bilibili(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_bilibili(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=4
            ):
                self._add_record(records, seen, rec)

            catalog_loaded = len(records) >= 30
            github_repos = BILI_GITHUB_REPOS if not catalog_loaded else BILI_GITHUB_REPOS[:2]
            for repo, known in github_repos:
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["哔哩哔哩", "GitHub"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="社区",
                        record_filter=is_bilibili_relevant,
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        meta.setdefault("catalog", "github")
                        rec.metadata = meta
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

            if not catalog_loaded:
                for query in CODE_SEARCH_QUERIES:
                    for item in await search_code_skill_md(client, query, headers, per_page=20):
                        repo = item.get("repository", {}).get("full_name", "")
                        path = item.get("path", "")
                        if not repo or "SKILL.md" not in path or repo in BILI_REPO_BLOCKLIST:
                            continue
                        blob = f"{repo} {path}".lower()
                        if not any(k in blob for k in ("bilibili", "bili-", "哔哩", "b站")):
                            continue
                        prefix = path.replace("/SKILL.md", "")
                        key = f"{repo}:{prefix}"
                        if key in seen:
                            continue
                        skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                        text = await fetch_skill_md_text(client, repo, prefix, headers)
                        fallback_desc = f"B站相关 SKILL.md · {repo}"
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
                            tags=["哔哩哔哩", "SKILL.md", category],
                            metadata={
                                "repo": repo,
                                "path": path,
                                "categoryName": category,
                                "catalog": "github",
                            },
                        )
                        self._add_record(records, seen, rec)

                known_repos = {r for r, _ in BILI_GITHUB_REPOS}
                extra_repos: set[str] = set()
                for query in REPO_SEARCH_QUERIES:
                    for item in await search_repositories(client, query, headers, per_page=8):
                        name = item.get("full_name", "")
                        if not name or name in known_repos or name in BILI_REPO_BLOCKLIST:
                            continue
                        if not is_dedicated_bilibili_repo(name):
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
                            tags=["哔哩哔哩", "GitHub"],
                            roots=("", "skills"),
                            record_filter=is_bilibili_relevant,
                        )
                        for rec in batch:
                            meta = dict(rec.metadata or {})
                            meta.setdefault("catalog", "github")
                            rec.metadata = meta
                            self._add_record(records, seen, rec)
                    except Exception:
                        continue

        return await apply_vendor_relevance_split(self.vendor, records)

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        return []
