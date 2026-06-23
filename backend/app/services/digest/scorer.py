"""最终排序评分 —— 白名单厂商 + install_count 为主。"""

from __future__ import annotations

import math
from typing import Any

from app.services.digest.config_loader import domestic_vendors, load_digest_config
from app.services.digest.pools import CandidateContext, POOL_OFFICIAL
from app.services.digest.quality import compute_digest_quality
from app.services.enrichment.skill_classification import PUBLISHER_OFFICIAL, publisher_type_for


def _normalize_weights(weights: dict[str, Any]) -> dict[str, float]:
    raw = {k: float(v) for k, v in weights.items()}
    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}


def platform_ratios(candidates: list[CandidateContext]) -> dict[str, float]:
    if not candidates:
        return {}
    counts: dict[str, int] = {}
    for c in candidates:
        src = c.skill.source_id
        counts[src] = counts.get(src, 0) + 1
    n = len(candidates)
    return {k: v / n for k, v in counts.items()}


def _install_score(install: int, cfg: dict[str, Any]) -> float:
    scoring = cfg.get("scoring") or {}
    exp = float(scoring.get("install_exponent") or 0.42)
    mult = float(scoring.get("install_multiplier") or 3.2)
    if install <= 0:
        return 0.0
    return min(100.0, (install ** exp) * mult)


def score_trend(ctx: CandidateContext, cfg: dict[str, Any]) -> float:
    scoring = cfg.get("scoring") or {}
    install = ctx.skill.install_count or 0
    base = _install_score(install, cfg)
    velocity = ctx.growth.trend_velocity_score or 0.0
    factor = float(scoring.get("trend_velocity_factor") or 0.05)
    sw = (scoring.get("source_weights") or {}).get(ctx.skill.source_id)
    if sw is None:
        sw = (scoring.get("source_weights") or {}).get("default", 0.8)
    return min(100.0, base * 0.95 + velocity * factor * float(sw))


def score_official(ctx: CandidateContext, cfg: dict[str, Any]) -> float:
    skill = ctx.skill
    scoring = cfg.get("scoring") or {}
    meta = skill.metadata_json if isinstance(skill.metadata_json, dict) else {}
    pub = publisher_type_for(skill)

    if skill.vendor in domestic_vendors(cfg):
        return float(scoring.get("whitelist_vendor_score") or 85)

    if pub == PUBLISHER_OFFICIAL or meta.get("official"):
        return float(scoring.get("official_publisher_score") or 70)

    if POOL_OFFICIAL in ctx.pools:
        return 40.0
    return 0.0


def score_quality(ctx: CandidateContext, cfg: dict[str, Any]) -> float:
    scoring = cfg.get("scoring") or {}
    factor = float(scoring.get("quality_factor") or 0.15)
    return compute_digest_quality(ctx.skill) * factor


def score_diversity(ctx: CandidateContext, ratios: dict[str, float]) -> float:
    ratio = ratios.get(ctx.skill.source_id, 0.0)
    return max(0.0, min(100.0, (1.0 - ratio) * 100)) * 0.2


def score_candidate(
    ctx: CandidateContext,
    cfg: dict[str, Any],
    *,
    platform_ratio_map: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    scoring = cfg.get("scoring") or {}
    mode = scoring.get("mode") or "default"
    ratios = platform_ratio_map or {}

    if mode == "whitelist_install":
        install = ctx.skill.install_count or 0
        install_part = _install_score(install, cfg)
        vendor_part = score_official(ctx, cfg)
        total = min(100.0, install_part * 0.55 + vendor_part * 0.45)
        breakdown = {
            "trend": round(install_part, 2),
            "official": round(vendor_part, 2),
            "quality": round(score_quality(ctx, cfg), 2),
            "diversity": round(score_diversity(ctx, ratios), 2),
        }
        return round(total, 2), breakdown

    weights = _normalize_weights((scoring.get("final_weights") or {}))
    breakdown = {
        "trend": round(score_trend(ctx, cfg), 2),
        "official": round(score_official(ctx, cfg), 2),
        "quality": round(score_quality(ctx, cfg), 2),
        "diversity": round(score_diversity(ctx, ratios), 2),
    }
    total = sum(breakdown[k] * weights.get(k, 0) for k in breakdown)
    return round(total, 2), breakdown


def score_all_candidates(
    candidates: list[CandidateContext],
    cfg: dict[str, Any] | None = None,
) -> None:
    cfg = cfg or load_digest_config()
    ratios = platform_ratios(candidates)
    for ctx in candidates:
        total, bd = score_candidate(ctx, cfg, platform_ratio_map=ratios)
        ctx.score_total = total
        ctx.score_breakdown = bd
