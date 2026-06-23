"""每日精选数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.models import Skill


@dataclass
class DigestPickItem:
    rank: int
    slot: str
    pool: str
    skill: Skill
    score: float
    score_breakdown: dict[str, float]
    growth: dict[str, Any]
    recommend_reason: str
    is_official: bool
    is_new: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "slot": self.slot,
            "pool": self.pool,
            "skill_id": self.skill.id,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "growth": self.growth,
            "recommend_reason": self.recommend_reason,
            "is_official": self.is_official,
            "is_new": self.is_new,
        }


@dataclass
class DigestResult:
    digest_date: date
    top_n: int
    items: list[DigestPickItem] = field(default_factory=list)
    content_md: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    config_version: str = "1"

    def skill_ids(self) -> list[int]:
        return [item.skill.id for item in self.items]
