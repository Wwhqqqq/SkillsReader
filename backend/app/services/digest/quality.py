"""质量评分模块 —— 实现文档 §6 的 Quality Score 策略（精选排序用）。

注意：入库时的启发式 quality_score 由 scan/normalizer.compute_quality_score 计算；
本模块在精选阶段二次加工，使用 Skill 已入库字段（含 quality_score）。
"""

from __future__ import annotations

from app.models import Skill


def _md_structure_score(skill: Skill) -> float:
    """基于 metadata 与描述内容评估 SKILL.md 的结构完整度。"""
    meta = skill.metadata_json if isinstance(skill.metadata_json, dict) else {}
    score = 0.0
    if skill.name:
        score += 20
    if meta.get("category") or meta.get("categoryName"):
        score += 20
    tags = skill.tags or []
    if tags:
        score += 20
    desc = (skill.llm_summary or skill.raw_description or "").lower()
    if any(k in desc for k in ("usage", "example", "用法", "示例", "how to")):
        score += 40
    elif len(desc) >= 80:
        score += 25
    return min(100.0, score)


def compute_digest_quality(skill: Skill) -> float:
    # 描述长度归一化：以 120 字为满分标准
    desc_len = len((skill.llm_summary or skill.raw_description or "").strip())
    description_length_norm = min(100.0, desc_len / 120 * 100)
    tag_richness = min(100.0, len(skill.tags or []) * 20)
    md_score = _md_structure_score(skill)
    filter_pass = float(skill.quality_score or 0)
    total = (
        0.3 * description_length_norm
        + 0.2 * tag_richness
        + 0.2 * md_score
        + 0.3 * filter_pass
    )
    return round(min(100.0, total), 2)


def quality_breakdown(skill: Skill) -> dict:
    """供测试平台追踪展示的质量分明细（精选阶段）。"""
    desc_len = len((skill.llm_summary or skill.raw_description or "").strip())
    description_length_norm = min(100.0, desc_len / 120 * 100)
    tag_richness = min(100.0, len(skill.tags or []) * 20)
    md_score = _md_structure_score(skill)
    filter_pass = float(skill.quality_score or 0)
    return {
        "description_length_norm": round(description_length_norm, 2),
        "tag_richness": round(tag_richness, 2),
        "md_structure_score": round(md_score, 2),
        "filter_pass_strength": round(filter_pass, 2),
        "inbound_quality_score": int(skill.quality_score or 0),
        "weights": {"description": 0.3, "tags": 0.2, "md": 0.2, "filter": 0.3},
        "quality_score": compute_digest_quality(skill),
        "formula": "0.3*desc_norm + 0.2*tags + 0.2*md + 0.3*inbound_quality_score",
        "note": "inbound_quality_score 来自 normalizer.compute_quality_score 入库打分",
    }
