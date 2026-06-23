"""
API 路由辅助函数 —— ORM Skill → Pydantic Schema 转换。

避免在每个路由里重复写字段映射。
"""

from __future__ import annotations

from app.models import Skill
from app.schemas import DigestPickItemOut, GrowthMetricsOut, RankingItem, ScoreBreakdownOut, SkillOut


def skill_to_out(skill: Skill) -> SkillOut:
    """
    把 SQLAlchemy Skill 模型转成 API 响应用的 SkillOut。

    skill.tags or []: tags 可能为 None，默认空列表
    """
    return SkillOut(
        id=skill.id,
        fingerprint=skill.fingerprint,
        vendor=skill.vendor,
        source_id=skill.source_id,
        external_id=skill.external_id,
        name=skill.name,
        raw_description=skill.raw_description,
        llm_summary=skill.llm_summary,
        llm_summary_at=skill.llm_summary_at,
        detail_url=skill.detail_url,
        tags=skill.tags or [],
        install_count=skill.install_count,
        quality_score=skill.quality_score,
        first_seen_at=skill.first_seen_at,
        publish_date=skill.publish_date,
        last_seen_at=skill.last_seen_at,
        status=skill.status,
    )


def to_ranking_items(items: list[tuple], is_new: bool = False) -> list[RankingItem]:
    """
    把 ranker 返回的 [(Skill, score), ...] 转成 RankingItem 列表。

    enumerate(items, 1): rank 从 1 开始
    """
    result = []
    for i, (skill, score) in enumerate(items, 1):
        result.append(
            RankingItem(
                rank=i,
                skill=skill_to_out(skill),
                score=score,
                is_new=is_new,
                is_official=skill.vendor in ("美团", "阿里", "腾讯", "字节", "百度"),
            )
        )
    return result


def to_digest_pick_items(items) -> list[DigestPickItemOut]:
    out: list[DigestPickItemOut] = []
    for item in items:
        bd = item.score_breakdown or {}
        growth = item.growth or {}
        out.append(
            DigestPickItemOut(
                rank=item.rank,
                slot=item.slot,
                pool=item.pool,
                skill=skill_to_out(item.skill),
                score=item.score,
                score_breakdown=ScoreBreakdownOut(
                    trend=bd.get("trend", 0),
                    official=bd.get("official", 0),
                    quality=bd.get("quality", 0),
                    diversity=bd.get("diversity", 0),
                    total=item.score,
                ),
                growth=GrowthMetricsOut(**growth),
                recommend_reason=item.recommend_reason,
                is_official=item.is_official,
                is_new=item.is_new,
            )
        )
    return out
