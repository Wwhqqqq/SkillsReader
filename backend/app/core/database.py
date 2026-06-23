"""
数据库连接与会话管理 —— SQLAlchemy 2.0 异步模式。

核心对象:
    Base                  — 所有 ORM 模型的基类
    engine                — 连接池，真正连 MySQL
    async_session_factory — 创建 AsyncSession 的工厂
    get_db                — FastAPI 依赖注入用，每个请求一个 session
"""

from collections.abc import AsyncGenerator  # 异步生成器类型，用于 yield session

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase  # 声明式 ORM 基类（SQLAlchemy 2.0 风格）

from app.core.config import get_settings


class Base(DeclarativeBase):
    """
    所有 models/ 里的类都继承 Base。
    Base.metadata 包含所有表结构，create_all() 据此建表。
    """
    pass


settings = get_settings()

# create_async_engine: 创建异步数据库引擎（连接池）
engine = create_async_engine(
    settings.database_url,
    echo=False,          # True 时会打印每条 SQL，调试时可开
    pool_pre_ping=True,  # 取连接前先 ping，避免用到已断开的连接
    pool_recycle=3600,   # 连接 1 小时后回收，防止 MySQL wait_timeout 踢掉
)

# sessionmaker 工厂：每次 async with async_session_factory() 得到一个新的 AsyncSession
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,       # Session 类型
    expire_on_commit=False,    # commit 后对象属性仍可访问，不用 refresh
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入函数。

    用法: async def route(session: AsyncSession = Depends(get_db))

    yield 之前: 创建 session
    yield 之后: 正常则 commit，异常则 rollback
    """
    async with async_session_factory() as session:
        try:
            yield session          # 把 session 交给路由函数使用
            await session.commit() # 路由正常结束 → 提交事务
        except Exception:
            await session.rollback()  # 出错 → 回滚
            raise
