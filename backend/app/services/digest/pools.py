"""候选池模块 —— 实现候选技能的查询、入池判断与池分类。

本模块负责将已入库的 `Skill` 按照文档中 "Official / Popularity / Trend / Discovery" 四类池子分类，
并提供构建候选 `CandidateContext` 的流水：

- `query_candidate_skills`：从 DB 读取候选技能集（基于质量阈值与最近活跃时间）。
- `batch_growth_metrics`（外部） -> `is_pool_eligible`：硬过滤入池条件。
- `classify_pools`：将满足的技能映射到一个或多个池子（官方/热度/趋势/发现）。
- `build_candidates`：整合以上步骤，返回可用于评分的 `CandidateContext` 列表。

所有函数均保留轻量注释以便追踪对应文档 §4 内容。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill
from app.adapters.common.platform_filters import is_platform_relevant, skill_as_record
from app.services.scan.skill_gate import is_real_skill
from app.services.digest.config_loader import domestic_vendors, load_digest_config
from app.services.digest.metrics import GrowthMetrics, batch_growth_metrics
from app.services.enrichment.skill_classification import PUBLISHER_OFFICIAL, publisher_type_for

POOL_OFFICIAL = "official"
POOL_POPULARITY = "popularity"
POOL_TREND = "trend"
POOL_DISCOVERY = "discovery"


@dataclass
class CandidateContext:
    # 入库模型对象
    skill: Skill
    # GrowthMetrics 实例，包含 1/3/7 天增长与趋势评分
    growth: GrowthMetrics
    # 属于的池子集合（字符串常量 POOL_*）
    pools: set[str] = field(default_factory=set)
    # 最终评分与细分
    score_total: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    # 推荐理由（由 reasons.build_recommend_reason 填充）
    recommend_reason: str = ""
    # 由 selector 设置的槽位名（official/trend/discovery/fill）
    slot: str = ""
    # 元信息：是否被判定为官方发布
    is_official: bool = False
    # 是否为当天新发现（用于 discovery 排序）
    is_new: bool = False
    # 是否由 skills.sh 标记为 trending（趋势雷达来源）
    skills_sh_trending: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill.id,
            "pools": sorted(self.pools),
            "score_total": self.score_total,
            "score_breakdown": self.score_breakdown,
            "recommend_reason": self.recommend_reason,
            "slot": self.slot,
            "is_official": self.is_official,
            "is_new": self.is_new,
            "skills_sh_trending": self.skills_sh_trending,
            "growth": self.growth.to_dict(),
        }


def _meta(skill: Skill) -> dict[str, Any]:
    m = skill.metadata_json
    return m if isinstance(m, dict) else {}


def _is_skills_sh_trending(skill: Skill) -> bool:
    # skills.sh 适配器会在 metadata 中标记 `trend_source=True` 且设置 `section`（例如 'trending' / 'hot'）
    # 本函数返回 True 表示该 skill 来自 skills.sh 的趋势雷达，优先进入 TrendingPool。
    meta = _meta(skill)
    return bool(meta.get("trend_source")) and meta.get("section") in ("trending", "hot")


def is_pool_eligible(skill: Skill, growth: GrowthMetrics, cfg: dict[str, Any]) -> bool:
    """判断是否满足进入候选池的硬条件（至少满足一条即可）。

    硬条件包括：
    - 官方发布（publisher_type_for 判定或 metadata.official）
    - 安装数/Star 达到 `entry.min_install`
    - skills.sh 标记为 trending
    - GitHub 源且 stars 达到 baseline
    - 国内厂商且质量分达到门槛
    - 或者 growth.trend_velocity_score 达到 trend 阈值
    """
    meta = _meta(skill)
    entry = (cfg.get("pools") or {}).get("entry") or {}
    pub = publisher_type_for(skill)

    if pub == PUBLISHER_OFFICIAL or meta.get("official"):
        return True
    if skill.install_count >= int(entry.get("min_install") or 50):
        return True
    if _is_skills_sh_trending(skill):
        return True
    if skill.source_id == "github_watch" and skill.install_count >= int(
        entry.get("github_stars_baseline") or 30
    ):
        return True
    if skill.vendor in domestic_vendors(cfg) and skill.quality_score >= 50:
        return True
    if growth.trend_velocity_score >= float(
        (cfg.get("pools") or {}).get("trend", {}).get("min_trend_velocity") or 0.5
    ):
        return True
    return False


def classify_pools(
    skill: Skill,
    growth: GrowthMetrics,
    cfg: dict[str, Any],
    *,
    ref_date: date,
) -> set[str]:
    """将单个 Skill/ GrowthMetrics 分类到一个或多个池子（返回池名集合）。

    逻辑顺序：官方判定 -> 热度判断 -> 趋势判断 -> 发现池（基于年龄与质量）-> 国内厂商额外规则。
    返回集合可包含多个池子，例如一个既属于 trend 又满足 popularity。
    """
    pools: set[str] = set()
    pools_cfg = cfg.get("pools") or {}
    meta = _meta(skill)
    pub = publisher_type_for(skill)
    is_domestic = skill.vendor in domestic_vendors(cfg)
    sh_trend = _is_skills_sh_trending(skill)

    if pub == PUBLISHER_OFFICIAL or meta.get("official"):
        pools.add(POOL_OFFICIAL)
    elif is_domestic and skill.quality_score >= int(
        (pools_cfg.get("official") or {}).get("min_quality") or 45
    ):
        pools.add(POOL_OFFICIAL)

    pop = pools_cfg.get("popularity") or {}
    if skill.install_count >= int(pop.get("min_install") or 200):
        if skill.quality_score >= int(pop.get("min_quality") or 45):
            pools.add(POOL_POPULARITY)

    trend_min = float((pools_cfg.get("trend") or {}).get("min_trend_velocity") or 0.5)
    if growth.trend_velocity_score >= trend_min or sh_trend:
        pools.add(POOL_TREND)

    disc = pools_cfg.get("discovery") or {}
    age = (ref_date - skill.first_seen_at.date()).days if skill.first_seen_at else 999
    desc_len = len((skill.llm_summary or skill.raw_description or "").strip())
    if (
        age <= int(disc.get("max_age_days") or 14)
        and skill.quality_score >= int(disc.get("min_quality") or 50)
        and desc_len >= int(disc.get("min_description_len") or 30)
        and POOL_TREND not in pools
    ):
        pools.add(POOL_DISCOVERY)

    if is_domestic and age <= 3:
        # 国内厂商的新近条目在短期内会被额外加入官方或发现池以提升曝光。
        pools.add(POOL_OFFICIAL if pub == PUBLISHER_OFFICIAL else POOL_DISCOVERY)

    return pools


async def query_candidate_skills(
    session: AsyncSession,
    cfg: dict[str, Any],
    *,
    vendors: list[str] | None = None,
    ref_date: date | None = None,
) -> list[Skill]:
    sel = cfg.get("selection") or {}
    ref = ref_date or datetime.utcnow().date()
    conditions = [
        Skill.status == "active",
        Skill.quality_score >= int(sel.get("quality_threshold") or 40),
        Skill.digest_archived_at.is_(None),
        Skill.last_seen_at >= datetime.combine(ref - timedelta(days=30), datetime.min.time()),
    ]
    if vendors:
        conditions.append(Skill.vendor.in_(vendors))

    q = (
        select(Skill)
        .where(and_(*conditions))
        .order_by(Skill.last_seen_at.desc(), Skill.quality_score.desc())
        .limit(int(sel.get("candidate_pool_limit") or 1200))
    )
    return list((await session.scalars(q)).all())


async def build_candidates(
    session: AsyncSession,
    cfg: dict[str, Any] | None = None,
    *,
    vendors: list[str] | None = None,
    ref_date: date | None = None,
) -> list[CandidateContext]:
    cfg = cfg or load_digest_config()
    ref = ref_date or datetime.utcnow().date()
    skills = await query_candidate_skills(session, cfg, vendors=vendors, ref_date=ref)
    growth_map = await batch_growth_metrics(session, skills, ref, cfg)

    candidates: list[CandidateContext] = []
    for skill in skills:
        if not is_platform_relevant(skill_as_record(skill)):
            continue
        if not is_real_skill(skill):
            continue
        growth = growth_map[skill.id]
        if not is_pool_eligible(skill, growth, cfg):
            continue
        pools = classify_pools(skill, growth, cfg, ref_date=ref)
        if not pools:
            continue
        pub = publisher_type_for(skill)
        age = (ref - skill.first_seen_at.date()).days if skill.first_seen_at else 999
        candidates.append(
            CandidateContext(
                skill=skill,
                growth=growth,
                pools=pools,
                is_official=pub == PUBLISHER_OFFICIAL or bool(_meta(skill).get("official")),
                is_new=age <= 1,
                skills_sh_trending=_is_skills_sh_trending(skill),
            )
        )
    return candidates


async def build_candidates_from_skill_ids(
    session: AsyncSession,
    skill_ids: list[int],
    cfg: dict[str, Any] | None = None,
    *,
    ref_date: date | None = None,
) -> list[CandidateContext]:
    """为官方扫描新增构建候选（仅指定 skill id，不走全库查询）。"""
    if not skill_ids:
        return []
    cfg = cfg or load_digest_config()
    ref = ref_date or datetime.utcnow().date()
    skills = list(
        (await session.scalars(select(Skill).where(Skill.id.in_(skill_ids)))).all()
    )
    by_id = {s.id: s for s in skills}
    ordered = [by_id[i] for i in skill_ids if i in by_id]
    growth_map = await batch_growth_metrics(session, ordered, ref, cfg)

    candidates: list[CandidateContext] = []
    for skill in ordered:
        if not is_real_skill(skill):
            continue
        growth = growth_map[skill.id]
        pools = classify_pools(skill, growth, cfg, ref_date=ref) or {POOL_OFFICIAL}
        pub = publisher_type_for(skill)
        age = (ref - skill.first_seen_at.date()).days if skill.first_seen_at else 999
        candidates.append(
            CandidateContext(
                skill=skill,
                growth=growth,
                pools=pools,
                is_official=pub == PUBLISHER_OFFICIAL or bool(_meta(skill).get("official")),
                is_new=age <= 1,
                skills_sh_trending=_is_skills_sh_trending(skill),
            )
        )
    return candidates
