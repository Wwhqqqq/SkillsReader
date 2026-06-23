"""精选评分与选榜的详细追踪 —— 供测试平台展示完整计算过程。"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.digest.config_loader import config_version, domestic_vendors, load_digest_config
from app.services.digest.engine import finalize_digest_content
from app.services.digest.metrics import batch_growth_metrics, growth_rate, log_growth, pct_growth
from app.services.digest.pools import POOL_OFFICIAL, POOL_TREND, CandidateContext, build_candidates
from app.services.digest.quality import quality_breakdown
from app.services.digest.scorer import (
    _normalize_weights,
    platform_ratios,
    score_all_candidates,
    score_candidate,
    score_diversity,
    score_official,
    score_quality,
    score_trend,
)
from app.services.digest.selector import _scale_slots, select_structured_picks
from app.services.digest.types import DigestPickItem, DigestResult
from app.services.enrichment.skill_classification import PUBLISHER_OFFICIAL, publisher_type_for


def _history_flags(growth) -> dict[str, bool]:
    return {
        "1d": growth.value_1d_ago is not None,
        "3d": growth.value_3d_ago is not None,
        "7d": growth.value_7d_ago is not None,
    }


def trace_growth(skill, growth) -> dict[str, Any]:
    current = growth.metric_value
    v1, v3, v7 = growth.value_1d_ago, growth.value_3d_ago, growth.value_7d_ago
    return {
        "skill_id": skill.id,
        "skill_name": skill.name,
        "source_id": skill.source_id,
        "ref_metric_value": current,
        "snapshots": {"1d_ago": v1, "3d_ago": v3, "7d_ago": v7},
        "history_available": _history_flags(growth),
        "note": (
            "首日无历史快照时，1/3/7 日增长率可能使用 0 基线或 None→100% 回退；"
            "连续 7 日写入快照后，7 日窗口将使用真实历史值。"
        ),
        "growth_rate": {
            "1d": growth_rate(current, v1),
            "3d": growth_rate(current, v3),
            "7d": growth_rate(current, v7),
        },
        "growth_pct": {
            "1d": pct_growth(current, v1),
            "3d": pct_growth(current, v3),
            "7d": pct_growth(current, v7),
        },
        "log_growth": {
            "1d": log_growth(current, v1),
            "3d": log_growth(current, v3),
            "7d": log_growth(current, v7),
        },
        "z_score": {"1d": growth.z_1d, "3d": growth.z_3d, "7d": growth.z_7d},
        "trend_velocity_score": growth.trend_velocity_score,
        "formula": {
            "growth_rate": "(current - past) / max(past, 1); past=None 且 current>0 → 100%",
            "log_growth": "log(1 + growth_rate)",
            "z_score": "平台内 log_growth 的 z-score（同平台至少 2 条候选才有区分度）",
            "trend_velocity": "0.4*z_1d + 0.3*z_3d + 0.3*z_7d → 映射到 0–100",
        },
    }


def trace_quality(skill) -> dict[str, Any]:
    return quality_breakdown(skill)


def trace_score(ctx: CandidateContext, cfg: dict[str, Any], ratios: dict[str, float]) -> dict[str, Any]:
    scoring = cfg.get("scoring") or {}
    skill = ctx.skill
    meta = skill.metadata_json if isinstance(skill.metadata_json, dict) else {}
    sw = (scoring.get("source_weights") or {}).get(skill.source_id)
    if sw is None:
        sw = (scoring.get("source_weights") or {}).get("default", 0.8)

    install = skill.install_count or 0
    base_trend = ctx.growth.trend_velocity_score or ctx.growth.growth_score
    install_heat = (install ** 0.4) if install > 0 else 0.0
    total, breakdown = score_candidate(ctx, cfg, platform_ratio_map=ratios)
    weights = _normalize_weights((cfg.get("scoring") or {}).get("final_weights") or {})

    pub = publisher_type_for(skill)
    official_lines: list[str] = []
    if pub == PUBLISHER_OFFICIAL or meta.get("official"):
        official_lines.append(f"官方发布 +{scoring.get('official_publisher_bonus', 30)}")
        official_lines.append(f"metadata.official +{scoring.get('metadata_official_bonus', 20)}")
    if skill.vendor in domestic_vendors(cfg):
        official_lines.append(f"超级公司 {skill.vendor} +{scoring.get('domestic_vendor_bonus', 15)}")
    if POOL_OFFICIAL in ctx.pools:
        official_lines.append("OfficialPool +15")

    platform_ratio = ratios.get(skill.source_id, 0.0)
    weighted_parts = {k: round(breakdown[k] * weights.get(k, 0), 4) for k in breakdown}

    return {
        "dimensions": {
            "trend": {
                "score": breakdown["trend"],
                "detail": {
                    "trend_velocity_score": base_trend,
                    "source_weight": float(sw),
                    "install_heat": round(install_heat, 4),
                    "install_heat_component": round(install_heat * 0.15, 2),
                    "formula": f"min(100, trend_velocity({base_trend}) * {sw} + ({install}**0.4)*0.15)",
                },
            },
            "official": {"score": breakdown["official"], "bonuses": official_lines},
            "quality": {"score": breakdown["quality"], "detail": trace_quality(skill)},
            "diversity": {
                "score": breakdown["diversity"],
                "platform_ratio": round(platform_ratio, 4),
                "formula": f"(1 - {platform_ratio:.4f}) * 100",
            },
        },
        "final_weights": weights,
        "weighted_contribution": weighted_parts,
        "total": total,
        "formula": "Σ dimension_score × final_weight",
    }


def trace_selection(candidates: list[CandidateContext], cfg: dict[str, Any], top_n: int) -> list[dict[str, Any]]:
    sel = cfg.get("selection") or {}
    slots = sel.get("slots") or {}
    div = sel.get("diversity") or {}
    max_vendor = int(div.get("max_per_vendor") or 2)
    max_platform = int(div.get("max_per_platform") or 4)
    score_all_candidates(candidates, cfg)

    sort_score = lambda c: (c.score_total, c.growth.trend_velocity_score)
    sort_trend = lambda c: (c.growth.trend_velocity_score, c.growth.log_growth_1d, c.score_total)
    sort_disc = lambda c: (1 if c.is_new else 0, c.score_breakdown.get("quality", 0), c.score_total)

    steps: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    vendor_count: dict[str, int] = {}
    platform_count: dict[str, int] = {}

    for slot_name, pool, count in _scale_slots(slots, top_n):
        key = sort_score if pool == POOL_OFFICIAL else sort_trend if pool == POOL_TREND else sort_disc
        items = [c for c in candidates if pool in c.pools and c.skill.id not in selected_ids]
        items.sort(key=key, reverse=True)
        picked_ids: list[int] = []
        skipped: list[dict[str, Any]] = []

        for ctx in items:
            if len(picked_ids) >= count:
                break
            v, src = ctx.skill.vendor, ctx.skill.source_id
            if vendor_count.get(v, 0) >= max_vendor:
                skipped.append({"skill_id": ctx.skill.id, "name": ctx.skill.name, "reason": f"厂商 {v} 已达上限 {max_vendor}"})
                continue
            if platform_count.get(src, 0) >= max_platform:
                skipped.append({"skill_id": ctx.skill.id, "name": ctx.skill.name, "reason": f"平台 {src} 已达上限 {max_platform}"})
                continue
            picked_ids.append(ctx.skill.id)
            selected_ids.add(ctx.skill.id)
            vendor_count[v] = vendor_count.get(v, 0) + 1
            platform_count[src] = platform_count.get(src, 0) + 1

        steps.append(
            {
                "slot": slot_name,
                "pool": pool,
                "target_count": count,
                "picked_skill_ids": picked_ids,
                "skipped_diversity": skipped,
                "sort_key": "score_total" if pool == POOL_OFFICIAL else "trend_velocity" if pool == POOL_TREND else "discovery",
            }
        )

    return steps


def _metrics_readiness_note(candidates: list[CandidateContext]) -> dict[str, Any]:
    if not candidates:
        return {"message": "无候选技能", "full_7d_ready": False}
    full_7d = sum(1 for c in candidates if c.growth.value_7d_ago is not None)
    full_3d = sum(1 for c in candidates if c.growth.value_3d_ago is not None)
    full_1d = sum(1 for c in candidates if c.growth.value_1d_ago is not None)
    n = len(candidates)
    return {
        "candidates_with_1d_history": full_1d,
        "candidates_with_3d_history": full_3d,
        "candidates_with_7d_history": full_7d,
        "total_candidates": n,
        "full_7d_ready": full_7d == n and n > 0,
        "message": (
            "全部候选均有 7 日历史快照，7 日增速指标已完全生效"
            if full_7d == n and n > 0
            else f"部分候选缺少历史快照（1d:{full_1d}/{n}, 3d:{full_3d}/{n}, 7d:{full_7d}/{n}），"
            "需连续写入日快照后趋势分才会稳定"
        ),
    }


async def run_traced_digest(
    session: AsyncSession,
    *,
    digest_date: date,
    top_n: int = 10,
    vendors: list[str] | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_digest_config()
    candidates = await build_candidates(session, cfg, vendors=vendors, ref_date=digest_date)
    ratios = platform_ratios(candidates)
    score_all_candidates(candidates, cfg)

    candidate_traces = [
        {
            "skill_id": ctx.skill.id,
            "name": ctx.skill.name,
            "vendor": ctx.skill.vendor,
            "source_id": ctx.skill.source_id,
            "pools": sorted(ctx.pools),
            "growth": trace_growth(ctx.skill, ctx.growth),
            "score": trace_score(ctx, cfg, ratios),
            "is_official": ctx.is_official,
            "is_new": ctx.is_new,
        }
        for ctx in candidates
    ]

    picks = select_structured_picks(candidates, cfg, top_n=top_n)
    selection_steps = trace_selection(candidates, cfg, top_n)

    items: list[DigestPickItem] = []
    pick_traces = []
    for i, ctx in enumerate(picks, start=1):
        pool = next((p for p in ("official", "trend", "discovery", "popularity") if p in ctx.pools), "unknown")
        items.append(
            DigestPickItem(
                rank=i,
                slot=ctx.slot,
                pool=pool,
                skill=ctx.skill,
                score=ctx.score_total,
                score_breakdown=dict(ctx.score_breakdown),
                growth=ctx.growth.to_dict(),
                recommend_reason=ctx.recommend_reason,
                is_official=ctx.is_official,
                is_new=ctx.is_new,
            )
        )
        pick_traces.append(
            {
                "rank": i,
                "slot": ctx.slot,
                "skill_id": ctx.skill.id,
                "name": ctx.skill.name,
                "growth": trace_growth(ctx.skill, ctx.growth),
                "score": trace_score(ctx, cfg, ratios),
                "recommend_reason": ctx.recommend_reason,
            }
        )

    result = DigestResult(
        digest_date=digest_date,
        top_n=top_n,
        items=items,
        config_version=config_version(cfg),
        meta={"candidate_count": len(candidates), "selected_count": len(items), "vendors": vendors or []},
    )
    await finalize_digest_content(result, cfg)

    return {
        "digest_date": digest_date.isoformat(),
        "top_n": top_n,
        "content_md": result.content_md,
        "meta": result.meta,
        "selection_steps": selection_steps,
        "picks": pick_traces,
        "candidates": candidate_traces,
        "platform_ratios": {k: round(v, 4) for k, v in ratios.items()},
        "metrics_readiness": _metrics_readiness_note(candidates),
    }
