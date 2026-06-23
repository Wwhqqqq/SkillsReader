"""
Adapter 基类与数据结构 —— 所有平台抓取器的统一接口。

设计模式: 策略模式 + 适配器模式
    - 每个平台一个 SourceAdapter 子类
    - 全部输出 list[RawSkillRecord]，后续 pipeline 无需关心来源

学习重点:
    @dataclass  — 自动生成 __init__ 的数据类
    ABC         — 抽象基类，子类必须实现 fetch()
    async def   — 异步方法，内部用 httpx 发 HTTP 请求
"""

from __future__ import annotations

from abc import ABC, abstractmethod  # ABC=抽象基类, abstractmethod=强制子类实现
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawSkillRecord:
    """
    抓取结果的「标准格式」—— 从各平台 API/HTML 解析后统一转成此结构。

    dataclass 说明:
        带类型注解的字段会自动成为 __init__ 参数
        field(default_factory=list) 用于可变默认值（不能写 tags=[]）
    """

    external_id: str      # 源站唯一 ID，用于 fingerprint
    name: str             # 显示名称
    vendor: str           # 厂商：美团、阿里…
    source_id: str        # 对应 sources 表 id，如 meituan_ai_hub
    raw_description: str = ""       # 原始描述，可选
    detail_url: str = ""            # 详情页链接
    tags: list[str] = field(default_factory=list)  # 标签列表
    install_count: int = 0            # 安装量/热度（有则填）
    publish_date: str | None = None   # 发布日期字符串，pipeline 会 parse
    metadata: dict[str, Any] = field(default_factory=dict)  # 原始 JSON 等


@dataclass
class AdapterHealth:
    """health_check() 的返回结构，供 /debug 探针使用。"""

    ok: bool              # 是否健康
    message: str = ""     # 说明，如 "ok, 42 items" 或错误信息
    latency_ms: int = 0


class SourceAdapter(ABC):
    """
    所有平台 Adapter 的抽象父类。

    子类必须实现 async def fetch() -> list[RawSkillRecord]
    类属性 source_id / vendor 应与 sources.yaml 一致。
    """

    source_id: str = ""   # 类变量，子类覆盖
    vendor: str = ""

    @abstractmethod
    async def fetch(self) -> list[RawSkillRecord]:
        """从目标网站/API 抓取 Skill 列表。子类必须实现。"""
        raise NotImplementedError

    async def fetch_official_portal(self) -> list[RawSkillRecord]:
        """轻量官方门户抓取：仅各公司官网/API 新发布 Skill，不含 GitHub 等外部源。默认无。"""
        return []

    async def health_check(self) -> AdapterHealth:
        """
        默认健康检查：尝试 fetch 一次，成功则 ok。
        子类可覆盖做更轻量的探测。
        """
        try:
            records = await self.fetch()
            return AdapterHealth(ok=True, message=f"ok, {len(records)} items")
        except Exception as exc:
            return AdapterHealth(ok=False, message=str(exc))
