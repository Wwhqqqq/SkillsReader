"""滴滴平台过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_didi_relevant


def test_didi_accepts_official_repo():
    rec = RawSkillRecord(
        external_id="didi/didi-ride-skill:",
        name="didi-ride-skill",
        vendor="滴滴",
        source_id="didi_skills",
        raw_description="滴滴出行打车 Skill",
        metadata={"repo": "didi/didi-ride-skill", "path": "", "official": True},
    )
    assert is_didi_relevant(rec)


def test_didi_rejects_unrelated():
    rec = RawSkillRecord(
        external_id="foo/bar:skills/generic-tool",
        name="generic-tool",
        vendor="滴滴",
        source_id="didi_skills",
        raw_description="A generic devops helper",
        metadata={"repo": "foo/bar", "path": "skills/generic-tool"},
    )
    assert not is_didi_relevant(rec)


def test_didi_accepts_official_anchor():
    rec = RawSkillRecord(
        external_id="didi-mcp-platform",
        name="滴滴 MCP 服务",
        vendor="滴滴",
        source_id="didi_skills",
        raw_description="官方 MCP",
        metadata={"official": True},
    )
    assert is_didi_relevant(rec)
