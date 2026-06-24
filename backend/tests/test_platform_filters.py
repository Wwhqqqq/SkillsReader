"""平台相关性过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_xhs_relevant, is_zhihu_relevant


def test_zhihu_rejects_unrelated_html_templates():
    rec = RawSkillRecord(
        external_id="nexu-io/html-anything:next/src/lib/templates/skill",
        name="wireframe-sketch",
        vendor="知乎",
        source_id="zhihu_skills",
        raw_description="网格背景 + marker 笔触",
        metadata={"repo": "nexu-io/html-anything", "path": "next/src/lib/templates/skill"},
    )
    assert not is_zhihu_relevant(rec)


def test_zhihu_accepts_path_with_keyword():
    rec = RawSkillRecord(
        external_id="yezhengmao1/navi:.claude/skills/zhihu",
        name="zhihu",
        vendor="知乎",
        source_id="zhihu_skills",
        raw_description="获取知乎当前热榜话题",
        metadata={"repo": "yezhengmao1/navi", "path": ".claude/skills/zhihu"},
    )
    assert is_zhihu_relevant(rec)


def test_zhihu_accepts_dedicated_repo():
    rec = RawSkillRecord(
        external_id="liyxianren/zhihu:skills/zhihu-auto-publisher",
        name="Zhihu Auto Publisher",
        vendor="知乎",
        source_id="zhihu_skills",
        raw_description="Publish to Zhihu",
        metadata={"repo": "liyxianren/zhihu", "path": "skills/zhihu-auto-publisher"},
    )
    assert is_zhihu_relevant(rec)


def test_xhs_accepts_redskill_catalog_entry():
    rec = RawSkillRecord(
        external_id="redskill:xiaohongshu-mcp",
        name="Xiaohongshu Mcp",
        vendor="小红书",
        source_id="xiaohongshu_red_skill",
        raw_description="Python MCP client for full Xiaohongshu automation.",
        metadata={"redskill_catalog": True},
    )
    assert is_xhs_relevant(rec)


def test_xhs_rejects_unrelated_opencli():
    rec = RawSkillRecord(
        external_id="Baileybasic68/opencli-skill:opencli-skill",
        name="opencli",
        vendor="小红书",
        source_id="xiaohongshu_red_skill",
        raw_description="Generic opencli helper",
        metadata={"repo": "Baileybasic68/opencli-skill", "path": "opencli-skill"},
    )
    assert not is_xhs_relevant(rec)


def test_xhs_accepts_dedicated_repo():
    rec = RawSkillRecord(
        external_id="autoclaw-cc/xiaohongshu-skills:skills/xhs-publish",
        name="Xhs Publish",
        vendor="小红书",
        source_id="xiaohongshu_red_skill",
        raw_description="Publish notes",
        metadata={"repo": "autoclaw-cc/xiaohongshu-skills", "path": "skills/xhs-publish"},
    )
    assert is_xhs_relevant(rec)
