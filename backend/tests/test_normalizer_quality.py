"""入库质量分 compute_quality_score 单元测试。"""

from app.adapters.base import RawSkillRecord
from app.services.scan.normalizer import compute_quality_score


def test_desc_long_plus_5():
    rec = RawSkillRecord(
        external_id="1",
        name="T",
        vendor="海外社区",
        source_id="skills_sh",
        raw_description="这是一段超过二十个字的描述用于测试入库质量分。",
    )
    # 30 base + 5 desc = 35
    assert compute_quality_score(rec) == 35


def test_desc_short_plus_2():
    rec = RawSkillRecord(
        external_id="1",
        name="T",
        vendor="海外社区",
        source_id="skills_sh",
        raw_description="短描述",
    )
    assert compute_quality_score(rec) == 32  # 30 + 2


def test_big_company_in_desc_plus_15():
    rec = RawSkillRecord(
        external_id="1",
        name="T",
        vendor="海外社区",
        source_id="skills_sh",
        raw_description="对接腾讯混元 API 的长描述文本用于测试加分规则。",
    )
    # 30 + 5 + 15
    assert compute_quality_score(rec) == 50


def test_domestic_vendor_plus_30():
    rec = RawSkillRecord(
        external_id="1",
        name="T",
        vendor="美团",
        source_id="sim_meituan",
        raw_description="足够长的描述文本用于测试大厂 vendor 加分。",
    )
    # 30 + 5 + 30
    assert compute_quality_score(rec) == 65


def test_install_uses_power_04():
    rec = RawSkillRecord(
        external_id="1",
        name="T",
        vendor="海外社区",
        source_id="skills_sh",
        install_count=10000,
    )
    # 30 + min(20, 10000**0.4) = 30 + 20 = 50
    assert compute_quality_score(rec) == 50
