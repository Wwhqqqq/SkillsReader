"""
自媒体定向推送 Skill 选择器。

用途：为「自媒体定向推送」按钮生成 Top N 推荐：
- 筛选与自媒体平台（小红书/微信/抖音/快手/B站/知乎/微博等）相关的 Skill
- 优先推送热门/超级 app（高安装量/高增长）
- 对已推送过的 Skill 降低权重
- 优先推荐未推送过的 Skill
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import (
    add_self_media_pushed,
    get_self_media_pushed_ids,
)
from app.models import Skill
from app.services.digest.config_loader import load_digest_config
from app.services.digest.metrics import (
    GrowthMetrics,
    batch_growth_metrics,
    metric_abs_delta,
    momentum_score,
)
from app.services.digest.pools import CandidateContext

import re

# 自媒体平台关键词 → 用于匹配 skill name/description/tags
SELF_MEDIA_PLATFORMS: dict[str, list[str]] = {
    "小红书": ["小红书", "xiaohongshu", "xhs", "redbook", "rednote", "红书"],
    "微信/公众号": [
        "微信", "公众号", "wechat", "weixin", "视频号", "wechat-channel", "weixin-channel",
        "wechat-mp", "wechat-article", "wechat-official", "mp-weixin"
    ],
    "抖音": ["抖音", "douyin", "tiktok-cn", "dy-"],
    "快手": ["快手", "kuaishou", "kwai"],
    "B站": ["b站", "bilibili", "bilibili-video", "bilibili-content"],
    "知乎": ["知乎", "zhihu"],
    "微博": ["微博", "weibo"],
    "通用自媒体": [
        "自媒体", "内容创作", "content-creator", "self-media", "selfmedia",
        "social-auto", "video-creation", "viral-content", "social-media",
        "内容运营", "内容分发", "爆款", "选题", "标题优化",
    ],
}

# 超级 App 平台（高优先匹配）
SUPER_APP_PLATFORMS = {"小红书", "微信/公众号", "抖音", "快手", "B站"}


def _match_self_media_platform(
    name: str, tags: list[str], description: str
) -> tuple[str, int]:
    """
    判断一个 Skill 是否与自媒体平台相关。
    返回 (最佳匹配平台, 匹配分数 0-10)。

    匹配分数规则：
    - name 直接匹配平台关键词: +6
    - tags 包含平台关键词: +4
    - description 包含平台关键词: +2
    - 超级 App: +2 额外加成
    - 多个平台命中: 额外 +1 每个
    """
    name_lower = name.lower()
    desc_lower = (description or "").lower()
    tags_lower = [t.lower() for t in (tags or [])]

    platform_hits: dict[str, int] = {}
    best_platform = "通用自媒体"
    best_score = 0
    total_hits = 0

    for platform, keywords in SELF_MEDIA_PLATFORMS.items():
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            # 对于短拉丁关键词（<5 字符），使用 \b 词边界避免子串误匹配
            # 例如 "bili" 不应匹配 "observability"
            if len(kw) < 5 and kw.isascii():
                pattern = re.compile(r'\b' + re.escape(kw_lower) + r'\b')
            else:
                pattern = re.compile(re.escape(kw_lower))

            # name 匹配权重最高
            if pattern.search(name_lower):
                score += 6
            # tags 匹配
            for tag in tags_lower:
                if pattern.search(tag):
                    score += 4
                    break
            # description 匹配
            if pattern.search(desc_lower):
                score += 2

        if score > 0:
            platform_hits[platform] = score
            total_hits += 1
            # 超级 App 额外加成
            if platform in SUPER_APP_PLATFORMS:
                score += 2
            if score > best_score:
                best_score = score
                best_platform = platform

    # 多平台命中额外加成
    if total_hits > 1:
        best_score += min(total_hits - 1, 3)

    return best_platform, best_score


def _install_heat_score(skill: Skill, growth: GrowthMetrics) -> float:
    """
    安装热度分：综合安装量（log10）+ 近期增长（24h/7d 绝对增量）。
    """
    install_log = 0.0
    if skill.install_count and skill.install_count > 0:
        import math
        install_log = math.log10(min(skill.install_count, 1000000))

    d24 = metric_abs_delta(growth, window="24h")
    d7 = metric_abs_delta(growth, window="7d")

    # 安装量 log10 最高约 6（100万），增长最高约数百
    return install_log * 12.0 + d24 * 0.5 + d7 * 0.15 + momentum_score(growth) * 0.3


async def select_self_media_picks(
    session: AsyncSession,
    *,
    top_n: int = 10,
    ref_date: date | None = None,
) -> list[CandidateContext]:
    """
    自媒定向推送技能选择：
    1. 从数据库获取所有 active skills
    2. 筛选与自媒体平台相关的 skill（通过 name/tags/description 匹配）
    3. 已推送过的 skill 降低权重
    4. 按 platform_relevance + install_heat 综合排序
    """
    ref = ref_date or datetime.utcnow().date()
    cfg = load_digest_config()

    # 获取过去 60 天活跃的 skills
    cutoff = datetime.combine(ref - timedelta(days=60), datetime.min.time())
    skills = list(
        (
            await session.scalars(
                select(Skill).where(
                    Skill.status == "active",
                    Skill.last_seen_at >= cutoff,
                ).order_by(Skill.install_count.desc()).limit(2000)
            )
        ).all()
    )

    # 批量获取增长指标
    growth_map = await batch_growth_metrics(session, skills, ref, cfg)

    # 获取已推送的 skill IDs（Redis）
    pushed_ids = await get_self_media_pushed_ids()

    # 评分与分类
    scored: list[tuple[CandidateContext, str, float, bool]] = []  # (ctx, platform, score, is_pushed)

    for skill in skills:
        g = growth_map.get(skill.id) or GrowthMetrics(metric_value=skill.install_count or 0)
        platform, relevance_score = _match_self_media_platform(
            skill.name, skill.tags or [], skill.raw_description or ""
        )

        if relevance_score < 3:  # 匹配度太低，跳过
            continue

        is_pushed = skill.id in pushed_ids
        heat = _install_heat_score(skill, g)

        # 综合评分：相关度 × 热度，已推送降权
        push_penalty = 0.3 if is_pushed else 1.0
        combined = relevance_score * heat * push_penalty

        # 即使是已推送的，如果热度极高也保留机会（最少 0.3 权重）
        if is_pushed and combined < relevance_score * 100:
            continue  # 低热度已推送的跳过

        ctx = CandidateContext(
            skill=skill,
            growth=g,
            pools={"self_media"},
            is_official=_is_skill_official(skill),
            is_new=(ref - skill.first_seen_at.date()).days <= 3 if skill.first_seen_at else False,
        )
        scored.append((ctx, platform, combined, is_pushed))

    # 按综合评分降序排序
    scored.sort(key=lambda x: x[2], reverse=True)

    # 取 Top N，去重（按 skill.id）
    seen_ids: set[int] = set()
    picks: list[CandidateContext] = []
    platform_counts: dict[str, int] = defaultdict(int)

    for ctx, platform, score, is_pushed in scored:
        if ctx.skill.id in seen_ids:
            continue
        if len(picks) >= top_n:
            break

        # 单一平台最多占 40%，确保多样性
        max_per_platform = max(1, int(top_n * 0.4))
        if platform_counts[platform] >= max_per_platform:
            continue

        # 额外奖励：未推送过的 skill
        if not is_pushed:
            # 在 slot 中标注优先级
            ctx.slot = "self_media_unpushed" if not is_pushed else "self_media_pushed"
        else:
            ctx.slot = "self_media_pushed"

        ctx.score_total = score
        ctx.recommend_reason = _build_self_media_reason(ctx, platform, is_pushed)

        seen_ids.add(ctx.skill.id)
        picks.append(ctx)
        platform_counts[platform] += 1

    # 如果还不够 Top N，放宽平台限制再补
    if len(picks) < top_n:
        for ctx, platform, score, is_pushed in scored:
            if ctx.skill.id in seen_ids:
                continue
            if len(picks) >= top_n:
                break
            ctx.slot = "self_media_fill"
            ctx.score_total = score
            ctx.recommend_reason = _build_self_media_reason(ctx, platform, is_pushed)
            seen_ids.add(ctx.skill.id)
            picks.append(ctx)

    return picks


def _is_skill_official(skill: Skill) -> bool:
    meta = skill.metadata_json if isinstance(skill.metadata_json, dict) else {}
    return bool(meta.get("official") or meta.get("publisherType") == "官方发布")


def _build_self_media_reason(ctx: CandidateContext, platform: str, is_pushed: bool) -> str:
    parts = [platform]
    if ctx.is_official:
        parts.append("官方")
    if ctx.is_new:
        parts.append("新发现")
    if is_pushed:
        parts.append("曾推送(降权)")
    if ctx.skill.install_count and ctx.skill.install_count > 0:
        if ctx.skill.install_count >= 10000:
            parts.append(f"安装{ctx.skill.install_count / 10000:.1f}万")
        elif ctx.skill.install_count >= 1000:
            parts.append(f"安装{ctx.skill.install_count / 1000:.1f}k")
        else:
            parts.append(f"安装{ctx.skill.install_count}")
    return " · ".join(parts)


async def mark_self_media_pushed(skill_ids: list[int]) -> None:
    """推送完成后，将 skill IDs 标记为已推送（Redis SET，7 天过期）。"""
    await add_self_media_pushed(skill_ids)
