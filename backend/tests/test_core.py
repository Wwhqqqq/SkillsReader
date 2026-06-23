"""Unit tests."""

import pytest

from app.adapters.base import RawSkillRecord
from app.services.scan.normalizer import compute_fingerprint, compute_quality_score, normalize_name


def test_normalize_name():
    assert normalize_name("  Hello  World  ") == "hello world"


def test_fingerprint_stable():
    fp1 = compute_fingerprint("美团", "meituan_ai_hub", "skill-1", "外卖助手")
    fp2 = compute_fingerprint("美团", "meituan_ai_hub", "skill-1", "外卖助手")
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_differs_by_name():
    fp1 = compute_fingerprint("美团", "meituan_ai_hub", "1", "A")
    fp2 = compute_fingerprint("美团", "meituan_ai_hub", "1", "B")
    assert fp1 != fp2


def test_quality_score_domestic():
    rec = RawSkillRecord(
        external_id="1",
        name="Test",
        vendor="美团",
        source_id="meituan_ai_hub",
        raw_description="这是一个足够长的描述用于测试质量打分逻辑",
        detail_url="https://example.com",
        tags=["test"],
        install_count=100,
    )
    score = compute_quality_score(rec)
    assert score >= 40


def test_quality_score_low():
    rec = RawSkillRecord(
        external_id="1",
        name="X",
        vendor="海外社区",
        source_id="skills_sh",
    )
    assert compute_quality_score(rec) < 40


@pytest.mark.asyncio
async def test_meituan_adapter_fetch():
    from app.adapters.meituan import MeituanAdapter

    adapter = MeituanAdapter()
    records = await adapter.fetch()
    assert isinstance(records, list)
    assert len(records) >= 40


@pytest.mark.asyncio
async def test_aliyun_adapter_fetch():
    from app.adapters.aliyun.adapter import AliyunSkillsAdapter

    adapter = AliyunSkillsAdapter()
    records = await adapter.fetch()
    assert len(records) >= 40
    assert all("skills.aliyun.com/skills/" in r.detail_url for r in records[:3])


def test_format_push_content():
    from datetime import datetime

    from app.models import Skill
    from app.services.push.ruliu_notifier import PUSH_FOOTER, format_push_content

    skill = Skill(
        id=1,
        fingerprint="abc",
        vendor="美团",
        source_id="meituan",
        external_id="1",
        name="团购核销查询",
        llm_summary="支持团购券码校验与核销查询",
        detail_url="https://developer.meituan.com/ai-hub/skill-list?skill=tuangou-receipt-query",
        tags=["服务零售", "美团"],
        metadata_json={"categoryName": "服务零售"},
        first_seen_at=datetime.now(),
        last_seen_at=datetime.now(),
    )

    today_md = format_push_content(
        [(skill, 90.0)], [], mode="today", title_date="2026-06-17", vendors=["美团"]
    )
    assert "今日新增 Skill" in today_md
    assert "[团购核销查询]" in today_md
    assert "developer.meituan.com" in today_md
    assert "双榜日报" not in today_md
    assert "| # | Skill |" in today_md
    assert "| 1 |" in today_md

    lb_md = format_push_content(
        [], [(skill, 90.0)], mode="leaderboard", title_date="2026-06-17"
    )
    assert "Skill 总榜" in lb_md
    assert "今日新增" not in lb_md

    # 旧双榜已移除；format_push_content 仍用于 scan 自动推送（today 模式）


def test_ruliu_dm_payload_uses_md_msgtype():
    from app.services.push.ruliu_notifier import _plain_text_fallback

    plain = _plain_text_fallback("**1. [测试](https://example.com)**\n>描述：hello")
    assert "测试" in plain
    assert "https://example.com" in plain
    assert "**" not in plain
