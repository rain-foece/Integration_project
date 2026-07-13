"""FastAPI 应用入口。

注册路由、CORS、异常处理、启动/关闭事件。
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.config import settings
from server.models import init_db, close_db
from server.services.logging import setup_logging, get_logger

# 路由
from server.routers.cases import router as cases_router
from server.routers.evidences import router as evidences_router
from server.routers.tasks import router as tasks_router
from server.routers.reports import router as reports_router
from server.routers.tools import router as tools_router

# 异常处理
from server.routers.error_handlers import AppError, app_exception_handler, general_exception_handler

# 初始化日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库，关闭时清理资源。"""
    logger.info(f"应用启动中... {settings.APP_NAME} v{settings.APP_VERSION}")

    # 启动时初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    yield

    # 关闭时清理
    await close_db()
    logger.info("应用已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="电子数据取证工具集成系统 - 后端 API",
    lifespan=lifespan,
)

# ========== CORS 中间件 ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 注册异常处理器 ==========
app.add_exception_handler(AppError, app_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# ========== 注册路由 ==========
api_prefix = settings.API_V1_PREFIX
app.include_router(cases_router, prefix=api_prefix)
app.include_router(evidences_router, prefix=api_prefix)
app.include_router(tasks_router, prefix=api_prefix)
app.include_router(reports_router, prefix=api_prefix)
app.include_router(tools_router, prefix=api_prefix)

# ========== 静态文件 ==========
# web/ 目录与 server/ 同级的项目根目录下
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
app.mount("/static", StaticFiles(directory=web_dir), name="static")


@app.get("/")
async def index():
    """返回前端页面。"""
    index_path = os.path.join(web_dir, "index.html")
    return FileResponse(index_path)


# ========== 健康检查 ==========
@app.get("/health")
async def health_check():
    """健康检查端点。"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )