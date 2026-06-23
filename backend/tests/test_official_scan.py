"""Tests for official portal batch scan."""

from types import SimpleNamespace

from app.services.enrichment.skill_classification import publisher_type_for
from app.services.scan.official_portals import load_official_portals_config, official_portal_source_ids


def test_official_portal_source_ids():
    ids = official_portal_source_ids()
    assert "meituan_ai_hub" in ids
    assert "github_watch" not in ids
    assert "skills_sh" not in ids
    assert len(ids) == 12


def test_official_portals_config_has_urls():
    portals = load_official_portals_config()
    assert len(portals) == 12
    for p in portals:
        assert p.get("url", "").startswith("http")
        assert p.get("vendor")
        assert p.get("source_id")


def test_official_repo_mirror_classification():
    skill = SimpleNamespace(
        source_id="wechat_skillhub",
        external_id="skillsmp:tencentcloudbase-cloudbase-mcp-config-claude-skills-ai-model-wechat-skill-md",
        metadata_json={"catalog": "skillsmp", "repo": "TencentCloudBase/CloudBase-MCP"},
    )
    assert publisher_type_for(skill) == "官方发布"
