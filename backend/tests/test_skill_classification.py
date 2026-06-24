"""Tests for skill publisher / data source classification."""

from types import SimpleNamespace

from app.services.enrichment.skill_classification import (
    PUBLISHER_CREATOR,
    PUBLISHER_OFFICIAL,
    data_source_for,
    enrich_metadata,
    publisher_type_for,
)


def _skill(**kwargs):
    defaults = {
        "source_id": "meituan_ai_hub",
        "external_id": "mt:1",
        "metadata_json": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_official_api_is_official_publisher():
    skill = _skill(metadata_json={"catalog": "official_api"})
    assert publisher_type_for(skill) == PUBLISHER_OFFICIAL
    assert data_source_for(skill) == "美团AI Hub API"


def test_skillsmp_official_repo_mirror_is_official():
    skill = _skill(
        source_id="wechat_skillhub",
        external_id="skillsmp:tencentcloudbase-cloudbase-mcp-config-claude-skills-ai-model-wechat-skill-md",
        metadata_json={"catalog": "skillsmp", "repo": "TencentCloudBase/CloudBase-MCP"},
    )
    assert publisher_type_for(skill) == PUBLISHER_OFFICIAL


def test_skillsmp_is_creator():
    skill = _skill(
        source_id="meituan_ai_hub",
        external_id="skillsmp:abc",
        metadata_json={"catalog": "skillsmp"},
    )
    assert publisher_type_for(skill) == PUBLISHER_CREATOR
    assert data_source_for(skill) == "SkillsMP"


def test_redskill_catalog_is_creator_not_official():
    skill = _skill(
        source_id="xiaohongshu_red_skill",
        external_id="redskill:xiaohongshu-mcp",
        metadata_json={"catalog": "clawhub", "redskill_catalog": True},
    )
    assert publisher_type_for(skill) == PUBLISHER_CREATOR
    assert data_source_for(skill) == "ClawHub"


def test_redskill_legacy_flag_is_creator():
    skill = _skill(
        source_id="xiaohongshu_red_skill",
        external_id="redskill:xiaohongshu-mcp",
        metadata_json={"catalog": "clawhub", "redskill": True},
    )
    assert publisher_type_for(skill) == PUBLISHER_CREATOR


def test_xhs_official_entry_is_official():
    skill = _skill(
        source_id="xiaohongshu_red_skill",
        external_id="xhs-red-skill-platform",
        metadata_json={"catalog": "official", "official": True},
    )
    assert publisher_type_for(skill) == PUBLISHER_OFFICIAL


def test_enrich_metadata_sets_labels():
    meta = enrich_metadata(
        {"catalog": "clawhub"},
        vendor="知乎",
        source_id="zhihu_skills",
        external_id="clawhub:x",
    )
    assert meta["publisherType"] == PUBLISHER_CREATOR
    assert meta["dataSource"] == "ClawHub"
