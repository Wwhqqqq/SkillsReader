"""
Pydantic 数据模型（Schema）—— API 请求/响应的数据结构与校验。

与 models/（SQLAlchemy ORM）的区别:
    ORM     — 对应数据库表，读写 MySQL
    Schema  — 对应 JSON API，定义返回给前端的字段形状

常用配置:
    ConfigDict(from_attributes=True)  — 允许从 ORM 对象 model_validate(orm_obj)
    Field(default_factory=list)       — 可变默认值
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceOut(BaseModel):
    """GET /api/sources 返回的单个采集源。"""

    model_config = ConfigDict(from_attributes=True)  # 可从 Source ORM 转换

    id: str
    vendor: str
    name: str
    url: str
    category: str
    enabled: bool              # 是否参与 Worker 扫描
    interval_sec: int          # 扫描间隔秒
    adapter: str               # ADAPTER_MAP 键名
    priority: int
    supplemental: bool         # 是否补充源
    last_run_at: datetime | None
    last_status: str           # idle / scanning / ok / error
    last_error: str | None
    items_total: int


class SourceUpdate(BaseModel):
    """PATCH /api/sources/{id} 请求体；None 表示不修改该字段。"""

    enabled: bool | None = None
    interval_sec: int | None = None


class SkillOut(BaseModel):
    """Skill API 响应字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fingerprint: str
    vendor: str
    source_id: str
    external_id: str
    name: str
    raw_description: str | None
    llm_summary: str | None
    llm_summary_at: datetime | None
    detail_url: str | None
    tags: list[str] = Field(default_factory=list)
    install_count: int
    quality_score: int
    first_seen_at: datetime
    publish_date: date | None
    last_seen_at: datetime
    status: str


class SkillListResponse(BaseModel):
    """分页 Skill 列表包装。"""

    items: list[SkillOut]
    total: int       # 总条数
    page: int
    page_size: int


