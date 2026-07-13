"""统一的 API 错误响应格式。"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi import Request
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误响应模型。"""
    error: dict


def error_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """生成统一格式的错误响应。

    Args:
        code: 错误码
        message: 错误信息
        status_code: HTTP 状态码

    Returns:
        JSONResponse
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


class AppError(HTTPException):
    """应用自定义异常，支持统一错误格式。"""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.error_code = code
        self.error_message = message
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


async def app_exception_handler(request: Request, exc: AppError):
    """全局异常处理器（AppError）。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.error_message,
            }
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """全局异常处理器（通用）。"""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"服务器内部错误: {str(exc)}",
            }
        },
    )