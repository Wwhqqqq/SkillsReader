"""
国内社区 Adapter 的平台相关性过滤 —— 避免 GitHub 整仓扫描污染 vendor 标签。
"""

from __future__ import annotations

from typing import Any

import re

from app.adapters.base import RawSkillRecord

ZHIHU_KEYWORDS = re.compile(r"zhihu|知乎", re.I)
XHS_KEYWORDS = re.compile(
    r"xhs|xiaohongshu|redbook|redskill|rednote|小红书|红书|薯|笔记发布|笔记运营",
    re.I,
)
ZHIHU_DEDICATED_REPO = re.compile(r"zhihu|知乎", re.I)
XHS_DEDICATED_REPO = re.compile(r"xiaohongshu|xhs|redbook|redskill|rednote", re.I)
BILI_KEYWORDS = re.compile(r"bilibili|bili-|哔哩|b站|B站|bvid|BV号", re.I)
BILI_DEDICATED_REPO = re.compile(r"bilibili|bili-|哔哩|b站|bili_", re.I)
KUAISHOU_KEYWORDS = re.compile(r"kuaishou|快手|kwai|v\.kuaishou|photo_id|maxhub-kuaishou", re.I)
KUAISHOU_DEDICATED_REPO = re.compile(r"kuaishou|快手|kwai|maxhub-kuaishou", re.I)
DIDI_KEYWORDS = re.compile(
    r"didi|滴滴|didichuxing|didi-ride|DIDI_MCP|mcp\.didichuxing|taxi_estimate",
    re.I,
)
DIDI_DEDICATED_REPO = re.compile(r"^didi/|didichuxing|didi-ride", re.I)
PDD_KEYWORDS = re.compile(
    r"pinduoduo|拼多多|pdd-|pdd_|open\.pinduoduo|多多进宝|mcp-cn-pinduoduo|pdd\.ddk",
    re.I,
)
PDD_DEDICATED_REPO = re.compile(r"pinduoduo|拼多多|mcp-cn-pdd|mcp-cn-pinduoduo|pdd-coupon|pdd_", re.I)
CTRIP_KEYWORDS = re.compile(
    r"ctrip|携程|wendao|问道|tripgenie|trips-ai|"
    r"flights\.ctrip|vacations\.ctrip|trip\.com|"
    r"wendao-skill-prod|tripgenie-openclaw-prod|"
    r"WENDAO_API_KEY|TRIPGENIE_API_KEY|ctrip-flight|ctrip-hotel|ctrip-wendao",
    re.I,
)
CTRIP_DEDICATED_REPO = re.compile(
    r"ctrip|trips-ai|wendao|ctrip-skill|ctrip-wendao|ctrip-flight|ctrip-hotel",
    re.I,
)
CTRIP_NOISE = re.compile(
    r"tripwire|roundtrip|trip-compact|trip-advisor|tripseek|triply|"
    r"business\s+trip|road\s+trip|round\s+trip",
    re.I,
)
DEWU_KEYWORDS = re.compile(
    r"dewu|poizon|得物|"
    r"open\.dewu|open\.poizon|"
    r"得物开放平台|"
    r"dewu-seeding|dw-skills|"
    r"poizon-l10n|"
    r"app\.poizon\.com|cdn\.poizon\.com|"
    r"global\.dewu|"
    r"specfusion.*dewu|source=dewu",
    re.I,
)
DEWU_DEDICATED_REPO = re.compile(
    r"dewu|poizon|dw-skills|specfusion|skill_l10n|clawde-skills",
    re.I,
)
POIZON_NOISE = re.compile(
    r"poison(?:ed|ing|-face|-mask|-trace|-fail|-audit|-publisher|-pipeline|-triage|-l10n)?|"
    r"responder-poison|cache-poisoning|network-poisoning|"
    r"memory-poison|poisoned-skill|poisoned-pipeline|"
    r"t1677-poisoned|poison-face|poison-mask",
    re.I,
)
DEWU_CJK_NOISE = re.compile(
    r"配得上|qianshao-deserve|deserve|"
    r"得た|得る|得た知|sync-knowledge|knowledge-placement|"
    r"prove-geometric|得几何|"
    r"东得多|wu-jundong|"
    r"万得|wind-find|wind-alice|wind-mcp|"
    r"gaokao-adi",
    re.I,
)
DEWU_OPEN_NOISE = re.compile(
    r"open-pr|open-source|open-gstack|open-notebook|open-design|"
    r"open-dynamic-workflows|open-code-review|open-redirect|open-sets",
    re.I,
)
DW_SKILLS_NOISE = re.compile(
    r"dataworks|dw-skill-eval|dw-0[1-5]-|"
    r"salesforce|dw\.system|6502-merlin|"
    r"datawizard|context-engineering-workflows",
    re.I,
)
TENCENT_KEYWORDS = re.compile(
    r"wechat|weixin|微信|miniprogram|小程序|wx\.cloud|wx\.modelContext|"
    r"wecom|wework|企业微信|qyapi\.weixin|openclaw-weixin|tencent-weixin|"
    r"tencentcloud|cloudbase|云开发|混元|hunyuan|TencentCloudBase|WecomTeam|"
    r"mp-skills|agent\.skills|docs\.qq\.com|tencent-docs|"
    r"tencent-cos|tencent-meeting|qqmap|@tencent-weixin",
    re.I,
)
TENCENT_DEDICATED_REPO = re.compile(
    r"TencentCloudBase|WecomTeam|Tencent/openclaw-weixin|wechat-miniprogram/ai-mode|"
    r"wechat-miniprogram|Tencent/wechat",
    re.I,
)
TENCENT_QQ_USERNAME_NOISE = re.compile(
    r"^qq[0-9]{3,}|447662-qq|qq5855144|github\.com/qq[0-9]",
    re.I,
)
TENCENT_GENERIC_PUBLISHER = re.compile(
    r"wechat-publisher|wechatsync|zhihu-to-wechat|ppt2wechat",
    re.I,
)
TENCENT_INTERVIEW_NOISE = re.compile(
    r"阿里.{0,6}腾讯.{0,6}美团|腾讯.{0,6}阿里.{0,6}字节|"
    r"面试.{0,8}腾讯|八股|coding-interview",
    re.I,
)

