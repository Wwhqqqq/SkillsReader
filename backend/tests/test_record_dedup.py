"""跨源 Skill 去重单元测试。"""

from app.adapters.base import RawSkillRecord
from app.adapters.common.record_dedup import canonical_dedup_key, dedupe_vendor_records


def test_dedupe_clawhub_and_github_same_skill():
    claw = RawSkillRecord(
        external_id="clawhub:maxhub-kuaishou",
        name="maxhub-kuaishou",
        vendor="快手",
        source_id="kuaishou_skills",
        raw_description="ClawHub",
        metadata={"catalog": "clawhub", "slug": "maxhub-kuaishou"},
    )
    gh = RawSkillRecord(
        external_id="XieWxx/maxhub-api-skills:maxhub-kuaishou",
        name="maxhub-kuaishou",
        vendor="快手",
        source_id="kuaishou_skills",
        raw_description="GitHub SKILL.md",
        detail_url="https://github.com/XieWxx/maxhub-api-skills/tree/main/maxhub-kuaishou",
        metadata={
            "catalog": "github",
            "repo": "XieWxx/maxhub-api-skills",
            "path": "maxhub-kuaishou",
        },
    )
    assert canonical_dedup_key(claw) == canonical_dedup_key(gh)
    out = dedupe_vendor_records([claw, gh])
    assert len(out) == 1
    assert out[0].metadata.get("catalog") == "github"


def test_official_entries_not_merged():
    a = RawSkillRecord(
        external_id="kuaishou-open-platform",
        name="快手开放平台",
        vendor="快手",
        source_id="kuaishou_skills",
        metadata={"official": True},
    )
    b = RawSkillRecord(
        external_id="kuaishou-miniprogram",
        name="快手小程序",
        vendor="快手",
        source_id="kuaishou_skills",
        metadata={"official": True},
    )
    out = dedupe_vendor_records([a, b])
    assert len(out) == 2


def test_dedupe_skillsmp_with_github_url():
    smp = RawSkillRecord(
        external_id="skillsmp:abc123",
        name="kuaishou-upload",
        vendor="快手",
        source_id="kuaishou_skills",
        metadata={"catalog": "skillsmp", "githubUrl": "https://github.com/dreammis/social-auto-upload"},
    )
    gh = RawSkillRecord(
        external_id="dreammis/social-auto-upload:skills/kuaishou-upload",
        name="kuaishou-upload",
        vendor="快手",
        source_id="kuaishou_skills",
        metadata={
            "catalog": "github",
            "repo": "dreammis/social-auto-upload",
            "path": "skills/kuaishou-upload",
        },
    )
    out = dedupe_vendor_records([smp, gh])
    assert len(out) == 1
