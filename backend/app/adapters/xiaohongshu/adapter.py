"""
小红书 RED Skill Adapter —— redskill.org + 社区 GitHub 等。

yaml: adapter: xiaohongshu_red_skill
"""

from __future__ import annotations

import httpx

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.adapters.common.github import (
    build_records_from_repo,
    fetch_skill_md_text,
    github_headers,
    get_with_retry,
    parse_skill_md,
    search_code_skill_md,
    search_repositories,
)
from app.adapters.common.platform_filters import (
    XHS_REPO_BLOCKLIST,
    is_dedicated_xhs_repo,
    is_xhs_relevant,
)
from app.adapters.common.record_utils import add_platform_record
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor
from app.services.enrichment.vendor_relevance import PROMPT_VERSION, apply_vendor_relevance_split
from app.services.skill_links import clawhub_skills_url, is_aggregate_mirror_url

REDSKILL_DIRECTORY_URL = "https://redskill.org/"
REDSKILL_CATALOG_URL = f"{REDSKILL_DIRECTORY_URL}data/redskill-xiaohongshu-cases.json"

XHS_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    (
        "autoclaw-cc/xiaohongshu-skills",
        (
            "",
            "skills/xhs-auth",
            "skills/xhs-publish",
            "skills/xhs-explore",
            "skills/xhs-interact",
            "skills/xhs-content-ops",
        ),
    ),
    ("autoclaw-cc/xiaohongshu-mcp-skills", None),
    ("chenxiachan/xhs-claude-skills", None),
    ("ibreez3/xiaohongshu-skill", None),
    ("comeonzhj/Auto-Redbook-Skills", None),
    ("Xiangyu-CAS/xiaohongshu-ops-skill", None),
    ("BoomSky0416/redbook-creator", None),
    ("OrangeViolin/wechat-to-xiaohongshu", None),
    ("zhjiang22/openclaw-xhs", None),
    ("lucasygu/redbook", None),
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md xiaohongshu",
    "filename:SKILL.md redbook",
    "filename:SKILL.md 小红书",
)

REPO_SEARCH_QUERIES = (
    "xiaohongshu skill",
    "redbook skill agent",
    "redskill xiaohongshu",
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "xhs-red-skill-platform",
        "name": "小红书 RED Skill 官方分发",
        "raw_description": "小红书 RED Skill：笔记挂载 Skill 组件，用户复制口令安装到 Agent（2026 年 6 月全量上线）",
        "detail_url": "https://www.xiaohongshu.com/explore",
        "tags": ["小红书", "RED Skill", "官方"],
        "category": "RED Skill",
    },
    {
        "external_id": "xhs-red-skill-spec",
        "name": "小红书 Skill 上传规范",
        "raw_description": "官方 Skill 上传规范：SKILL.md 提交、场景标签、安全与原创要求",
        "detail_url": "https://www.xiaohongshu.com",
        "tags": ["小红书", "官方", "规范"],
        "category": "官方规范",
    },
]