ZHIHU_REPO_BLOCKLIST = frozenset(
    {
        "nexu-io/html-anything",
        "yezhengmao1/navi",
    }
)

XHS_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
        "David-Li0406/meta-skill-evloving",
        "yuanjian068yuan/opc-comment-lead-radar",
        "Baileybasic68/opencli-skill",
        "ponyodong2026/ponyo-cover-anchor-system",
    }
)

BILI_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
    }
)

KUAISHOU_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
        "yangbuyiya/yby6-video-parser-skill",
    }
)

DIDI_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
    }
)

PDD_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
        "yangbuyiya/yby6-video-parser-skill",
    }
)

CTRIP_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
        "ShoumikSaha/agent-skill-security",
    }
)

DEWU_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
        "PurpleAILAB/Decepticon",
        "wgpsec/AboutSecurity",
        "Hmbown/mmbnchips",
    }
)

TENCENT_REPO_BLOCKLIST = frozenset(
    {
        "lxyeternal/MalSkillBench",
        "ShoumikSaha/agent-skill-security",
    }
)


def repo_from_record(rec: RawSkillRecord) -> str:
    meta = rec.metadata or {}
    repo = meta.get("repo") or ""
    if repo:
        return repo
    external_id = rec.external_id or ""
    if external_id.startswith(("redskill:", "github-case:")):
        return ""
    if ":" in external_id:
        return external_id.split(":", 1)[0]
    return ""


def skill_text_blob(rec: RawSkillRecord) -> str:
    meta = rec.metadata or {}
    parts = [
        rec.name or "",
        rec.external_id or "",
        rec.raw_description or "",
        meta.get("path") or "",
        meta.get("repo") or "",
        repo_from_record(rec),
    ]
    return " ".join(parts)


def is_dedicated_zhihu_repo(repo: str) -> bool:
    return bool(repo and ZHIHU_DEDICATED_REPO.search(repo))


def is_dedicated_xhs_repo(repo: str) -> bool:
    return bool(repo and XHS_DEDICATED_REPO.search(repo))


