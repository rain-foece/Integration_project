"""日志配置模块 — 使用 Python 内置 logging，无需外部依赖。"""

import logging
import sys
from server.config import settings


def setup_logging():
    """配置日志系统。"""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    if settings.LOG_FORMAT == "json":
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str | None = None) -> logging.Logger:
    """获取日志记录器。

    Args:
        name: 日志记录器名称

    Returns:
        Logger 实例
    """
    logger = logging.getLogger(name or __name__)
    return logger