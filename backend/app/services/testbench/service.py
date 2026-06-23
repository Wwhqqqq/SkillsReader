"""测试平台业务逻辑 —— 独立测试库中的 Skill / 快照 / 模拟推送。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill, SkillMetricSnapshot, Source
from app.services.digest.metrics import load_snapshots_map, upsert_daily_snapshot
from app.services.digest.trace import run_traced_digest
from app.services.scan.normalizer import compute_fingerprint

SIM_PLATFORMS: list[dict[str, Any]] = [
    {"id": "sim_meituan", "vendor": "美团", "name": "[模拟] 美团 AI Hub", "adapter": "meituan"},
    {"id": "sim_tencent", "vendor": "腾讯", "name": "[模拟] 腾讯 SkillHub", "adapter": "wechat_skillhub"},
    {"id": "sim_aliyun", "vendor": "阿里", "name": "[模拟] 阿里云 Skills", "adapter": "aliyun_skills"},
    {"id": "sim_xiaohongshu", "vendor": "小红书", "name": "[模拟] 小红书 RED Skill", "adapter": "xiaohongshu_red_skill"},
    {"id": "sim_skills_sh", "vendor": "海外社区", "name": "[模拟] skills.sh", "adapter": "skills_sh"},
    {"id": "sim_github", "vendor": "GitHub", "name": "[模拟] GitHub Watch", "adapter": "github_watch"},
    {"id": "sim_zhihu", "vendor": "知乎", "name": "[模拟] 知乎 Skills", "adapter": "zhihu_skills"},
    {"id": "sim_bilibili", "vendor": "哔哩哔哩", "name": "[模拟] 哔哩哔哩 Skills", "adapter": "bilibili_skills"},
]


async def ensure_sim_platforms(session: AsyncSession) -> list[Source]:
    out: list[Source] = []
    for p in SIM_PLATFORMS:
        row = await session.get(Source, p["id"])
        if not row:
            row = Source(
                id=p["id"],
                vendor=p["vendor"],
                name=p["name"],
                url="https://testbench.local/",
                category="simulation",
                enabled=True,
                interval_sec=86400,
                adapter=p["adapter"],
                priority=99,
                supplemental=p["id"] in ("sim_skills_sh", "sim_github"),
            )
            session.add(row)
        else:
            row.vendor = p["vendor"]
            row.name = p["name"]
        out.append(row)
    await session.flush()
    return out


async def list_platforms(session: AsyncSession) -> list[dict[str, Any]]:
    await ensure_sim_platforms(session)
    rows = list((await session.scalars(select(Source).where(Source.category == "simulation"))).all())
    return [
        {"id": r.id, "vendor": r.vendor, "name": r.name, "adapter": r.adapter}
        for r in rows
    ]


async def list_skills(session: AsyncSession, *, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    total = await session.scalar(select(func.count()).select_from(Skill).where(Skill.status == "active"))
    rows = list(
        (
            await session.scalars(
                select(Skill)
                .where(Skill.status == "active")
                .order_by(Skill.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return {"items": [_skill_dict(s) for s in rows], "total": total or 0, "page": page, "page_size": page_size}


def _skill_dict(skill: Skill) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "vendor": skill.vendor,
        "source_id": skill.source_id,
        "external_id": skill.external_id,
        "raw_description": skill.raw_description,
        "detail_url": skill.detail_url,
        "tags": skill.tags or [],
        "install_count": skill.install_count,
        "quality_score": skill.quality_score,
        "first_seen_at": skill.first_seen_at.isoformat() if skill.first_seen_at else None,
        "last_seen_at": skill.last_seen_at.isoformat() if skill.last_seen_at else None,
        "metadata_json": skill.metadata_json or {},
        "status": skill.status,
    }


async def create_skill(session: AsyncSession, body: dict[str, Any]) -> dict[str, Any]:
    await ensure_sim_platforms(session)
    source_id = body["source_id"]
    src = await session.get(Source, source_id)
    if not src:
        raise ValueError(f"未知模拟平台: {source_id}")

    name = body["name"].strip()
    external_id = body.get("external_id") or f"sim:{source_id}:{name}"
    fp = compute_fingerprint(src.vendor, source_id, external_id, name)
    seen_day = _parse_date(body.get("first_seen_date")) or date.today()
    seen_ts = datetime.combine(seen_day, datetime.min.time())

    skill = Skill(
        fingerprint=fp,
        vendor=src.vendor,
        source_id=source_id,
        external_id=external_id,
        name=name,
        raw_description=body.get("raw_description") or "",
        detail_url=body.get("detail_url") or "",
        tags=body.get("tags") or [src.vendor],
        install_count=int(body.get("install_count") or 0),
        quality_score=int(body.get("quality_score") or 60),
        first_seen_at=seen_ts,
        last_seen_at=seen_ts,
        metadata_json=body.get("metadata_json") or {},
        status="active",
    )
    if body.get("official"):
        skill.metadata_json = {**(skill.metadata_json or {}), "official": True}

    session.add(skill)
    await session.flush()

    init_metric = int(body.get("install_count") or 0)
    if init_metric >= 0:
        await upsert_daily_snapshot(session, skill, snapshot_date=seen_day)
        skill.install_count = init_metric

    return _skill_dict(skill)


async def update_skill(session: AsyncSession, skill_id: int, body: dict[str, Any]) -> dict[str, Any]:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise ValueError("Skill 不存在")

    for field in ("name", "raw_description", "detail_url", "external_id"):
        if field in body and body[field] is not None:
            setattr(skill, field, body[field])
    if "tags" in body:
        skill.tags = body["tags"]
    if "install_count" in body:
        skill.install_count = int(body["install_count"])
    if "quality_score" in body:
        skill.quality_score = int(body["quality_score"])
    if "metadata_json" in body:
        skill.metadata_json = body["metadata_json"]
    if "first_seen_date" in body and body["first_seen_date"]:
        d = _parse_date(body["first_seen_date"])
        skill.first_seen_at = datetime.combine(d, datetime.min.time())
    if "last_seen_date" in body and body["last_seen_date"]:
        d = _parse_date(body["last_seen_date"])
        skill.last_seen_at = datetime.combine(d, datetime.max.time())

    await session.flush()
    return _skill_dict(skill)


async def delete_skill(session: AsyncSession, skill_id: int) -> None:
    await session.execute(delete(SkillMetricSnapshot).where(SkillMetricSnapshot.skill_id == skill_id))
    skill = await session.get(Skill, skill_id)
    if skill:
        await session.delete(skill)


async def list_snapshot_dates(session: AsyncSession) -> list[str]:
    rows = (
        await session.scalars(
            select(SkillMetricSnapshot.snapshot_date)
            .distinct()
            .order_by(SkillMetricSnapshot.snapshot_date.desc())
        )
    ).all()
    return [d.isoformat() for d in rows]


async def list_snapshots_for_date(session: AsyncSession, ref_date: date) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.scalars(
                select(SkillMetricSnapshot).where(SkillMetricSnapshot.snapshot_date == ref_date)
            )
        ).all()
    )
    skill_map = {
        s.id: s
        for s in (
            await session.scalars(select(Skill).where(Skill.id.in_([r.skill_id for r in rows] or [0])))
        ).all()
    }
    return [
        {
            "skill_id": r.skill_id,
            "skill_name": skill_map[r.skill_id].name if r.skill_id in skill_map else "?",
            "source_id": r.source_id,
            "snapshot_date": r.snapshot_date.isoformat(),
            "metric_value": r.metric_value,
        }
        for r in rows
    ]


async def upsert_snapshots_batch(
    session: AsyncSession,
    ref_date: date,
    items: list[dict[str, Any]],
) -> int:
    count = 0
    ref_ts = datetime.combine(ref_date, datetime.max.time())
    for item in items:
        skill = await session.get(Skill, int(item["skill_id"]))
        if not skill:
            continue
        value = int(item["metric_value"])
        existing = await session.scalar(
            select(SkillMetricSnapshot).where(
                SkillMetricSnapshot.skill_id == skill.id,
                SkillMetricSnapshot.snapshot_date == ref_date,
            )
        )
        if existing:
            existing.metric_value = value
            existing.source_id = skill.source_id
        else:
            session.add(
                SkillMetricSnapshot(
                    skill_id=skill.id,
                    snapshot_date=ref_date,
                    metric_value=value,
                    metric_kind="install",
                    source_id=skill.source_id,
                )
            )
        skill.install_count = value
        skill.last_seen_at = max(skill.last_seen_at or ref_ts, ref_ts)
        count += 1
    await session.flush()
    return count


async def generate_timeline(
    session: AsyncSession,
    skill_id: int,
    start_date: date,
    values: list[int],
) -> int:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise ValueError("Skill 不存在")
    count = 0
    for i, val in enumerate(values):
        d = start_date + timedelta(days=i)
        await upsert_snapshots_batch(session, d, [{"skill_id": skill_id, "metric_value": val}])
        count += 1
    if values:
        skill.first_seen_at = datetime.combine(start_date, datetime.min.time())
    return count


async def prepare_ref_date(session: AsyncSession, ref_date: date) -> dict[str, Any]:
    """将各 Skill 的 install_count / last_seen_at 同步到参考日快照值。"""
    snap_map = await load_snapshots_map(
        session,
        [s.id for s in (await session.scalars(select(Skill).where(Skill.status == "active"))).all()],
        ref_date,
    )
    updated = 0
    ref_ts = datetime.combine(ref_date, datetime.max.time())
    for skill in (await session.scalars(select(Skill).where(Skill.status == "active"))).all():
        snaps = snap_map.get(skill.id, {})
        if ref_date in snaps:
            skill.install_count = snaps[ref_date]
            skill.last_seen_at = ref_ts
            updated += 1
    await session.flush()
    return {"ref_date": ref_date.isoformat(), "skills_synced": updated}


async def reset_test_db(session: AsyncSession) -> None:
    await session.execute(delete(SkillMetricSnapshot))
    await session.execute(delete(Skill))
    await session.execute(delete(Source).where(Source.category == "simulation"))
    await ensure_sim_platforms(session)


async def simulate_push(
    session: AsyncSession,
    *,
    ref_date: date,
    top_n: int = 10,
    vendors: list[str] | None = None,
) -> dict[str, Any]:
    await prepare_ref_date(session, ref_date)
    return await run_traced_digest(session, digest_date=ref_date, top_n=top_n, vendors=vendors)


def _parse_date(raw: str | date | None) -> date:
    if raw is None:
        return date.today()
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw)[:10])
