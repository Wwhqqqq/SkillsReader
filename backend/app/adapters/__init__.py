"""
Adapter 注册表 —— 把字符串名称映射到具体 Adapter 类。

config/sources.yaml 里 adapter: meituan
    → get_adapter("meituan")
    → MeituanAdapter()
    → await adapter.fetch()

新增平台步骤:
    1. 在 adapters/<vendor>/ 下新建 adapter.py 继承 SourceAdapter
    2. 在本文件 ADAPTER_MAP 注册
    3. 在 config/sources.yaml 添加条目
"""

from __future__ import annotations

from app.adapters.aliyun import AliyunSkillsAdapter
from app.adapters.base import SourceAdapter
from app.adapters.bilibili import BilibiliSkillsAdapter
from app.adapters.ctrip import CtripSkillsAdapter
from app.adapters.dewu import DewuSkillsAdapter
from app.adapters.didi import DidiSkillsAdapter
from app.adapters.pinduoduo import PinduoduoSkillsAdapter
from app.adapters.kuaishou import KuaishouSkillsAdapter
from app.adapters.bytedance import BytedanceSkillsAdapter, VolcengineFindAdapter
from app.adapters.meituan import MeituanAdapter
from app.adapters.supplemental import GitHubWatchAdapter, SkillsShAdapter
from app.adapters.tencent import WechatSkillhubAdapter
from app.adapters.xiaohongshu import XiaohongshuSkillsAdapter
from app.adapters.zhihu import ZhihuSkillsAdapter

# dict[键类型, 值类型]: yaml 里的 adapter 名 → Adapter 类（注意存的是类，不是实例）
ADAPTER_MAP: dict[str, type[SourceAdapter]] = {
    "meituan": MeituanAdapter,
    "aliyun_skills": AliyunSkillsAdapter,
    "skills_sh": SkillsShAdapter,
    "github_watch": GitHubWatchAdapter,
    "volcengine_find": VolcengineFindAdapter,
    "bytedance_skills": BytedanceSkillsAdapter,
    "wechat_skillhub": WechatSkillhubAdapter,
    "zhihu_skills": ZhihuSkillsAdapter,
    "xiaohongshu_red_skill": XiaohongshuSkillsAdapter,
    "bilibili_skills": BilibiliSkillsAdapter,
    "kuaishou_skills": KuaishouSkillsAdapter,
    "didi_skills": DidiSkillsAdapter,
    "pinduoduo_skills": PinduoduoSkillsAdapter,
    "ctrip_skills": CtripSkillsAdapter,
    "dewu_skills": DewuSkillsAdapter,
}


def get_adapter(adapter_name: str) -> SourceAdapter:
    """
    工厂函数：根据名称实例化 Adapter。

    type[SourceAdapter] 表示「类本身」；cls() 创建实例。
    """
    cls = ADAPTER_MAP.get(adapter_name)
    if cls is None:
        raise ValueError(f"Unknown adapter: {adapter_name}")
    return cls()  # 每次扫描新建实例，无状态
