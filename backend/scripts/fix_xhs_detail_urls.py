#!/usr/bin/env python3
"""修正 DB 中小红书 RedSkill 记录的聚合镜像 detail_url。"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.core.database import async_session_factory
from app.init_db import init_db
from app.models import Skill
from app.services.skill_links import clawhub_skills_url, extract_skill_slug, is_aggregate_mirror_url


async def main() -> None:
    await init_db(dispose=False)
    fixed = 0
    async with async_session_factory() as session:
        skills = list(
            (
                await session.scalars(
                    select(Skill).where(
                        Skill.source_id == "xiaohongshu_red_skill",
                        Skill.status == "active",
                    )
                )
            ).all()
        )
        for skill in skills:
            url = (skill.detail_url or "").strip()
            if not is_aggregate_mirror_url(url) and url.startswith("https://clawhub-skills.com/skills/"):
                continue
            slug = extract_skill_slug(skill)
            if not slug and skill.external_id.startswith("redskill:"):
                slug = skill.external_id.split(":", 1)[1]
            if not slug:
                continue
            new_url = clawhub_skills_url(slug)
            meta = skill.metadata_json if isinstance(skill.metadata_json, dict) else {}
            meta = dict(meta)
            meta.setdefault("slug", slug)
            meta["redskill"] = True
            meta["catalog"] = "clawhub"
            meta["clawhub"] = True
            skill.detail_url = new_url
            skill.metadata_json = meta
            fixed += 1
        await session.commit()
    print(f"fixed {fixed} xiaohongshu detail_url records")


if __name__ == "__main__":
    asyncio.run(main())
