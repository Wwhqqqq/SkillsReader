#!/usr/bin/env python3
"""各采集源连通性探测 —— 验证 fetch 是否符合需求。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.adapters import get_adapter

# 重点源 + 各类型代表
PROBE_SOURCES = [
    ("skills_sh", "skills.sh 趋势/热度"),
    ("github_watch", "GitHub 监控"),
    ("meituan", "美团官方 API"),
    ("wechat_skillhub", "腾讯 SkillHub"),
    ("aliyun_skills", "阿里 Skills 门户"),
]


async def probe(adapter_key: str, label: str) -> dict:
    adapter = get_adapter(adapter_key)
    try:
        records = await adapter.fetch()
        with_install = sum(1 for r in records if (r.install_count or 0) > 0)
        with_url = sum(1 for r in records if r.detail_url)
        with_desc = sum(1 for r in records if (r.raw_description or "").strip())
        sample = records[0] if records else None
        return {
            "adapter": adapter_key,
            "label": label,
            "ok": len(records) > 0,
            "count": len(records),
            "with_install": with_install,
            "with_url": with_url,
            "with_desc": with_desc,
            "sample_name": sample.name if sample else None,
            "sample_install": sample.install_count if sample else 0,
            "error": None,
        }
    except Exception as exc:
        return {
            "adapter": adapter_key,
            "label": label,
            "ok": False,
            "count": 0,
            "error": str(exc),
        }


async def main() -> None:
    print("=== 采集源探测 ===")
    results = []
    for key, label in PROBE_SOURCES:
        r = await probe(key, label)
        results.append(r)
        status = "OK" if r["ok"] else "FAIL"
        line = f"[{status}] {label} ({key}): {r.get('count', 0)} 条"
        if r.get("with_install") is not None:
            line += f", 有安装量 {r['with_install']}"
        if r.get("sample_name"):
            line += f" | 样例: {r['sample_name'][:40]}"
        if r.get("error"):
            line += f" | {r['error']}"
        print(line)

    failed = [r for r in results if not r["ok"]]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
