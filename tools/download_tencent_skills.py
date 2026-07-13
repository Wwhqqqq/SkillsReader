"""
从 ClawHub API 下载找到的腾讯系 Skill 的 SKILL.md 文件。
"""
import asyncio
import json
import re
from pathlib import Path

import httpx

OUTPUT_DIR = Path("/Users/wangheqiao/Desktop/腾讯Skills")

SKILL_SLUGS = {
    "腾讯自选股-金融数据查询": "westockdata",
    "腾讯文档_v1": "tencent-docs",
    "腾讯文档_v2": "tencent-docs-markdown",
    "腾讯地图·地图助手_v1": "qqmap",
    "腾讯地图·地图助手_v2": "tencentmap-webservice-skill",
    "腾讯乐享": "lexiang-mcp-skill",
    "腾讯会议": "tencent-meeting-skill",
    "EdgeOne Pages Deploy": "tencent-edgeone-skill",
}


async def download_skill(client: httpx.AsyncClient, name: str, slug: str):
    """从 ClawHub API 下载技能详情。"""
    print(f"Downloading: {name} ({slug})")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Get skill detail
        resp = await client.get(
            f"https://clawhub.ai/api/v1/skills/{slug}",
            headers={"Accept": "application/json", "User-Agent": "SkillGetter/1.0"},
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            skill = data.get("skill") or data
            out = OUTPUT_DIR / f"{slug}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(skill, f, ensure_ascii=False, indent=2)
            print(f"  ✓ Saved {out}")

            # Try to get README/SKILL.md content
            md_url = f"https://clawhub.ai/api/v1/skills/{slug}/readme"
            md_resp = await client.get(md_url, headers={"Accept": "text/markdown", "User-Agent": "SkillGetter/1.0"}, timeout=15.0)
            if md_resp.status_code == 200 and len(md_resp.text) > 50:
                md_path = OUTPUT_DIR / f"{slug}.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    # Extract relevant content
                    text = md_resp.text
                    f.write(text)
                print(f"  ✓ Saved README {md_path}")
        else:
            print(f"  ✗ Failed to get skill detail: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ✗ Error: {e}")


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [
            download_skill(client, name, slug) for name, slug in SKILL_SLUGS.items()
        ]
        await asyncio.gather(*tasks)

    print(f"\nDone! Files saved to {OUTPUT_DIR}")
    # List files
    for f in sorted(OUTPUT_DIR.glob("*")):
        size = f.stat().st_size
        print(f"  {f.name} ({size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
