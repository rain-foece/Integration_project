# 应用配置模块，从环境变量读取配置项

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


# 应用配置类，所有配置项均可通过环境变量覆盖
class Settings(BaseSettings):

    # 应用基础配置
    APP_NAME: str = "Forensics Tool Integration Platform"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # 数据库配置
    # SQLite 数据库文件，固定放在项目根目录，无论从哪个目录启动都能找到
    DB_PATH: str = str(Path(__file__).resolve().parent.parent / "forensics.db")
    DATABASE_URL: str = ""

    # 切换 PostgreSQL 时使用：
    # DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/forensics"

    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis 配置（Celery 消息队列）
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 文件存储配置
    # 证据文件存储根目录
    STORAGE_ROOT: str = str(Path(__file__).resolve().parent.parent / "storage")
    # 子目录
    EVIDENCE_DIR: str = "evidences"
    REPORT_DIR: str = "reports"
    TEMP_DIR: str = "temp"

    # 单文件上传大小限制（字节），默认 500MB
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024

    # 允许上传的文件类型
    ALLOWED_EXTENSIONS: list[str] = [
        ".raw", ".dd", ".img", ".e01", ".ex01", ".aff", ".vmdk",
        ".vhd", ".vhdx", ".zip", ".tar", ".gz", ".7z",
        ".txt", ".csv", ".json", ".xml", ".log", ".pcap", ".pcapng",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp",
        ".exe", ".dll", ".sys", ".elf", ".macho",
    ]

    # API 配置
    API_V1_PREFIX: str = "/api/v1"

    # CORS 允许的来源
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json 或 console

    # Celery 配置
    CELERY_TASK_TIME_LIMIT: int = 3600  # 任务超时时间（秒），默认 1 小时
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300  # 软超时

    # 工具适配器配置
    TOOLS_CONFIG_PATH: str = str(Path(__file__).resolve().parent.parent / "tools_config.yaml")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 全局配置单例
settings = Settings()
# 如果 DATABASE_URL 未通过环境变量设置，则使用项目根目录的 SQLite 数据库
if not settings.DATABASE_URL:
    settings.DATABASE_URL = f"sqlite+aiosqlite:///{settings.DB_PATH}"


# 获取存储目录路径字典，并确保目录存在
def get_storage_paths() -> dict:
    base = Path(settings.STORAGE_ROOT)
    paths = {
        "evidence": base / settings.EVIDENCE_DIR,
        "report": base / settings.REPORT_DIR,
        "temp": base / settings.TEMP_DIR,
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths
