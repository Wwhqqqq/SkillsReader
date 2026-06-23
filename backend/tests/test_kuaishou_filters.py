"""快手平台过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_kuaishou_relevant


def test_kuaishou_accepts_dedicated_repo():
    rec = RawSkillRecord(
        external_id="XieWxx/maxhub-api-skills:maxhub-kuaishou",
        name="maxhub-kuaishou",
        vendor="快手",
        source_id="kuaishou_skills",
        raw_description="快手数据查询",
        metadata={"repo": "XieWxx/maxhub-api-skills", "path": "maxhub-kuaishou"},
    )
    assert is_kuaishou_relevant(rec)


def test_kuaishou_rejects_unrelated():
    rec = RawSkillRecord(
        external_id="foo/bar:skills/generic-tool",
        name="generic-tool",
        vendor="快手",
        source_id="kuaishou_skills",
        raw_description="A generic devops helper",
        metadata={"repo": "foo/bar", "path": "skills/generic-tool"},
    )
    assert not is_kuaishou_relevant(rec)


def test_kuaishou_accepts_official():
    rec = RawSkillRecord(
        external_id="kuaishou-open-platform",
        name="快手开放平台",
        vendor="快手",
        source_id="kuaishou_skills",
        raw_description="官方开放平台",
        metadata={"official": True},
    )
    assert is_kuaishou_relevant(rec)
