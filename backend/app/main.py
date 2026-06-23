"""
FastAPI 应用入口 —— 提供 REST API + WebSocket，供 Vue 前端调用。

启动方式（在 backend/ 目录下）:
    python -m app.main

本进程不负责定时扫描；扫描由 app.worker.scan_loop 负责。
两者共享同一 MySQL 数据库。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager  # 用于 FastAPI 生命周期 lifespan

import uvicorn   # ASGI 服务器，真正监听 HTTP 端口
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # 跨域中间件，允许前端 localhost:5173 访问

# 导入各 API 路由模块（每个模块里有一个 APIRouter）
from app.api import debug, digest, push, ruliu_callback, scan, skills, sources, stats, testbench
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.redis_client import close_redis
from app.core.test_database import init_test_db
from app.services.scan.source_sync import sync_sources_from_yaml
from app.core.database import async_session_factory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期钩子：
    - yield 之前：应用启动时执行（建表、同步配置）
    - yield 之后：应用关闭时执行（清理 Redis 连接）

    @asynccontextmanager 把 async 函数变成「异步上下文管理器」。
    """
    # engine.begin() 开启事务；run_sync 在异步引擎上运行同步的建表函数
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # 根据 models/ 定义创建所有表

    async with async_session_factory() as session:
        await sync_sources_from_yaml(session)  # YAML → sources 表
        await session.commit()

    try:
        await init_test_db()
    except Exception as exc:
        logger.warning("Test database init skipped: %s", exc)

    logger.info("SkillGetter API started")
    yield  # 此处之后 API 开始接受请求
    await close_redis()


def create_app() -> FastAPI:
    """
    工厂函数：创建并配置 FastAPI 实例。
    分离出来便于测试时 import create_app() 而不启动 uvicorn。
    """
    settings = get_settings()
    app = FastAPI(
        title="SkillGetter",
        version="1.0.0",
        lifespan=lifespan,  # 绑定上面的启动/关闭逻辑
    )

    # CORS：浏览器前端（不同端口）访问 API 时必须配置，否则被拦
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,  # 来自 .env CORS_ORIGINS
        allow_credentials=True,
        allow_methods=["*"],   # 允许所有 HTTP 方法
        allow_headers=["*"],   # 允许所有请求头
    )

    # 挂载各子路由；最终路径 = router.prefix + 装饰器路径
    app.include_router(stats.router)       # /api/health, /api/stats/*
    app.include_router(sources.router)     # /api/sources/*
    app.include_router(skills.router)      # /api/skills
    app.include_router(digest.router)      # /api/digest/*
    app.include_router(scan.router)        # /api/scan/*, /api/ws/scan-events
    app.include_router(push.router)        # /api/push/*
    app.include_router(ruliu_callback.router)  # 如流回调
    app.include_router(debug.router)       # /api/debug/*
    app.include_router(testbench.router)   # /api/testbench/*
    return app


# 模块级 app 对象，uvicorn 通过字符串 "app.main:app" 引用
app = create_app()


def main() -> None:
    """CLI 入口：配置日志并启动 uvicorn。"""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    uvicorn.run(
        "app.main:app",           # import 路径: 模块:变量名
        host=settings.api_host,   # 0.0.0.0 表示监听所有网卡
        port=settings.api_port,   # 默认 8000
        reload=False,             # 生产环境关闭热重载
    )


if __name__ == "__main__":
    main()
