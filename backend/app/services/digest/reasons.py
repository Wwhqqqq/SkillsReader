"""推荐理由生成模块。"""

from __future__ import annotations

from app.services.digest.metrics import metric_abs_delta
from app.services.digest.pools import (
    POOL_MOMENTUM,
    POOL_OFFICIAL,
    POOL_RECENT_24H,
    POOL_RECENT_7D,
    CandidateContext,
)
from app.services.enrichment.skill_classification import PUBLISHER_OFFICIAL, publisher_type_for


def build_recommend_reason(ctx: CandidateContext, slot: str) -> str:
    skill = ctx.skill
    growth = ctx.growth
    pub = publisher_type_for(skill)
    parts: list[str] = []

    if slot in ("recent_24h", "official_new") or POOL_RECENT_24H in ctx.pools:
        parts.append("24h内新发现")

    if slot == "recent_7d" or POOL_RECENT_7D in ctx.pools:
        if "24h内新发现" not in parts:
            parts.append("7天内新发现")

    if slot == "momentum" or POOL_MOMENTUM in ctx.pools:
        d24 = metric_abs_delta(growth, window="24h")
        d7 = metric_abs_delta(growth, window="7d")
        if d24 > 0:
            parts.append(f"24h安装+{d24}")
        elif d7 > 0:
            parts.append(f"7d安装+{d7}")
        elif growth.growth_3d_pct and growth.growth_3d_pct > 0:
            parts.append(f"24h增速+{growth.growth_3d_pct:.0f}%")

    if slot == "official" or POOL_OFFICIAL in ctx.pools:
        if pub == PUBLISHER_OFFICIAL:
            parts.append(f"{skill.vendor}官方发布")
        else:
            parts.append(skill.vendor)

    if pub == PUBLISHER_OFFICIAL and "官方发布" not in "；".join(parts):
        parts.append(f"{skill.vendor}官方发布")

    if skill.install_count and skill.install_count >= 100 and not any("安装" in p for p in parts):
        parts.append(f"安装/Star {skill.install_count}")

    if not parts:
        parts.append("综合动量领先")

    return "；".join(parts)
