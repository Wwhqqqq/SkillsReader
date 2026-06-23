"""Tests for skill gate (portal anchor filtering)."""

from types import SimpleNamespace

from app.services.scan.skill_gate import is_bilibili_portal_anchor, is_real_skill


def test_bilibili_portal_anchor_detected():
    skill = SimpleNamespace(
        external_id="bilibili-open-platform",
        detail_url="https://open.bilibili.com/",
        metadata_json={"official": True, "catalog": "official"},
    )
    assert is_bilibili_portal_anchor(skill)
    assert not is_real_skill(skill)


def test_bilibili_github_skill_is_real():
    skill = SimpleNamespace(
        external_id="dreammis/social-auto-upload:skills/bilibili-upload",
        detail_url="https://github.com/dreammis/social-auto-upload/tree/main/skills/bilibili-upload",
        metadata_json={"catalog": "github"},
    )
    assert not is_bilibili_portal_anchor(skill)
    assert is_real_skill(skill)
