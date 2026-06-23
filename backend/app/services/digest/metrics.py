"""指标快照 + 跨平台 Log/Z-Score 趋势速度（8 小时 × N 窗口）。"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill, SkillMetricSnapshot
from app.services.digest.config_loader import load_digest_config


@dataclass
class GrowthMetrics:
    metric_value: int = 0
    metric_kind: str = "install"
    value_1d_ago: int | None = None
    value_3d_ago: int | None = None
    value_7d_ago: int | None = None
    growth_1d_pct: float = 0.0
    growth_3d_pct: float = 0.0
    growth_7d_pct: float = 0.0
    log_growth_1d: float = 0.0
    log_growth_3d: float = 0.0
    log_growth_7d: float = 0.0
    z_1d: float = 0.0
    z_3d: float = 0.0
    z_7d: float = 0.0
    trend_velocity_score: float = 0.0
    growth_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_value": self.metric_value,
            "metric_kind": self.metric_kind,
            "value_1d_ago": self.value_1d_ago,
            "value_3d_ago": self.value_3d_ago,
            "value_7d_ago": self.value_7d_ago,
            "growth_1d_pct": round(self.growth_1d_pct, 2),
            "growth_3d_pct": round(self.growth_3d_pct, 2),
            "growth_7d_pct": round(self.growth_7d_pct, 2),
            "log_growth_1d": round(self.log_growth_1d, 4),
            "log_growth_3d": round(self.log_growth_3d, 4),
            "log_growth_7d": round(self.log_growth_7d, 4),
            "z_1d": round(self.z_1d, 3),
            "z_3d": round(self.z_3d, 3),
            "z_7d": round(self.z_7d, 3),
            "trend_velocity_score": round(self.trend_velocity_score, 2),
            "growth_score": round(self.growth_score, 2),
        }


def metrics_window_cfg(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_digest_config()
    m = cfg.get("metrics") or {}
    period_hours = int(m.get("period_hours") or 8)
    lookback = m.get("lookback_periods") or [1, 3, 7]
    periods = [int(x) for x in lookback[:3]] + [1, 3, 7]
    p1, p3, p7 = periods[0], periods[1], periods[2]
    return {
        "period_hours": period_hours,
        "p1": p1,
        "p3": p3,
        "p7": p7,
        "h1": p1 * period_hours,
        "h3": p3 * period_hours,
        "h7": p7 * period_hours,
    }


def growth_rate(current: int, past: int | None) -> float:
    if past is None:
        return 1.0 if current > 0 else 0.0
    return (current - past) / max(past, 1)


def log_growth(current: int, past: int | None) -> float:
    return math.log1p(max(0.0, growth_rate(current, past)))


def pct_growth(current: int, past: int | None) -> float:
    return growth_rate(current, past) * 100.0


def _zscore(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [0.0] * len(values)
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev <= 1e-9:
        return [0.0] * len(values)
    return [(v - mean) / stdev for v in values]


def apply_platform_zscores(
    items: list[tuple[str, GrowthMetrics]],
    cfg: dict[str, Any],
) -> None:
    vw = (cfg.get("scoring") or {}).get("velocity_weights") or {}
    w1 = float(vw.get("z_1d") or 0.4)
    w3 = float(vw.get("z_3d") or 0.3)
    w7 = float(vw.get("z_7d") or 0.3)
    total_w = w1 + w3 + w7 or 1.0
    trend_factor = float((cfg.get("scoring") or {}).get("trend_velocity_factor") or 1.0)

    by_platform: dict[str, list[GrowthMetrics]] = {}
    for platform, gm in items:
        by_platform.setdefault(platform, []).append(gm)

    for _platform, group in by_platform.items():
        z1 = _zscore([g.log_growth_1d for g in group])
        z3 = _zscore([g.log_growth_3d for g in group])
        z7 = _zscore([g.log_growth_7d for g in group])
        for i, gm in enumerate(group):
            gm.z_1d = z1[i]
            gm.z_3d = z3[i]
            gm.z_7d = z7[i]
            raw = (w1 * gm.z_1d + w3 * gm.z_3d + w7 * gm.z_7d) / total_w
            mapped = max(0.0, min(100.0, (raw + 2) * 25))
            gm.trend_velocity_score = round(mapped * trend_factor, 2)
            gm.growth_score = gm.trend_velocity_score


def _value_at_or_before(
    timeline: list[tuple[datetime, int]], target: datetime
) -> int | None:
    best: int | None = None
    for ts, val in timeline:
        if ts <= target:
            best = val
        else:
            break
    return best


async def record_snapshot_now(
    session: AsyncSession,
    skill: Skill,
    *,
    recorded_at: datetime | None = None,
) -> None:
    """每次扫描写入一条时间点快照（支持 8 小时窗口）。"""
    ts = recorded_at or datetime.utcnow().replace(tzinfo=None)
    value = max(0, int(skill.install_count or 0))
    session.add(
        SkillMetricSnapshot(
            skill_id=skill.id,
            snapshot_date=ts.date(),
            recorded_at=ts,
            metric_value=value,
            metric_kind="install",
            source_id=skill.source_id,
        )
    )


async def upsert_daily_snapshot(
    session: AsyncSession,
    skill: Skill,
    *,
    snapshot_date: date | None = None,
) -> None:
    await record_snapshot_now(session, skill, recorded_at=datetime.utcnow().replace(tzinfo=None))


async def record_snapshots_for_skills(
    session: AsyncSession,
    skill_ids: list[int],
    *,
    snapshot_date: date | None = None,
) -> int:
    if not skill_ids:
        return 0
    skills = list(
        (await session.scalars(select(Skill).where(Skill.id.in_(skill_ids)))).all()
    )
    for skill in skills:
        await record_snapshot_now(session, skill)
    return len(skills)


async def load_snapshots_map(
    session: AsyncSession,
    skill_ids: list[int],
    ref_date: date,
) -> dict[int, dict[date, int]]:
    if not skill_ids:
        return {}
    start = ref_date - timedelta(days=8)
    rows = (
        await session.scalars(
            select(SkillMetricSnapshot).where(
                SkillMetricSnapshot.skill_id.in_(skill_ids),
                SkillMetricSnapshot.snapshot_date >= start,
                SkillMetricSnapshot.snapshot_date <= ref_date,
            )
        )
    ).all()
    out: dict[int, dict[date, int]] = {}
    for row in rows:
        out.setdefault(row.skill_id, {})[row.snapshot_date] = row.metric_value
    return out


async def load_snapshot_timelines(
    session: AsyncSession,
    skill_ids: list[int],
    ref_dt: datetime,
    *,
    hours_back: int = 60,
) -> dict[int, list[tuple[datetime, int]]]:
    if not skill_ids:
        return {}
    start = ref_dt - timedelta(hours=hours_back)
    rows = (
        await session.scalars(
            select(SkillMetricSnapshot)
            .where(
                SkillMetricSnapshot.skill_id.in_(skill_ids),
                SkillMetricSnapshot.recorded_at.isnot(None),
                SkillMetricSnapshot.recorded_at >= start,
                SkillMetricSnapshot.recorded_at <= ref_dt,
            )
            .order_by(SkillMetricSnapshot.recorded_at.asc())
        )
    ).all()
    out: dict[int, list[tuple[datetime, int]]] = {sid: [] for sid in skill_ids}
    for row in rows:
        if row.recorded_at is not None:
            out.setdefault(row.skill_id, []).append((row.recorded_at, row.metric_value))
    return out


def build_growth_metrics(
    skill: Skill,
    snapshots: dict[date, int],
    ref_date: date,
) -> GrowthMetrics:
    """日粒度快照（兼容旧测试）。"""
    current = snapshots.get(ref_date, skill.install_count or 0)
    d1, d3, d7 = ref_date - timedelta(days=1), ref_date - timedelta(days=3), ref_date - timedelta(days=7)
    v1, v3, v7 = snapshots.get(d1), snapshots.get(d3), snapshots.get(d7)

    if not snapshots and skill.first_seen_at:
        age = (ref_date - skill.first_seen_at.date()).days
        if age <= 1 and current > 0:
            v1 = 0
        if age <= 3 and current > 0 and v3 is None:
            v3 = 0
        if age <= 7 and current > 0 and v7 is None:
            v7 = 0

    meta = skill.metadata_json if isinstance(skill.metadata_json, dict) else {}
    if meta.get("trend_source") and meta.get("section") in ("trending", "hot") and v1 is None:
        v1 = 0

    return GrowthMetrics(
        metric_value=current,
        value_1d_ago=v1,
        value_3d_ago=v3,
        value_7d_ago=v7,
        growth_1d_pct=pct_growth(current, v1),
        growth_3d_pct=pct_growth(current, v3),
        growth_7d_pct=pct_growth(current, v7),
        log_growth_1d=log_growth(current, v1),
        log_growth_3d=log_growth(current, v3),
        log_growth_7d=log_growth(current, v7),
    )


def build_growth_metrics_at(
    skill: Skill,
    timeline: list[tuple[datetime, int]],
    ref_dt: datetime,
    cfg: dict[str, Any] | None = None,
) -> GrowthMetrics:
    """8 小时 × N 窗口：1/3/7 个周期前。"""
    win = metrics_window_cfg(cfg)
    current = skill.install_count or 0
    if timeline:
        current = timeline[-1][1]

    t1 = ref_dt - timedelta(hours=win["h1"])
    t3 = ref_dt - timedelta(hours=win["h3"])
    t7 = ref_dt - timedelta(hours=win["h7"])
    v1 = _value_at_or_before(timeline, t1)
    v3 = _value_at_or_before(timeline, t3)
    v7 = _value_at_or_before(timeline, t7)

    if skill.first_seen_at:
        age_h = (ref_dt - skill.first_seen_at).total_seconds() / 3600.0
        if age_h <= win["h1"] and current > 0 and v1 is None:
            v1 = 0
        if age_h <= win["h3"] and current > 0 and v3 is None:
            v3 = 0
        if age_h <= win["h7"] and current > 0 and v7 is None:
            v7 = 0

    return GrowthMetrics(
        metric_value=current,
        value_1d_ago=v1,
        value_3d_ago=v3,
        value_7d_ago=v7,
        growth_1d_pct=pct_growth(current, v1),
        growth_3d_pct=pct_growth(current, v3),
        growth_7d_pct=pct_growth(current, v7),
        log_growth_1d=log_growth(current, v1),
        log_growth_3d=log_growth(current, v3),
        log_growth_7d=log_growth(current, v7),
    )


async def batch_growth_metrics(
    session: AsyncSession,
    skills: list[Skill],
    ref_date: date,
    cfg: dict[str, Any] | None = None,
) -> dict[int, GrowthMetrics]:
    cfg = cfg or load_digest_config()
    win = metrics_window_cfg(cfg)
    ref_dt = datetime.combine(ref_date, datetime.max.time()).replace(microsecond=0)
    skill_ids = [s.id for s in skills]

    timelines = await load_snapshot_timelines(
        session, skill_ids, ref_dt, hours_back=win["h7"] + win["period_hours"]
    )
    has_timeline = any(timelines.get(sid) for sid in skill_ids)

    out: dict[int, GrowthMetrics] = {}
    if has_timeline:
        for skill in skills:
            out[skill.id] = build_growth_metrics_at(
                skill, timelines.get(skill.id, []), ref_dt, cfg
            )
    else:
        snap_map = await load_snapshots_map(session, skill_ids, ref_date)
        for skill in skills:
            out[skill.id] = build_growth_metrics(
                skill, snap_map.get(skill.id, {}), ref_date
            )

    apply_platform_zscores([(s.source_id, out[s.id]) for s in skills], cfg)
    return out
