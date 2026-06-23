"""Tests for Ruliu push formatting."""

from types import SimpleNamespace

from app.services.push.ruliu_notifier import (
    TABLE_HEADER,
    TABLE_SEP,
    _split_row_cells_by_desc,
    _skill_row_cells,
    format_push_content,
    format_skill_table_row,
    split_md_messages,
)


def _skill(name: str, desc: str, vendor: str = "美团") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        vendor=vendor,
        llm_summary=desc,
        raw_description=desc,
        detail_url="https://example.com/s",
        tags=[vendor],
        metadata_json={"categoryName": "测试"},
    )


def test_push_uses_markdown_table():
    content = format_push_content(
        [(_skill("测试Skill", "描述内容"), 90.0)],
        [],
        mode="today",
    )
    assert TABLE_HEADER in content
    assert TABLE_SEP in content
    assert "| 1 |" in content
    assert "测试Skill" in content


def test_push_table_full_description_no_ellipsis():
    desc = "这是一段超过二十个字的完整 Skill 描述，用于验证推送表格中描述列不会被截断成省略号。"
    content = format_push_content(
        [(_skill("测试Skill", desc), 90.0)],
        [],
        mode="today",
    )
    assert TABLE_HEADER in content
    assert "…" not in content
    assert desc in content


def test_push_table_includes_description():
    desc = "这是一段 Skill 描述，用于验证表格单元格内展示。"
    content = format_push_content(
        [(_skill("测试Skill", desc), 90.0)],
        [],
        mode="today",
    )
    assert "测试Skill" in content
    assert desc in content


def test_split_long_table_row_keeps_full_description():
    desc = "完整描述" * 120
    skill = _skill("长描述Skill", desc)
    row = format_skill_table_row(1, skill, is_new=True)
    assert "…" not in row
    assert desc in row

    parts = _split_row_cells_by_desc(_skill_row_cells(1, skill, is_new=True), 500)
    assert len(parts) > 1
    joined_desc = "".join(
        p.strip().removeprefix("|").removesuffix("|").split("|")[6].strip() for p in parts
    )
    assert joined_desc == desc
    assert "…" not in "".join(parts)
    text = "hello\n\n*（如有新skill发布将第一时间推送）*"
    parts = split_md_messages(text)
    assert len(parts) == 1


def test_split_md_messages_table_multiple_parts():
    rows = []
    for i in range(1, 25):
        rows.append(
            f"| {i} | [Skill-{i}](https://example.com/{i}) | 美团 | 官方发布 | SkillsMP | 分类 | "
            f"{'长描述内容' * 8} | [查看](https://example.com/{i}) |"
        )
    body = "\n".join(
        [
            "##### SkillGetter 测试",
            "",
            TABLE_HEADER,
            TABLE_SEP,
            *rows,
        ]
    )
    parts = split_md_messages(body + "\n\n*（如有新skill发布将第一时间推送）*")
    assert len(parts) >= 2
    assert all(len(p) <= 2048 for p in parts)
    assert TABLE_HEADER in parts[1]
