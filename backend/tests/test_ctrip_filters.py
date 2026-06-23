"""携程平台过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_ctrip_relevant


def test_ctrip_accepts_dedicated_repo():
    rec = RawSkillRecord(
        external_id="yflaz/ctrip-skill:ctrip-skill",
        name="ctrip-skill",
        vendor="携程",
        source_id="ctrip_skills",
        raw_description="携程机票火车查询",
        metadata={"repo": "yflaz/ctrip-skill", "path": "ctrip-skill"},
    )
    assert is_ctrip_relevant(rec)


def test_ctrip_rejects_unrelated_trip_noise():
    rec = RawSkillRecord(
        external_id="foo/bar:skills/roundtrip-radar",
        name="roundtrip-radar",
        vendor="携程",
        source_id="ctrip_skills",
        raw_description="Round trip flight price radar for generic airlines",
        metadata={"repo": "foo/bar", "path": "skills/roundtrip-radar"},
    )
    assert not is_ctrip_relevant(rec)


def test_ctrip_accepts_official():
    rec = RawSkillRecord(
        external_id="ctrip-wendao-openclaw",
        name="携程问道 OpenClaw Skill",
        vendor="携程",
        source_id="ctrip_skills",
        raw_description="官方 Wendao Skill",
        metadata={"official": True},
    )
    assert is_ctrip_relevant(rec)
