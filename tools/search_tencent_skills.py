"""
搜索所有腾讯系 Skill 在各个渠道的情况。
渠道：
1. ClawHub (clawhub.ai) — 社区市场
2. SkillsMP (skillsmp.com) — 社区市场
3. GitHub - code search (SKILL.md)
4. GitHub - repo search
5. Tencent Cloud MCP plaza (cloud.tencent.com/developer/mcp)
6. 阿里云 Skills Portal (skills.aliyun.com)
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

# 要搜索的腾讯系 Skills
TENCENT_SKILLS = [
    "腾讯自选股-金融数据查询",
    "腾讯文档",
    "腾讯新闻",
    "腾讯ima",
    "腾讯文档PDFKit",
    "腾讯文档高考志愿填报助手",
    "腾讯云通用文字识别OCR",
    "Skill安全审计（云鼎实验室）",
    "腾讯地图·地图助手",
    "腾讯乐享",
    "腾讯云CloudBase",
    "腾讯会议",
    "腾讯微云",
    "元宝搜索标准版",
    "EdgeOne Pages Deploy",
    "AndonQ",
    "腾讯问卷",
    "腾讯云广告文字识别OCR",
    "腾讯云表格识别OCR",
    "腾讯校园招聘",
    "MigraQ",
    "腾讯云解决方案PPT制作",
    "腾讯云可观测平台API",
    "腾讯云COS",
    "腾讯云试题批改",
    "腾讯云实时文档抽取",
    "腾讯电子签",
    "腾讯游戏防沉迷家长管控助手",
    "腾讯云竞品分析",
    "公益文书助手",
    "腾讯文档智能页面",
    "腾讯云日志服务CLS",
    "腾讯云知",
    "鹅厂辟谣助手",
    "腾讯音乐校招助手",
    "腾讯技术公益智能助手",
    "腾讯音乐人AI助手",
    "腾讯云COS向量",
]

# 每个 skill 的别名/关键词映射
SKILL_KEYWORDS: dict[str, list[str]] = {
    "腾讯自选股-金融数据查询": ["自选股", "stock", "金融数据", "tencent-stock"],
    "腾讯文档": ["腾讯文档", "tencent-docs", "docs.qq.com", "tendoc"],
    "腾讯新闻": ["腾讯新闻", "news.qq", "tencent-news"],
    "腾讯ima": ["ima", "ima.qq.com", "腾讯ima"],
    "腾讯文档PDFKit": ["PDFKit", "pdf", "腾讯文档pdf"],
    "腾讯文档高考志愿填报助手": ["高考志愿", "志愿填报", "gaokao"],
    "腾讯云通用文字识别OCR": ["OCR", "文字识别", "通用ocr"],
    "Skill安全审计（云鼎实验室）": ["安全审计", "云鼎", "security-audit", "ydlab"],
    "腾讯地图·地图助手": ["腾讯地图", "map", "qqmap", "位置服务"],
    "腾讯乐享": ["乐享", "lexiangla", "tencent-lexiang"],
    "腾讯云CloudBase": ["CloudBase", "cloudbase", "云开发"],
    "腾讯会议": ["腾讯会议", "tencent-meeting", "meeting.tencent"],
    "腾讯微云": ["微云", "weiyun", "tencent-weiyun"],
    "元宝搜索标准版": ["元宝", "yuanbao", "hunyuan-search"],
    "EdgeOne Pages Deploy": ["EdgeOne", "edgeone", "teo"],
    "AndonQ": ["AndonQ", "andonq", "智能客服"],
    "腾讯问卷": ["腾讯问卷", "wj.qq.com", "tencent-survey"],
    "腾讯云广告文字识别OCR": ["广告ocr", "广告文字识别", "ad-ocr"],
    "腾讯云表格识别OCR": ["表格ocr", "table-ocr", "表格识别"],
    "腾讯校园招聘": ["校园招聘", "campus", "校招"],
    "MigraQ": ["MigraQ", "migraq", "迁移服务"],
    "腾讯云解决方案PPT制作": ["解决方案ppt", "ppt", "方案制作"],
    "腾讯云可观测平台API": ["可观测", "observability", "监控"],
    "腾讯云COS": ["COS", "cos", "对象存储"],
    "腾讯云试题批改": ["试题批改", "批改", "exam-grading"],
    "腾讯云实时文档抽取": ["文档抽取", "doc-extract", "实时抽取"],
    "腾讯电子签": ["电子签", "esign", "tencent-esign"],
    "腾讯游戏防沉迷家长管控助手": ["防沉迷", "游戏管控", "parent-control"],
    "腾讯云竞品分析": ["竞品分析", "competitive", "对比分析"],
    "公益文书助手": ["公益文书", "公益", "public-welfare"],
    "腾讯文档智能页面": ["智能页面", "smart-page", "文档页面"],
    "腾讯云日志服务CLS": ["CLS", "日志服务", "cls"],
    "腾讯云知": ["云知", "lexiangla", "乐享"],
    "鹅厂辟谣助手": ["辟谣", "rumor", "fact-check"],
    "腾讯音乐校招助手": ["音乐校招", "music-campus"],
    "腾讯技术公益智能助手": ["技术公益", "公益", "tech-welfare"],
    "腾讯音乐人AI助手": ["音乐人", "music-artist", "tme"],
    "腾讯云COS向量": ["COS向量", "vector", "向量"],
}


@dataclass
class SearchResult:
    skill_name: str
    clawhub: str = ""
    skillsmp: str = ""
    github_repo: str = ""
    github_code: str = ""
    tencent_mcp: str = ""
    aliyun: str = ""
    notes: list[str] = field(default_factory=list)


async def search_clawhub(client: httpx.AsyncClient, name: str, keywords: list[str]) -> str:
    """在 ClawHub 搜索。"""
    for q in keywords[:3]:
        try:
            resp = await client.get(
                "https://clawhub.ai/api/v1/search",
                params={"q": q, "limit": 5, "nonSuspiciousOnly": "true"},
                headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                results = resp.json().get("results") or []
                for item in results:
                    title = (item.get("title") or item.get("name") or "").lower()
                    desc = (item.get("description") or "").lower()
                    slug = item.get("slug", "")
                    # match by keyword or name fragment
                    if any(k.lower() in title or k.lower() in desc for k in keywords[:3]):
                        return f"https://clawhub.ai/skill/{slug}"
                # also try direct slug
                for q2 in keywords[:2]:
                    resp2 = await client.get(
                        f"https://clawhub.ai/api/v1/skills/{q2.lower().replace(' ', '-')}",
                        headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
                        timeout=10.0,
                    )
                    if resp2.status_code == 200:
                        data = resp2.json()
                        skill = data.get("skill") or data
                        if isinstance(skill, dict) and skill.get("slug"):
                            return f"https://clawhub.ai/skill/{skill['slug']}"
        except Exception:
            pass
    return ""


async def search_skillsmp(client: httpx.AsyncClient, name: str, keywords: list[str]) -> str:
    """在 SkillsMP 搜索。"""
    for q in keywords[:3]:
        try:
            resp = await client.get(
                "https://skillsmp.com/api/v1/skills/search",
                params={"q": q, "page": 1, "limit": 10, "sortBy": "stars"},
                headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                results = resp.json().get("results") or resp.json().get("data") or []
                if isinstance(results, list):
                    for item in results:
                        title = (item.get("title") or item.get("name") or "").lower()
                        desc = (item.get("description") or "").lower()
                        slug = item.get("slug") or item.get("id", "")
                        if any(k.lower() in title or k.lower() in desc for k in keywords[:3]):
                            return f"https://skillsmp.com/skills/{slug}"
        except Exception:
            pass
    return ""


async def search_github_repo(client: httpx.AsyncClient, name: str, keywords: list[str]) -> str:
    """搜索 GitHub 仓库。"""
    for q in keywords[:2]:
        try:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": f"{q} skill", "per_page": 5, "sort": "updated"},
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "SkillGetter/1.0",
                         "Authorization": "token github_pat_11BFSY6YI0d3J3c5I7A6wT_5N5r5F5k5L5m5Q5x5Z5a5S5d5F5g5H5j5K5l5Z5x5C5v5B5n5M5"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                for repo in resp.json().get("items", []):
                    name_lower = repo.get("full_name", "").lower()
                    desc = (repo.get("description") or "").lower()
                    if any(k.lower() in name_lower or k.lower() in desc for k in keywords[:2]):
                        return repo.get("html_url", "")
        except Exception:
            pass
    return ""


async def search_github_code(client: httpx.AsyncClient, name: str, keywords: list[str]) -> str:
    """搜索 GitHub code (SKILL.md)。"""
    for q in keywords[:2]:
        try:
            resp = await client.get(
                "https://api.github.com/search/code",
                params={"q": f"filename:SKILL.md {q}", "per_page": 5},
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "SkillGetter/1.0",
                         "Authorization": "token github_pat_11BFSY6YI0d3J3c5I7A6wT_5N5r5F5k5L5m5Q5x5Z5a5S5d5F5g5H5j5K5l5Z5x5C5v5B5n5M5"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    path = item.get("path", "")
                    repo = item.get("repository", {}).get("full_name", "")
                    if any(k.lower() in path.lower() or k.lower() in repo.lower() for k in keywords[:2]):
                        html_url = item.get("html_url", "")
                        # convert to raw content URL
                        raw_url = html_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                        return html_url
        except Exception:
            pass
    return ""


async def search_tencent_mcp(client: httpx.AsyncClient, name: str, keywords: list[str]) -> str:
    """在腾讯云 MCP 广场搜索。通过 HTML 页面搜索。"""
    for q in keywords[:2]:
        try:
            resp = await client.get(
                "https://cloud.tencent.com/developer/mcp",
                params={"search": q},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                timeout=15.0,
            )
            if resp.status_code == 200 and resp.text:
                # Simple check — if keyword appears in page text, it's there
                if q.lower() in resp.text.lower():
                    return f"https://cloud.tencent.com/developer/mcp?search={q}"
        except Exception:
            pass
    return ""


async def search_aliyun(client: httpx.AsyncClient, name: str, keywords: list[str]) -> str:
    """在阿里云 Skills Portal 搜索。"""
    for q in keywords[:2]:
        try:
            resp = await client.get(
                "https://skills.aliyun.com/api/public/skills",
                params={"page": 1, "pageSize": 500},
                headers={"Accept": "application/json", "User-Agent": "IKnow/1.0"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("code") == 200:
                    for group in payload.get("data") or []:
                        if not isinstance(group, dict):
                            continue
                        for item in group.get("list") or []:
                            if not isinstance(item, dict):
                                continue
                            skill_name = (item.get("skillName") or item.get("name") or "").lower()
                            desc = (item.get("summary") or item.get("description") or "").lower()
                            if any(k.lower() in skill_name or k.lower() in desc for k in keywords[:3]):
                                return f"https://skills.aliyun.com/skills/{item.get('skillName', '')}"
        except Exception:
            pass
    return ""


async def search_one_skill(client: httpx.AsyncClient, name: str) -> SearchResult:
    result = SearchResult(skill_name=name)
    keywords = SKILL_KEYWORDS.get(name, [name])

    # Add some generic keywords
    kw_set = list(dict.fromkeys(keywords + [name]))

    tasks = [
        search_clawhub(client, name, kw_set),
        search_skillsmp(client, name, kw_set),
        search_github_repo(client, name, kw_set),
        search_github_code(client, name, kw_set),
        search_tencent_mcp(client, name, kw_set),
        search_aliyun(client, name, kw_set),
    ]
    result.clawhub, result.skillsmp, result.github_repo, result.github_code, result.tencent_mcp, result.aliyun = await asyncio.gather(*tasks)
    return result


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        results: list[SearchResult] = []
        for i, name in enumerate(TENCENT_SKILLS):
            print(f"[{i+1}/{len(TENCENT_SKILLS)}] Searching: {name}")
            result = await search_one_skill(client, name)
            results.append(result)
            # Be nice to APIs
            await asyncio.sleep(0.5)

        # Print results
        print("\n\n===== 搜索结果 =====\n")
        print(f"| Skill 名称 | ClawHub | SkillsMP | GitHub Repo | GitHub Code | 腾讯云MCP | 阿里云 |")
        print(f"|---|---|---|---|---|---|---|")
        for r in results:
            found = any([r.clawhub, r.skillsmp, r.github_repo, r.github_code, r.tencent_mcp, r.aliyun])
            clawhub_link = f"[✓]({r.clawhub})" if r.clawhub else "✗"
            skillsmp_link = f"[✓]({r.skillsmp})" if r.skillsmp else "✗"
            github_repo_link = f"[✓]({r.github_repo})" if r.github_repo else "✗"
            github_code_link = f"[✓]({r.github_code})" if r.github_code else "✗"
            mcp_link = f"[✓]({r.tencent_mcp})" if r.tencent_mcp else "✗"
            aliyun_link = f"[✓]({r.aliyun})" if r.aliyun else "✗"
            print(f"| {r.skill_name} | {clawhub_link} | {skillsmp_link} | {github_repo_link} | {github_code_link} | {mcp_link} | {aliyun_link} |")

        # Collate results
        print("\n\n===== 找到的 Skill 详细链接 =====\n")
        for r in results:
            links = []
            if r.clawhub: links.append(f"ClawHub: {r.clawhub}")
            if r.skillsmp: links.append(f"SkillsMP: {r.skillsmp}")
            if r.github_repo: links.append(f"GitHub Repo: {r.github_repo}")
            if r.github_code: links.append(f"GitHub Code: {r.github_code}")
            if r.tencent_mcp: links.append(f"腾讯云MCP: {r.tencent_mcp}")
            if r.aliyun: links.append(f"阿里云: {r.aliyun}")
            if links:
                print(f"### {r.skill_name}")
                for l in links:
                    print(f"- {l}")
                print()


if __name__ == "__main__":
    asyncio.run(main())
