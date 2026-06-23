"""Tests for push description polishing."""

from types import SimpleNamespace

from app.services.digest.push_desc import fallback_push_descriptions, truncate_description
from app.services.digest.types import DigestPickItem


def _item(skill_id: int, name: str, desc: str) -> DigestPickItem:
    skill = SimpleNamespace(
        id=skill_id,
        name=name,
        vendor="腾讯",
        llm_summary=desc,
        raw_description=desc,
    )
    return DigestPickItem(
        rank=1,
        slot="official",
        pool="official",
        skill=skill,
        score=1.0,
        score_breakdown={},
        growth={},
        recommend_reason="",
        is_official=True,
        is_new=False,
    )


def test_truncate_description_max_25():
    text = "这是一段超过二十五个字的 Skill 描述，用于验证截断逻辑是否按字数限制生效。"
    out = truncate_description(text, 25)
    assert len(out) <= 25
    assert out


def test_fallback_push_descriptions_respects_max_len():
    desc = "Skyline 小程序 JSON 配置规范技能，涵盖 app.json 全局配置与页面 json 配置。"
    items = [_item(1, "skyline-config", desc)]
    out = fallback_push_descriptions(items, 25)
    assert len(out[1]) <= 25
