#!/usr/bin/env python3
"""向测试库灌入 8 天多平台演示数据 —— 可直接跑模拟推送。"""

from __future__ import annotations

import asyncio
from datetime import date

from app.core.test_database import init_test_db, test_session_factory
from app.services.testbench.service import (
    create_skill,
    generate_timeline,
    prepare_ref_date,
    reset_test_db,
)

START_DATE = date(2026, 6, 16)
END_DATE = date(2026, 6, 23)

# (source_id, name, official, quality, 8日 install 曲线)
DEMO_SKILLS: list[tuple[str, str, bool, int, list[int]]] = [
    # 美团 — 官方稳定 + 社区爆发
    ("sim_meituan", "美团外卖 Agent", True, 85, [800, 820, 850, 880, 920, 980, 1050, 1120]),
    ("sim_meituan", "美团到店核销 Skill", True, 78, [300, 310, 320, 335, 350, 370, 390, 410]),
    ("sim_meituan", "美团优惠券检索", False, 62, [20, 45, 90, 160, 280, 450, 680, 950]),
    # 腾讯
    ("sim_tencent", "腾讯文档 AI 助手", True, 88, [1200, 1210, 1230, 1250, 1280, 1320, 1380, 1450]),
    ("sim_tencent", "微信客服 Skill", True, 82, [500, 505, 515, 530, 550, 580, 620, 670]),
    ("sim_tencent", "混元 Agent 插件", False, 70, [50, 80, 130, 210, 340, 520, 780, 1100]),
    # 阿里
    ("sim_aliyun", "通义千问 Tool Hub", True, 86, [900, 910, 925, 940, 960, 990, 1030, 1080]),
    ("sim_aliyun", "DashScope 搜索 Skill", False, 68, [30, 55, 100, 180, 300, 480, 720, 1000]),
    # 小红书 — 高增长
    ("sim_xiaohongshu", "小红书 RED Skill 官方", True, 80, [200, 220, 260, 320, 400, 520, 680, 880]),
    ("sim_xiaohongshu", "xhs-note-creator", False, 72, [40, 70, 120, 200, 320, 500, 760, 1100]),
    ("sim_xiaohongshu", "xiaohongshu-mcp", False, 75, [100, 150, 230, 350, 520, 750, 1050, 1420]),
    # 知乎 / B站
    ("sim_zhihu", "知乎热榜 API Skill", True, 76, [150, 155, 165, 180, 200, 230, 270, 320]),
    ("sim_zhihu", "知乎问答写作助手", False, 65, [10, 25, 50, 90, 150, 240, 380, 580]),
    ("sim_bilibili", "B站投稿自动化", False, 68, [25, 40, 70, 120, 200, 320, 500, 750]),
    ("sim_bilibili", "B站数据分析 MCP", False, 64, [15, 22, 35, 55, 85, 130, 200, 310]),
    # 海外 — skills.sh 趋势 + GitHub
    ("sim_skills_sh", "agent-workflow-trend", False, 60, [5, 15, 40, 90, 180, 350, 620, 980]),
    (
        "sim_skills_sh",
        "ai-coding-hot",
        False,
        58,
        [8, 20, 45, 95, 190, 380, 650, 1050],
    ),
    ("sim_github", "openclaw-xhs-stars", False, 66, [80, 85, 95, 110, 140, 190, 260, 360]),
    ("sim_github", "volcengine-skills-repo", False, 70, [200, 205, 215, 230, 250, 280, 320, 380]),
]


async def main() -> None:
    await init_test_db()
    async with test_session_factory() as session:
        await reset_test_db(session)
        await session.commit()

    created = 0
    async with test_session_factory() as session:
        for source_id, name, official, quality, timeline in DEMO_SKILLS:
            meta = {"official": True} if official else {}
            if source_id == "sim_skills_sh":
                meta.update({"trend_source": True, "section": "trending", "catalog": "skills_sh"})
            skill = await create_skill(
                session,
                {
                    "source_id": source_id,
                    "name": name,
                    "external_id": f"demo:{source_id}:{name}",
                    "raw_description": f"测试平台演示 Skill · {name} · 用于验证 8 日增速与 Top10 选榜逻辑。",
                    "detail_url": f"https://testbench.local/skills/{source_id}/{name}",
                    "tags": [source_id.replace("sim_", "")],
                    "install_count": timeline[0],
                    "quality_score": quality,
                    "first_seen_date": START_DATE.isoformat(),
                    "official": official,
                    "metadata_json": meta,
                },
            )
            await generate_timeline(session, skill["id"], START_DATE, timeline)
            created += 1
        await prepare_ref_date(session, END_DATE)
        await session.commit()

    print(f"=== 测试库演示数据已就绪 ===")
    print(f"Skills: {created}")
    print(f"日期范围: {START_DATE.isoformat()} ~ {END_DATE.isoformat()} (8 天)")
    print(f"模拟推送请选日期: {END_DATE.isoformat()}")
    print("前端: 测试平台 → 模拟推送 → 运行")


if __name__ == "__main__":
    asyncio.run(main())
