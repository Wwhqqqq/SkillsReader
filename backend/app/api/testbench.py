"""测试平台 API —— /api/testbench/*，使用独立测试库。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.test_database import get_test_db, init_test_db
from app.services.testbench import service as tb

router = APIRouter(prefix="/api/testbench", tags=["testbench"])


class SkillCreate(BaseModel):
    source_id: str
    name: str
    external_id: str = ""
    raw_description: str = ""
    detail_url: str = ""
    tags: list[str] = Field(default_factory=list)
    install_count: int = 0
    quality_score: int = 60
    first_seen_date: str | None = None
    official: bool = False
    metadata_json: dict = Field(default_factory=dict)


class SkillUpdate(BaseModel):
    name: str | None = None
    external_id: str | None = None
    raw_description: str | None = None
    detail_url: str | None = None
    tags: list[str] | None = None
    install_count: int | None = None
    quality_score: int | None = None
    first_seen_date: str | None = None
    last_seen_date: str | None = None
    metadata_json: dict | None = None


class SnapshotItem(BaseModel):
    skill_id: int
    metric_value: int


class SnapshotBatch(BaseModel):
    snapshot_date: str
    items: list[SnapshotItem]


class TimelineGenerate(BaseModel):
    skill_id: int
    start_date: str
    values: list[int]


class SimulateRequest(BaseModel):
    digest_date: str
    top_n: int = 10
    vendors: list[str] = Field(default_factory=list)


@router.post("/init")
async def init_db(session: AsyncSession = Depends(get_test_db)):
    await init_test_db()
    platforms = await tb.ensure_sim_platforms(session)
    return {"ok": True, "platforms": len(platforms)}


@router.post("/reset")
async def reset_db(session: AsyncSession = Depends(get_test_db)):
    await tb.reset_test_db(session)
    return {"ok": True}


@router.get("/platforms")
async def platforms(session: AsyncSession = Depends(get_test_db)):
    return await tb.list_platforms(session)


@router.get("/skills")
async def list_skills(page: int = 1, page_size: int = 100, session: AsyncSession = Depends(get_test_db)):
    return await tb.list_skills(session, page=page, page_size=page_size)


@router.post("/skills")
async def create_skill(body: SkillCreate, session: AsyncSession = Depends(get_test_db)):
    try:
        return await tb.create_skill(session, body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/skills/{skill_id}")
async def update_skill(skill_id: int, body: SkillUpdate, session: AsyncSession = Depends(get_test_db)):
    try:
        return await tb.update_skill(session, skill_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: int, session: AsyncSession = Depends(get_test_db)):
    await tb.delete_skill(session, skill_id)
    return {"ok": True}


@router.get("/snapshots/dates")
async def snapshot_dates(session: AsyncSession = Depends(get_test_db)):
    return await tb.list_snapshot_dates(session)


@router.get("/snapshots")
async def snapshots(snapshot_date: str, session: AsyncSession = Depends(get_test_db)):
    return await tb.list_snapshots_for_date(session, date.fromisoformat(snapshot_date))


@router.put("/snapshots")
async def upsert_snapshots(body: SnapshotBatch, session: AsyncSession = Depends(get_test_db)):
    n = await tb.upsert_snapshots_batch(session, date.fromisoformat(body.snapshot_date), [i.model_dump() for i in body.items])
    return {"updated": n}


@router.post("/snapshots/timeline")
async def generate_timeline(body: TimelineGenerate, session: AsyncSession = Depends(get_test_db)):
    try:
        n = await tb.generate_timeline(session, body.skill_id, date.fromisoformat(body.start_date), body.values)
        return {"days_written": n}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/prepare-date")
async def prepare_date(snapshot_date: str, session: AsyncSession = Depends(get_test_db)):
    return await tb.prepare_ref_date(session, date.fromisoformat(snapshot_date))


@router.post("/simulate")
async def simulate(body: SimulateRequest, session: AsyncSession = Depends(get_test_db)):
    vendors = body.vendors or None
    return await tb.simulate_push(
        session,
        ref_date=date.fromisoformat(body.digest_date),
        top_n=body.top_n,
        vendors=vendors,
    )