class XiaohongshuSkillsAdapter(SourceAdapter):
    source_id = "xiaohongshu_red_skill"
    vendor = "小红书"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        add_platform_record(records, seen, rec, is_xhs_relevant)

    async def fetch(self) -> list[RawSkillRecord]:
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        headers = github_headers()
        timeout = httpx.Timeout(90.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            catalog, github_cases = await self._fetch_redskill_catalog(client)
            catalog_loaded = len(catalog) >= 10

            for item in catalog:
                slug = item.get("slug", "")
                if not slug:
                    continue
                ext_id = f"redskill:{slug}"
                category = item.get("category", "ClawHub")
                desc = item.get("description", "") or f"ClawHub 公开小红书 Skill · {slug}"
                install = item.get("installCommand", "")
                if install:
                    desc = f"{desc} · 安装: {install}"
                source_url = str(item.get("sourceUrl") or "").strip()
                if source_url and not is_aggregate_mirror_url(source_url):
                    detail_url = source_url
                else:
                    detail_url = clawhub_skills_url(slug)
                rec = RawSkillRecord(
                    external_id=ext_id,
                    name=item.get("name") or slug,
                    vendor=self.vendor,
                    source_id=self.source_id,
                    raw_description=desc[:400],
                    detail_url=detail_url,
                    tags=["小红书", "ClawHub", "RedSkill"],
                    install_count=int(item.get("installs") or 0),
                    metadata={
                        "categoryName": category,
                        "slug": slug,
                        "downloads": item.get("downloads"),
                        "installs": item.get("installs"),
                        "risk": item.get("risk"),
                        "installCommand": install,
                        "redskill": True,
                        "catalog": "clawhub",
                        "clawhub": True,
                        "vendorRelevance": {
                            "relevant": True,
                            "prompt_version": PROMPT_VERSION,
                            "source": "redskill_catalog",
                        },
                    },
                )
                self._add_record(records, seen, rec)

            for case in github_cases:
                repo = case.get("repo", "")
                name = case.get("name", "") or repo.split("/")[-1]
                if not repo:
                    continue
                ext_id = f"github-case:{repo}:{name}"
                rec = RawSkillRecord(
                    external_id=ext_id,
                    name=name,
                    vendor=self.vendor,
                    source_id=self.source_id,
                    raw_description=case.get("value", "")[:400] or f"RedSkill 精选 GitHub · {repo}",
                    detail_url=case.get("url") or f"https://github.com/{repo}",
                    tags=["小红书", "RedSkill", "GitHub"],
                    metadata={
                        "repo": repo,
                        "categoryName": "RedSkill 精选",
                        "redskill": True,
                        "catalog": "redskill",
                        "installCommand": case.get("copy", ""),
                    },
                )
                self._add_record(records, seen, rec)

            github_repos = XHS_GITHUB_REPOS if not catalog_loaded else XHS_GITHUB_REPOS[:3]
            for repo, known in github_repos:
                if repo in XHS_REPO_BLOCKLIST:
                    continue
                try:
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["小红书", "GitHub"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="社区",
                        record_filter=is_xhs_relevant,
                    )
                    for rec in batch:
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

            if not catalog_loaded:
                for query in CODE_SEARCH_QUERIES:
                    for item in await search_code_skill_md(client, query, headers, per_page=25):
                        repo = item.get("repository", {}).get("full_name", "")
                        path = item.get("path", "")
                        if not repo or "SKILL.md" not in path or repo in XHS_REPO_BLOCKLIST:
                            continue
                        blob = f"{repo} {path}".lower()
                        if not any(
                            k in blob
                            for k in ("xhs", "xiaohongshu", "redbook", "redskill", "小红书")
                        ):
                            continue
                        prefix = path.replace("/SKILL.md", "")
                        key = f"{repo}:{prefix}"
                        if key in seen:
                            continue
                        skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                        text = await fetch_skill_md_text(client, repo, prefix, headers)
                        fallback_desc = f"小红书 RED Skill · {repo}"
                        if text:
                            skill_name, desc, category = parse_skill_md(
                                text, skill_name, fallback_desc
                            )
                        else:
                            desc, category = fallback_desc, "社区"
                        rec = RawSkillRecord(
                            external_id=key,
                            name=skill_name,
                            vendor=self.vendor,
                            source_id=self.source_id,
                            raw_description=desc,
                            detail_url=item.get("html_url", ""),
                            tags=["小红书", "SKILL.md", category],
                            metadata={"repo": repo, "path": path, "categoryName": category},
                        )
                        self._add_record(records, seen, rec)

                known_repos = {r for r, _ in XHS_GITHUB_REPOS}
                for query in REPO_SEARCH_QUERIES:
                    for item in await search_repositories(client, query, headers, per_page=8):
                        repo = item.get("full_name", "")
                        if (
                            not repo
                            or repo in known_repos
                            or repo in XHS_REPO_BLOCKLIST
                            or not is_dedicated_xhs_repo(repo)
                        ):
                            continue
                        try:
                            batch = await build_records_from_repo(
                                client,
                                repo,
                                vendor=self.vendor,
                                source_id=self.source_id,
                                headers=headers,
                                tags=["小红书", "社区"],
                                roots=("", "skills"),
                                record_filter=is_xhs_relevant,
                            )
                            for rec in batch:
                                self._add_record(records, seen, rec)
                        except Exception:
                            continue

            for rec in await fetch_skillsmp_for_vendor(
                client,
                vendor=self.vendor,
                source_id=self.source_id,
                max_pages=3,
                record_filter=is_xhs_relevant,
            ):
                self._add_record(records, seen, rec)

        for entry in OFFICIAL_ENTRIES:
            rec = RawSkillRecord(
                external_id=entry["external_id"],
                name=entry["name"],
                vendor=self.vendor,
                source_id=self.source_id,
                raw_description=entry["raw_description"],
                detail_url=entry["detail_url"],
                tags=entry["tags"],
                metadata={"categoryName": entry.get("category", "RED Skill"), "official": True, "catalog": "official"},
            )
            self._add_record(records, seen, rec)

        return await apply_vendor_relevance_split(self.vendor, records)

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        """仅 redskill.org 官方目录 + 官方文档入口，不含 GitHub/SkillsMP。"""
        from app.adapters.common.official_entries import records_from_official_entries

        records = records_from_official_entries(
            source_id=self.source_id, vendor=self.vendor, entries=OFFICIAL_ENTRIES
        )
        seen = {r.external_id for r in records}
        timeout = httpx.Timeout(60.0, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            catalog, _github_cases = await self._fetch_redskill_catalog(client)
            for item in catalog:
                slug = item.get("slug", "")
                if not slug:
                    continue
                ext_id = f"redskill:{slug}"
                if ext_id in seen:
                    continue
                category = item.get("category", "RED Skill")
                desc = item.get("description", "") or f"RED Skill 官方目录 · {slug}"
                install = item.get("installCommand", "")
                if install:
                    desc = f"{desc} · 安装: {install}"
                detail_url = str(item.get("sourceUrl") or "").strip() or f"{REDSKILL_DIRECTORY_URL}#{slug}"
                rec = RawSkillRecord(
                    external_id=ext_id,
                    name=str(item.get("name") or slug),
                    vendor=self.vendor,
                    source_id=self.source_id,
                    raw_description=desc,
                    detail_url=detail_url,
                    tags=["小红书", "RED Skill", "官方"],
                    metadata={"categoryName": category, "official": True, "catalog": "official"},
                )
                self._add_record(records, seen, rec)
        return records

    async def _fetch_redskill_catalog(
        self, client: httpx.AsyncClient
    ) -> tuple[list[dict], list[dict]]:
        try:
            resp = await get_with_retry(
                client,
                REDSKILL_CATALOG_URL,
                headers={"User-Agent": "SkillGetter/1.0", "Accept": "application/json"},
            )
            if resp.status_code != 200:
                return [], []
            data = resp.json()
            rows = data.get("rows", [])
            github_cases = data.get("githubCases", [])
            if isinstance(rows, list):
                return rows, github_cases if isinstance(github_cases, list) else []
        except Exception:
            pass
        return [], []
