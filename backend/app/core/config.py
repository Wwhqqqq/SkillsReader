"""
应用配置模块 —— 从 .env 文件和环境变量读取所有配置项。

技术栈:
    pydantic-settings 的 BaseSettings 会自动:
    - 读取 .env 文件
    - 把环境变量名映射到类字段（不区分大小写，DATABASE_URL → database_url）
    - 做类型校验（str/int/bool）

使用方式:
    from app.core.config import get_settings
    settings = get_settings()
    print(settings.database_url)
"""

from functools import lru_cache  # 缓存装饰器：get_settings() 只创建一次 Settings 实例
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Path(__file__) = 本文件路径 app/core/config.py
# .parents[0]=core, [1]=app, [2]=backend, [3]=项目根 IKnow/
ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT_DIR / "config"  # 存放 sources.yaml、rank.yaml


class Settings(BaseSettings):
    """
    所有可配置项的定义。
    等号右边是「默认值」；.env 或环境变量存在时会覆盖默认值。
    """

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),  # 自动加载项目根 .env
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里多余的键不报错
    )

    # ── 数据库 & 缓存 ──
    database_url: str = "mysql+aiomysql://root:whq050207@127.0.0.1:3306/iknow"
    test_database_url: str = "mysql+aiomysql://root:whq050207@127.0.0.1:3306/iknow_test"
    # 格式: mysql+aiomysql://用户:密码@主机:端口/库名
    # aiomysql 是异步 MySQL 驱动，配合 SQLAlchemy asyncio 使用

    redis_url: str = "redis://127.0.0.1:6379/0"
    # Redis 用于: 扫描事件 pub/sub、全局扫描开关；不可用时降级内存

    # ── DeepSeek LLM（OpenAI 兼容接口）──
    deepseek_api_key: str = ""  # 空则 LLM 用原文降级
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # ── GitHub / 国内代码托管补充源 ──
    github_token: str = ""  # 提高 GitHub API 限流额度
    skillsmp_api_key: str = ""  # SkillsMP 目录 API（可选，提高配额）
    gitee_token: str = ""
    modelscope_api_token: str = ""

    # ── 新 Skill 自动推送 ──
    auto_push_mode: str = "dm"  # off | dm | group
    auto_push_max_items: int = 15

    # ── 火山引擎 AgentKit ──
    volcengine_access_key: str = ""
    volcengine_secret_key: str = ""
    volcengine_region: str = "cn-beijing"

    # ── 如流 Open API 推送 ──
    ruliu_app_key: str = ""
    ruliu_app_secret: str = ""
    ruliu_agent_id: str = ""
    ruliu_api_base: str = "https://apiin.im.baidu.com/api/v1"
    ruliu_group_id: str = "13038971"
    ruliu_allow_group: bool = True
    ruliu_notify_target: str = "dm"      # dm=私聊, group=群
    ruliu_dm_user: str = "wangheqiao"
    ruliu_callback_token: str = ""       # 如流回调验签
    ruliu_callback_aes_key: str = ""

    # ── Worker / 日志 ──
    scan_global_enabled: bool = True  # 全局是否允许扫描
    tz: str = "Asia/Shanghai"         # 排行榜「今日」用的时区
    log_level: str = "INFO"           # DEBUG/INFO/WARNING/ERROR

    # ── API 服务 ──
    api_host: str = "0.0.0.0"   # 监听地址
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"  # 逗号分隔

    @property
    def cors_origin_list(self) -> list[str]:
        """
        @property 把方法变成「只读属性」，调用 settings.cors_origin_list 而非 cors_origin_list()
        把逗号分隔字符串转成 list，供 CORSMiddleware 使用。
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache  # 无参数函数只执行一次，后续返回缓存的 Settings 单例
def get_settings() -> Settings:
    return Settings()