class ScanEventOut(BaseModel):
    """扫描事件，/live 页与 GET /api/scan/events 使用。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: str | None
    level: str           # info | success | error
    event_type: str      # scan_start | scan_done | scan_error
    message: str
    payload: dict[str, Any]
    created_at: datetime


class OverviewStats(BaseModel):
    """Dashboard 总览统计。"""

    total_skills: int
    today_new: int
    active_sources: int
    total_sources: int
    scanning_sources: int
    last_push_at: datetime | None
    scan_enabled: bool


class VendorStat(BaseModel):
    vendor: str
    total: int
    today_new: int
    categories: dict[str, int] = Field(default_factory=dict)


class VendorStatsResponse(BaseModel):
    vendors: list[VendorStat]
    meituan_total: int = 0


class RankingItem(BaseModel):
    rank: int
    skill: SkillOut
    score: float
    is_new: bool = False
    is_official: bool = False  # 是否大厂官方 Skill


class RankingResponse(BaseModel):
    items: list[RankingItem]
    meta: dict[str, Any] = Field(default_factory=dict)


class GrowthMetricsOut(BaseModel):
    metric_value: int = 0
    metric_kind: str = "install"
    value_1d_ago: int | None = None
    value_3d_ago: int | None = None
    value_7d_ago: int | None = None
    growth_1d_pct: float = 0.0
    growth_3d_pct: float = 0.0
    growth_7d_pct: float = 0.0
    growth_score: float = 0.0


class ScoreBreakdownOut(BaseModel):
    trend: float = 0.0
    official: float = 0.0
    quality: float = 0.0
    diversity: float = 0.0
    total: float = 0.0


class DigestPickItemOut(BaseModel):
    rank: int
    slot: str
    pool: str
    skill: SkillOut
    score: float
    score_breakdown: ScoreBreakdownOut
    growth: GrowthMetricsOut
    recommend_reason: str = ""
    is_official: bool = False
    is_new: bool = False


class PushPreviewRequest(BaseModel):
    top_n: int = 10
    date: str | None = None
    vendors: list[str] = Field(default_factory=list)
    channel: str = "digest"  # digest | official_new


class PushPreviewResponse(BaseModel):
    content_md: str
    char_count: int
    skill_count: int
    items: list[DigestPickItemOut]
    needs_split: bool = False
    config_version: str = "1"
    meta: dict[str, Any] = Field(default_factory=dict)
    digest_date: date | None = None
    top_n: int = 10


class PushSendRequest(BaseModel):
    top_n: int = 10
    date: str | None = None
    vendors: list[str] = Field(default_factory=list)
    channel: str = "digest"  # digest | official_new
    dry_run: bool = False
    target: str = "dm"  # dm | group


class PushSendResponse(BaseModel):
    success: bool
    message: str
    push_log_id: int | None = None
    digest_run_id: int | None = None
    content_md: str | None = None


class ScanTriggerRequest(BaseModel):
    """POST /api/scan/trigger  body。"""

    source_ids: list[str] = Field(default_factory=list)  # 空=扫全部 enabled
    vendors: list[str] = Field(default_factory=list)


class OfficialPortalOut(BaseModel):
    """GET /api/scan/official/portals"""

    vendor: str
    name: str
    url: str
    source_id: str


class OfficialScanStatusOut(BaseModel):
    """GET /api/scan/official/status"""

    status: str = "idle"
    started_at: str | None = None
    finished_at: str | None = None
    sources_total: int = 0
    sources_ok: int = 0
    sources_error: int = 0
    new_count: int = 0
    new_official_count: int = 0
    vendor_new_counts: dict[str, int] = Field(default_factory=dict)
    push_status: str | None = None
    error_message: str | None = None


class AdapterProbeRequest(BaseModel):
    source_id: str


class AdapterProbeResponse(BaseModel):
    source_id: str
    success: bool
    count: int
    duration_ms: int
    sample: list[dict[str, Any]]
    error: str | None = None


class GlobalScanToggle(BaseModel):
    enabled: bool


class AutoPushSettings(BaseModel):
    mode: str = "dm"  # off | dm | group


class AutoPushSettingsResponse(BaseModel):
    mode: str
    labels: dict[str, str] = Field(
        default_factory=lambda: {
            "off": "关闭自动推送",
            "dm": "自动推送 · 单聊",
            "group": "自动推送 · 群聊",
        }
    )


class DigestPreviewRequest(BaseModel):
    date: str | None = None
    top_n: int = 10
    vendors: list[str] = Field(default_factory=list)
    channel: str = "digest"  # digest | official_new


class DigestPreviewResponse(BaseModel):
    digest_date: date
    top_n: int
    items: list[DigestPickItemOut]
    content_md: str
    char_count: int
    config_version: str
    meta: dict[str, Any] = Field(default_factory=dict)
    needs_split: bool = False


class DigestGenerateResponse(BaseModel):
    run_id: int
    digest_date: date
    top_n: int
    skill_count: int
    config_version: str


class DigestSendRequest(BaseModel):
    date: str | None = None
    top_n: int = 10
    vendors: list[str] = Field(default_factory=list)
    channel: str = "digest"  # digest | official_new
    dry_run: bool = False
    target: str = "dm"


class DigestSendResponse(BaseModel):
    success: bool
    message: str
    push_log_id: int | None = None
    digest_run_id: int | None = None
    content_md: str | None = None


class DigestScheduleSettings(BaseModel):
    enabled: bool = True
    times: list[str] = Field(default_factory=lambda: ["09:00", "18:00"])
    timezone: str = "Asia/Shanghai"
    target: str = "dm"
    top_n: int = 10
    official_new_enabled: bool = False
    official_new_time: str = "08:30"
    official_new_top_n: int = 10


class DigestConfigResponse(BaseModel):
    version: str
    config: dict[str, Any]
    schedule: DigestScheduleSettings
