"""结构化 Top N 选择模块 —— 24h/7d 新发现 + 安装量变化最大。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.services.digest.config_loader import domestic_vendors
from app.services.digest.metrics import metric_abs_delta, momentum_score
from app.services.digest.pools import (
    POOL_MOMENTUM,
    POOL_OFFICIAL,
    POOL_POPULARITY,
    POOL_RECENT_24H,
    POOL_RECENT_7D,
    POOL_TREND,
    CandidateContext,
)
from app.services.digest.reasons import build_recommend_reason
from app.services.digest.scorer import score_all_candidates


def _scale_slots(slots_cfg: dict[str, Any], top_n: int) -> list[tuple[str, str, int]]:
    raw = [(n, str(s.get("pool") or n), int(s.get("count") or 0)) for n, s in slots_cfg.items()]
    base = sum(c for _, _, c in raw) or top_n
    scaled, assigned = [], 0
    for i, (slot, pool, count) in enumerate(raw):
        n = top_n - assigned if i == len(raw) - 1 else max(0, round(count * top_n / base))
        scaled.append((slot, pool, n))
        assigned += n
    diff = top_n - sum(n for _, _, n in scaled)
    if diff and scaled:
        s, p, n = scaled[0]
        scaled[0] = (s, p, n + diff)
    return scaled


def _pick_from_pool(
    candidates: list[CandidateContext],
    pool: str,
    count: int,
    *,
    selected_ids: set[int],
    vendor_count: dict[str, int],
    platform_count: dict[str, int],
    max_vendor: int,
    max_platform: int,
    sort_key,
) -> list[CandidateContext]:
    items = [c for c in candidates if pool in c.pools and c.skill.id not in selected_ids]
    items.sort(key=sort_key, reverse=True)
    picked: list[CandidateContext] = []
    for ctx in items:
        if len(picked) >= count:
            break
        v, src = ctx.skill.vendor, ctx.skill.source_id
        if vendor_count.get(v, 0) >= max_vendor:
            continue
        if platform_count.get(src, 0) >= max_platform:
            continue
        picked.append(ctx)
        selected_ids.add(ctx.skill.id)
        vendor_count[v] = vendor_count.get(v, 0) + 1
        platform_count[src] = platform_count.get(src, 0) + 1
    return picked


def _first_seen_ts(ctx: CandidateContext) -> datetime:
    return ctx.skill.first_seen_at or datetime.min


def _momentum_sort_key(ctx: CandidateContext):
    g = ctx.growth
    return (
        momentum_score(g),
        metric_abs_delta(g, window="24h"),
        metric_abs_delta(g, window="7d"),
        g.growth_3d_pct or 0,
        ctx.skill.install_count or 0,
    )


def _recent_sort_key(ctx: CandidateContext):
    return (
        _first_seen_ts(ctx),
        momentum_score(ctx.growth),
        ctx.skill.install_count or 0,
        1 if ctx.is_official else 0,
    )


def _sort_key_for_pool(pool: str, cfg: dict[str, Any]):
    if pool == POOL_RECENT_24H:
        return _recent_sort_key
    if pool == POOL_RECENT_7D:
        return _recent_sort_key
    if pool == POOL_MOMENTUM:
        return _momentum_sort_key
    if pool == POOL_OFFICIAL:
        return lambda c: (c.score_total, c.skill.install_count or 0, c.growth.trend_velocity_score)
    if pool == POOL_POPULARITY:
        return lambda c: (c.skill.install_count or 0, momentum_score(c.growth))
    if pool == POOL_TREND:
        return _momentum_sort_key
    return _recent_sort_key


def select_structured_picks(
    candidates: list[CandidateContext],
    cfg: dict[str, Any],
    *,
    top_n: int | None = None,
) -> list[CandidateContext]:
    sel = cfg.get("selection") or {}
    top_n = top_n or int(sel.get("default_top_n") or 10)
    slots = sel.get("slots") or {}
    div = sel.get("diversity") or {}
    max_vendor = int(div.get("max_per_vendor") or 2)
    max_platform = int(div.get("max_per_platform") or 4)

    score_all_candidates(candidates, cfg)

    result: list[CandidateContext] = []
    selected_ids: set[int] = set()
    vendor_count: dict[str, int] = {}
    platform_count: dict[str, int] = {}

    for slot_name, pool, count in _scale_slots(slots, top_n):
        key = _sort_key_for_pool(pool, cfg)
        picked = _pick_from_pool(
            candidates,
            pool,
            count,
            selected_ids=selected_ids,
            vendor_count=vendor_count,
            platform_count=platform_count,
            max_vendor=max_vendor,
            max_platform=max_platform,
            sort_key=key,
        )
        for ctx in picked:
            ctx.slot = slot_name
            ctx.recommend_reason = build_recommend_reason(ctx, slot_name)
            result.append(ctx)

    if len(result) < top_n:
        for ctx in sorted(
            [c for c in candidates if c.skill.id not in selected_ids],
            key=_momentum_sort_key,
            reverse=True,
        ):
            if len(result) >= top_n:
                break
            ctx.slot = ctx.slot or "fill"
            ctx.recommend_reason = build_recommend_reason(ctx, ctx.slot)
            result.append(ctx)

    return result[:top_n]


def _official_new_priority(ctx: CandidateContext) -> int:
    meta = ctx.skill.metadata_json if isinstance(ctx.skill.metadata_json, dict) else {}
    if meta.get("catalog") == "official_github" or (
        meta.get("official") and meta.get("repo")
    ):
        return 3
    if ctx.is_official:
        return 2
    return 1


def _is_recent_official(
    ctx: CandidateContext,
    *,
    ref: date,
    ref_dt: datetime | None,
    max_new_days: int,
    max_new_hours: int | None,
    skip_recency_filter: bool,
) -> bool:
    if skip_recency_filter:
        return True
    fs = ctx.skill.first_seen_at
    if not fs:
        return False
    if max_new_hours and max_new_hours > 0 and ref_dt is not None:
        age_h = (ref_dt - fs).total_seconds() / 3600.0
        return age_h <= max_new_hours
    age_days = (ref - fs.date()).days
    return age_days <= max_new_days


def select_official_new_picks(
    candidates: list[CandidateContext],
    cfg: dict[str, Any],
    *,
    top_n: int | None = None,
    ref_date: date | None = None,
    skip_recency_filter: bool = False,
    skip_official_filter: bool = False,
    skip_diversity_limits: bool = False,
    domestic_only: bool | None = None,
) -> list[CandidateContext]:
    """挑选官方发布、且在最近 N 天/小时内首次发现的 Skill（官方新增日报 / 保底推送）。"""
    sel = cfg.get("selection") or {}
    push_cfg = (cfg.get("push") or {}).get("official_new") or {}
    ref = ref_date or datetime.now(timezone.utc).replace(tzinfo=None).date()
    ref_dt = datetime.combine(ref, datetime.max.time()).replace(microsecond=0)
    top_n = top_n or int(push_cfg.get("top_n") or sel.get("default_top_n") or 10)
    max_new_days = int(push_cfg.get("max_new_days") or 1)
    max_new_hours = push_cfg.get("max_new_hours")
    max_new_hours = int(max_new_hours) if max_new_hours is not None else None
    if domestic_only is None:
        domestic_only = bool(push_cfg.get("domestic_only", False))
    div = sel.get("diversity") or {}
    max_vendor = int(push_cfg.get("max_per_vendor") or div.get("max_per_vendor") or 2)
    max_platform = int(push_cfg.get("max_per_platform") or div.get("max_per_platform") or 4)
    domestic = domestic_vendors(cfg)

    score_all_candidates(candidates, cfg)

    def eligible(ctx: CandidateContext) -> bool:
        if skip_official_filter:
            if not ctx.skill.first_seen_at:
                return False
        elif not ctx.is_official or not ctx.skill.first_seen_at:
            return False
        if domestic_only and ctx.skill.vendor not in domestic:
            return False
        return _is_recent_official(
            ctx,
            ref=ref,
            ref_dt=ref_dt,
            max_new_days=max_new_days,
            max_new_hours=max_new_hours,
            skip_recency_filter=skip_recency_filter,
        )

    items = [c for c in candidates if eligible(c)]
    items.sort(
        key=lambda c: (
            _official_new_priority(c),
            _first_seen_ts(c),
            c.score_total,
            c.skill.quality_score,
        ),
        reverse=True,
    )

    result: list[CandidateContext] = []
    vendor_count: dict[str, int] = {}
    platform_count: dict[str, int] = {}
    for ctx in items:
        if len(result) >= top_n:
            break
        if not skip_diversity_limits:
            v, src = ctx.skill.vendor, ctx.skill.source_id
            if vendor_count.get(v, 0) >= max_vendor:
                continue
            if platform_count.get(src, 0) >= max_platform:
                continue
            vendor_count[v] = vendor_count.get(v, 0) + 1
            platform_count[src] = platform_count.get(src, 0) + 1
        ctx.slot = "official_new"
        ctx.recommend_reason = build_recommend_reason(ctx, "official_new")
        result.append(ctx)
    return result


def select_guaranteed_official_new(
    candidates: list[CandidateContext],
    cfg: dict[str, Any],
    *,
    ref_date: date | None = None,
) -> list[CandidateContext]:
    """综合精选保底：国内大公司 24h 内官方发布必入选（不受 top_n / 多样性截断）。"""
    push_cfg = (cfg.get("push") or {}).get("official_new") or {}
    if not push_cfg.get("guarantee_in_digest", True):
        return []
    return select_official_new_picks(
        candidates,
        cfg,
        top_n=9999,
        ref_date=ref_date,
        skip_diversity_limits=True,
        domestic_only=bool(push_cfg.get("domestic_only", True)),
    )
