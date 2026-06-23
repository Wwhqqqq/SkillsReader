"""将 `DigestResult` 格式化为人类可读的 Markdown 文本。"""

from __future__ import annotations

from typing import Any

from app.services.digest.types import DigestResult
from app.services.push.ruliu_notifier import TABLE_HEADER, TABLE_SEP


def _escape_table_cell(text: str, max_len: int | None = None) -> str:
    cell = text.replace("|", "/").replace("\n", " ").strip()
    if max_len is not None and len(cell) > max_len:
        cell = cell[: max_len - 1] + "…"
    return cell or "-"


def _escape_md(text: str) -> str:
    return text.replace("\n", " ").replace("[", "(").replace("]", ")").strip()


def _skill_link(skill) -> str:
    from app.services.skill_links import resolve_skill_detail_url

    return resolve_skill_detail_url(
        skill,
        default="https://developer.meituan.com/ai-hub/skill-list",
    )


def _skill_description(skill, push_desc: str | None = None) -> str:
    if push_desc:
        return _escape_table_cell(push_desc)
    desc = (skill.llm_summary or skill.raw_description or "-").strip()
    return _escape_table_cell(_escape_md(desc))


def _skill_category(skill) -> str:
    tags = skill.tags or []
    meta = skill.metadata_json or {}
    if isinstance(meta, dict):
        if meta.get("categoryName"):
            return str(meta["categoryName"])
        if meta.get("category"):
            return str(meta["category"])
    skip = {
        "美团", "阿里", "腾讯", "字节", "知乎", "小红书", "哔哩哔哩", "快手",
        "滴滴", "拼多多", "携程", "得物", "github", "skills.sh", "云资源", "生活服务", "海外社区",
    }
    for t in tags:
        if t not in skip:
            return str(t)
    return tags[0] if tags else "-"


def _format_table_row(item, *, include_reason: bool, push_desc: str | None = None) -> str:
    from app.services.enrichment.skill_classification import data_source_for, publisher_type_for

    skill = item.skill
    link = _skill_link(skill)
    marker = " 🆕" if item.is_new else ""
    desc = _skill_description(skill, push_desc=push_desc)
    if include_reason and item.recommend_reason:
        desc = f"{desc} · {_escape_table_cell(item.recommend_reason)}"

    cells = (
        str(item.rank),
        f"[{_escape_table_cell(skill.name)}]({link}){marker}",
        _escape_table_cell(skill.vendor),
        _escape_table_cell(publisher_type_for(skill)),
        _escape_table_cell(data_source_for(skill)),
        _escape_table_cell(_skill_category(skill)),
        desc,
        f"[查看]({link})",
    )
    return "| " + " | ".join(cells) + " |"


def _format_table_rows(result: DigestResult, cfg: dict[str, Any]) -> list[str]:
    push_cfg = cfg.get("push") or {}
    include_reason = push_cfg.get("include_recommend_reason", True)
    push_descs = (result.meta or {}).get("push_descriptions") or {}

    lines = [TABLE_HEADER, TABLE_SEP]
    for item in result.items:
        lines.append(
            _format_table_row(
                item,
                include_reason=include_reason,
                push_desc=push_descs.get(item.skill.id),
            )
        )
    return lines


def format_digest_markdown(result: DigestResult, cfg: dict[str, Any] | None = None) -> str:
    """如流推送默认仅输出表格；`push.table_only: false` 时输出完整分段文案。"""
    cfg = cfg or {}
    push_cfg = dict(cfg.get("push") or {})
    channel = (result.meta or {}).get("channel") or "digest"
    if channel == "official_new":
        push_cfg = {**push_cfg, **(push_cfg.get("official_new") or {})}
    if push_cfg.get("table_only", True):
        rows = _format_table_rows(result, cfg)
        if push_cfg.get("include_title") and channel == "official_new" and rows:
            title_tpl = push_cfg.get("title_template") or "SkillGetter 官方发布新增日报 · {date}"
            title = title_tpl.format(top_n=result.top_n, date=result.digest_date.isoformat())
            return f"##### {title}\n\n" + "\n".join(rows)
        return "\n".join(rows)

    from app.services.enrichment.skill_classification import data_source_for, publisher_type_for

    SLOT_LABELS = {
        "official": "🏢 官方精选",
        "trend": "📈 趋势爆发",
        "discovery": "🆕 新发现",
        "fill": "⭐ 综合推荐",
    }

    def _growth_cell(growth: dict[str, Any]) -> str:
        parts = []
        for key, label in (("growth_1d_pct", "8h"), ("growth_3d_pct", "24h"), ("growth_7d_pct", "56h")):
            val = growth.get(key)
            if val is not None and float(val) > 0:
                parts.append(f"{label}+{float(val):.0f}%")
        if parts:
            return " / ".join(parts)
        metric = growth.get("metric_value")
        if metric:
            return f"指标 {metric}"
        return "-"

    title_tpl = push_cfg.get("title_template") or "SkillGetter 每日精选 Top{top_n} · {date}"
    title = title_tpl.format(top_n=result.top_n, date=result.digest_date.isoformat())
    include_reason = push_cfg.get("include_recommend_reason", True)
    include_breakdown = push_cfg.get("include_score_breakdown", True)

    lines = [f"## {title}", ""]
    current_slot = None
    for item in result.items:
        if item.slot != current_slot:
            current_slot = item.slot
            lines.append(f"### {SLOT_LABELS.get(item.slot, item.slot)}")
            lines.append("")

        skill = item.skill
        link = _skill_link(skill)
        marker = " 🆕" if item.is_new else ""
        official_tag = " [官方]" if item.is_official else ""
        lines.append(f"**{item.rank}. [{skill.name}]({link}){official_tag}{marker}**")
        lines.append(
            f"- 公司：{skill.vendor} | 发布：{publisher_type_for(skill)} | "
            f"来源：{data_source_for(skill)} | 分类：{_skill_category(skill)}"
        )
        lines.append(f"- 描述：{_skill_description(skill, push_desc=(result.meta or {}).get('push_descriptions', {}).get(skill.id))}")
        if include_reason and item.recommend_reason:
            lines.append(f"- 推荐理由：{_escape_md(item.recommend_reason)}")
        lines.append(f"- 增长：{_growth_cell(item.growth)}")
        if include_breakdown:
            bd = item.score_breakdown
            lines.append(
                f"- 评分：{item.score:.1f} "
                f"(趋势 {bd.get('trend', 0):.0f} / 官方 {bd.get('official', 0):.0f} / "
                f"质量 {bd.get('quality', 0):.0f} / 多样性 {bd.get('diversity', 0):.0f})"
            )
        lines.append(f"- 链接：[查看]({link})")
        lines.append("")

    lines.extend(["", *_format_table_rows(result, cfg)])
    meta = result.meta or {}
    lines.append("")
    lines.append(
        f"_候选 {meta.get('candidate_count', 0)} 条 · 精选 {len(result.items)} 条 · "
        f"配置 v{result.config_version}_"
    )
    return "\n".join(lines)