def is_dedicated_bilibili_repo(repo: str) -> bool:
    return bool(repo and BILI_DEDICATED_REPO.search(repo))


def is_dedicated_kuaishou_repo(repo: str) -> bool:
    return bool(repo and KUAISHOU_DEDICATED_REPO.search(repo))


def is_dedicated_didi_repo(repo: str) -> bool:
    return bool(repo and DIDI_DEDICATED_REPO.search(repo))


def is_dedicated_pinduoduo_repo(repo: str) -> bool:
    return bool(repo and PDD_DEDICATED_REPO.search(repo))


def is_dedicated_ctrip_repo(repo: str) -> bool:
    return bool(repo and CTRIP_DEDICATED_REPO.search(repo))


def is_dedicated_dewu_repo(repo: str) -> bool:
    return bool(repo and DEWU_DEDICATED_REPO.search(repo))


def is_dedicated_tencent_repo(repo: str) -> bool:
    return bool(repo and TENCENT_DEDICATED_REPO.search(repo))


# 知乎相关性过滤
def is_zhihu_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    if meta.get("official"):
        return True
    if (rec.external_id or "").startswith("zhihu-"):
        return True

    repo = repo_from_record(rec)
    if repo in ZHIHU_REPO_BLOCKLIST:
        return bool(ZHIHU_KEYWORDS.search(skill_text_blob(rec)))
    if is_dedicated_zhihu_repo(repo):
        return True
    return bool(ZHIHU_KEYWORDS.search(skill_text_blob(rec)))


def is_xhs_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official") or meta.get("redskill") or external_id.startswith("redskill:"):
        return True
    if external_id.startswith("github-case:"):
        return True

    repo = repo_from_record(rec)
    if repo in XHS_REPO_BLOCKLIST:
        return bool(XHS_KEYWORDS.search(skill_text_blob(rec)))
    if is_dedicated_xhs_repo(repo):
        return True
    return bool(XHS_KEYWORDS.search(skill_text_blob(rec)))


def is_bilibili_relevant(rec: RawSkillRecord) -> bool:
    from app.services.scan.skill_gate import is_bilibili_portal_anchor

    if is_bilibili_portal_anchor(rec):
        return False

    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official"):
        return True
    if external_id.startswith(("clawhub:", "skillsmp:")):
        return True

    repo = repo_from_record(rec)
    if repo in BILI_REPO_BLOCKLIST:
        return bool(BILI_KEYWORDS.search(skill_text_blob(rec)))
    if is_dedicated_bilibili_repo(repo):
        return True
    return bool(BILI_KEYWORDS.search(skill_text_blob(rec)))


def is_kuaishou_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official"):
        return True
    if external_id.startswith(("clawhub:", "skillsmp:")):
        return True

    repo = repo_from_record(rec)
    if repo in KUAISHOU_REPO_BLOCKLIST:
        return bool(KUAISHOU_KEYWORDS.search(skill_text_blob(rec)))
    if is_dedicated_kuaishou_repo(repo):
        return True
    return bool(KUAISHOU_KEYWORDS.search(skill_text_blob(rec)))


def is_didi_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official"):
        return True
    if external_id.startswith(("clawhub:", "skillsmp:")):
        return True

    repo = repo_from_record(rec)
    if repo in DIDI_REPO_BLOCKLIST:
        return bool(DIDI_KEYWORDS.search(skill_text_blob(rec)))
    if is_dedicated_didi_repo(repo):
        return True
    return bool(DIDI_KEYWORDS.search(skill_text_blob(rec)))


def is_pinduoduo_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official"):
        return True
    if external_id.startswith(("clawhub:", "skillsmp:")):
        return True

    repo = repo_from_record(rec)
    if repo in PDD_REPO_BLOCKLIST:
        return bool(PDD_KEYWORDS.search(skill_text_blob(rec)))
    if is_dedicated_pinduoduo_repo(repo):
        return True
    return bool(PDD_KEYWORDS.search(skill_text_blob(rec)))


