"""LLM  enrichment、厂商相关性、分类与汇总。"""

__all__ = [
    "apply_vendor_relevance_split",
    "collect_vendor_stats",
    "data_source_for",
    "enrich_metadata",
    "enrich_skill",
    "enrich_skills_batch",
    "filter_records_by_vendor_relevance",
    "format_vendor_coverage_md",
    "publisher_type_for",
]


def __getattr__(name: str):
    if name in ("enrich_skill", "enrich_skills_batch"):
        from app.services.enrichment.llm_enricher import enrich_skill, enrich_skills_batch

        return {"enrich_skill": enrich_skill, "enrich_skills_batch": enrich_skills_batch}[name]
    if name in ("data_source_for", "enrich_metadata", "publisher_type_for"):
        from app.services.enrichment.skill_classification import (
            data_source_for,
            enrich_metadata,
            publisher_type_for,
        )

        return {
            "data_source_for": data_source_for,
            "enrich_metadata": enrich_metadata,
            "publisher_type_for": publisher_type_for,
        }[name]
    if name in ("apply_vendor_relevance_split", "filter_records_by_vendor_relevance"):
        from app.services.enrichment.vendor_relevance import (
            apply_vendor_relevance_split,
            filter_records_by_vendor_relevance,
        )

        return {
            "apply_vendor_relevance_split": apply_vendor_relevance_split,
            "filter_records_by_vendor_relevance": filter_records_by_vendor_relevance,
        }[name]
    if name in ("collect_vendor_stats", "format_vendor_coverage_md"):
        from app.services.enrichment.vendor_summary import (
            collect_vendor_stats,
            format_vendor_coverage_md,
        )

        return {
            "collect_vendor_stats": collect_vendor_stats,
            "format_vendor_coverage_md": format_vendor_coverage_md,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
