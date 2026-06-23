"""Tests for skill export."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.export.skill_export import (
    RECENT_EXPORT_HOURS,
    build_bundle_filename,
    build_export_filename,
    export_columns_for,
    rows_to_csv,
    skill_in_recent_hours_window,
    skill_to_row,
)


def _skill(**kwargs):
    defaults = {
        "name": "demo",
        "vendor": "美团",
        "llm_summary": "摘要",
        "raw_description": "",
        "detail_url": "",
        "tags": [],
        "metadata_json": {},
        "first_seen_at": None,
        "publish_date": None,
        "install_count": 0,
        "quality_score": 0,
        "source_id": "meituan_ai_hub",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_skill_to_row():
    skill = _skill(
        raw_description="原始",
        detail_url="https://example.com",
        tags=["美团", "生活服务"],
        metadata_json={"categoryName": "餐饮", "catalog": "official_api"},
        install_count=10,
        quality_score=80,
        first_seen_at=datetime(2025, 6, 17, 8, 53, 0),
    )
    row = skill_to_row(skill, 1)
    assert row["name"] == "demo"
    assert row["category"] == "餐饮"
    assert row["publisher_type"] == "官方发布"
    assert row["data_source"] == "美团AI Hub API"
    assert row["first_seen_at"] == "2025-06-17 16:53:00"


def test_export_columns_domestic_no_metrics():
    cols = export_columns_for([_skill()])
    labels = [label for label, _ in cols]
    assert "首次发现(北京)" in labels
    assert "安装量" not in labels


def test_build_export_filename_last_official_scan():
    name = build_export_filename(
        fmt="xlsx", vendor=None, today_only=False, last_official_scan=True
    )
    assert "最近官方扫描新增" in name


def test_skill_in_recent_hours_window():
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    now_sh = datetime(2025, 6, 17, 16, 53, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    recent_utc = (now_sh - timedelta(hours=2)).astimezone(timezone.utc).replace(tzinfo=None)
    old_utc = (now_sh - timedelta(hours=25)).astimezone(timezone.utc).replace(tzinfo=None)

    assert skill_in_recent_hours_window(
        SimpleNamespace(first_seen_at=recent_utc),
        hours=RECENT_EXPORT_HOURS,
        now_shanghai=now_sh,
    )
    assert not skill_in_recent_hours_window(
        SimpleNamespace(first_seen_at=old_utc),
        hours=RECENT_EXPORT_HOURS,
        now_shanghai=now_sh,
    )


def test_build_bundle_filename_recent():
    name = build_bundle_filename(today_only=False, scope="domestic", recent_only=True)
    assert f"近{RECENT_EXPORT_HOURS}小时新发现" in name
    assert name.endswith(".zip")


def test_rows_to_csv_has_bom():
    data = rows_to_csv([_skill()])
    assert data.startswith("\ufeff".encode())
