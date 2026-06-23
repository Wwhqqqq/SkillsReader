"""扫描与入库：adapter 抓取 → 规范化 → 写入数据库。"""

from app.services.scan.events import emit_event
from app.services.scan.normalizer import (
    compute_fingerprint,
    compute_quality_score,
    normalize_name,
)
from app.services.scan.pipeline import ingest_records
from app.services.scan.scanner import scan_source
from app.services.scan.source_sync import sync_sources_from_yaml

__all__ = [
    "compute_fingerprint",
    "compute_quality_score",
    "emit_event",
    "ingest_records",
    "normalize_name",
    "scan_source",
    "sync_sources_from_yaml",
]
