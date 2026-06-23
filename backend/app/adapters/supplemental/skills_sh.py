"""
skills.sh 趋势雷达源 —— 文档 §3（双通道：API 增量 + HTML 榜单 + 关键词）。

本 Adapter 的职责是作为趋势雷达（high-frequency trend source）：

- 主动抓取 skills.sh 的 API 或 HTML 榜单，抽取带有 views/installs 的条目；
- 将条目转换为 `RawSkillRecord` 并设置 `metadata.trend_source=True` 与 `section` 字段；
- 不直接参与主排序权重（主流水线以 metadata.trend_source 作入池/趋势判断），
    但可高概率将早期爆发的 skill 推入 TrendingPool 供后续评分使用。

实现要点已经保留：安装数解析、路径解析、API/HTML 两通道合并与关键词增强。
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.services.digest.config_loader import load_digest_config

SKILLS_SH_URL = "https://skills.sh"
SKILL_PATH_RE = re.compile(
    r"^/(?:(site)/)?(?P<owner>[^/]+(?:/[^/]+)*)/(?P<name>[^/]+)$"
)
INSTALL_SUFFIX_RE = re.compile(
    r"(?:(\d+(?:\.\d+)?)([KMB]))$|(\d+)\+\d+$|(\d+)-\d+$"
)
NAV = frozenset({"topic", "topics", "official", "audits", "docs", "trending", "hot", "top", "search", "about"})


def _parse_install(text: str) -> int:
    """解析诸如 '578.4K' / '771+6' / '123' 等安装/浏览量后缀为整数。

    返回 0 表示无法解析或无数值信息。
    """
    m = INSTALL_SUFFIX_RE.search(text.strip())
    if not m:
        return 0
    if m.group(1) and m.group(2):
        mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2)]
        return int(float(m.group(1)) * mult)
    if m.group(3):
        return int(m.group(3))
    if m.group(4):
        return int(m.group(4))
    return 0


def _display_name(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _record_from_path(href: str, text: str, *, section: str, keyword: str = "") -> RawSkillRecord | None:
    """根据页面路径与锚文本构造 RawSkillRecord。返回 None 表示该链接不是技能条目（例如导航页）。

    - 只接受以 '/' 开头的内部路径；
    - 使用 SKILL_PATH_RE 提取 owner 与 name；忽略短 slug 或导航类路径；
    - 填充 `external_id` 前缀为 'skillsh:owner:slug'，并在 metadata 中设置 `trend_source` 与 section。
    """
    if not href.startswith("/"):
        return None
    m = SKILL_PATH_RE.match(href.split("?")[0].split("#")[0])
    if not m:
        return None
    owner, name_slug = m.group("owner"), m.group("name")
    if owner.split("/")[0] in NAV or name_slug in NAV or len(name_slug) < 2:
        return None

    views = _parse_install(text)
    path_id = href.strip("/").replace("/", ":")
    external_id = f"skillsh:{path_id}"[:128]
    detail = f"{SKILLS_SH_URL}{href}"
    summary = f"Listed on skills.sh ({section})"
    if views:
        summary += f" with {views:,} views"
    if keyword:
        summary += f" · keyword:{keyword}"

    return RawSkillRecord(
        external_id=external_id,
        name=_display_name(name_slug),
        vendor="海外社区",
        source_id="skills_sh",
        raw_description=summary,
        detail_url=detail,
        install_count=views,
        tags=["skills.sh", section] + ([keyword] if keyword else []),
        metadata={
            "catalog": "skills_sh",
            "section": section,
            "owner": owner,
            "skill_slug": name_slug,
            "trend_source": True,
            "publish_ts": time.time(),
        },
    )


class SkillsShAdapter(SourceAdapter):
    source_id = "skills_sh"
    vendor = "海外社区"

    async def fetch(self) -> list[RawSkillRecord]:
        """抓取主入口：

        1) 通道 A：尝试调用站点 API（增量接口），优先解析 JSON 返回的条目；
        2) 通道 B：抓取 HTML 榜单页面（home/trending/hot/top），解析内链；
        3) 关键词增强：在已抓取结果上标记 keyword hit，并尝试搜索页抓取；

        使用 `seen` 字典合并重复条目，保留 install_count 更大的记录，最终按 install_count 降序返回前 500 条。
        """
        cfg = load_digest_config()
        sh_cfg = cfg.get("skills_sh") or {}
        keywords = list(sh_cfg.get("keywords") or ["AI", "agent", "workflow"])
        api_paths = list(sh_cfg.get("api_paths") or ["/api/latest"])

        seen: dict[str, RawSkillRecord] = {}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 通道 A：API 增量（站点未开放时静默跳过）
            since = int(time.time()) - 86400 * 7
            for path in api_paths:
                for param in ({"since": since}, {"since": str(since)}, {}):
                    try:
                        resp = await client.get(
                            f"{SKILLS_SH_URL}{path}",
                            params=param,
                            headers={"Accept": "application/json", "User-Agent": "SkillGetter/2.0"},
                        )
                        if resp.status_code != 200:
                            continue
                        data = resp.json()
                        for rec in self._parse_api_payload(data, section="api"):
                            self._merge(seen, rec)
                        break
                    except Exception:
                        continue

            # 通道 B：HTML 榜单
            for section, path in [("home", ""), ("trending", "/trending"), ("hot", "/hot"), ("top", "/top")]:
                try:
                    resp = await client.get(
                        f"{SKILLS_SH_URL}{path}",
                        headers={"User-Agent": "SkillGetter/2.0"},
                    )
                    resp.raise_for_status()
                    for rec in self._parse_html(resp.text, section=section):
                        self._merge(seen, rec)
                except httpx.HTTPError:
                    continue

            # 关键词过滤增强（在已抓记录上标记 + 尝试搜索页）
            for kw in keywords:
                for rec in list(seen.values()):
                    blob = f"{rec.name} {rec.raw_description} {' '.join(rec.tags or [])}".lower()
                    if kw.lower() in blob:
                        meta = dict(rec.metadata or {})
                        meta["keyword_hit"] = kw
                        rec.metadata = meta
                try:
                    resp = await client.get(
                        f"{SKILLS_SH_URL}/",
                        params={"q": kw},
                        headers={"User-Agent": "SkillGetter/2.0"},
                    )
                    if resp.status_code == 200:
                        for rec in self._parse_html(resp.text, section="keyword", keyword=kw):
                            self._merge(seen, rec)
                except httpx.HTTPError:
                    continue

        out = sorted(seen.values(), key=lambda r: r.install_count, reverse=True)
        return out[:500]

    @staticmethod
    def _merge(seen: dict[str, RawSkillRecord], rec: RawSkillRecord) -> None:
        key = rec.external_id or rec.name.lower()
        prev = seen.get(key)
        if prev is None or rec.install_count > prev.install_count:
            seen[key] = rec

    def _parse_api_payload(self, data: Any, *, section: str) -> list[RawSkillRecord]:
        """解析 API 返回的 JSON 结构，兼容多种字段名（items/skills/title/url/views）。

        对每个条目构造 RawSkillRecord（通过 _record_from_path），并用返回的 views/installs 覆盖 install_count 与摘要。
        """
        items = data if isinstance(data, list) else (data.get("items") or data.get("skills") or [])
        out: list[RawSkillRecord] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or "")
            url = str(item.get("url") or item.get("link") or "")
            if not title:
                continue
            href = url.replace(SKILLS_SH_URL, "") if url.startswith(SKILLS_SH_URL) else url
            views = int(item.get("views") or item.get("installs") or 0)
            rec = _record_from_path(href, f"x{views}K" if views else title, section=section)
            if rec:
                rec.install_count = max(rec.install_count, views)
                rec.raw_description = str(item.get("summary") or rec.raw_description)
                out.append(rec)
        return out

    def _parse_html(self, html: str, *, section: str, keyword: str = "") -> list[RawSkillRecord]:
        # 解析 HTML，抽取所有内部链接并尝试转换为技能记录
        soup = BeautifulSoup(html, "lxml")
        out: list[RawSkillRecord] = []
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if not href.startswith("/") or not text or len(text) > 200:
                continue
            rec = _record_from_path(href, text, section=section, keyword=keyword)
            if rec:
                out.append(rec)
        return out
