"""得物平台过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_dewu_relevant


def test_dewu_accepts_dedicated_repo():
    rec = RawSkillRecord(
        external_id="wxkingstar/SpecFusion:specfusion",
        name="specfusion",
        vendor="得物",
        source_id="dewu_skills",
        raw_description="得物开放平台 API 文档检索 source=dewu",
        metadata={"repo": "wxkingstar/SpecFusion", "path": "specfusion"},
    )
    assert is_dewu_relevant(rec)


def test_dewu_rejects_poison_noise():
    rec = RawSkillRecord(
        external_id="foo/bar:skills/poisoned-pipeline",
        name="poisoned-pipeline",
        vendor="得物",
        source_id="dewu_skills",
        raw_description="Security benchmark for poisoned skill pipelines",
        metadata={"repo": "foo/bar", "path": "skills/poisoned-pipeline"},
    )
    assert not is_dewu_relevant(rec)


def test_dewu_accepts_official():
    rec = RawSkillRecord(
        external_id="dewu-open-platform",
        name="得物开放平台",
        vendor="得物",
        source_id="dewu_skills",
        raw_description="官方开放平台",
        metadata={"official": True},
    )
    assert is_dewu_relevant(rec)
