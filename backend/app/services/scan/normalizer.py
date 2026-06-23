"""
数据标准化工具 —— 指纹去重、日期解析、质量打分。

fingerprint 算法:
    SHA256(vendor|source_id|external_id|normalize_name(name))
    同一 Skill 多次抓取 → 相同 fingerprint → pipeline 走 UPDATE 而非重复 INSERT
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime

from app.adapters.base import RawSkillRecord
from app.services.digest.config_loader import domestic_vendors

# 描述中额外识别的大厂英文名/别名
_BIG_COMPANY_ALIASES = (
    "meituan",
    "alibaba",
    "aliyun",
    "tencent",
    "wechat",
    "bytedance",
    "volcengine",
    "douyin",
    "tiktok",
    "zhihu",
    "xiaohongshu",
    "xhs",
    "redbook",
    "bilibili",
    "b站",
    "kuaishou",
    "didi",
    "pinduoduo",
    "pdd",
    "ctrip",
    "dewu",
    "poizon",
    "baidu",
)


def normalize_name(name: str) -> str:
    """
    名称标准化：去首尾空白、合并连续空格、转小写。
    避免 "外卖助手" 与 "  外卖助手  " 被当成两条。
    """
    return re.sub(r"\s+", " ", name.strip().lower())


def compute_fingerprint(vendor: str, source_id: str, external_id: str, name: str) -> str:
    """
    计算 Skill 唯一指纹（64 位十六进制 SHA256）。

    hashlib.sha256(s.encode()).hexdigest():
        把字符串 UTF-8 编码后哈希，hexdigest() 得 hex 字符串
    """
    raw = f"{vendor}|{source_id}|{external_id}|{normalize_name(name)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_publish_date(value: str | None) -> date | None:
    """
    把字符串日期转为 date 对象。
    str | None 表示参数可以是 str 或 None（Python 3.10+ 联合类型写法）。
    """
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue  # 格式不匹配试下一个
    return None


def _mentions_big_company(text: str) -> bool:
    blob = text.lower()
    for name in domestic_vendors():
        if name in text or name.lower() in blob:
            return True
    return any(alias in blob for alias in _BIG_COMPANY_ALIASES)


def compute_quality_score(record: RawSkillRecord) -> int:
    """
    启发式质量分 0-100，入库时写入 Skill.quality_score。

    - 基础分 30
    - 有描述且 >20 字 +5；有描述 ≤20 字 +2
    - 描述含大厂名 +15
    - 大厂 vendor +30
    - 有 detail_url +10；有 tags +5
    - install_count 贡献 min(20, install**0.4)
    """
    score = 30
    desc = (record.raw_description or "").strip()
    if desc:
        score += 5 if len(desc) > 20 else 2
        if _mentions_big_company(desc):
            score += 15
    if record.detail_url:
        score += 10
    if record.tags:
        score += 5
    if record.install_count > 0:
        score += min(20, int(record.install_count**0.4))
    if record.vendor in domestic_vendors():
        score += 30
    return min(100, score)
