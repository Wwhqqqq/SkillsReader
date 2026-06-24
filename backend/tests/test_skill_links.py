"""Skill 详情链接解析单元测试。"""

from app.models import Skill
from app.services.skill_links import (
    clawhub_skills_url,
    is_aggregate_mirror_url,
    is_broken_clawhub_ai_url,
    normalize_clawhub_detail_url,
    resolve_skill_detail_url,
)


def test_aggregate_mirror_detected():
    url = "https://gitcode.csdn.net/69b97a480a2f6a37c5982b84.html"
    assert is_aggregate_mirror_url(url) is True


def test_resolve_redskill_slug_to_clawhub_page():
    skill = Skill(
        id=1,
        fingerprint="fp-1",
        vendor="小红书",
        source_id="xiaohongshu_red_skill",
        external_id="redskill:xiaohongshu-mcp",
        name="Xiaohongshu Mcp",
        detail_url="https://gitcode.csdn.net/69b97a480a2f6a37c5982b84.html",
        metadata_json={
            "slug": "xiaohongshu-mcp",
            "redskill_catalog": True,
            "catalog": "clawhub",
        },
    )
    assert resolve_skill_detail_url(skill) == clawhub_skills_url("xiaohongshu-mcp")


def test_resolve_keeps_valid_url():
    skill = Skill(
        id=2,
        fingerprint="fp-2",
        vendor="滴滴",
        source_id="didi_skills",
        external_id="clawhub:didi-ride",
        name="Didi Ride",
        detail_url="https://clawhub.ai/didi/didi-ride-skill-official",
        metadata_json={"slug": "didi-ride"},
    )
    assert resolve_skill_detail_url(skill) == "https://clawhub.ai/didi/didi-ride-skill-official"


def test_broken_clawhub_ai_single_slug():
    url = "https://clawhub.ai/xhs-cn"
    assert is_broken_clawhub_ai_url(url) is True
    assert normalize_clawhub_detail_url(url) == clawhub_skills_url("xhs-cn")


def test_resolve_fixes_broken_clawhub_ai():
    skill = Skill(
        id=3,
        fingerprint="fp-3",
        vendor="小红书",
        source_id="xiaohongshu_red_skill",
        external_id="clawhub:xhs-cn",
        name="小红书",
        detail_url="https://clawhub.ai/xhs-cn",
        metadata_json={"slug": "xhs-cn", "catalog": "clawhub"},
    )
    assert resolve_skill_detail_url(skill) == clawhub_skills_url("xhs-cn")
