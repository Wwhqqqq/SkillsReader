"""结构化 Top N 选择模块。

本模块实现文档 §7.3 中的槽位分配（slots）与多样性约束（同厂商/同平台上限），
以及从各池中按不同排序策略挑选候选填充最终 TopN 的逻辑。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services.digest.pools import (
    POOL_DISCOVERY,
    POOL_OFFICIAL,
    POOL_TREND,
    CandidateContext,
)
from app.services.digest.reasons import build_recommend_reason
from app.services.digest.scorer import score_all_candidates


def _scale_slots(slots_cfg: dict[str, Any], top_n: int) -> list[tuple[str, str, int]]:
    # 将 slots 配置（如 {"official": {"pool":"official","count":3}, ...}）
    # 按 top_n 缩放为实际的每个槽位分配数量，保证总和为 top_n。
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
    # 过滤出属于指定池且未被选中的候选，按传入的 sort_key 排序（可以是分数/趋势/质量等复合键）
    items = [c for c in candidates if pool in c.pools and c.skill.id not in selected_ids]
    items.sort(key=sort_key, reverse=True)
    picked: list[CandidateContext] = []
    # 迭代候选并实时应用多样性约束：同一厂商与同一平台的选入次数不得超过阈值
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

    # 先为所有候选计算分数（score_total 与 score_breakdown）
    score_all_candidates(candidates, cfg)

    # 不同槽位使用不同的排序键：
    # - 官方槽位优先总体得分；
    # - 趋势槽位优先 trend_velocity_score；
    # - 发现槽位优先新近标记与质量分。
    sort_score = lambda c: (c.score_total, c.growth.trend_velocity_score)
    sort_trend = lambda c: (c.growth.trend_velocity_score, c.growth.log_growth_1d, c.score_total)
    sort_disc = lambda c: (1 if c.is_new else 0, c.score_breakdown.get("quality", 0), c.score_total)

    result: list[CandidateContext] = []
    selected_ids: set[int] = set()
    vendor_count: dict[str, int] = {}
    platform_count: dict[str, int] = {}

    # 逐槽位挑选：按 scaled slots 顺序对每个池挑选指定数量
    for slot_name, pool, count in _scale_slots(slots, top_n):
        key = sort_score if pool == POOL_OFFICIAL else sort_trend if pool == POOL_TREND else sort_disc
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

    # 若不足 top_n，则补位：按总体评分从剩余候选中补充，slot 标记为 'fill'
    if len(result) < top_n:
        for ctx in sorted(
            [c for c in candidates if c.skill.id not in selected_ids],
            key=sort_score,
            reverse=True,
        ):
            if len(result) >= top_n:
                break
            ctx.slot = ctx.slot or "fill"
            ctx.recommend_reason = build_recommend_reason(ctx, ctx.slot)
            result.append(ctx)

    return result[:top_n]


def _first_seen_ts(ctx: CandidateContext) -> datetime:
    return ctx.skill.first_seen_at or datetime.min


def _official_new_priority(ctx: CandidateContext) -> int:
    meta = ctx.skill.metadata_json if isinstance(ctx.skill.metadata_json, dict) else {}
    if meta.get("catalog") == "official_github" or (
        meta.get("official") and meta.get("repo")
    ):
        return 3
    if ctx.is_official:
        return 2
    return 1


def select_official_new_picks(
    candidates: list[CandidateContext],
    cfg: dict[str, Any],
    *,
    top_n: int | None = None,
    ref_date: date | None = None,
    skip_recency_filter: bool = False,
    skip_official_filter: bool = False,
) -> list[CandidateContext]:
    """仅挑选官方发布、且在最近 N 天内首次发现的 Skill（官方新增日报）。"""
    sel = cfg.get("selection") or {}
    push_cfg = (cfg.get("push") or {}).get("official_new") or {}
    ref = ref_date or datetime.utcnow().date()
    top_n = top_n or int(push_cfg.get("top_n") or sel.get("default_top_n") or 10)
    max_new_days = int(push_cfg.get("max_new_days") or 1)
    div = sel.get("diversity") or {}
    max_vendor = int(push_cfg.get("max_per_vendor") or div.get("max_per_vendor") or 2)
    max_platform = int(push_cfg.get("max_per_platform") or div.get("max_per_platform") or 4)

    score_all_candidates(candidates, cfg)

    def is_recent_official(ctx: CandidateContext) -> bool:
        if skip_official_filter:
            return bool(ctx.skill.first_seen_at)
        if not ctx.is_official or not ctx.skill.first_seen_at:
            return False
        if skip_recency_filter:
            return True
        age = (ref - ctx.skill.first_seen_at.date()).days
        return age <= max_new_days

    items = [c for c in candidates if is_recent_official(c)]
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
        v, src = ctx.skill.vendor, ctx.skill.source_id
        if vendor_count.get(v, 0) >= max_vendor:
            continue
        if platform_count.get(src, 0) >= max_platform:
            continue
        ctx.slot = "official_new"
        ctx.recommend_reason = build_recommend_reason(ctx, "official")
        result.append(ctx)
        vendor_count[v] = vendor_count.get(v, 0) + 1
        platform_count[src] = platform_count.get(src, 0) + 1
    return result
