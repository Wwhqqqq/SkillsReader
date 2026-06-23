"""
SkillsMP 目录抓取 —— 各公司 adapter 共用的社区 Skill 发现源。
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable
from typing import Any

import httpx

from app.adapters.base import RawSkillRecord
from app.core.config import get_settings
from app.services.enrichment.vendor_relevance import filter_records_by_vendor_relevance

logger = logging.getLogger(__name__)

SKILLSMP_SEARCH_URL = "https://skillsmp.com/api/v1/skills/search"
MAX_EXTERNAL_ID_LEN = 128

VENDOR_SEARCH_QUERIES: dict[str, tuple[str, ...]] = {
    "美团": ("meituan", "美团"),
    "阿里": ("aliyun", "阿里云", "dashscope"),
    "字节": ("volcengine", "coze", "扣子", "bytedance"),
    "知乎": ("zhihu", "知乎"),
    "小红书": ("xiaohongshu", "redbook", "小红书"),
    "哔哩哔哩": ("bilibili", "哔哩哔哩", "b站", "B站"),
    "快手": ("kuaishou", "快手", "kwai", "maxhub-kuaishou"),
    "滴滴": ("didi", "滴滴", "didichuxing", "didi-ride"),
    "拼多多": ("pinduoduo", "拼多多", "pdd", "多多进宝", "pdd-coupon"),
    "携程": ("ctrip", "携程", "wendao", "问道", "tripgenie", "ctrip-wendao", "ctrip-flight", "ctrip-hotel"),
    "得物": ("dewu", "poizon", "得物", "得物开放平台", "open.dewu", "dewu-seeding", "dw-skills", "poizon-l10n"),
    "腾讯": (
        "wechat", "tencent", "wecom", "wework", "微信", "腾讯", "企业微信",
        "hunyuan", "混元", "miniprogram", "TencentCloudBase", "WecomTeam", "openclaw-weixin", "cloudbase",
    ),
}

VENDOR_KEYWORD: dict[str, re.Pattern[str]] = {
    "美团": re.compile(r"meituan|美团|dianping|大众点评", re.I),
    "阿里": re.compile(r"aliyun|阿里云|dashscope|通义|百炼", re.I),
    "字节": re.compile(r"volcengine|coze|扣子|bytedance|字节|火山", re.I),
    "知乎": re.compile(r"zhihu|知乎", re.I),
    "小红书": re.compile(
        r"xhs|xiaohongshu|redbook|redskill|rednote|小红书|红书", re.I
    ),
    "哔哩哔哩": re.compile(r"bilibili|bili-|哔哩|b站|B站|bvid", re.I),
    "快手": re.compile(r"kuaishou|快手|kwai|maxhub-kuaishou|v\.kuaishou", re.I),
    "滴滴": re.compile(r"didi|滴滴|didichuxing|didi-ride|DIDI_MCP|mcp\.didichuxing", re.I),
    "拼多多": re.compile(r"pinduoduo|拼多多|pdd-|pdd_|open\.pinduoduo|多多进宝|mcp-cn-pinduoduo", re.I),
    "携程": re.compile(
        r"ctrip|携程|wendao|问道|tripgenie|trips-ai|"
        r"flights\.ctrip|trip\.com|ctrip-flight|ctrip-hotel|ctrip-wendao",
        re.I,
    ),
    "得物": re.compile(
        r"dewu|poizon|得物|open\.dewu|open\.poizon|"
        r"dewu-seeding|dw-skills|poizon-l10n|specfusion.*dewu|source=dewu",
        re.I,
    ),
    "腾讯": re.compile(
        r"wechat|weixin|微信|miniprogram|小程序|wecom|wework|企业微信|"
        r"TencentCloudBase|WecomTeam|cloudbase|混元|hunyuan|openclaw-weixin|"
        r"tencent-docs|docs\.qq\.com|tencent-cos|tencent-meeting",
        re.I,
    ),
}

SKILLSMP_REPO_SKIP = re.compile(
    r"github\.com/[^/]+/(zhihu-plus-plus|MalSkillBench)", re.I
)


def _github_repo_from_url(url: str) -> str:
    if not url or "github.com/" not in url:
        return ""
    path = url.split("github.com/", 1)[1].strip("/").split("?")[0]
    parts = path.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return path


def skillsmp_external_id(skill_id: str) -> str:
    ext = f"skillsmp:{skill_id}"
    if len(ext) <= MAX_EXTERNAL_ID_LEN:
        return ext
    digest = hashlib.sha256(skill_id.encode()).hexdigest()[:32]
    return f"skillsmp:{digest}"


def _skillsmp_headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "SkillGetter/1.0"}
    api_key = get_settings().skillsmp_api_key.strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def record_from_skillsmp(
    item: dict[str, Any],
    *,
    source_id: str,
    vendor: str,
) -> RawSkillRecord:
    skill_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or skill_id or "SkillsMP Skill")
    desc = str(item.get("description") or "")[:400]
    github = str(item.get("githubUrl") or "")
    detail = str(item.get("skillUrl") or github or "https://skillsmp.com")
    stars = int(item.get("stars") or 0)
    repo = _github_repo_from_url(github)
    return RawSkillRecord(
        external_id=skillsmp_external_id(skill_id),
        name=name,
        vendor=vendor,
        source_id=source_id,
        raw_description=desc or f"SkillsMP · {vendor} · {name}",
        detail_url=detail,
        tags=[vendor, "SkillsMP", "社区"],
        install_count=stars,
        metadata={
            "categoryName": "SkillsMP",
            "catalog": "skillsmp",
            "skillsmpId": skill_id,
            "repo": repo,
            "githubUrl": github,
            "skillsmp": True,
            "stars": stars,
        },
    )


def is_vendor_skillsmp_relevant(vendor: str, rec: RawSkillRecord) -> bool:
    pattern = VENDOR_KEYWORD.get(vendor)
    if not pattern:
        return True
    blob = " ".join(
        [
            rec.name or "",
            rec.external_id or "",
            rec.raw_description or "",
            str((rec.metadata or {}).get("repo") or ""),
            str((rec.metadata or {}).get("githubUrl") or ""),
        ]
    )
    return bool(pattern.search(blob))


def dedupe_skillsmp_records(records: list[RawSkillRecord]) -> list[RawSkillRecord]:
    """按 githubUrl / repo / 名称去重，保留 stars 最高的一条。"""
    best: dict[str, RawSkillRecord] = {}
    for rec in records:
        meta = rec.metadata or {}
        github = str(meta.get("githubUrl") or "").strip().lower()
        repo = str(meta.get("repo") or "").strip().lower()
        name_key = (rec.name or "").strip().lower()
        key = github or repo or name_key or rec.external_id
        prev = best.get(key)
        if prev is None or rec.install_count > prev.install_count:
            best[key] = rec
    return list(best.values())


async def fetch_skillsmp_for_vendor(
    client: httpx.AsyncClient,
    *,
    vendor: str,
    source_id: str,
    queries: tuple[str, ...] | None = None,
    max_pages: int = 3,
    limit: int = 50,
    record_filter: Callable[[RawSkillRecord], bool] | None = None,
) -> list[RawSkillRecord]:
    search_queries = queries or VENDOR_SEARCH_QUERIES.get(vendor, (vendor,))
    records: list[RawSkillRecord] = []
    seen: set[str] = set()
    headers = _skillsmp_headers()

    for query in search_queries:
        for page in range(1, max_pages + 1):
            try:
                resp = await client.get(
                    SKILLSMP_SEARCH_URL,
                    params={
                        "q": query,
                        "page": page,
                        "limit": limit,
                        "sortBy": "stars",
                    },
                    headers=headers,
                    timeout=60.0,
                )
                if resp.status_code == 429:
                    logger.warning(
                        "SkillsMP rate limited vendor=%s q=%s page=%s — returning partial",
                        vendor,
                        query,
                        page,
                    )
                    break
                if resp.status_code != 200:
                    logger.warning(
                        "SkillsMP failed vendor=%s q=%s status=%s",
                        vendor,
                        query,
                        resp.status_code,
                    )
                    break
                skills = (resp.json().get("data") or {}).get("skills") or []
                if not skills:
                    break
                for item in skills:
                    github = str(item.get("githubUrl") or "")
                    if SKILLSMP_REPO_SKIP.search(github):
                        continue
                    skill_id = str(item.get("id") or "")
                    if not skill_id or skill_id in seen:
                        continue
                    rec = record_from_skillsmp(
                        item, source_id=source_id, vendor=vendor
                    )
                    if not is_vendor_skillsmp_relevant(vendor, rec):
                        continue
                    if record_filter and not record_filter(rec):
                        continue
                    seen.add(skill_id)
                    records.append(rec)
            except Exception as exc:
                logger.warning("SkillsMP error vendor=%s q=%s: %s", vendor, query, exc)
                break

    if not get_settings().skillsmp_api_key.strip():
        logger.debug("SkillsMP API key not set vendor=%s — using default quota", vendor)

    records = dedupe_skillsmp_records(records)
    if records:
        records = await filter_records_by_vendor_relevance(vendor, records)
    return records
