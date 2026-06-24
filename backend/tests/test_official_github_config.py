"""Tests for official GitHub repo config."""

from app.adapters.common.official_github_config import (
    is_official_github_repo,
    list_official_github_repos,
    vendor_github_scan_specs,
)


def test_agentlymail_is_official_repo():
    assert is_official_github_repo("Tencent/AgentlyMail")


def test_tencent_vendor_has_agentlymail():
    repos = [r for r, _, _ in vendor_github_scan_specs("腾讯")]
    assert "Tencent/AgentlyMail" in repos


def test_config_not_empty():
    assert len(list_official_github_repos()) >= 10
