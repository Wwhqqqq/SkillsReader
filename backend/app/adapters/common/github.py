"""
GitHub SKILL.md 发现共用工具 —— 多个 Adapter 复用的搜索/解析函数。

被 github_watch、zhihu、xiaohongshu、wechat 等 Adapter 引用。
"""

from __future__ import annotations

import asyncio
import base64
import re
from collections.abc import Callable
from typing import Any

import httpx

from app.adapters.base import RawSkillRecord
from app.core.config import get_settings


def github_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SkillGetter/1.0"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict | None = None,
    retries: int = 3,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await client.get(url, headers=headers, params=params)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt + 1 < retries:
                await asyncio.sleep(2**attempt)
    raise last_exc or RuntimeError("GitHub request failed")


def parse_skill_md(text: str, fallback_name: str, fallback_desc: str) -> tuple[str, str, str]:
    name = fallback_name
    desc = fallback_desc
    category = "未分类"

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key, val = key.strip().lower(), val.strip().strip('"').strip("'")
            if key == "name" and val:
                name = val
            elif key in ("description", "desc") and val:
                desc = val[:400]
            elif key in ("category", "tags") and val:
                category = val.split(",")[0].strip() or category
    else:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines and lines[0].startswith("#"):
            name = lines[0].lstrip("#").strip() or name
        body = " ".join(ln for ln in lines[1:] if not ln.startswith("#"))
        if body:
            desc = re.sub(r"[#*`]", "", body)[:400]

    return name, desc or fallback_desc, category


def _skill_md_path(prefix: str) -> str:
    return f"{prefix}/SKILL.md".strip("/")


async def fetch_skill_md_raw(
    client: httpx.AsyncClient,
    repo: str,
    prefix: str,
) -> str:
    """Fetch SKILL.md via raw.githubusercontent.com (no API quota)."""
    rel = _skill_md_path(prefix)
    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}"
        try:
            resp = await client.get(url, headers={"User-Agent": "SkillGetter/1.0"})
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
        except Exception:
            continue
    return ""


async def fetch_skill_md_text(
    client: httpx.AsyncClient,
    repo: str,
    prefix: str,
    headers: dict[str, str],
) -> str:
    rel = _skill_md_path(prefix)
    try:
        resp = await get_with_retry(
            client,
            f"https://api.github.com/repos/{repo}/contents/{rel}",
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("content", "")
            if content:
                return base64.b64decode(content).decode("utf-8", errors="ignore")
    except Exception:
        pass
    return await fetch_skill_md_raw(client, repo, prefix)


async def scan_repo_via_git_tree(
    client: httpx.AsyncClient,
    repo: str,
    headers: dict[str, str],
) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for branch in ("main", "master"):
        resp = await get_with_retry(
            client,
            f"https://api.github.com/repos/{repo}/git/trees/{branch}",
            headers=headers,
            params={"recursive": "1"},
        )
        if resp.status_code != 200:
            continue
        for item in resp.json().get("tree", []):
            path = item.get("path", "")
            if not path.endswith("/SKILL.md") and path != "SKILL.md":
                continue
            prefix = path[: -len("/SKILL.md")]
            slug = prefix.split("/")[-1] if prefix else repo.split("/")[-1]
            if prefix not in seen:
                seen.add(prefix)
                found.append((prefix, slug))
        if found:
            break
    return found


async def scan_repo_skill_paths(
    client: httpx.AsyncClient,
    repo: str,
    headers: dict[str, str],
    *,
    roots: tuple[str, ...] = ("", "skills"),
    known_prefixes: tuple[str, ...] | None = None,
) -> list[tuple[str, str]]:
    """Return list of (skill_path_prefix, slug) where SKILL.md exists."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    for root in roots:
        url = (
            f"https://api.github.com/repos/{repo}/contents/{root}"
            if root
            else f"https://api.github.com/repos/{repo}/contents"
        )
        try:
            resp = await get_with_retry(client, url, headers=headers)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        items = resp.json()
        if not isinstance(items, list):
            continue

        if any(i.get("name") == "SKILL.md" and i.get("type") == "file" for i in items):
            key = root or repo.split("/")[-1]
            if key not in seen:
                seen.add(key)
                found.append((root, key))

        for item in items:
            if item.get("type") != "dir":
                continue
            name = item.get("name", "")
            if name.startswith("."):
                continue
            prefix = f"{root}/{name}".strip("/") if root else name
            md_resp = await get_with_retry(
                client,
                f"https://api.github.com/repos/{repo}/contents/{prefix}/SKILL.md",
                headers=headers,
            )
            if md_resp.status_code == 200 and prefix not in seen:
                seen.add(prefix)
                found.append((prefix, name))

    if not found:
        try:
            for prefix, slug in await scan_repo_via_git_tree(client, repo, headers):
                if prefix not in seen:
                    seen.add(prefix)
                    found.append((prefix, slug))
        except Exception:
            pass

    if not found and known_prefixes:
        for prefix in known_prefixes:
            text = await fetch_skill_md_raw(client, repo, prefix)
            if not text:
                continue
            slug = prefix.split("/")[-1] if prefix else repo.split("/")[-1]
            if prefix not in seen:
                seen.add(prefix)
                found.append((prefix, slug))

    return found


async def build_records_from_repo(
    client: httpx.AsyncClient,
    repo: str,
    *,
    vendor: str,
    source_id: str,
    headers: dict[str, str],
    tags: list[str],
    roots: tuple[str, ...] = ("", "skills"),
    known_prefixes: tuple[str, ...] | None = None,
    category_default: str = "社区",
    record_filter: Callable[[RawSkillRecord], bool] | None = None,
) -> list[RawSkillRecord]:
    records: list[RawSkillRecord] = []
    paths = await scan_repo_skill_paths(
        client, repo, headers, roots=roots, known_prefixes=known_prefixes
    )
    for prefix, slug in paths:
        text = await fetch_skill_md_text(client, repo, prefix, headers)
        fallback_name = slug.replace("-", " ").title()
        fallback_desc = f"GitHub Skill · {repo}/{prefix or slug}"
        if text:
            name, desc, category = parse_skill_md(text, fallback_name, fallback_desc)
        else:
            name, desc, category = fallback_name, fallback_desc, category_default

        detail = f"https://github.com/{repo}/tree/main/{prefix}" if prefix else f"https://github.com/{repo}"
        rec = RawSkillRecord(
            external_id=f"{repo}:{prefix or slug}",
            name=name,
            vendor=vendor,
            source_id=source_id,
            raw_description=desc,
            detail_url=detail,
            tags=[*tags, category],
            metadata={"repo": repo, "path": prefix, "categoryName": category},
        )
        if record_filter and not record_filter(rec):
            continue
        records.append(rec)
    return records


async def search_code_skill_md(
    client: httpx.AsyncClient,
    query: str,
    headers: dict[str, str],
    *,
    per_page: int = 30,
) -> list[dict[str, Any]]:
    if not get_settings().github_token:
        return []
    resp = await get_with_retry(
        client,
        "https://api.github.com/search/code",
        headers=headers,
        params={"q": query, "per_page": per_page},
    )
    if resp.status_code != 200:
        return []
    return resp.json().get("items", [])


async def search_repositories(
    client: httpx.AsyncClient,
    query: str,
    headers: dict[str, str],
    *,
    per_page: int = 15,
) -> list[dict[str, Any]]:
    resp = await get_with_retry(
        client,
        "https://api.github.com/search/repositories",
        headers=headers,
        params={"q": query, "per_page": per_page, "sort": "updated"},
    )
    if resp.status_code != 200:
        return []
    return resp.json().get("items", [])
