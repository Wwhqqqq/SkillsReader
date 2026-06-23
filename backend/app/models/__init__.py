"""
ORM 数据库模型 —— Python 类 ↔ MySQL 表的映射。

SQLAlchemy 2.0 写法说明:
    Mapped[str]           — 字段类型注解，IDE 可提示
    mapped_column(...)    — 列定义（类型、主键、索引等）
    __tablename__         — 对应 MySQL 表名

关系概览:
    Source    — 采集源（来自 sources.yaml + 运行状态）
    Skill     — Skill 主数据（抓取结果入库）
    ScanRun   — 每次扫描一条记录
    ScanEvent — 实时日志（/live 页）
    LlmJob    — LLM 调用任务
    DailyDigest / PushLog — 日报与推送历史
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,       # 复合索引
    Integer,
    String,
    Text,        # 长文本
    func,        # SQL 函数如 now()
)
from sqlalchemy.dialects.mysql import JSON  # MySQL JSON 列类型
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Source(Base):
    """采集源配置表 —— 与 config/sources.yaml 同步，并记录运行状态。"""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 主键，如 "meituan_ai_hub"，与 yaml 里 id 一致

    vendor: Mapped[str] = mapped_column(String(64), nullable=False)
    # 厂商显示名：美团、阿里、腾讯…

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # 源的人类可读名称

    url: Mapped[str] = mapped_column(String(512), default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    # 分类标签，如 domestic / supplemental

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # False 时 Worker 跳过此源

    interval_sec: Mapped[int] = mapped_column(Integer, default=300)
    # 扫描间隔（秒），Worker 用来判断是否该扫

    adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    # 对应 adapters/__init__.py 里 ADAPTER_MAP 的键，如 "meituan"

    priority: Mapped[int] = mapped_column(Integer, default=5)
    # 数字越小越优先扫描

    supplemental: Mapped[bool] = mapped_column(Boolean, default=False)
    # 是否为补充源（海外社区等），排行榜权重可能不同

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 上次成功扫描结束时间

    last_status: Mapped[str] = mapped_column(String(32), default="idle")
    # idle | scanning | ok | error

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_total: Mapped[int] = mapped_column(Integer, default=0)
    # 累计新发现 Skill 数（近似）

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Skill(Base):
    """Skill 主表 —— 所有平台抓取结果的统一存储。"""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # SHA256 指纹，用于去重；由 vendor+source_id+external_id+name 计算

    vendor: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), default="")
    # 源站原始 ID

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 源站原始描述

    llm_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    llm_summary_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # DeepSeek 生成的中文摘要

    detail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tags: Mapped[Any] = mapped_column(JSON, default=list)
    # JSON 数组，如 ["生活服务", "美团"]

    install_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    # 0-100 质量分，低于 40 可能 status=filtered

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # 首次入库时间 → 「今日新增」依据

    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # 最近一次扫描仍出现的时间

    status: Mapped[str] = mapped_column(String(32), default="active")
    # active | filtered | archived

    digest_archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Any] = mapped_column(JSON, default=dict)
    # 原始 API item 等调试信息

    __table_args__ = (
        Index("ix_skills_first_seen", "first_seen_at"),
        Index("ix_skills_vendor_first_seen", "vendor", "first_seen_at"),
    )


class ScanRun(Base):
    """单次扫描运行记录 —— 每次 scan_source 一条。"""

    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    # running | success | error

    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScanEvent(Base):
    """扫描事件日志 —— 写入 DB 并 Redis 广播，供 /live 页展示。"""

    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # scan_start | scan_done | scan_error

    message: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class LlmJob(Base):
    """LLM  enrichment 任务记录 —— 追踪每次 DeepSeek 调用。"""

    __tablename__ = "llm_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | running | done | failed

    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    result: Mapped[str | None] = mapped_column(String(512), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DailyDigest(Base):
    """每日日报 —— 今日榜+总榜内容，用于如流推送。"""

    __tablename__ = "daily_digests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    digest_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    today_skill_ids: Mapped[Any] = mapped_column(JSON, default=list)
    leaderboard_skill_ids: Mapped[Any] = mapped_column(JSON, default=list)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    push_status: Mapped[str] = mapped_column(String(32), default="pending")
    push_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    selection_meta: Mapped[Any] = mapped_column(JSON, default=dict)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SkillMetricSnapshot(Base):
    """Skill 指标快照 —— 用于计算 8h×N 窗口增长率。"""

    __tablename__ = "skill_metric_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    metric_value: Mapped[int] = mapped_column(Integer, default=0)
    metric_kind: Mapped[str] = mapped_column(String(32), default="install")
    source_id: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (
        Index("ix_skill_metric_snapshots_skill_recorded", "skill_id", "recorded_at"),
    )


class DigestPickRun(Base):
    """每日精选 Top N 生成记录 —— 含完整 picks JSON 与推送状态。"""

    __tablename__ = "digest_pick_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    digest_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    top_n: Mapped[int] = mapped_column(Integer, default=10)
    picks: Mapped[Any] = mapped_column(JSON, default=list)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_version: Mapped[str] = mapped_column(String(32), default="1")
    selection_meta: Mapped[Any] = mapped_column(JSON, default=dict)
    push_status: Mapped[str] = mapped_column(String(32), default="pending")
    push_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PushLog(Base):
    """推送历史 —— 每次如流发送一条记录。"""

    __tablename__ = "push_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    push_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(64), default="")
    vendors: Mapped[Any] = mapped_column(JSON, default=list)
    skill_count: Mapped[int] = mapped_column(Integer, default=0)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    response: Mapped[Any] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