def is_ctrip_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official"):
        return True
    if external_id.startswith(("clawhub:", "skillsmp:")):
        return True

    blob = skill_text_blob(rec)
    if CTRIP_NOISE.search(blob) and not CTRIP_KEYWORDS.search(blob):
        return False

    repo = repo_from_record(rec)
    if repo in CTRIP_REPO_BLOCKLIST:
        return bool(CTRIP_KEYWORDS.search(blob))
    if is_dedicated_ctrip_repo(repo):
        return True
    return bool(CTRIP_KEYWORDS.search(blob))


def _dewu_noise_without_signal(blob: str) -> bool:
    if DEWU_CJK_NOISE.search(blob) and not DEWU_KEYWORDS.search(blob):
        return True
    if DEWU_OPEN_NOISE.search(blob) and not DEWU_KEYWORDS.search(blob):
        return True
    if DW_SKILLS_NOISE.search(blob) and not DEWU_KEYWORDS.search(blob):
        return True
    if POIZON_NOISE.search(blob) and not DEWU_KEYWORDS.search(blob):
        return True
    return False


def is_dewu_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official"):
        return True
    if external_id.startswith(("clawhub:", "skillsmp:")):
        return True

    blob = skill_text_blob(rec)
    if _dewu_noise_without_signal(blob):
        return False

    repo = repo_from_record(rec)
    if repo in DEWU_REPO_BLOCKLIST:
        return bool(DEWU_KEYWORDS.search(blob))
    if is_dedicated_dewu_repo(repo):
        return True
    return bool(DEWU_KEYWORDS.search(blob))


def _tencent_noise_without_signal(blob: str, repo: str = "") -> bool:
    if TENCENT_QQ_USERNAME_NOISE.search(blob) and not TENCENT_KEYWORDS.search(blob):
        return True
    if TENCENT_INTERVIEW_NOISE.search(blob) and not TENCENT_KEYWORDS.search(blob):
        return True
    if TENCENT_GENERIC_PUBLISHER.search(blob) and not is_dedicated_tencent_repo(repo):
        return True
    if DEWU_OPEN_NOISE.search(blob) and not TENCENT_KEYWORDS.search(blob):
        return True
    return False


def is_tencent_relevant(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    external_id = rec.external_id or ""
    if meta.get("official"):
        return True
    if external_id.startswith(("clawhub:", "skillsmp:")):
        return True

    blob = skill_text_blob(rec)
    repo = repo_from_record(rec)
    if _tencent_noise_without_signal(blob, repo):
        return False

    if repo in TENCENT_REPO_BLOCKLIST:
        return bool(TENCENT_KEYWORDS.search(blob))
    if is_dedicated_tencent_repo(repo):
        return True
    return bool(TENCENT_KEYWORDS.search(blob))


VENDOR_RELEVANCE_CHECKERS = {
    "知乎": is_zhihu_relevant,
    "小红书": is_xhs_relevant,
    "哔哩哔哩": is_bilibili_relevant,
    "快手": is_kuaishou_relevant,
    "滴滴": is_didi_relevant,
    "拼多多": is_pinduoduo_relevant,
    "携程": is_ctrip_relevant,
    "得物": is_dewu_relevant,
    "腾讯": is_tencent_relevant,
}


def skill_as_record(skill: Any) -> RawSkillRecord:
    """ORM Skill → RawSkillRecord，供 digest 候选池 platform_filters 复用。"""
    meta = skill.metadata_json if isinstance(getattr(skill, "metadata_json", None), dict) else {}
    return RawSkillRecord(
        external_id=str(getattr(skill, "external_id", "") or ""),
        name=str(getattr(skill, "name", "") or ""),
        vendor=str(getattr(skill, "vendor", "") or ""),
        source_id=str(getattr(skill, "source_id", "") or ""),
        raw_description=str(getattr(skill, "raw_description", "") or ""),
        detail_url=str(getattr(skill, "detail_url", "") or ""),
        tags=list(getattr(skill, "tags", None) or []),
        install_count=int(getattr(skill, "install_count", 0) or 0),
        metadata=dict(meta),
    )


def is_platform_relevant(rec: RawSkillRecord) -> bool:
    """文档 §4.4 Step1：platform_filters 硬过滤。"""
    checker = VENDOR_RELEVANCE_CHECKERS.get(rec.vendor)
    if checker is None:
        return True
    return checker(rec)
