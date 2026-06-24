"""Ruliu Open API notifier."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.models import Skill
from app.services.enrichment.skill_classification import data_source_for, publisher_type_for

logger = logging.getLogger(__name__)

PRODUCT_NAME = "SkillGetter"
PUSH_FOOTER = "（如有新skill发布将第一时间推送）"

_token_cache: dict[str, Any] = {"token": "", "expire_at": 0.0}
MD_MAX_LEN = 2048


async def _get_app_access_token() -> str:
    settings = get_settings()
    if not settings.ruliu_app_key or not settings.ruliu_app_secret:
        raise ValueError("RULIU_APP_KEY and RULIU_APP_SECRET required")

    now = time.time()
    if _token_cache["token"] and _token_cache["expire_at"] > now + 60:
        return _token_cache["token"]

    secret_md5 = hashlib.md5(settings.ruliu_app_secret.encode()).hexdigest().lower()
    url = f"{settings.ruliu_api_base.rstrip('/')}/auth/app_access_token"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            json={"app_key": settings.ruliu_app_key, "app_secret": secret_md5},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "ok":
            raise RuntimeError(f"Ruliu auth failed: {data}")
        token = data["data"]["app_access_token"]
        expire = data["data"].get("expire", 7200)
        _token_cache["token"] = token
        _token_cache["expire_at"] = now + expire
        return token


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer-{token}",
        "LOGID": str(int(time.time() * 1000)),
    }


def _escape_md(text: str) -> str:
    return text.replace("\n", " ").replace("[", "(").replace("]", ")").strip()


def _skill_link(skill: Skill) -> str:
    from app.services.skill_links import resolve_skill_detail_url

    return resolve_skill_detail_url(
        skill,
        default="https://developer.meituan.com/ai-hub/skill-list",
    )


def _skill_category(skill: Skill) -> str:
    tags = skill.tags or []
    meta = skill.metadata_json or {}
    if isinstance(meta, dict):
        if meta.get("categoryName"):
            return str(meta["categoryName"])
        if meta.get("category"):
            return str(meta["category"])
    for t in tags:
        if t not in (
            "美团", "阿里", "腾讯", "字节", "知乎", "小红书", "哔哩哔哩", "快手", "滴滴", "拼多多", "携程", "得物",
            "github", "skills.sh", "云资源", "生活服务",
        ):
            return str(t)
    return tags[0] if tags else "-"


def _skill_description(skill: Skill) -> str:
    """Full description for push — no ellipsis truncation."""
    desc = (skill.llm_summary or skill.raw_description or "-").strip()
    return _escape_md(desc) or "-"


def _escape_table_cell(text: str, max_len: int | None = None) -> str:
    cell = text.replace("|", "/").replace("\n", " ").strip()
    if max_len is not None and len(cell) > max_len:
        cell = cell[: max_len - 1] + "…"
    return cell or "-"


TABLE_HEADER = "| # | Skill | 公司 | 发布类型 | 数据来源 | 分类 | 描述 | 链接 |"
TABLE_SEP = "|---|-------|------|----------|----------|------|------|------|"
VENDOR_TABLE_HEADER = "| 公司 | 数量 | 主要分类 |"
VENDOR_TABLE_SEP = "|------|------|----------|"


def format_skill_block(rank: int, skill: Skill, *, is_new: bool = False) -> str:
    link = _skill_link(skill)
    marker = " 🆕" if is_new else ""
    return (
        f"**{rank}. [{skill.name}]({link}){marker}**\n"
        f"- 公司：{skill.vendor} | 分类：{_skill_category(skill)}\n"
        f"- 描述：{_skill_description(skill)}\n"
        f"- 链接：[查看]({link})"
    )


def format_skill_blocks(items: list[tuple[Skill, float]], *, is_new: bool = False) -> list[str]:
    if not items:
        return []
    return [format_skill_block(i, skill, is_new=is_new) for i, (skill, _) in enumerate(items, 1)]


def _skill_row_cells(rank: int, skill: Skill, *, is_new: bool = False) -> tuple[str, str, str, str, str, str, str, str]:
    link = _skill_link(skill)
    marker = " 🆕" if is_new else ""
    return (
        str(rank),
        f"[{_escape_table_cell(skill.name)}]({link}){marker}",
        skill.vendor,
        _escape_table_cell(publisher_type_for(skill)),
        _escape_table_cell(data_source_for(skill)),
        _escape_table_cell(_skill_category(skill)),
        _escape_table_cell(_skill_description(skill)),
        f"[查看]({link})",
    )


def _join_row_cells(cells: tuple[str, str, str, str, str, str, str, str]) -> str:
    return "| " + " | ".join(cells) + " |"


def format_skill_table_row(rank: int, skill: Skill, is_new: bool = False) -> str:
    return _join_row_cells(_skill_row_cells(rank, skill, is_new=is_new))


def _split_row_cells_by_desc(
    cells: tuple[str, str, str, str, str, str, str, str],
    max_len: int,
) -> list[str]:
    rank, name, vendor, pub_type, data_src, cat, desc, link = cells
    first_prefix = f"| {rank} | {name} | {vendor} | {pub_type} | {data_src} | {cat} | "
    cont_prefix = "| | | | | | | "
    suffix = f" | {link} |"

    full = f"{first_prefix}{desc}{suffix}"
    if len(full) <= max_len:
        return [full]

    rows: list[str] = []
    remaining = desc
    first = True
    while remaining:
        prefix = first_prefix if first else cont_prefix
        budget = max_len - len(prefix) - len(suffix)
        if budget < 1:
            rows.append(full[:max_len])
            break
        piece = remaining[:budget]
        remaining = remaining[budget:]
        rows.append(f"{prefix}{piece}{suffix}")
        first = False
    return rows or [full]


def _split_table_row_by_desc(row: str, max_len: int) -> list[str]:
    """Split one table row into continuation rows when description exceeds message budget."""
    if len(row) <= max_len:
        return [row]

    inner = row.strip().removeprefix("|").removesuffix("|")
    parts = [p.strip() for p in inner.split("|")]
    if len(parts) != 8:
        return [row]
    return _split_row_cells_by_desc(tuple(parts), max_len)


def format_skill_table(items: list[tuple[Skill, float]], *, is_new: bool = False) -> list[str]:
    if not items:
        return []
    lines = [TABLE_HEADER, TABLE_SEP]
    for i, (skill, _) in enumerate(items, 1):
        lines.append(format_skill_table_row(i, skill, is_new=is_new))
    return lines


def split_md_messages(content: str, max_len: int = MD_MAX_LEN) -> list[str]:
    """Split long MD into multiple messages (each <= max_len). Footer only on last part."""
    body = content.strip()
    footer = f"*{PUSH_FOOTER}*"
    if body.endswith(footer):
        body = body[: -len(footer)].rstrip()

    if len(body) + len(footer) + 2 <= max_len:
        return [f"{body}\n\n{footer}"]

    if TABLE_HEADER in body:
        return _split_table_md(body, footer, max_len)

    parts: list[str] = []
    remaining = body
    footer_reserve = len(footer) + 2

    while remaining:
        limit = max_len - footer_reserve if not parts else max_len
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        cut = remaining.rfind("\n\n", 0, limit)
        if cut < limit // 3:
            cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunk = remaining[:cut].rstrip()
        if not chunk:
            chunk = remaining[:limit]
        if len(chunk) > limit:
            chunk = chunk[:limit].rstrip()
        parts.append(chunk)
        remaining = remaining[len(chunk) :].lstrip()

    if not parts:
        return [footer]

    last = parts[-1]
    combined = f"{last}\n\n{footer}"
    if len(combined) <= max_len:
        parts[-1] = combined
    else:
        allowed = max(0, max_len - footer_reserve)
        parts[-1] = f"{last[:allowed].rstrip()}\n\n{footer}"
    return parts


def _vendor_label(vendors: list[str] | None) -> str:
    if not vendors:
        return ""
    return " · ".join(vendors)


def build_push_title(
    mode: str,
    *,
    title_date: str = "",
    vendors: list[str] | None = None,
) -> str:
    vendor_part = _vendor_label(vendors)
    prefix = f"{PRODUCT_NAME} · {vendor_part} · " if vendor_part else f"{PRODUCT_NAME} · "
    titles = {
        "today": f"{prefix}今日新增 Skill",
        "leaderboard": f"{prefix}Skill 总榜",
        "dual": f"{prefix}Skill 精选",
        "custom": f"{prefix}Skill 精选",
    }
    title = titles.get(mode, f"{prefix}Skill 推送")
    if title_date:
        title = f"{title} ({title_date})"
    return title


def build_section_heading(
    section: str,
    mode: str,
    vendors: list[str] | None = None,
) -> str:
    vendor_part = _vendor_label(vendors)
    if section == "today":
        if mode == "dual":
            return "**今日新增**" if not vendor_part else f"**{vendor_part} · 今日新增**"
        return f"**{vendor_part} · 今日新增 Skill**" if vendor_part else "**今日新增 Skill**"
    if section == "leaderboard":
        if mode == "dual":
            return "**Skill 总榜**" if not vendor_part else f"**{vendor_part} · Skill 总榜**"
        return f"**{vendor_part} · Skill 总榜**" if vendor_part else "**Skill 总榜**"
    return "**Skill 列表**"


def _split_table_md(body: str, footer: str, max_len: int) -> list[str]:
    """Split markdown tables on row boundaries; repeat header on continuations."""
    lines = body.split("\n")
    parts: list[str] = []
    chunk: list[str] = []
    table_header: list[str] = []

    def chunk_text(extra_footer: bool = False) -> str:
        text = "\n".join(chunk).strip()
        if extra_footer:
            text = f"{text}\n\n{footer}"
        return text

    def flush(extra_footer: bool = False) -> None:
        nonlocal chunk
        if chunk:
            parts.append(chunk_text(extra_footer))
            chunk = []

    for line in lines:
        if line == TABLE_HEADER:
            table_header = [TABLE_HEADER, TABLE_SEP]
            chunk.append(line)
            continue
        if line == TABLE_SEP:
            if table_header:
                chunk.append(line)
            continue

        if line.startswith("| ") and table_header:
            row_lines = _split_table_row_by_desc(line, max_len - 80) if len(line) > max_len - 80 else [line]
            for row_line in row_lines:
                candidate = "\n".join(chunk + [row_line])
                reserve = len(f"\n\n{footer}") + 2
                has_data_rows = len(chunk) > len(table_header)
                if has_data_rows and len(candidate) + reserve > max_len:
                    flush(False)
                    chunk.extend(table_header)
                chunk.append(row_line)
            continue

        chunk.append(line)

    flush(True)
    return parts if parts else [footer]


def format_push_content(
    today_items: list[tuple[Skill, float]],
    leaderboard_items: list[tuple[Skill, float]],
    *,
    mode: str = "dual",
    title_date: str = "",
    vendors: list[str] | None = None,
) -> str:
    """Generate Ruliu MD push body (markdown table layout)."""
    lines = [f"##### {build_push_title(mode, title_date=title_date, vendors=vendors)}", ""]

    if leaderboard_items:
        lines.append(build_section_heading("leaderboard", mode, vendors))
        lines.append("")
        lines.extend(format_skill_table(leaderboard_items))
        lines.append("")

    if today_items:
        lines.append(build_section_heading("today", mode, vendors))
        lines.append("")
        lines.extend(format_skill_table(today_items, is_new=True))
        lines.append("")

    lines.append(f"*{PUSH_FOOTER}*")
    return "\n".join(lines).strip()


def format_push_messages(
    today_items: list[tuple[Skill, float]],
    leaderboard_items: list[tuple[Skill, float]],
    *,
    mode: str = "dual",
    title_date: str = "",
    vendors: list[str] | None = None,
) -> list[str]:
    """Return one or more MD messages ready to send."""
    return split_md_messages(
        format_push_content(
            today_items,
            leaderboard_items,
            mode=mode,
            title_date=title_date,
            vendors=vendors,
        )
    )


def format_digest_md(
    today_items: list[tuple[Skill, float]],
    leaderboard_items: list[tuple[Skill, float]],
    *,
    title_date: str = "",
    mode: str = "dual",
    vendors: list[str] | None = None,
) -> str:
    return format_push_content(
        today_items, leaderboard_items, mode=mode, title_date=title_date, vendors=vendors
    )


def _parse_dm_response(data: dict[str, Any]) -> None:
    if data.get("code") == "ok":
        inner = data.get("data")
        if isinstance(inner, dict) and inner.get("errcode", 0) not in (0, None):
            raise RuntimeError(f"Ruliu DM push failed: {data}")
        return
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"Ruliu DM push failed: {data}")


def _plain_text_fallback(content: str) -> str:
    import re

    text = content
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    return text.strip()


async def send_dm_markdown(content: str, *, touser: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    target_user = touser or settings.ruliu_dm_user
    if not target_user:
        raise ValueError("RULIU_DM_USER required for DM push")

    body = content[:MD_MAX_LEN]
    token = await _get_app_access_token()
    url = f"{settings.ruliu_api_base.rstrip('/')}/app/message/send"

    payloads = [
        {"touser": target_user, "msgtype": "md", "md": {"content": body}},
        {
            "touser": target_user,
            "msgtype": "text",
            "text": {"content": _plain_text_fallback(body)},
        },
    ]

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=15.0) as client:
        for payload in payloads:
            try:
                resp = await client.post(url, json=payload, headers=_auth_headers(token))
                data = resp.json()
                if resp.status_code >= 400:
                    last_error = RuntimeError(f"Ruliu DM HTTP error: {data}")
                    continue
                _parse_dm_response(data)
                return {"touser": target_user, "payload_type": payload["msgtype"], "response": data}
            except Exception as exc:
                last_error = exc
                logger.warning("DM push attempt failed (%s): %s", payload.get("msgtype"), exc)

    raise RuntimeError(f"Ruliu DM push failed: {last_error}")


async def send_dm_to_users(content: str, users: list[str]) -> list[dict[str, Any]]:
    if not users:
        raise ValueError("no DM recipients")
    results: list[dict[str, Any]] = []
    messages = split_md_messages(content)
    for user in users:
        for idx, part in enumerate(messages):
            results.append(await send_dm_markdown(part, touser=user))
            if idx + 1 < len(messages):
                await asyncio.sleep(0.3)
        await asyncio.sleep(0.2)
    return results


async def send_group_md(
    content: str, *, group_id: str | None = None, force: bool = False
) -> dict[str, Any]:
    settings = get_settings()
    if not force and not settings.ruliu_allow_group:
        return {"skipped": True, "message": "RULIU_ALLOW_GROUP=false"}
    target_group = group_id or settings.ruliu_group_id
    if not target_group:
        raise ValueError("RULIU_GROUP_ID required for group push")

    token = await _get_app_access_token()
    url = f"{settings.ruliu_api_base.rstrip('/')}/robot/msg/groupmsgsend"
    md_body = content[:MD_MAX_LEN]
    payload = {
        "message": {
            "header": {
                "toid": int(target_group),
                "totype": "GROUP",
                "msgtype": "MD",
                "clientmsgid": int(time.time() * 1000),
                "role": "robot",
            },
            "body": [{"type": "MD", "content": md_body}],
        }
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=_auth_headers(token))
        data = resp.json()
        if resp.status_code >= 400 or data.get("code") != "ok":
            raise RuntimeError(f"Ruliu group push failed: {data}")
        return data


async def send_digest(
    content: str, dry_run: bool = False, *, target: str | None = None, dm_users: list[str] | None = None
) -> dict[str, Any]:
    settings = get_settings()
    messages = split_md_messages(content)
    if dry_run:
        return {"dry_run": True, "parts": len(messages), "content_preview": messages[0][:500]}
    if not settings.ruliu_app_key:
        return {"dry_run": True, "message": "RULIU_APP_KEY not configured"}

    from app.services.push.push_targets import get_push_recipients

    recipients = await get_push_recipients()
    notify_target = (target or settings.ruliu_notify_target).lower()
    results: list[dict[str, Any]] = []

    if notify_target == "group":
        group_ids = recipients.get("group_ids") or []
        if not group_ids and settings.ruliu_group_id:
            group_ids = [settings.ruliu_group_id]
        for gid in group_ids:
            for idx, part in enumerate(messages):
                results.append(await send_group_md(part, group_id=gid, force=True))
                if idx + 1 < len(messages):
                    await asyncio.sleep(0.3)
            await asyncio.sleep(0.2)
    else:
        users = dm_users or recipients.get("dm_users") or []
        if not users and settings.ruliu_dm_user:
            users = [settings.ruliu_dm_user]
        for user in users:
            for idx, part in enumerate(messages):
                results.append(await send_dm_markdown(part, touser=user))
                if idx + 1 < len(messages):
                    await asyncio.sleep(0.3)
            await asyncio.sleep(0.2)

    return {"parts": len(messages), "results": results}


async def send_test_message() -> dict[str, Any]:
    content = (
        f"##### {PRODUCT_NAME} 如流 MD 测试\n\n"
        f"{TABLE_HEADER}\n"
        f"{TABLE_SEP}\n"
        f"| 1 | [团购核销查询](https://developer.meituan.com/ai-hub/skill-list?skill=tuangou-receipt-query) 🆕 "
        f"| 美团 | 服务零售 | 支持团购券码校验与核销查询 | [查看](https://developer.meituan.com/ai-hub/skill-list?skill=tuangou-receipt-query) |\n\n"
        f"*{PUSH_FOOTER}*"
    )
    return await send_dm_markdown(content)
