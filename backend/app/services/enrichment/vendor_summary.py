"""
厂商覆盖摘要 —— 为如流机器人回复生成各平台 Skill 数量统计。

被 ruliu_commands / ruliu_callback 调用。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill
from app.services.push.ruliu_notifier import (
    PRODUCT_NAME,
    PUSH_FOOTER,
    VENDOR_TABLE_HEADER,
    VENDOR_TABLE_SEP,
)

DOMESTIC_VENDORS = ("美团", "阿里", "字节", "知乎", "小红书", "哔哩哔哩", "快手", "滴滴", "拼多多", "携程", "得物", "腾讯")
SUPPLEMENTAL_VENDORS = ("海外社区", "GitHub")


def _category_label(skill: Skill) -> str:
    meta = skill.metadata_json or {}
    if isinstance(meta, dict):
        if meta.get("categoryName"):
            return str(meta["categoryName"])
        if meta.get("category"):
            return str(meta["category"])
    tags = skill.tags or []
    skip = {
        "美团", "阿里", "腾讯", "字节", "知乎", "小红书", "哔哩哔哩", "快手", "滴滴", "拼多多", "携程", "得物", "github", "skills.sh",
        "云资源", "生活服务", "海外社区",
    }
    for t in tags:
        if t not in skip:
            return str(t)
    return "未分类"


async def collect_vendor_stats(session: AsyncSession) -> dict[str, dict]:
    skills = list(
        (await session.scalars(select(Skill).where(Skill.status == "active"))).all()
    )
    stats: dict[str, dict] = {}
    for s in skills:
        v = s.vendor
        if v not in stats:
            stats[v] = {"total": 0, "categories": {}}
        stats[v]["total"] += 1
        cat = _category_label(s)
        stats[v]["categories"][cat] = stats[v]["categories"].get(cat, 0) + 1
    return stats


def _top_categories(categories: dict[str, int], limit: int = 3) -> str:
    if not categories:
        return "-"
    ordered = sorted(categories.items(), key=lambda x: -x[1])
    return "、".join(name for name, _ in ordered[:limit])


def format_vendor_coverage_md(stats: dict[str, dict]) -> str:
    """生成「收录了哪些公司 Skill」的群聊回复 Markdown。"""
    lines = [
        f"##### {PRODUCT_NAME} · 已收录 Skill 公司",
        "",
        "目前持续扫描并收录以下公司 Skill：",
        "",
        VENDOR_TABLE_HEADER,
        VENDOR_TABLE_SEP,
    ]

    domestic_total = 0
    for vendor in DOMESTIC_VENDORS:
        info = stats.get(vendor)
        if not info or info["total"] <= 0:
            continue
        domestic_total += info["total"]
        cats = _top_categories(info["categories"])
        lines.append(f"| {vendor} | {info['total']} | {cats} |")

    if domestic_total == 0:
        lines.append("| （暂无国内公司数据） | 0 | - |")
    else:
        lines.append("")
        lines.append(f"**国内合计：{domestic_total} 条 Skill**")

    supplemental = []
    for vendor in SUPPLEMENTAL_VENDORS:
        info = stats.get(vendor)
        if info and info["total"] > 0:
            supplemental.append(f"{vendor} {info['total']} 条")

    if supplemental:
        lines.append("")
        lines.append(f"*补充源：{' · '.join(supplemental)}*")

    lines.append("")
    lines.append(f"*{PUSH_FOOTER}*")
    return "\n".join(lines)
