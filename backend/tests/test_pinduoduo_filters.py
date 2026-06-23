"""拼多多平台过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_pinduoduo_relevant


def test_pinduoduo_accepts_dedicated_path():
    rec = RawSkillRecord(
        external_id="TonyWang-hub/mcp-cn-commerce:packages/mcp-cn-pinduoduo",
        name="mcp-cn-pinduoduo",
        vendor="拼多多",
        source_id="pinduoduo_skills",
        raw_description="拼多多 MCP Server",
        metadata={
            "repo": "TonyWang-hub/mcp-cn-commerce",
            "path": "packages/mcp-cn-pinduoduo",
        },
    )
    assert is_pinduoduo_relevant(rec)


def test_pinduoduo_rejects_unrelated():
    rec = RawSkillRecord(
        external_id="foo/bar:skills/generic-tool",
        name="generic-tool",
        vendor="拼多多",
        source_id="pinduoduo_skills",
        raw_description="A generic devops helper",
        metadata={"repo": "foo/bar", "path": "skills/generic-tool"},
    )
    assert not is_pinduoduo_relevant(rec)


def test_pinduoduo_accepts_official():
    rec = RawSkillRecord(
        external_id="pdd-open-platform",
        name="拼多多开放平台",
        vendor="拼多多",
        source_id="pinduoduo_skills",
        raw_description="官方开放平台",
        metadata={"official": True},
    )
    assert is_pinduoduo_relevant(rec)
