"""
统计与健康检查 API —— Dashboard 总览、厂商分布。

路由:
    GET  /api/health
    GET  /api/stats/overview
    GET  /api/stats/vendors
    POST /api/notify-test  （如流测试消息）
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import is_scan_globally_enabled
from app.models import PushLog, Skill, Source
from app.schemas import OverviewStats, VendorStat, VendorStatsResponse

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/health")
async def health():
    """K8s/负载均衡探活用，无 DB 依赖。"""
    return {"status": "ok", "service": "iknow"}


@router.post("/notify-test")
async def notify_test():
    """发送一条如流测试消息，验证 RULIU_* 配置。"""
    from app.services.push.ruliu_notifier import send_test_message

    try:
        result = await send_test_message()
        return {"success": True, "result": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/stats/overview", response_model=OverviewStats)
async def overview(session: AsyncSession = Depends(get_db)):
    """Dashboard 顶部卡片：总数、今日新增、源状态等。"""
    total = (
        await session.scalar(
            select(func.count())
            .select_from(Skill)
            .where(Skill.status == "active")
        )
        or 0
    )
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    today_new = (
        await session.scalar(
            select(func.count())
            .select_from(Skill)
            .where(
                Skill.status == "active",
                Skill.first_seen_at >= today_start,
            )
        )
        or 0
    )
    sources = list((await session.scalars(select(Source))).all())
    active = sum(1 for s in sources if s.enabled)
    scanning = sum(1 for s in sources if s.last_status == "scanning")
    last_push = await session.scalar(
        select(PushLog.created_at)
        .where(PushLog.status == "sent")
        .order_by(PushLog.created_at.desc())
        .limit(1)
    )
    scan_enabled = await is_scan_globally_enabled()
    return OverviewStats(
        total_skills=total,
        today_new=today_new,
        active_sources=active,
        total_sources=len(sources),
        scanning_sources=scanning,
        last_push_at=last_push,
        scan_enabled=scan_enabled,
    )


@router.get("/stats/vendors", response_model=VendorStatsResponse)
async def vendor_stats(session: AsyncSession = Depends(get_db)):
    """按 vendor 聚合 Skill 数量与分类分布。"""
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    skills = list(
        (
            await session.scalars(select(Skill).where(Skill.status == "active"))
        ).all()
    )

    vendor_map: dict[str, dict] = {}
    meituan_total = 0
    for s in skills:
        v = s.vendor
        if v not in vendor_map:
            vendor_map[v] = {"total": 0, "today_new": 0, "categories": {}}
        vendor_map[v]["total"] += 1
        if s.first_seen_at and s.first_seen_at >= today_start:
            vendor_map[v]["today_new"] += 1
        cat = _skill_category_label(s)
        vendor_map[v]["categories"][cat] = vendor_map[v]["categories"].get(cat, 0) + 1
        if s.source_id == "meituan_ai_hub":
            meituan_total += 1

    vendors = [
        VendorStat(
            vendor=k,
            total=v["total"],
            today_new=v["today_new"],
            categories=dict(sorted(v["categories"].items(), key=lambda x: -x[1])),
        )
        for k, v in sorted(vendor_map.items(), key=lambda x: -x[1]["total"])
    ]
    return VendorStatsResponse(vendors=vendors, meituan_total=meituan_total)


def _skill_category_label(skill: Skill) -> str:
    """从 metadata 或 tags 推断分类显示名。"""
    meta = skill.metadata_json or {}
    if isinstance(meta, dict):
        if meta.get("categoryName"):
            return str(meta["categoryName"])
        if meta.get("category"):
            return str(meta["category"])
    tags = skill.tags or []
    skip = {"美团", "阿里", "腾讯", "字节", "知乎", "小红书", "哔哩哔哩", "快手", "滴滴", "拼多多", "携程", "得物", "github", "skills.sh", "云资源", "生活服务", "海外社区"}
    for t in tags:
        if t not in skip:
            return str(t)
    return "未分类"
