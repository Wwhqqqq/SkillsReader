"""
阿里云 Agent Skills 门户 Adapter —— 官方公开 JSON API。

数据来源: https://skills.aliyun.com/api/public/skills
抓取方式: 与 meituan.py 类似，httpx GET + resp.json()
yaml: adapter: aliyun_skills, id: aliyun_skills_portal
"""

from __future__ import annotations

import httpx

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

ALIYUN_SKILLS_API = "https://skills.aliyun.com/api/public/skills"
ALIYUN_PORTAL = "https://skills.aliyun.com"


class AliyunSkillsAdapter(SourceAdapter):
    source_id = "aliyun_skills_portal"
    vendor = "阿里"

    async def fetch(self) -> list[RawSkillRecord]:
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                ALIYUN_SKILLS_API,
                params={"page": 1, "pageSize": 500},
                headers={"Accept": "application/json", "User-Agent": "IKnow/1.0"},
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 200:
                raise RuntimeError(f"Aliyun API error: {payload}")

            for group in payload.get("data") or []:
                if not isinstance(group, dict):
                    continue
                for item in group.get("list") or []:
                    if not isinstance(item, dict):
                        continue
                    rec = self._to_record(item)
                    if rec.external_id in seen:
                        continue
                    seen.add(rec.external_id)
                    records.append(rec)

            for rec in await fetch_skillsmp_for_vendor(
                client,
                vendor=self.vendor,
                source_id=self.source_id,
                max_pages=2,
            ):
                if rec.external_id not in seen:
                    seen.add(rec.external_id)
                    records.append(rec)
        return await apply_vendor_relevance_split(self.vendor, records)

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        """仅阿里云 Skills 官方 API。"""
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                ALIYUN_SKILLS_API,
                params={"page": 1, "pageSize": 500},
                headers={"Accept": "application/json", "User-Agent": "IKnow/1.0"},
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 200:
                raise RuntimeError(f"Aliyun API error: {payload}")
            for group in payload.get("data") or []:
                if not isinstance(group, dict):
                    continue
                for item in group.get("list") or []:
                    if not isinstance(item, dict):
                        continue
                    rec = self._to_record(item)
                    if rec.external_id in seen:
                        continue
                    seen.add(rec.external_id)
                    records.append(rec)
        return records

    def _to_record(self, item: dict) -> RawSkillRecord:
        skill_name = str(item.get("skillName") or "")
        display = str(item.get("displayName") or skill_name)
        category = str(item.get("categoryName") or item.get("categoryCode") or "云产品")
        sub = str(item.get("subCategoryName") or item.get("subCategoryCode") or "")
        install = int(item.get("totalInstallCount") or item.get("installCount") or 0)
        desc = str(item.get("description") or "")
        version = str(item.get("version") or "")
        tags = ["阿里", category]
        if sub:
            tags.append(sub)

        return RawSkillRecord(
            external_id=skill_name,
            name=display,
            vendor=self.vendor,
            source_id=self.source_id,
            raw_description=desc,
            detail_url=f"{ALIYUN_PORTAL}/skills/{skill_name}",
            tags=tags,
            install_count=install,
            publish_date=(item.get("createdAt") or "")[:10] or None,
            metadata={
                "skillName": skill_name,
                "categoryCode": item.get("categoryCode"),
                "categoryName": category,
                "subCategoryName": sub,
                "version": version,
                "catalog": "official_api",
                "official": True,
                "raw": item,
            },
        )
