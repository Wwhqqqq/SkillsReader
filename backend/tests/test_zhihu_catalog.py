"""知乎多源目录单元测试。"""

from app.adapters.common.platform_filters import is_zhihu_relevant
from app.adapters.common.skillsmp_catalog import record_from_skillsmp
from app.adapters.zhihu.catalog import record_from_clawhub


def test_record_from_clawhub():
    rec = record_from_clawhub(
        {"slug": "zhihu-cli", "displayName": "Zhihu CLI", "summary": "Search Zhihu hot topics"},
        source_id="zhihu_skills",
        vendor="知乎",
    )
    assert rec.external_id == "clawhub:zhihu-cli"
    assert is_zhihu_relevant(rec)


def test_record_from_skillsmp():
    rec = record_from_skillsmp(
        {
            "id": "abc-skill",
            "name": "zhihu-search",
            "description": "Search Zhihu content",
            "githubUrl": "https://github.com/foo/zhihu-search",
            "skillUrl": "https://skillsmp.com/creators/foo/zhihu-search/skill",
            "stars": 12,
        },
        source_id="zhihu_skills",
        vendor="知乎",
    )
    assert rec.external_id.startswith("skillsmp:")
    assert len(rec.external_id) <= 128
    assert rec.metadata["catalog"] == "skillsmp"
    assert is_zhihu_relevant(rec)
