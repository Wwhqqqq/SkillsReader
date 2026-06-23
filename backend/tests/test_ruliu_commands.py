"""Ruliu @机器人 command tests."""

import pytest

from app.services.push.ruliu_commands import is_vendor_coverage_query, normalize_message_text


@pytest.mark.parametrize(
    "text,expected",
    [
        ("@SkillGetter 你都收录了哪些公司的skill", True),
        ("你都收录了哪些公司的skill", True),
        ("有哪些厂商 skill", True),
        ("今天天气怎么样", False),
        ("hello", False),
    ],
)
def test_vendor_coverage_query(text: str, expected: bool):
    assert is_vendor_coverage_query(text) is expected


def test_normalize_strips_at_mention():
    assert normalize_message_text("@SkillGetter 你都收录了哪些公司的skill") == "你都收录了哪些公司的skill"
