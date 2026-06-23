"""腾讯平台过滤单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.platform_filters import is_tencent_relevant


def test_tencent_accepts_official_github_repo():
    rec = RawSkillRecord(
        external_id="TencentCloudBase/skills:miniprogram-development",
        name="miniprogram-development",
        vendor="腾讯",
        source_id="wechat_skillhub",
        raw_description="CloudBase 小程序开发 Skill",
        metadata={"repo": "TencentCloudBase/skills", "path": "miniprogram-development"},
    )
    assert is_tencent_relevant(rec)


def test_tencent_rejects_qq_username_noise():
    rec = RawSkillRecord(
        external_id="qq5855144/foo:skills/generic",
        name="generic-tool",
        vendor="腾讯",
        source_id="wechat_skillhub",
        raw_description="A generic helper",
        metadata={"repo": "qq5855144/foo", "path": "skills/generic"},
    )
    assert not is_tencent_relevant(rec)


def test_tencent_accepts_clawhub_slug():
    rec = RawSkillRecord(
        external_id="clawhub:tencent-docs",
        name="tencent-docs",
        vendor="腾讯",
        source_id="wechat_skillhub",
        raw_description="腾讯文档 skill",
        metadata={"catalog": "clawhub", "slug": "tencent-docs"},
    )
    assert is_tencent_relevant(rec)


def test_tencent_rejects_wechat_publisher():
    rec = RawSkillRecord(
        external_id="foo/bar:skills/wechat-publisher",
        name="wechat-publisher",
        vendor="腾讯",
        source_id="wechat_skillhub",
        raw_description="Publish to wechat and other platforms",
        metadata={"repo": "foo/bar", "path": "skills/wechat-publisher"},
    )
    assert not is_tencent_relevant(rec)
