"""官方 GitHub Skill 仓库配置 —— config/official_github_repos.yaml"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml

from app.core.config import CONFIG_DIR

CONFIG_PATH = CONFIG_DIR / "official_github_repos.yaml"


@dataclass(frozen=True)
class OfficialGithubRepo:
    vendor: str
    repo: str
    roots: tuple[str, ...] = ("", "skills")
    known_prefixes: tuple[str, ...] | None = None


@dataclass(frozen=True)
class OrgPrefixRule:
    vendor: str
    prefix: str


def _tuple_roots(raw: list[str] | None) -> tuple[str, ...]:
    if not raw:
        return ("", "skills")
    return tuple(str(x) for x in raw)


@lru_cache
def load_official_github_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"repos": [], "org_prefixes": []}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def list_official_github_repos() -> tuple[OfficialGithubRepo, ...]:
    cfg = load_official_github_config()
    out: list[OfficialGithubRepo] = []
    for row in cfg.get("repos") or []:
        if not row or not row.get("repo"):
            continue
        kp = row.get("known_prefixes")
        out.append(
            OfficialGithubRepo(
                vendor=str(row.get("vendor") or ""),
                repo=str(row["repo"]).strip(),
                roots=_tuple_roots(row.get("roots")),
                known_prefixes=tuple(str(x) for x in kp) if kp else None,
            )
        )
    return tuple(out)


@lru_cache
def list_org_prefix_rules() -> tuple[OrgPrefixRule, ...]:
    cfg = load_official_github_config()
    return tuple(
        OrgPrefixRule(vendor=str(r.get("vendor") or ""), prefix=str(r.get("prefix") or "").lower())
        for r in (cfg.get("org_prefixes") or [])
        if r and r.get("prefix")
    )


def all_official_repo_names() -> frozenset[str]:
    return frozenset(r.repo for r in list_official_github_repos())


def vendor_github_scan_specs(vendor: str) -> tuple[tuple[str, tuple[str, ...], tuple[str, ...] | None], ...]:
    rows = [r for r in list_official_github_repos() if r.vendor == vendor]
    return tuple((r.repo, r.roots, r.known_prefixes) for r in rows)


def vendor_github_scan_list(vendor: str) -> tuple[tuple[str, tuple[str, ...] | None], ...]:
    rows = [r for r in list_official_github_repos() if r.vendor == vendor]
    return tuple((r.repo, r.known_prefixes) for r in rows)


def is_official_github_repo(repo: str) -> bool:
    name = (repo or "").strip()
    if not name:
        return False
    lower_name = name.lower()
    if lower_name in {r.lower() for r in all_official_repo_names()}:
        return True
    for rule in list_org_prefix_rules():
        if lower_name.startswith(rule.prefix):
            return True
    return False


def official_github_repo_for_vendor(vendor: str, repo: str) -> bool:
    lower_name = (repo or "").strip().lower()
    if not lower_name:
        return False
    for r in list_official_github_repos():
        if r.vendor == vendor and r.repo.lower() == lower_name:
            return True
    for rule in list_org_prefix_rules():
        if rule.vendor == vendor and lower_name.startswith(rule.prefix):
            return True
    return False
