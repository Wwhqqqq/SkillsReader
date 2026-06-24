"""
社区 Skill 厂商定向审核 —— DeepSeek 两阶段判定 Skill 是否真正面向某公司产品/平台/API。

SkillsMP / ClawHub / GitHub 社区检索仅作候选发现；入库前须通过本模块审核。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.adapters.base import RawSkillRecord
from app.core.config import get_settings

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_FILE = CACHE_DIR / "vendor_relevance_cache.json"

# 升级 prompt 时递增，旧缓存自动失效
PROMPT_VERSION = "2"
CONFIDENCE_MIN = 0.82

OFFICIAL_CATALOGS = frozenset({"official", "official_api", "official_github"})

VENDOR_REPO_PATTERN: dict[str, re.Pattern[str]] = {
    "美团": re.compile(r"meituan|美团|dianping|大众点评", re.I),
    "阿里": re.compile(r"aliyun|阿里云|dashscope|通义|百炼", re.I),
    "字节": re.compile(r"volcengine|coze|扣子|bytedance|字节|火山", re.I),
    "知乎": re.compile(r"zhihu|知乎", re.I),
    "小红书": re.compile(
        r"xhs|xiaohongshu|redbook|redskill|rednote|小红书|红书", re.I
    ),
    "哔哩哔哩": re.compile(r"bilibili|bili-|哔哩|b站|B站|bvid", re.I),
    "快手": re.compile(r"kuaishou|快手|kwai|maxhub-kuaishou|v\.kuaishou", re.I),
    "滴滴": re.compile(r"didi|滴滴|didichuxing|didi-ride|DIDI_MCP|mcp\.didichuxing", re.I),
    "拼多多": re.compile(r"pinduoduo|拼多多|pdd-|pdd_|open\.pinduoduo|多多进宝|mcp-cn-pinduoduo", re.I),
    "携程": re.compile(
        r"ctrip|携程|wendao|问道|tripgenie|trips-ai|"
        r"flights\.ctrip|trip\.com|ctrip-flight|ctrip-hotel|ctrip-wendao",
        re.I,
    ),
    "得物": re.compile(
        r"dewu|poizon|得物|open\.dewu|open\.poizon|"
        r"dewu-seeding|dw-skills|poizon-l10n|specfusion.*dewu|source=dewu",
        re.I,
    ),
    "腾讯": re.compile(
        r"wechat|weixin|微信|miniprogram|小程序|wecom|wework|企业微信|"
        r"TencentCloudBase|WecomTeam|cloudbase|混元|hunyuan|openclaw-weixin|"
        r"tencent-docs|docs\.qq\.com|tencent-cos|tencent-meeting",
        re.I,
    ),
}

MULTI_PLATFORM_APPS = re.compile(
    r"淘宝|拼多多|抖音|快手|知乎|小红书|美团|哔哩|bilibili|B站|高德|QQ音乐|"
    r"支付宝|百度|微信|京东|微博|网易云|滴滴|饿了么|携程|得物",
    re.I,
)
FOUNDER_OR_QUOTES = re.compile(
    r"语录|金句|传记|认知框架|蒸馏|饭否|创始人说|名人说|王兴|马云|张一鸣|"
    r"段永平|雷军说|创业认知",
    re.I,
)
GENERIC_SHORTCUT = re.compile(
    r"剪切板|剪贴板|快捷指令|一键跳转|分享链接|deeplink|app跳转|多平台|"
    r"主流\s*app|多个app",
    re.I,
)
PARALLEL_VENDORS = re.compile(
    r"美团.{0,8}饿了么|饿了么.{0,8}美团|"
    r"阿里.{0,8}腾讯|腾讯.{0,8}阿里|"
    r"抖音.{0,8}快手|快手.{0,8}抖音",
    re.I,
)

VENDOR_ECOSYSTEM: dict[str, str] = {
    "美团": "美团开放平台 / AI Hub / 商家·外卖·到店 / 大众点评 / 美团 Passport 等业务 API",
    "阿里": "阿里云 / 通义 / DashScope / 百炼 / 钉钉等阿里系产品 API",
    "字节": "火山引擎 / 扣子 Coze / 字节 AgentKit / 抖音开放平台等字节系产品",
    "知乎": "知乎开放平台 / 知乎 API / 知乎创作者·热榜·问答自动化",
    "小红书": "小红书 RED Skill / 小红书开放平台 / 笔记发布·运营·MCP 自动化",
    "哔哩哔哩": "哔哩哔哩开放平台 / B站视频·直播 API / UP主上传·下载·字幕·数据分析 Skill",
    "快手": "快手开放平台 / 短视频·直播·电商 API / 创作者上传·数据查询·热榜分析 Skill",
    "滴滴": "滴滴 MCP 服务 / 网约车·地图 API / didi-ride-skill 官方打车 Agent Skill",
    "拼多多": "拼多多开放平台 / 多多进宝·商家 API / 电商 MCP·优惠券·选品 Skill",
    "携程": "携程问道 Wendao / TripGenie OpenClaw / 机票酒店查询·比价·热榜 / 商旅 MCP（企业）",
    "得物": "得物开放平台 DOP / Poizon Open Platform / SpecFusion 文档检索 / 种草文案·品牌本地化 Skill",
    "腾讯": "微信小程序 AI 模式 / CloudBase mp-skills / 企业微信 OpenClaw / 腾讯云 ADP·MCP 广场 / ClawHub 社区 Skill",
}

VENDOR_NEGATIVE_EXAMPLES: dict[str, list[str]] = {
    "美团": [
        "❌ 支持淘宝/拼多多/美团/抖音等多 App 剪贴板链接跳转 —— 多平台工具",
        "❌ 王兴饭否语录认知框架 —— 人物内容非开发 Skill",
        "❌ 美团+饿了么 Excel 数据同步 —— 跨平台工具非美团专属",
        "✅ meituan-passport-user-auth —— 美团 Passport 授权 API",
        "✅ meituan-queue —— 美团/点评排队取号 API",
    ],
    "阿里": [
        "❌ 通用 DevOps 工具顺带支持阿里云 —— 非阿里专属",
        "✅ DashScope 通义 API 调用封装 —— 阿里专属",
    ],
    "字节": [
        "❌ 通用 Agent 框架仅举例 Coze —— 非字节专属",
        "✅ volcengine AgentKit ListSharingSkills —— 字节官方",
    ],
    "知乎": [
        "❌ 通用写作助手可发多平台含知乎 —— 非知乎专属",
        "✅ zhihu-cli 热榜/问答 API —— 知乎专属",
    ],
    "小红书": [
        "❌ 社媒一键发多平台含小红书 —— 非小红书专属",
        "✅ xhs-publish 小红书笔记发布 MCP —— 小红书专属",
    ],
    "哔哩哔哩": [
        "❌ 多平台剪贴板/一键跳转含 B站 —— 非 B站专属",
        "❌ social-auto-upload 等多平台上传工具 —— 除非子 Skill 专做 bilibili-upload",
        "✅ bilibili-video-download yutto 下载 —— B站专属",
        "✅ bilibili-cc-to-notion B站字幕笔记 —— B站专属",
        "✅ bili-content-analysis UP主/视频分析 —— B站专属",
    ],
    "快手": [
        "❌ 多平台剪贴板/一键跳转含快手 —— 非快手专属",
        "❌ social-auto-upload 等多平台上传工具 —— 除非子 Skill 专做 kuaishou-upload",
        "❌ yby6-video-parser 等 20+ 平台视频解析 —— 非快手专属",
        "✅ maxhub-kuaishou 快手数据查询/热榜/评论 —— 快手专属",
        "✅ kuaishou-upload sau CLI 上传 —— 快手专属",
        "✅ resolve-kwai-cdn-url 快手分享链接解析 —— 快手专属",
    ],
    "滴滴": [
        "❌ 多平台剪贴板/导航/打车聚合含滴滴 —— 非滴滴专属",
        "❌ 高德/百度地图通用导航 Skill 顺带提及打车 —— 非滴滴专属",
        "✅ didi-ride-skill 官方打车 Skill —— 滴滴 MCP 专属",
        "✅ didi-ride-skill-official ClawHub 官方包 —— 滴滴专属",
        "✅ 基于 mcp.didichuxing.com 的 MCP 工具封装 —— 滴滴专属",
    ],
    "拼多多": [
        "❌ 多平台剪贴板/一键跳转含拼多多 —— 非拼多多专属",
        "❌ cn-ecommerce-search 等 8 平台统一搜索 —— 非拼多多专属",
        "❌ specfusion 等多平台 API 文档聚合 —— 非拼多多专属",
        "✅ pdd-coupon-bot 拼多多优惠券/百亿补贴 —— 拼多多专属",
        "✅ mcp-cn-pinduoduo 拼多多商家 MCP —— 拼多多专属",
        "✅ 多多进宝/PDD DDK 推广转链 Skill —— 拼多多专属",
    ],
    "携程": [
        "❌ tripwire/roundtrip/trip-advisor 等通用 trip 英文词 —— 非携程专属",
        "❌ 多 OTA 比价工具顺带含携程 —— 除非子 Skill 专做 ctrip",
        "❌ hotelrate-crawl 等多平台酒店报价聚合 —— 非携程专属",
        "✅ wendao-skill / ctrip-wendao 携程问道 OpenClaw —— 携程官方",
        "✅ tcom-tripgenie-skill TripGenie OpenClaw —— 携程官方",
        "✅ ctrip-flight-sunrise / flight-monitor 携程机票监控 —— 携程专属",
        "✅ yflaz/ctrip-skill 携程机票火车查询 —— 携程专属",
    ],
    "得物": [
        "❌ poison/poisoned-pipeline/cache-poisoning 等安全测试 Skill —— poizon 误匹配",
        "❌ 配得上/万得/wind-mcp 等「得物」同形字噪声 —— 非得物专属",
        "❌ dataworks/dw-skill-eval 等 dw- 前缀 DataWorks Skill —— 非得物",
        "❌ 多平台社媒发布工具顺带含得物 —— 除非子 Skill 专做得物",
        "✅ SpecFusion source=dewu 得物开放平台 API 文档检索 —— 得物专属",
        "✅ dewu-seeding-copywriter 得物种草文案 —— 得物专属",
        "✅ poizon-l10n POIZON 品牌本地化 —— 得物/Poizon 专属",
        "✅ ClawHub dewu 得物公开规则/入驻整理 —— 得物相关",
    ],
    "腾讯": [
        "❌ GitHub 用户名 qq123456 等非 QQ 产品 Skill —— 误匹配",
        "❌ wechat-publisher/wechatsync 等多平台同步工具 —— 非微信专属",
        "❌ 面试八股「阿里腾讯美团」并列 —— 非腾讯专属",
        "❌ 仅提及 QQ音乐/QQ邮箱 的消费产品 —— 非 Agent Skill",
        "✅ TencentCloudBase/skills 云开发官方 Skill —— 腾讯专属",
        "✅ awesome-miniprogram-skills 小程序 AI demo —— 腾讯专属",
        "✅ WecomTeam/wecom-openclaw-plugin 企业微信 OpenClaw —— 腾讯专属",
        "✅ tencent-docs / tencent-cos-skill ClawHub 腾讯云文档/COS —— 腾讯专属",
    ],
}

_cache_lock = asyncio.Lock()
_memory_cache: dict[str, dict[str, Any]] | None = None


def _cache_key(vendor: str, external_id: str) -> str:
    return f"{vendor}|{external_id}"


def _load_cache() -> dict[str, dict[str, Any]]:
    global _memory_cache
    if _memory_cache is not None:
        return _memory_cache
    if CACHE_FILE.exists():
        try:
            _memory_cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            return _memory_cache
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("vendor relevance cache load failed: %s", exc)
    _memory_cache = {}
    return _memory_cache


def _save_cache(cache: dict[str, dict[str, Any]]) -> None:
    global _memory_cache
    _memory_cache = cache
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("vendor relevance cache save failed: %s", exc)


def is_official_record(rec: RawSkillRecord) -> bool:
    meta = rec.metadata or {}
    if meta.get("official") or meta.get("agentkit"):
        return True
    return str(meta.get("catalog") or "") in OFFICIAL_CATALOGS


def _record_text(rec: RawSkillRecord) -> str:
    meta = rec.metadata or {}
    return " ".join(
        [
            rec.name or "",
            rec.raw_description or "",
            str(meta.get("repo") or ""),
            str(meta.get("githubUrl") or ""),
            str(meta.get("path") or ""),
        ]
    )


def is_dedicated_vendor_repo(vendor: str, rec: RawSkillRecord) -> bool:
    pattern = VENDOR_REPO_PATTERN.get(vendor)
    if not pattern:
        return False
    meta = rec.metadata or {}
    repo = str(meta.get("repo") or "")
    if repo and pattern.search(repo):
        return True
    external_id = rec.external_id or ""
    if ":" in external_id and not external_id.startswith(("skillsmp:", "clawhub:")):
        repo_part = external_id.split(":", 1)[0]
        return bool(pattern.search(repo_part))
    return False


def is_heuristically_irrelevant(vendor: str, rec: RawSkillRecord) -> tuple[bool, str]:
    """明显不属于该 vendor 的社区 Skill，无需调用 LLM。"""
    text = _record_text(rec)
    apps = MULTI_PLATFORM_APPS.findall(text)
    if len(set(apps)) >= 3:
        return True, "多平台通用工具，非单一厂商定向开发"
    if GENERIC_SHORTCUT.search(text) and len(set(apps)) >= 2:
        return True, "剪贴板/快捷跳转类多 App 工具"
    if FOUNDER_OR_QUOTES.search(text):
        return True, "人物语录/认知类内容，非平台开发 Skill"
    if PARALLEL_VENDORS.search(text):
        return True, "并列多个竞品平台，非单一厂商定向开发"
    if vendor == "美团" and re.search(r"饿了么|ele\.me", text, re.I):
        if re.search(r"美团", text, re.I):
            return True, "美团与饿了么并列的跨平台工具"
    return False, ""


def _attach_relevance_meta(rec: RawSkillRecord, result: dict[str, Any]) -> None:
    meta = dict(rec.metadata or {})
    meta["vendorRelevance"] = {
        "relevant": bool(result.get("relevant")),
        "reason": str(result.get("reason") or ""),
        "source": str(result.get("source") or "llm"),
        "confidence": result.get("confidence"),
        "prompt_version": PROMPT_VERSION,
    }
    rec.metadata = meta


def _normalize_llm_result(item: dict[str, Any]) -> dict[str, Any]:
    relevant = bool(item.get("relevant"))
    confidence = float(item.get("confidence") or 0.0)
    if relevant and confidence < CONFIDENCE_MIN:
        relevant = False
        reason = str(item.get("reason") or "") + f"（置信度 {confidence:.2f} 不足 {CONFIDENCE_MIN}）"
    else:
        reason = str(item.get("reason") or "")
    return {
        "relevant": relevant,
        "reason": reason,
        "confidence": confidence,
        "source": "llm",
        "prompt_version": PROMPT_VERSION,
    }


def _build_batch_prompt(vendor: str, batch: list[RawSkillRecord]) -> str:
    ecosystem = VENDOR_ECOSYSTEM.get(vendor, vendor)
    examples = VENDOR_NEGATIVE_EXAMPLES.get(vendor, [])
    lines = [
        "你是 Agent Skill 厂商归属审核专家。任务：判断 Skill 是否**专门**为指定厂商生态定向开发。",
        f"目标厂商：{vendor}",
        f"生态范围：{ecosystem}",
        "",
        "## 收录标准（relevant=true，须同时满足）",
        "1. **核心用途**必须是调用该厂商 API、商家/开发者工具，或该平台的专属自动化工作流；",
        "2. 去掉该厂商名称后，Skill 的主要价值**不复存在**（不是「顺带支持」）；",
        "3. confidence ≥ 0.82 才可通过。",
        "",
        "## 拒绝标准（relevant=false，满足任一）",
        "- 通用工具，描述中**并列**多个 App/平台（含目标厂商之一）；",
        "- 人物语录、传记、创业认知、名人说，非开发工具；",
        "- 关键词命中但主体是其他公司；",
        "- 跨平台数据同步/对比（如美团+饿了么、多社媒一键发布）；",
        "- 仅在某处举例提到该厂商，核心功能与厂商无关。",
        "",
        "## 参考样例",
        *[f"  {ex}" for ex in examples],
        "",
        "返回 JSON：",
        '{"results":[{"id":"<external_id>","relevant":true/false,'
        '"reason":"一句话说明归属判断依据","confidence":0.0-1.0}]}',
        "",
        "## 待审核",
    ]
    for i, rec in enumerate(batch, 1):
        meta = rec.metadata or {}
        catalog = meta.get("catalog") or "community"
        lines.append(
            f'{i}. id="{rec.external_id}" name="{rec.name}" '
            f'catalog="{catalog}" repo="{meta.get("repo") or ""}" '
            f'desc="{(rec.raw_description or "")[:350]}"'
        )
    return "\n".join(lines)


def _build_recheck_prompt(vendor: str, rec: RawSkillRecord, first: dict[str, Any]) -> str:
    meta = rec.metadata or {}
    return f"""复核以下 Skill 是否应归入「{vendor}」。

