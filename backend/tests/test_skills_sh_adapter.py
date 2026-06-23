"""Tests for skills.sh adapter (v2 doc)."""

import pytest

from app.adapters.supplemental.skills_sh import (
    SkillsShAdapter,
    _parse_install,
    _record_from_path,
)


def test_parse_install_suffixes():
    assert _parse_install("2frontend-designanthropics/skills578.4K") == 578_400
    assert _parse_install("1find-skillsvercel-labs/skills771+6") == 771


def test_record_external_id_prefix():
    rec = _record_from_path(
        "/anthropics/skills/frontend-design",
        "2frontend-designanthropics/skills578.4K",
        section="trending",
    )
    assert rec is not None
    assert rec.external_id.startswith("skillsh:")
    assert rec.metadata.get("trend_source") is True
    assert rec.install_count == 578_400


def test_skips_nav_links():
    assert _record_from_path("/trending", "Trending", section="home") is None


@pytest.mark.asyncio
async def test_skills_sh_live_fetch():
    recs = await SkillsShAdapter().fetch()
    assert len(recs) >= 50
    assert all(r.external_id.startswith("skillsh:") for r in recs)
    assert all(r.metadata.get("trend_source") for r in recs)
    names = {r.name.lower() for r in recs}
    assert "docs" not in names
