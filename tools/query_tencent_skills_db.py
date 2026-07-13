"""
从 IKnow 数据库和已知渠道查询腾讯系 Skills 的信息。
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models import Skill

# 要搜索的腾讯系 Skills
TENCENT_SKILLS = [
    "腾讯自选股-金融数据查询",
    "腾讯文档",
    "腾讯新闻",
    "腾讯ima",
    "腾讯文档PDFKit",
    "腾讯文档高考志愿填报助手",
    "腾讯云通用文字识别OCR",
    "Skill安全审计（云鼎实验室）",
    "腾讯地图·地图助手",
    "腾讯乐享",
    "腾讯云CloudBase",
    "腾讯会议",
    "腾讯微云",
    "元宝搜索标准版",
    "EdgeOne Pages Deploy",
    "AndonQ",
    "腾讯问卷",
    "腾讯云广告文字识别OCR",
    "腾讯云表格识别OCR",
    "腾讯校园招聘",
    "MigraQ",
    "腾讯云解决方案PPT制作",
    "腾讯云可观测平台API",
    "腾讯云COS",
    "腾讯云试题批改",
    "腾讯云实时文档抽取",
    "腾讯电子签",
    "腾讯游戏防沉迷家长管控助手",
    "腾讯云竞品分析",
    "公益文书助手",
    "腾讯文档智能页面",
    "腾讯云日志服务CLS",
    "腾讯云知",
    "鹅厂辟谣助手",
    "腾讯音乐校招助手",
    "腾讯技术公益智能助手",
    "腾讯音乐人AI助手",
    "腾讯云COS向量",
]


async def query_db():
    async with async_session_factory() as session:
        # 查询 vendor=腾讯 的所有 active skills
        result = await session.execute(
            select(Skill).where(
                Skill.vendor == "腾讯",
                Skill.status == "active",
            ).order_by(Skill.name)
        )
        skills = result.scalars().all()
        print(f"数据库中共有 {len(skills)} 个腾讯 active skills\n")

        # Build name index
        name_index: dict[str, list[Skill]] = {}
        for s in skills:
            key = s.name.lower().strip()
            name_index.setdefault(key, []).append(s)

        results = []
        for target in TENCENT_SKILLS:
            target_lower = target.lower().strip()
            matched_skills = []

            # 1. exact match
            if target_lower in name_index:
                matched_skills = name_index[target_lower]

            # 2. fuzzy match — name contains target keywords or vice versa
            if not matched_skills:
                target_keywords = target_lower.replace("（", " ").replace("）", " ").replace("·", " ").replace("-", " ").replace("—", " ").split()
                for s in skills:
                    s_lower = s.name.lower()
                    # Check if significant keywords match
                    score = sum(1 for kw in target_keywords if len(kw) > 1 and kw in s_lower)
                    if score >= 2 or (score >= 1 and len(target_keywords) <= 3):
                        matched_skills.append(s)

            # 3. check metadata for official/tencent match
            if not matched_skills:
                for s in skills:
                    meta = s.metadata_json if isinstance(s.metadata_json, dict) else {}
                    s_lower = s.name.lower()
                    # Try matching significant words
                    target_parts = [p for p in target_lower.replace("（"," ").replace("）"," ").replace("·"," ").replace("-"," ").split() if len(p) > 1]
                    if any(p in s_lower for p in target_parts):
                        matched_skills.append(s)

            if matched_skills:
                for s in matched_skills[:2]:  # at most 2 matches
                    meta = s.metadata_json if isinstance(s.metadata_json, dict) else {}
                    catalog = meta.get("catalog", "unknown")
                    detail_url = s.detail_url or ""
                    repo = meta.get("repo", "")
                    results.append({
                        "target": target,
                        "matched_name": s.name,
                        "detail_url": detail_url,
                        "catalog": catalog,
                        "source_id": s.source_id,
                        "external_id": s.external_id,
                        "repo": repo,
                        "raw_description": (s.raw_description or "")[:100],
                        "install_count": s.install_count or 0,
                        "first_seen_at": str(s.first_seen_at) if s.first_seen_at else "",
                    })
            else:
                results.append({
                    "target": target,
                    "matched_name": "",
                    "detail_url": "",
                    "catalog": "NOT_FOUND",
                    "source_id": "",
                    "external_id": "",
                    "repo": "",
                    "raw_description": "",
                    "install_count": 0,
                    "first_seen_at": "",
                })

        # Print report
        print(f"| {'Skill 名称':<30} | {'数据库中匹配':<12} | {'渠道':<20} | {'链接/详情':<80} |")
        print(f"|{'-'*32}|{'-'*14}|{'-'*22}|{'-'*82}|")
        for r in results:
            name = r["target"]
            if r["matched_name"]:
                found = "✓ " + r["matched_name"][:10]
                channel = r["source_id"] or r["catalog"]
                link = r["detail_url"] or r["repo"] or ""
                if not link and r["external_id"]:
                    link = f"external_id: {r['external_id']}"
            else:
                found = "✗ 未找到"
                channel = "-"
                link = "-"
            print(f"| {name:<30} | {found:<12} | {channel:<20} | {link:<80} |")

        return results


if __name__ == "__main__":
    results = asyncio.run(query_db())
    print("\n\n===== JSON 输出 =====")
    print(json.dumps(results, ensure_ascii=False, indent=2))
