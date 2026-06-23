"""厂商定向审核（启发式 + LLM）单元测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.base import RawSkillRecord
from app.services.enrichment import vendor_relevance as vr


def _rec(name: str, desc: str, **meta) -> RawSkillRecord:
    return RawSkillRecord(
        external_id=meta.pop("external_id", "skillsmp:test-1"),
        name=name,
        vendor="美团",
        source_id="meituan_ai_hub",
        raw_description=desc,
        metadata={"catalog": "skillsmp", **meta},
    )


def test_rejects_multi_platform_clipboard_skill():
    rec = _rec(
        "clipboard-deeplink",
        "将剪切板中的 App 跳转链接制作成一个可复用的快捷指令 Skill。"
        "支持淘宝、拼多多、抖音、快手、知乎、小红书、美团、哔哩哔哩、高德、QQ音乐、支付宝、百度等主流 App 的分享链接。",
    )
    bad, reason = vr.is_heuristically_irrelevant("美团", rec)
    assert bad
    assert "多平台" in reason


def test_rejects_founder_quotes_skill():
    rec = _rec(
        "wang-xing-quotes",
        "王兴（互联网创业）认知与表达框架（压缩蒸馏）：极简刻薄金句、无限游戏叙事。"
        "触发：美团、饭否语录 等。非荐股；非内幕",
    )
    bad, _ = vr.is_heuristically_irrelevant("美团", rec)
    assert bad


def test_rejects_meituan_eleme_cross_platform():
    rec = _rec(
        "sync-dashboard",
        "针对美团和饿了么的Excel数据同步到dashboard，核心功能围绕双平台。",
    )
    bad, reason = vr.is_heuristically_irrelevant("美团", rec)
    assert bad
    assert "竞品" in reason or "饿了么" in reason or "跨平台" in reason


def test_is_official_record_skips_review():
    rec = _rec("official-skill", "官方 API", catalog="official_api", official=True)
    assert vr.is_official_record(rec)


def test_accepts_dedicated_meituan_repo():
    rec = _rec(
        "meituan-passport-user-auth",
        "美团 Passport 用户授权登录 Skill，用于生成授权链接并轮询获取用户态登录 Token。",
        repo="jinguyuan/jinguyuan-dumpling-skill",
        external_id="skillsmp:passport",
    )
    assert not vr.is_heuristically_irrelevant("美团", rec)[0]


@pytest.mark.asyncio
async def test_filter_uses_llm_batch(monkeypatch):
    monkeypatch.setattr(vr, "_memory_cache", {})
    monkeypatch.setattr(vr, "CACHE_FILE", vr.CACHE_DIR / "test_vendor_relevance_cache.json")

    good = _rec(
        "meituan-queue",
        "美团排队取号 API 封装，供商家场景调用。",
        external_id="skillsmp:queue",
    )
    bad = _rec(
        "multi-app",
        "支持淘宝、拼多多、抖音、快手、知乎、小红书、美团、哔哩哔哩的剪贴板链接跳转。",
        external_id="skillsmp:multi",
    )

    mock_classify = AsyncMock(
        return_value={
            "skillsmp:queue": {
                "relevant": True,
                "reason": "美团 API 专用",
                "confidence": 0.95,
                "source": "llm",
                "prompt_version": vr.PROMPT_VERSION,
            },
            "skillsmp:multi": {
                "relevant": False,
                "reason": "多平台工具",
                "confidence": 0.9,
                "source": "llm",
                "prompt_version": vr.PROMPT_VERSION,
            },
        }
    )

    with patch.object(vr, "_classify_batch_llm", mock_classify):
        with patch("app.services.enrichment.vendor_relevance.get_settings") as gs:
            gs.return_value.deepseek_api_key = "test-key"
            gs.return_value.deepseek_base_url = "https://api.deepseek.com/v1"
            gs.return_value.deepseek_model = "deepseek-chat"
            out = await vr.filter_records_by_vendor_relevance("美团", [good, bad])

    assert len(out) == 1
    assert out[0].external_id == "skillsmp:queue"
    assert out[0].metadata["vendorRelevance"]["relevant"] is True
