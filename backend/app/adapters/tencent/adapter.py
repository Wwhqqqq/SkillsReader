"""
腾讯 Agent Skill 社区 Adapter —— ClawHub、SkillsMP、GitHub、微信/云开发/企业微信官方锚点。

yaml: adapter: wechat_skillhub
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
    TENCENT_REPO_BLOCKLIST,
    is_dedicated_tencent_repo,
    is_tencent_relevant,
)
from app.adapters.common.record_utils import add_platform_record
from app.adapters.tencent.catalog import fetch_clawhub_tencent, fetch_skillsmp_tencent
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

TENCENT_GITHUB_REPOS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("TencentCloudBase/skills", None),
    ("TencentCloudBase/awesome-miniprogram-skills", None),
    ("TencentCloudBase/cloudbase-skills", None),
    ("TencentCloudBase/CloudBase-MCP", None),
    ("wechat-miniprogram/ai-mode-skills", None),
    ("WecomTeam/wecom-openclaw-plugin", ("skills",)),
    ("Tencent/wechat-miniprogram-demo", None),
    ("wechat-miniprogram/miniprogram-demo", None),
)

OFFICIAL_GITHUB_REPOS = frozenset(
    {
        "TencentCloudBase/skills",
        "TencentCloudBase/awesome-miniprogram-skills",
        "TencentCloudBase/cloudbase-skills",
        "TencentCloudBase/CloudBase-MCP",
        "TencentCloudBase/mp-skills",
        "wechat-miniprogram/ai-mode-skills",
        "WecomTeam/wecom-openclaw-plugin",
    }
)

CODE_SEARCH_QUERIES = (
    "filename:SKILL.md repo:TencentCloudBase",
    "filename:SKILL.md wechat miniprogram",
    "filename:SKILL.md 微信小程序",
    "filename:SKILL.md wework OR wecom",
    "filename:SKILL.md openclaw-weixin",
    "filename:SKILL.md cloudbase",
    "filename:SKILL.md hunyuan",
)

REPO_SEARCH_QUERIES = (
    "tencent skill agent",
    "wechat skill agent openclaw",
    "wecom openclaw skill",
    "微信小程序 skill agent",
    "cloudbase skill agent",
    "mp-skills miniprogram",
)

OFFICIAL_PLATFORM_IDS = frozenset(
    {
        "wechat-miniprogram-ai-guide",
        "wechat-miniprogram-ai-agent",
        "wechat-miniprogram-ai-integration",
        "wechat-open-platform-ai",
        "cloudbase-mp-skills",
        "mp-skills-cli",
        "openclaw-weixin-official",
        "wecom-openclaw-plugin-official",
        "tencent-cloud-adp",
        "tencent-mcp-plaza",
    }
)

OFFICIAL_ENTRIES = [
    {
        "external_id": "wechat-miniprogram-ai-guide",
        "name": "微信小程序 AI 开发模式",
        "raw_description": "微信官方小程序 AI 开发模式接入指南，SKILL.md + mcp.json 规范",
        "detail_url": "https://developers.weixin.qq.com/miniprogram/dev/ai/guide.html",
        "tags": ["腾讯", "微信小程序", "官方", "AI开发"],
        "category": "AI开发",
    },
    {
        "external_id": "wechat-miniprogram-ai-agent",
        "name": "小程序 AI Agent 能力",
        "raw_description": "微信小程序 AI Agent 组件与对话能力接入文档",
        "detail_url": "https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/agent.html",
        "tags": ["腾讯", "微信小程序", "官方", "Agent"],
        "category": "Agent",
    },
    {
        "external_id": "wechat-miniprogram-ai-integration",
        "name": "小程序 agent.skills 集成规范",
        "raw_description": "app.json 中 agent.skills[] 声明方式；每小程序最多约 30 个 Skill，无全局公开列表 API",
        "detail_url": "https://developers.weixin.qq.com/miniprogram/dev/ai/integration.html",
        "tags": ["腾讯", "微信小程序", "官方", "集成"],
        "category": "官方规范",
    },
    {
        "external_id": "wechat-open-platform-ai",
        "name": "微信开放平台",
        "raw_description": "微信开放平台 AI 相关接口与第三方接入说明",
        "detail_url": "https://developers.weixin.qq.com/doc/oplatform/open/intro.html",
        "tags": ["腾讯", "微信开放平台", "官方"],
        "category": "开放平台",
    },
    {
        "external_id": "cloudbase-mp-skills",
        "name": "CloudBase 小程序 Skill 教程",
        "raw_description": "云开发 mp-skills CLI 与小程序 Skill 快速入门",
        "detail_url": "https://docs.cloudbase.net/en/mp-skill/quick-start",
        "tags": ["腾讯", "CloudBase", "官方", "小程序"],
        "category": "云开发",
    },
    {
        "external_id": "mp-skills-cli",
        "name": "mp-skills CLI（TencentCloudBase）",
        "raw_description": "npx mp-skills find/add — 发现与安装 awesome-miniprogram-skills 等官方 demo Skill",
        "detail_url": "https://github.com/TencentCloudBase/mp-skills",
        "tags": ["腾讯", "CloudBase", "官方", "CLI"],
        "category": "官方工具",
    },
    {
        "external_id": "openclaw-weixin-official",
        "name": "OpenClaw 微信通道插件（官方）",
        "raw_description": "Tencent/openclaw-weixin — npm @tencent-weixin/openclaw-weixin 个人微信 OpenClaw 通道",
        "detail_url": "https://github.com/Tencent/openclaw-weixin",
        "tags": ["腾讯", "微信", "官方", "OpenClaw"],
        "category": "官方插件",
    },
    {
        "external_id": "wecom-openclaw-plugin-official",
        "name": "企业微信 OpenClaw 插件（官方）",
        "raw_description": "WecomTeam/wecom-openclaw-plugin — 内置约 15 个企业微信 Skill（通讯录/文档/会议/智能表格等）",
        "detail_url": "https://github.com/WecomTeam/wecom-openclaw-plugin",
        "tags": ["腾讯", "企业微信", "官方", "OpenClaw"],
        "category": "官方插件",
    },
    {
        "external_id": "tencent-cloud-adp",
        "name": "腾讯云 ADP Agent 开发平台",
        "raw_description": "DescribeSkillSummaryList 等 ADP Skill/Agent API（需 SpaceId 与云账号，租户私有列表）",
        "detail_url": "https://cloud.tencent.com/document/product/1759/132540",
        "tags": ["腾讯", "腾讯云", "官方", "ADP"],
        "category": "企业平台",
    },
    {
        "external_id": "tencent-mcp-plaza",
        "name": "腾讯云 MCP 广场",
        "raw_description": "约 1000+ MCP 服务目录，含 CloudBase MCP、企业微信机器人、腾讯文档/位置服务等（HTML 目录，无公开 list API）",
        "detail_url": "https://cloud.tencent.com/developer/mcp",
        "tags": ["腾讯", "腾讯云", "官方", "MCP"],
        "category": "MCP 广场",
    },
    {
        "external_id": "skillhub-cn-mirror",
        "name": "SkillHub.cn（ClawHub 镜像）",
        "raw_description": "skillhub.tencent.com → skillhub.cn，ClawHub 中文镜像；收录通过 ClawHub API 抓取",
        "detail_url": "https://skillhub.cn/",
        "tags": ["腾讯", "社区", "SkillHub"],
        "category": "社区生态",
        "catalog": "community",
    },
    {
        "external_id": "tencent-agent-skills-ecosystem",
        "name": "腾讯 Agent Skill 社区生态",
        "raw_description": "无微信官方 Skill 全局列表；社区分布于 ClawHub/SkillsMP/GitHub（TencentCloudBase/skills、wecom-openclaw 等）",
        "detail_url": "https://developers.weixin.qq.com/miniprogram/dev/ai/guide.html",
        "tags": ["腾讯", "社区", "生态说明"],
        "category": "社区生态",
        "catalog": "community",
    },
]


class WechatSkillhubAdapter(SourceAdapter):
    source_id = "wechat_skillhub"
    vendor = "腾讯"

    def _add_record(self, records: list[RawSkillRecord], seen: set[str], rec: RawSkillRecord) -> None:
        add_platform_record(records, seen, rec, is_tencent_relevant)

    async def fetch(self) -> list[RawSkillRecord]:
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        headers = github_headers()
        timeout = httpx.Timeout(90.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for rec in await fetch_clawhub_tencent(
                client, source_id=self.source_id, vendor=self.vendor
            ):
                self._add_record(records, seen, rec)

            for rec in await fetch_skillsmp_tencent(
                client, source_id=self.source_id, vendor=self.vendor, max_pages=4
            ):
                self._add_record(records, seen, rec)

            for repo, known in TENCENT_GITHUB_REPOS:
                try:
                    is_official_repo = repo in OFFICIAL_GITHUB_REPOS
                    batch = await build_records_from_repo(
                        client,
                        repo,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        headers=headers,
                        tags=["腾讯", "GitHub", "官方" if is_official_repo else "社区"],
                        roots=("", "skills"),
                        known_prefixes=known,
                        category_default="官方" if is_official_repo else "社区",
                        record_filter=is_tencent_relevant,
                    )
                    for rec in batch:
                        meta = dict(rec.metadata or {})
                        if is_official_repo:
                            meta.setdefault("catalog", "official_github")
                            meta["official"] = True
                        else:
                            meta.setdefault("catalog", "github")
                        rec.metadata = meta
                        self._add_record(records, seen, rec)
                except Exception:
                    continue

            for query in CODE_SEARCH_QUERIES:
                for item in await search_code_skill_md(client, query, headers, per_page=20):
                    repo = item.get("repository", {}).get("full_name", "")
                    path = item.get("path", "")
                    if not repo or "SKILL.md" not in path or repo in TENCENT_REPO_BLOCKLIST:
                        continue
                    blob = f"{repo} {path}".lower()
                    if not any(
                        k in blob
                        for k in (
                            "wechat",
                            "weixin",
                            "微信",
                            "tencent",
                            "wecom",
                            "wework",
                            "cloudbase",
                            "miniprogram",
                            "hunyuan",
                        )
                    ):
                        continue
                    prefix = path.replace("/SKILL.md", "")
                    key = f"{repo}:{prefix}"
                    if key in seen:
                        continue
                    skill_name = prefix.split("/")[-1] if "/" in prefix else repo.split("/")[-1]
                    text = await fetch_skill_md_text(client, repo, prefix, headers)
                    fallback_desc = f"腾讯生态 SKILL.md · {repo}"
                    if text:
                        skill_name, desc, category = parse_skill_md(text, skill_name, fallback_desc)
                    else:
                        desc, category = fallback_desc, "社区"
                    catalog = "official_github" if repo in OFFICIAL_GITHUB_REPOS else "github"
                    rec = RawSkillRecord(
                        external_id=key,
                        name=skill_name,
                        vendor=self.vendor,
                        source_id=self.source_id,
                        raw_description=desc,
                        detail_url=item.get("html_url", ""),
                        tags=["腾讯", "SKILL.md", category],
                        metadata={
                            "repo": repo,
                            "path": path,
                            "categoryName": category,
                            "catalog": catalog,
                            "official": repo in OFFICIAL_GITHUB_REPOS,
                        },
                    )
                    self._add_record(records, seen, rec)

            known_repos = {r for r, _ in TENCENT_GITHUB_REPOS}
            extra_repos: set[str] = set()
            for query in REPO_SEARCH_QUERIES:
                for item in await search_repositories(client, query, headers, per_page=8):
                    name = item.get("full_name", "")
                    if not name or name in known_repos or name in TENCENT_REPO_BLOCKLIST:
                        continue
                    if not is_dedicated_tencent_repo(name):
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
                        tags=["腾讯", "GitHub"],
                        roots=("", "skills"),
                        record_filter=is_tencent_relevant,
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
        """仅微信/腾讯官方开发者文档入口，不含 GitHub/SkillsMP/ClawHub。"""
        from app.adapters.common.official_entries import records_from_official_entries

        return records_from_official_entries(
            source_id=self.source_id,
            vendor=self.vendor,
            entries=OFFICIAL_ENTRIES,
            official_ids=OFFICIAL_PLATFORM_IDS,
        )
