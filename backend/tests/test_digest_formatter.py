"""Digest push markdown formatter tests."""

from datetime import date
from types import SimpleNamespace

from app.services.digest.formatter import format_digest_markdown
from app.services.digest.types import DigestPickItem, DigestResult
from app.services.push.ruliu_notifier import TABLE_HEADER, split_md_messages


def _skill(name: str, desc: str, url: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        vendor="腾讯",
        tags=["腾讯"],
        llm_summary=desc,
        raw_description=desc,
        detail_url=url,
        metadata_json={"publisherType": "官方发布", "official": True, "catalog": "official"},
        source_id="wechat_skillhub",
    )


def test_table_includes_full_description_and_link():
    url = "https://github.com/TencentCloudBase/mp-skills/tree/main/skills/wxa-ai-mode-dev"
    desc = "微信小程序 AI 开发模式官方 Skill，用于 agent 接入与调试。"
    item = DigestPickItem(
        rank=1,
        slot="official_new",
        pool="official",
        skill=_skill("wxa-ai-mode-dev", desc, url),
        score=60.0,
        score_breakdown={},
        growth={},
        recommend_reason="腾讯官方发布",
        is_official=True,
        is_new=True,
    )
    result = DigestResult(digest_date=date(2026, 6, 23), top_n=1, items=[item], meta={"channel": "digest"})
    md = format_digest_markdown(result, {"push": {"table_only": True, "include_recommend_reason": True}})

    assert TABLE_HEADER in md
    assert desc in md
    assert "…" not in md
    assert f"[查看]({url})" in md
    assert f"]({url})" in md


def test_long_description_splits_without_ellipsis():
    url = "https://github.com/example/repo/tree/main/skills/demo-skill"
    desc = "完整描述" * 80
    item = DigestPickItem(
        rank=1,
        slot="official",
        pool="official",
        skill=_skill("demo-skill", desc, url),
        score=50.0,
        score_breakdown={},
        growth={},
        recommend_reason="",
        is_official=True,
        is_new=False,
    )
    result = DigestResult(digest_date=date(2026, 6, 23), top_n=1, items=[item])
    md = format_digest_markdown(result, {"push": {"table_only": True}})
    parts = split_md_messages(md)
    joined = "".join(parts)
    assert desc in joined
    assert "…" not in joined
