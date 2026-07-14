# 数据库会话与引擎管理模块

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from server.config import settings


# SQLAlchemy 声明式基类
class Base(DeclarativeBase):
    pass


# 异步引擎（echo 仅开发环境开启）
# 注意：SQLite 不支持 pool_size/max_overflow，仅 PostgreSQL 等支持连接池
_engine_kwargs = {"echo": settings.DB_ECHO}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
    })

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# 异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# FastAPI 依赖注入：获取数据库会话
async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 初始化数据库，创建所有表
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# 关闭数据库引擎
async def close_db():
    await engine.dispose()
