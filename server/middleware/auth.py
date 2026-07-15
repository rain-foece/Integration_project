# JWT 认证中间件，仅在网页模式下生效

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from server.config import settings
from server.services.auth_service import decode_token


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 桌面模式跳过认证
        if settings.RUN_MODE == "desktop":
            return await call_next(request)

        # 公开路径无需认证
        public_paths = ["/api/v1/auth/", "/health", "/static/", "/login.html"]
        path = request.url.path
        if request.method == "GET" and path == "/":
            return await call_next(request)
        for prefix in public_paths:
            if path.startswith(prefix):
                return await call_next(request)

        # 需要认证的 API 路径
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "请先登录"}},
            )

        token = auth_header[7:]
        payload = decode_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "TOKEN_EXPIRED", "message": "登录已过期，请重新登录"}},
            )

        request.state.user_id = int(payload["sub"])
        request.state.username = payload.get("username", "")
        request.state.role = payload.get("role", "analyst")
        return await call_next(request)