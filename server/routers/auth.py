# 用户认证路由：注册、登录

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.models import get_db
from server.services.auth_service import register_user, authenticate_user, create_token
from server.routers.error_handlers import AppError
from server.services.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    email: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await register_user(db, body.username, body.password, body.email)
    except ValueError as e:
        raise AppError(code="USER_EXISTS", message=str(e), status_code=409)
    token = create_token({"sub": str(user.id), "username": user.username, "role": user.role})
    logger.info(f"新用户注册 username={user.username}")
    return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.username, body.password)
    if not user:
        raise AppError(code="AUTH_FAILED", message="用户名或密码错误", status_code=401)
    token = create_token({"sub": str(user.id), "username": user.username, "role": user.role})
    logger.info(f"用户登录 username={user.username}")
    return TokenResponse(access_token=token, username=user.username, role=user.role)