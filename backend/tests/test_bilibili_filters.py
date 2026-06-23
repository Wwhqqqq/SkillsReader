"""哔哩哔哩平台过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_bilibili_relevant


def test_bilibili_accepts_dedicated_repo():
    rec = RawSkillRecord(
        external_id="yutto-dev/yutto:skills/bilibili-video-download",
        name="bilibili-video-download",
        vendor="哔哩哔哩",
        source_id="bilibili_skills",
        raw_description="Download Bilibili videos with yutto",
        metadata={"repo": "yutto-dev/yutto", "path": "skills/bilibili-video-download"},
    )
    assert is_bilibili_relevant(rec)


def test_bilibili_rejects_unrelated():
    rec = RawSkillRecord(
        external_id="foo/bar:skills/generic-tool",
        name="generic-tool",
        vendor="哔哩哔哩",
        source_id="bilibili_skills",
        raw_description="Generic automation helper",
        metadata={"repo": "foo/bar", "path": "skills/generic-tool"},
    )
    assert not is_bilibili_relevant(rec)


def test_bilibili_rejects_portal_anchor():
    rec = RawSkillRecord(
        external_id="bilibili-open-platform",
        name="哔哩哔哩开放平台",
        vendor="哔哩哔哩",
        source_id="bilibili_skills",
        raw_description="官方 API",
        detail_url="https://open.bilibili.com/",
        metadata={"official": True, "catalog": "official"},
    )
    assert not is_bilibili_relevant(rec)
