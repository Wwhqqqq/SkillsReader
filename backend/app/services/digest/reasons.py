"""推荐理由生成模块。

根据候选的池子、是否官方、增长指标与安装数等信息拼接短中文推荐理由，供推送文案直接使用。
如果没有显著信号，则选择得分最高的维度作为默认理由。
"""

from __future__ import annotations

from app.services.digest.pools import (
    POOL_DISCOVERY,
    POOL_OFFICIAL,
    POOL_POPULARITY,
    POOL_TREND,
    CandidateContext,
)
from app.services.enrichment.skill_classification import PUBLISHER_OFFICIAL, publisher_type_for


def build_recommend_reason(ctx: CandidateContext, slot: str) -> str:
    skill = ctx.skill
    growth = ctx.growth
    pub = publisher_type_for(skill)
    parts: list[str] = []

    if slot == "official" or POOL_OFFICIAL in ctx.pools:
        if pub == PUBLISHER_OFFICIAL:
            parts.append(f"{skill.vendor}官方发布")
        else:
            parts.append(skill.vendor)

    if slot == "trend" or POOL_TREND in ctx.pools:
        # 趋势槽位：若由 skills.sh 命中则标注来源；同时若趋势速度 > 0 显示数值作为说明
        if ctx.skills_sh_trending:
            parts.append("skills.sh 趋势雷达")
        if growth.trend_velocity_score >= 1:
            parts.append(f"趋势速度 {growth.trend_velocity_score:.0f}")

    if slot == "discovery" or POOL_DISCOVERY in ctx.pools:
        # 发现槽位：若为当天新发现则强调，否则标注为新近高质量条目
        if ctx.is_new:
            parts.append("今日新发现")
        else:
            parts.append("新近高质量 Skill")

    if POOL_POPULARITY in ctx.pools and skill.install_count >= 100:
        # 热度池：显示安装/Star 数量作为支持理由
        parts.append(f"安装/Star {skill.install_count}")

    if not parts:
        bd = ctx.score_breakdown
        top_dim = max(bd, key=bd.get) if bd else "quality"
        label = {"official": "官方属性", "trend": "趋势", "quality": "内容质量", "diversity": "多样性"}
        parts.append(f"综合{label.get(top_dim, '评分')}领先")

    return "；".join(parts)
