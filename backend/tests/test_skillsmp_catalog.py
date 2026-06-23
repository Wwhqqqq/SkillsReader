"""SkillsMP 去重与 stats 单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.skillsmp_catalog import dedupe_skillsmp_records


def test_dedupe_skillsmp_by_github_url():
    a = RawSkillRecord(
        external_id="skillsmp:a",
        name="meituan-queue",
        vendor="美团",
        source_id="meituan_ai_hub",
        raw_description="queue",
        install_count=10,
        metadata={"githubUrl": "https://github.com/foo/bar", "catalog": "skillsmp"},
    )
    b = RawSkillRecord(
        external_id="skillsmp:b",
        name="meituan-queue",
        vendor="美团",
        source_id="meituan_ai_hub",
        raw_description="queue dup",
        install_count=50,
        metadata={"githubUrl": "https://github.com/foo/bar", "catalog": "skillsmp"},
    )
    out = dedupe_skillsmp_records([a, b])
    assert len(out) == 1
    assert out[0].external_id == "skillsmp:b"
