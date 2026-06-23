"""推送前用 DeepSeek 压缩精选 Skill 简介。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.services.digest.types import DigestPickItem

logger = logging.getLogger(__name__)

PUSH_DESC_PROMPT = """你是推送文案编辑。为下列 Agent Skill 各写一条中文简介。

要求：
1. 每条不超过 {max_len} 个字（汉字/标点均计 1 字）
2. 只写核心用途，不编造未给出的功能
3. 不要引号、不要序号、不要 Skill 名称重复堆砌
4. 仅输出 JSON 数组，格式：[{{"id": 123, "summary": "简介"}}]

Skills：
{payload}
"""


def _source_description(skill) -> str:
    return (skill.llm_summary or skill.raw_description or skill.name or "").strip()


def truncate_description(text: str, max_len: int) -> str:
    cell = re.sub(r"\s+", " ", text.replace("|", "/").replace("\n", " ")).strip()
    if not cell:
        return "-"
    if len(cell) <= max_len:
        return cell
    cut = cell[:max_len]
    for sep in ("。", "；", "，", "、", " ", "·"):
        idx = cut.rfind(sep)
        if idx >= max(8, max_len // 2):
            return cut[: idx + (1 if sep in "。；" else 0)].strip() or cut
    return cut


def fallback_push_descriptions(items: list[DigestPickItem], max_len: int) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in items:
        skill = item.skill
        base = _source_description(skill)
        if not base or base == skill.name:
            base = f"{skill.vendor} {skill.name} 相关能力"
        out[skill.id] = truncate_description(base, max_len)
    return out


def _parse_llm_json(content: str) -> list[dict[str, Any]]:
    text = (content or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    parsed = json.loads(text)
    return parsed if isinstance(parsed, list) else []


async def polish_push_descriptions(
    items: list[DigestPickItem],
    push_cfg: dict[str, Any] | None = None,
) -> dict[int, str]:
    """为精选条目生成推送用短简介（默认 ≤25 字）。"""
    push_cfg = push_cfg or {}
    max_len = int(push_cfg.get("description_max_len") or 25)
    if not items:
        return {}

    fallback = fallback_push_descriptions(items, max_len)
    settings = get_settings()
    if not settings.deepseek_api_key:
        return fallback

    payload = json.dumps(
        [
            {
                "id": item.skill.id,
                "name": item.skill.name,
                "vendor": item.skill.vendor,
                "description": _source_description(item.skill)[:400],
            }
            for item in items
        ],
        ensure_ascii=False,
    )
    prompt = PUSH_DESC_PROMPT.format(max_len=max_len, payload=payload)

    try:
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        resp = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.2,
        )
        rows = _parse_llm_json(resp.choices[0].message.content or "")
    except Exception as exc:
        logger.warning("DeepSeek push desc polish failed: %s", exc)
        return fallback

    out = dict(fallback)
    for row in rows:
        sid = row.get("id")
        summary = str(row.get("summary") or "").strip()
        if sid is None or not summary:
            continue
        out[int(sid)] = truncate_description(summary, max_len)
    return out