第一次判定：relevant={first.get("relevant")} confidence={first.get("confidence")} reason={first.get("reason")}

请严格按「专门定向开发」标准二次审核。只有核心功能离不开 {vendor} 平台时才 relevant=true。

Skill:
- id: {rec.external_id}
- name: {rec.name}
- catalog: {meta.get("catalog") or ""}
- repo: {meta.get("repo") or ""}
- desc: {(rec.raw_description or "")[:400]}

返回 JSON：{{"relevant":true/false,"reason":"...","confidence":0.0-1.0}}"""


async def _classify_batch_llm(
    vendor: str,
    batch: list[RawSkillRecord],
) -> dict[str, dict[str, Any]]:
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    prompt = _build_batch_prompt(vendor, batch)
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {
                "role": "system",
                "content": "你是严格的 Skill 厂商归属审核员。宁可漏收，不可错收。多平台工具一律拒绝。",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1200,
        temperature=0.05,
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "").strip()
    parsed = json.loads(raw)
    items = parsed.get("results") or parsed.get("items") or []
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        ext_id = str(item.get("id") or "")
        if not ext_id:
            continue
        by_id[ext_id] = _normalize_llm_result(item)
    for rec in batch:
        if rec.external_id not in by_id:
            by_id[rec.external_id] = {
                "relevant": False,
                "reason": "LLM 未返回判定，保守拒绝",
                "confidence": 0.0,
                "source": "llm",
                "prompt_version": PROMPT_VERSION,
            }
    return by_id


async def _recheck_single_llm(
    vendor: str,
    rec: RawSkillRecord,
    first: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    prompt = _build_recheck_prompt(vendor, rec, first)
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {
                "role": "system",
                "content": "你是严格的 Skill 厂商归属复核员。多平台/顺带提及一律拒绝。",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "").strip()
    parsed = json.loads(raw)
    result = _normalize_llm_result(parsed)
    result["source"] = "llm_recheck"
    return result


async def filter_records_by_vendor_relevance(
    vendor: str,
    records: list[RawSkillRecord],
    *,
    batch_size: int = 6,
) -> list[RawSkillRecord]:
    """过滤社区 Skill，仅保留真正面向该 vendor 定向开发的条目。"""
    if not records:
        return []

    settings = get_settings()
    accepted: list[RawSkillRecord] = []
    need_llm: list[RawSkillRecord] = []
    stats = {"cached_yes": 0, "cached_no": 0, "heuristic_no": 0, "llm_yes": 0, "llm_no": 0, "recheck_no": 0}

    async with _cache_lock:
        cache = _load_cache()

        for rec in records:
            key = _cache_key(vendor, rec.external_id)
            cached = cache.get(key)
            if cached is not None and cached.get("prompt_version") == PROMPT_VERSION:
                if cached.get("relevant"):
                    _attach_relevance_meta(rec, cached)
                    accepted.append(rec)
                    stats["cached_yes"] += 1
                else:
                    stats["cached_no"] += 1
                continue

            bad, reason = is_heuristically_irrelevant(vendor, rec)
            if bad:
                cache[key] = {
                    "relevant": False,
                    "reason": reason,
                    "source": "heuristic",
                    "prompt_version": PROMPT_VERSION,
                }
                stats["heuristic_no"] += 1
                continue

            need_llm.append(rec)

        if need_llm and settings.deepseek_api_key:
            for i in range(0, len(need_llm), batch_size):
                batch = need_llm[i : i + batch_size]
                try:
                    results = await _classify_batch_llm(vendor, batch)
                except Exception as exc:
                    logger.warning(
                        "vendor relevance LLM failed vendor=%s batch=%s: %s",
                        vendor,
                        i // batch_size + 1,
                        exc,
                    )
                    results = {
                        rec.external_id: {
                            "relevant": is_dedicated_vendor_repo(vendor, rec),
                            "reason": "LLM 失败，按专用仓库启发式",
                            "source": "heuristic_fallback",
                            "prompt_version": PROMPT_VERSION,
                        }
                        for rec in batch
                    }

                uncertain: list[RawSkillRecord] = []
                for rec in batch:
                    first = results.get(rec.external_id) or {
                        "relevant": False,
                        "reason": "无判定",
                        "confidence": 0.0,
                        "source": "llm",
                        "prompt_version": PROMPT_VERSION,
                    }
                    conf = float(first.get("confidence") or 0.0)
                    if first.get("relevant") and conf < CONFIDENCE_MIN + 0.05:
                        uncertain.append(rec)
                    elif not first.get("relevant") and conf >= 0.55 and is_dedicated_vendor_repo(vendor, rec):
                        uncertain.append(rec)

                recheck_map: dict[str, dict[str, Any]] = {}
                for rec in uncertain:
                    try:
                        first = results[rec.external_id]
                        recheck_map[rec.external_id] = await _recheck_single_llm(vendor, rec, first)
                    except Exception as exc:
                        logger.warning("vendor relevance recheck failed %s: %s", rec.external_id, exc)
                        recheck_map[rec.external_id] = results[rec.external_id]

                for rec in batch:
                    key = _cache_key(vendor, rec.external_id)
                    result = recheck_map.get(rec.external_id) or results.get(rec.external_id) or {
                        "relevant": False,
                        "reason": "无判定",
                        "source": "llm",
                        "prompt_version": PROMPT_VERSION,
                    }
                    cache[key] = result
                    if result.get("relevant"):
                        _attach_relevance_meta(rec, result)
                        accepted.append(rec)
                        stats["llm_yes"] += 1
                    else:
                        stats["llm_no"] += 1
                        if rec.external_id in recheck_map:
                            stats["recheck_no"] += 1
        elif need_llm:
            for rec in need_llm:
                key = _cache_key(vendor, rec.external_id)
                dedicated = is_dedicated_vendor_repo(vendor, rec)
                result = {
                    "relevant": dedicated,
                    "reason": "无 DeepSeek API，仅专用仓库通过" if dedicated else "无 DeepSeek API，保守拒绝",
                    "source": "heuristic_fallback",
                    "prompt_version": PROMPT_VERSION,
                }
                cache[key] = result
                if dedicated:
                    _attach_relevance_meta(rec, result)
                    accepted.append(rec)

        _save_cache(cache)

    logger.info(
        "vendor_relevance vendor=%s in=%s accepted=%s stats=%s",
        vendor,
        len(records),
        len(accepted),
        stats,
    )
    return accepted


async def apply_vendor_relevance_split(
    vendor: str,
    records: list[RawSkillRecord],
) -> list[RawSkillRecord]:
    """官方源直接保留；社区源（含 GitHub）走定向审核。"""
    if not records:
        return []

    official: list[RawSkillRecord] = []
    community: list[RawSkillRecord] = []
    for rec in records:
        if is_official_record(rec):
            official.append(rec)
            continue
        meta = rec.metadata or {}
        vr = meta.get("vendorRelevance") or {}
        if vr.get("relevant") and vr.get("prompt_version") == PROMPT_VERSION:
            official.append(rec)
            continue
        community.append(rec)

    if not community:
        return records

    filtered = await filter_records_by_vendor_relevance(vendor, community)
    return official + filtered
