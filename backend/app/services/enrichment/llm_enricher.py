"""DeepSeek LLM skill description enricher."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import LlmJob, Skill

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """你是 Agent Skill 情报编辑。根据以下信息，用中文写 1-2 句话（不超过80字）说明这个 Skill 做什么、适合什么场景。不要编造没有的功能。

厂商：{vendor}
名称：{name}
原始描述：{raw_description}
标签：{tags}
链接：{detail_url}"""


async def enrich_skill(session: AsyncSession, skill_id: int) -> str | None:
    skill = await session.get(Skill, skill_id)
    if not skill:
        return None

    settings = get_settings()
    if not settings.deepseek_api_key:
        summary = _fallback_summary(skill)
        skill.llm_summary = summary
        skill.llm_summary_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return summary

    prompt = PROMPT_TEMPLATE.format(
        vendor=skill.vendor,
        name=skill.name,
        raw_description=skill.raw_description or "无",
        tags=", ".join(skill.tags or []),
        detail_url=skill.detail_url or "",
    )
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

    if skill.llm_summary and skill.raw_description and len(skill.raw_description) >= 20:
        return skill.llm_summary

    job = LlmJob(skill_id=skill_id, status="running", prompt_hash=prompt_hash)
    session.add(job)
    await session.flush()

    start = time.time()
    try:
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        resp = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        summary = (resp.choices[0].message.content or "").strip()[:512]
        latency = int((time.time() - start) * 1000)
        job.status = "done"
        job.result = summary
        job.latency_ms = latency
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        skill.llm_summary = summary
        skill.llm_summary_at = job.finished_at
        return summary
    except Exception as exc:
        logger.warning("LLM enrich failed for skill %s: %s", skill_id, exc)
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        summary = _fallback_summary(skill)
        skill.llm_summary = summary
        skill.llm_summary_at = job.finished_at
        return summary


def _fallback_summary(skill: Skill) -> str:
    if skill.raw_description and len(skill.raw_description) >= 10:
        return skill.raw_description[:80]
    return f"{skill.vendor} 平台 Skill「{skill.name}」，详情见源站。"


async def enrich_skills_batch(session: AsyncSession, skill_ids: list[int]) -> None:
    for sid in skill_ids[:20]:
        await enrich_skill(session, sid)


async def get_skills_needing_enrich(session: AsyncSession, limit: int = 10) -> list[int]:
    q = (
        select(Skill.id)
        .where(
            Skill.status == "active",
            (Skill.llm_summary.is_(None)) | (Skill.llm_summary == ""),
        )
        .order_by(Skill.first_seen_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(q)).all())
