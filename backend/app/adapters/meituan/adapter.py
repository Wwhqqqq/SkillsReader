"""
美团 AI Hub Skill 列表 Adapter —— JSON API 分页抓取示例。

数据来源:
    列表 API: https://developer.meituan.com/api/v4/front/skill/service/list
    页面:     https://developer.meituan.com/ai-hub/skill-list

抓取方式:
    httpx 异步 GET + resp.json() 解析
    比 HTML 解析更稳定（推荐优先找 JSON API）

对应 yaml:
    adapter: meituan
    id: meituan_ai_hub
"""

from __future__ import annotations

import json
import re
from typing import Any  # Any = 任意类型，用于 JSON dict 等动态结构

import httpx  # 异步 HTTP 客户端

from app.adapters.base import RawSkillRecord, SourceAdapter
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor
from app.services.enrichment.vendor_relevance import apply_vendor_relevance_split

# 模块级常量：大写表示不应修改的配置
MEITUAN_LIST_URL = "https://developer.meituan.com/api/v4/front/skill/service/list"
MEITUAN_PAGE_URL = "https://developer.meituan.com/ai-hub/skill-list"
MEITUAN_DETAIL_BASE = "https://developer.meituan.com/ai-hub/skill-list"


class MeituanAdapter(SourceAdapter):
    """美团开放平台 Skill 列表抓取器。"""

    source_id = "meituan_ai_hub"  # 必须与 sources.yaml 的 id 一致
    vendor = "美团"

    async def fetch(self) -> list[RawSkillRecord]:
        """
        主入口：分页拉取最多 5 页 × 50 条，去重后返回。

        async with httpx.AsyncClient:
            创建 HTTP 客户端，离开 with 块自动关闭连接。
        """
        headers = {
            # User-Agent: 模拟浏览器，避免被反爬拒绝
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",  # 声明期望 JSON 响应
            "Referer": MEITUAN_PAGE_URL,   # 部分 API 校验来源页
        }
        records: list[RawSkillRecord] = []  # 类型注解：RawSkillRecord 的列表
        seen: set[str] = set()              # set 用于 O(1) 去重

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for page in range(1, 6): 
                resp = await client.get(
                    MEITUAN_LIST_URL,
                    params={"pageNo": page, "pageSize": 50},  # URL 查询参数 ?pageNo=1&pageSize=50
                    headers=headers,
                )
                resp.raise_for_status()  # HTTP 4xx/5xx 抛异常
                batch = self._parse_api(resp.json())  # JSON → Python dict
                if not batch:
                    break  # 空页则停止分页
                for rec in batch:
                    if rec.external_id not in seen:
                        seen.add(rec.external_id)
                        records.append(rec)
                if len(batch) < 50:
                    break  # 最后一页不足 50 条

            for rec in await fetch_skillsmp_for_vendor(
                client,
                vendor=self.vendor,
                source_id=self.source_id,
                max_pages=3,
            ):
                if rec.external_id not in seen:
                    seen.add(rec.external_id)
                    records.append(rec)
        return await apply_vendor_relevance_split(self.vendor, records)

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        """仅美团 AI Hub 官方 API，不含 SkillsMP。"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": MEITUAN_PAGE_URL,
        }
        records: list[RawSkillRecord] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for page in range(1, 6):
                resp = await client.get(
                    MEITUAN_LIST_URL,
                    params={"pageNo": page, "pageSize": 50},
                    headers=headers,
                )
                resp.raise_for_status()
                batch = self._parse_api(resp.json())
                if not batch:
                    break
                for rec in batch:
                    if rec.external_id not in seen:
                        seen.add(rec.external_id)
                        records.append(rec)
                if len(batch) < 50:
                    break
        return records

    def _parse_api(self, data: dict[str, Any]) -> list[RawSkillRecord]:
        """
        解析美团 API JSON 为 RawSkillRecord 列表。

        防御式编程:
            .get("key", default) 键不存在不报错
            isinstance(x, dict)  确保是字典再处理
            or 链                多个可能的字段名取第一个有值的
        """
        items: list[dict] = []
        biz = data.get("data", {}).get("biz", {})
        if isinstance(biz, dict):
            items = biz.get("data") or []
        elif isinstance(data.get("data"), list):
            items = data["data"]  # 兼容另一种响应结构

        records: list[RawSkillRecord] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            skill_name = item.get("skillName") or item.get("name") or ""
            display = item.get("displayName") or skill_name
            if not display:
                continue  # 无名称的条目跳过

            external_id = str(item.get("id") or skill_name)
            summary = item.get("summary") or ""
            description = item.get("description") or summary
            category = item.get("category") or "生活服务"
            published = item.get("publishedAt") or item.get("createdAt")
            pub_date = published[:10] if published else None  # 取 YYYY-MM-DD

            tags = [category, "美团"]
            if item.get("scenes"):
                tags.extend(str(s) for s in item["scenes"][:3])  # 最多 3 个场景标签

            records.append(
                RawSkillRecord(
                    external_id=external_id,
                    name=str(display).strip(),
                    vendor=self.vendor,
                    source_id=self.source_id,
                    raw_description=str(description or summary).strip(),
                    detail_url=f"{MEITUAN_DETAIL_BASE}?skill={skill_name}",
                    tags=tags,
                    publish_date=pub_date,
                    metadata={
                        "skillName": skill_name,
                        "raw": item,
                        "catalog": "official_api",
                        "official": True,
                    },
                )
            )
        return records

    def _parse_embedded_json(self, html: str) -> list[RawSkillRecord]:
        """
        备用方案：从 HTML 里抠 __NEXT_DATA__ 等嵌入 JSON。
        当 API 不可用时可以尝试；当前 fetch 主要走 _parse_api。
        """
        patterns = [
            r"__NEXT_DATA__\s*=\s*(\{.*?\})\s*;?\s*</script>",
            r'"data"\s*:\s*(\[.*?\])',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)  # DOTALL: . 匹配换行
            if not match:
                continue
            try:
                parsed = json.loads(match.group(1))  # group(1)=第一个捕获组
                if isinstance(parsed, list):
                    return [
                        self._to_record(item, i)
                        for i, item in enumerate(parsed)
                        if isinstance(item, dict)
                    ]
            except json.JSONDecodeError:
                continue
        return []

    def _to_record(self, item: dict, index: int) -> RawSkillRecord:
        """把单个 dict 转为 RawSkillRecord（嵌入 JSON 路径用）。"""
        name = item.get("displayName") or item.get("name") or f"skill-{index}"
        desc = item.get("description") or item.get("summary") or ""
        external_id = str(item.get("id") or item.get("skillName") or name)
        return RawSkillRecord(
            external_id=external_id,
            name=str(name).strip(),
            vendor=self.vendor,
            source_id=self.source_id,
            raw_description=str(desc).strip(),
            detail_url=MEITUAN_PAGE_URL,
            tags=["美团"],
            metadata={"raw": item},
        )
