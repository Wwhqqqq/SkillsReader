"""7 日历史快照指标 —— 验证首日空数据与第 8 日真实增速。"""

from datetime import date, datetime, timedelta

from app.models import Skill
from app.services.digest.config_loader import load_digest_config
from app.services.digest.metrics import apply_platform_zscores, build_growth_metrics, growth_rate


def _skill(sid: int, install: int, source_id: str = "sim_tencent") -> Skill:
    ts = datetime(2026, 6, 1, 12, 0, 0)
    return Skill(
        id=sid,
        fingerprint=f"timeline-{sid}",
        vendor="腾讯",
        source_id=source_id,
        external_id=f"ext-{sid}",
        name=f"Skill-{sid}",
        raw_description="测试用描述足够长用于质量评分与候选池逻辑验证。",
        install_count=install,
        quality_score=70,
        first_seen_at=ts,
        last_seen_at=ts,
        metadata_json={"official": sid == 1},
        tags=["腾讯"],
    )


def test_day1_no_history_uses_zero_baseline():
    ref = date(2026, 6, 1)
    skill = _skill(1, install=100)
    growth = build_growth_metrics(skill, {}, ref)
    assert growth.value_1d_ago == 0
    assert growth.growth_1d_pct == 10000.0  # (100-0)/1 * 100


def test_day8_full_7d_history():
    ref = date(2026, 6, 8)
    skill = _skill(1, install=500)
    snapshots = {
        ref: 500,
        ref - timedelta(days=1): 400,
        ref - timedelta(days=3): 250,
        ref - timedelta(days=7): 100,
    }
    growth = build_growth_metrics(skill, snapshots, ref)
    assert growth.value_7d_ago == 100
    assert growth.growth_7d_pct == 400.0
    assert growth_rate(500, 100) == 4.0


def test_partial_history_day4():
    ref = date(2026, 6, 4)
    skill = _skill(1, install=200)
    snapshots = {
        ref: 200,
        ref - timedelta(days=1): 150,
        ref - timedelta(days=3): 100,
    }
    growth = build_growth_metrics(skill, snapshots, ref)
    assert growth.value_1d_ago == 150
    assert growth.value_3d_ago == 100
    assert growth.value_7d_ago is None
    assert growth.growth_7d_pct == 100.0


def test_zscore_requires_multiple_candidates_same_platform():
    cfg = load_digest_config()
    ref = date(2026, 6, 8)
    s1 = _skill(1, 500)
    s2 = _skill(2, 300)
    snaps1 = {ref: 500, ref - timedelta(days=1): 100, ref - timedelta(days=3): 50, ref - timedelta(days=7): 10}
    snaps2 = {ref: 300, ref - timedelta(days=1): 280, ref - timedelta(days=3): 200, ref - timedelta(days=7): 100}
    g1 = build_growth_metrics(s1, snaps1, ref)
    g2 = build_growth_metrics(s2, snaps2, ref)
    apply_platform_zscores([("sim_tencent", g1), ("sim_tencent", g2)], cfg)
    assert g1.trend_velocity_score != g2.trend_velocity_score


def test_eight_day_timeline_simulation():
    """模拟连续 8 天每日写入快照，第 8 天 7 日增速应基于 D1 而非回退值。"""
    start = date(2026, 6, 1)
    daily = [10, 20, 35, 50, 80, 120, 200, 320]
    skill = _skill(1, install=daily[-1])
    snapshots: dict[date, int] = {}
    for i, val in enumerate(daily):
        snapshots[start + timedelta(days=i)] = val

    ref = start + timedelta(days=7)
    skill.install_count = daily[-1]
    growth = build_growth_metrics(skill, snapshots, ref)

    assert growth.metric_value == 320
    assert growth.value_7d_ago == 10
    assert growth.growth_7d_pct == 3100.0
    assert growth.value_1d_ago == 200
    assert growth.growth_1d_pct == 60.0
