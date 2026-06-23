"""Parse @机器人 messages and map to SkillGetter commands."""

from __future__ import annotations

import re

VENDOR_QUERY_PATTERNS = (
    re.compile(r"收录了哪些.*?(公司|厂商|平台).*?skill", re.I),
    re.compile(r"哪些.*?(公司|厂商|平台).*?skill", re.I),
    re.compile(r"都有什么.*?skill", re.I),
    re.compile(r"skill.*?有哪些", re.I),
    re.compile(r"厂商.*?统计", re.I),
    re.compile(r"覆盖.*?哪些", re.I),
)


def normalize_message_text(text: str) -> str:
    cleaned = re.sub(r"@[^\s@]+", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_vendor_coverage_query(text: str) -> bool:
    normalized = normalize_message_text(text).lower()
    if not normalized:
        return False
    for pattern in VENDOR_QUERY_PATTERNS:
        if pattern.search(normalized):
            return True
    keywords = ("收录", "哪些", "厂商", "公司", "平台", "skill")
    hits = sum(1 for k in keywords if k in normalized)
    return hits >= 3 and "skill" in normalized


def should_reply_to_group_message(
    *,
    content: str,
    chat_type: str | None = None,
    is_at_robot: bool = False,
) -> bool:
    if chat_type and chat_type.lower() not in ("group", "GROUP", "群", "群聊"):
        if not is_at_robot:
            return False
    if not is_at_robot and chat_type and chat_type.lower() in ("group", "GROUP"):
        return False
    return is_vendor_coverage_query(content)
