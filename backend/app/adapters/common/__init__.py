"""Adapter 共用工具：GitHub、SkillsMP、ClawHub、平台过滤。"""

from app.adapters.common.clawhub import CLAWHUB_SEARCH_URL, record_from_clawhub
from app.adapters.common.platform_filters import (
    is_bilibili_relevant,
    is_ctrip_relevant,
    is_dewu_relevant,
    is_tencent_relevant,
    is_didi_relevant,
    is_kuaishou_relevant,
    is_pinduoduo_relevant,
    is_xhs_relevant,
    is_zhihu_relevant,
)
from app.adapters.common.skillsmp_catalog import fetch_skillsmp_for_vendor

__all__ = [
    "CLAWHUB_SEARCH_URL",
    "fetch_skillsmp_for_vendor",
    "is_bilibili_relevant",
    "is_ctrip_relevant",
    "is_dewu_relevant",
    "is_tencent_relevant",
    "is_didi_relevant",
    "is_kuaishou_relevant",
    "is_pinduoduo_relevant",
    "is_xhs_relevant",
    "is_zhihu_relevant",
    "record_from_clawhub",
]
