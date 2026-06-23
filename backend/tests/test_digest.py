"""每日精选模块单元测试。"""

from datetime import date, datetime, timedelta

from app.models import Skill
from app.services.digest.config_loader import load_digest_config
from app.services.digest.metrics import GrowthMetrics, apply_platform_zscores, build_growth_metrics, growth_rate
from app.services.digest.pools import POOL_OFFICIAL, POOL_TREND, POOL_DISCOVERY, CandidateContext, classify_pools
from app.services.digest.scorer import score_candidate
from app.services.digest.selector import select_official_new_picks, select_structured_picks


def _skill(
    sid: int,
    *,
    vendor: str = "腾讯",
    install: int = 0,
    quality: int = 80,
    days_ago: int = 0,
    official: bool = True,
    source_id: str = "wechat_skillhub",
) -> Skill:
    ts = datetime.utcnow() - timedelta(days=days_ago)
    meta = {"publisherType": "官方发布" if official else "个人创作者", "catalog": "official"}
    return Skill(
        id=sid,
        fingerprint=f"fp-{sid}",
        vendor=vendor,
        source_id=source_id,
        external_id=str(sid),
        name=f"Skill-{sid}",
        raw_description="这是一个足够长的描述，用于测试发现池与质量评分逻辑。",
        install_count=install,
        quality_score=quality,
        first_seen_at=ts,
        last_seen_at=ts,
        metadata_json=meta,
        tags=[vendor],
    )


def test_growth_rate_from_zero():
    assert growth_rate(100, 0) == 100.0
    assert growth_rate(0, 0) == 0.0
    assert growth_rate(150, 100) == 0.5


def test_build_growth_metrics_with_snapshots():
    skill = _skill(1, install=200)
    ref = date.today()
    snapshots = {
        ref: 200,
        ref - timedelta(days=1): 100,
        ref - timedelta(days=3): 50,
        ref - timedelta(days=7): 20,
    }
    growth = build_growth_metrics(skill, snapshots, ref)
    assert growth.growth_1d_pct == 100.0
    assert growth.log_growth_1d > 0


def test_classify_official_pool():
    cfg = load_digest_config()
    skill = _skill(1, official=True, quality=70)
    growth = GrowthMetrics(metric_value=50, trend_velocity_score=1)
    pools = classify_pools(skill, growth, cfg, ref_date=date.today())
    assert POOL_OFFICIAL in pools


def test_classify_trend_pool_on_velocity():
    cfg = load_digest_config()
    skill = _skill(2, install=500, official=False, vendor="海外社区", quality=60, source_id="skills_sh")
    growth = GrowthMetrics(trend_velocity_score=60, metric_value=500)
    pools = classify_pools(skill, growth, cfg, ref_date=date.today())
    assert POOL_TREND in pools


def test_score_candidate_official_bonus():
    cfg = load_digest_config()
    skill = _skill(3, official=True, install=1000)
    growth = GrowthMetrics(trend_velocity_score=40)
    ctx = CandidateContext(skill=skill, growth=growth, pools={POOL_OFFICIAL})
    total, bd = score_candidate(ctx, cfg, platform_ratio_map={"wechat_skillhub": 0.2})
    assert total > 0
    assert bd["official"] >= 20


def test_structured_selector_respects_slot_counts():
    cfg = load_digest_config()
    ref = date.today()
    candidates = []
    for i in range(1, 21):
        official = i <= 5
        install = 1000 - i * 10
        skill = _skill(
            i,
            vendor=["腾讯", "阿里", "美团", "字节", "知乎"][i % 5],
            install=install,
            official=official,
            days_ago=i % 10,
            quality=70 + (i % 5),
        )
        growth = GrowthMetrics(
            metric_value=install,
            trend_velocity_score=50 if i <= 8 else 10,
            log_growth_1d=0.5 if i <= 8 else 0.1,
        )
        pools = classify_pools(skill, growth, cfg, ref_date=ref)
        if not pools:
            pools = {POOL_DISCOVERY}
        candidates.append(
            CandidateContext(
                skill=skill,
                growth=growth,
                pools=pools,
                is_official=official,
                is_new=i <= 2,
            )
        )
    apply_platform_zscores([(c.skill.source_id, c.growth) for c in candidates], cfg)

    picks = select_structured_picks(candidates, cfg, top_n=10)
    assert len(picks) == 10
    assert len({p.skill.id for p in picks}) == 10


def test_select_official_new_picks_only_official_and_recent():
    cfg = load_digest_config()
    ref = date.today()
    candidates = []
    for i, (official, days_ago) in enumerate([(True, 0), (True, 2), (False, 0)], start=1):
        skill = _skill(i, official=official, days_ago=days_ago, quality=80)
        growth = GrowthMetrics(trend_velocity_score=10)
        pools = classify_pools(skill, growth, cfg, ref_date=ref)
        candidates.append(
            CandidateContext(
                skill=skill,
                growth=growth,
                pools=pools or {POOL_DISCOVERY},
                is_official=official,
                is_new=days_ago <= 1,
            )
        )
    picks = select_official_new_picks(candidates, cfg, top_n=5, ref_date=ref)
    assert len(picks) == 1
    assert picks[0].is_official is True
    assert picks[0].slot == "official_new"
