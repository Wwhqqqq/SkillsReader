"""
GitHub Skill 仓库监控 Adapter —— 监控含 SKILL.md 的仓库。

数据来源: GitHub REST API（需 GITHUB_TOKEN 提高限流）
抓取方式: 遍历 WATCH_REPOS 列表，读仓库内容与 SKILL.md
yaml: adapter: github_watch, supplemental: true
"""

from __future__ import annotations

import base64
import re

import httpx

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.core.config import get_settings

WATCH_REPOS = [
    "anthropics/skills",
    "vercel-labs/agent-skills",
    "openai/skills",
]


class GitHubWatchAdapter(SourceAdapter):
    source_id = "github_watch"
    vendor = "GitHub"

    async def fetch(self) -> list[RawSkillRecord]:
        settings = get_settings()
        token = settings.github_token
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "IKnow/1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        records: list[RawSkillRecord] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for repo in WATCH_REPOS:
                try:
                    resp = await client.get(
                        f"https://api.github.com/repos/{repo}/contents",
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        continue
                    for item in resp.json():
                        if item.get("type") != "dir":
                            continue
                        name = item.get("name", "")
                        if name.startswith("."):
                            continue
                        desc = await self._fetch_skill_md(client, repo, name, headers)
                        records.append(
                            RawSkillRecord(
                                external_id=f"{repo}/{name}",
                                name=name,
                                vendor=self.vendor,
                                source_id=self.source_id,
                                raw_description=desc,
                                detail_url=item.get("html_url", f"https://github.com/{repo}"),
                                tags=["github", repo.split("/")[0]],
                                metadata={"repo": repo},
                            )
                        )
                except httpx.HTTPError:
                    continue

            if token:
                try:
                    resp = await client.get(
                        "https://api.github.com/search/code",
                        params={"q": "filename:SKILL.md", "per_page": 30},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        for item in resp.json().get("items", []):
                            repo = item.get("repository", {}).get("full_name", "")
                            path = item.get("path", "")
                            skill_name = path.split("/")[0] if "/" in path else repo.split("/")[-1]
                            records.append(
                                RawSkillRecord(
                                    external_id=f"{repo}:{path}",
                                    name=skill_name,
                                    vendor=self.vendor,
                                    source_id=self.source_id,
                                    raw_description=f"GitHub SKILL.md in {repo}",
                                    detail_url=item.get("html_url", ""),
                                    tags=["github", "SKILL.md"],
                                    metadata={"repo": repo, "path": path},
                                )
                            )
                except httpx.HTTPError:
                    pass

        seen: set[str] = set()
        unique: list[RawSkillRecord] = []
        for r in records:
            if r.external_id not in seen:
                seen.add(r.external_id)
                unique.append(r)
        return unique

    async def _fetch_skill_md(
        self, client: httpx.AsyncClient, repo: str, skill_dir: str, headers: dict
    ) -> str:
        try:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/contents/{skill_dir}/SKILL.md",
                headers=headers,
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            content = data.get("content", "")
            if content:
                text = base64.b64decode(content).decode("utf-8", errors="ignore")
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                body = " ".join(lines[:5])
                return re.sub(r"[#*`]", "", body)[:300]
        except Exception:
            pass
        return ""
