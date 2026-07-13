"""案件（Case）CRUD 路由。"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from server.models import get_db, CaseStatus
from server.services import case_service
from server.routers.error_handlers import AppError, error_response

router = APIRouter(prefix="/cases", tags=["案件管理"])


# ========== Pydantic Schema ==========

class CaseCreateRequest(BaseModel):
    """创建案件请求。"""
    case_number: str = Field(..., min_length=1, max_length=64, description="案件编号")
    name: str = Field(..., min_length=1, max_length=256, description="案件名称")
    description: str | None = Field(None, max_length=2048, description="案件描述")


class CaseUpdateRequest(BaseModel):
    """更新案件请求。"""
    name: str | None = Field(None, max_length=256, description="案件名称")
    description: str | None = Field(None, max_length=2048, description="案件描述")
    status: CaseStatus | None = Field(None, description="案件状态")


class CaseResponse(BaseModel):
    """案件响应。"""
    id: int
    case_number: str
    name: str
    description: str | None
    status: CaseStatus
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CaseListResponse(BaseModel):
    """案件列表响应。"""
    items: list[CaseResponse]
    total: int
    skip: int
    limit: int


# ========== 路由 ==========

@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    body: CaseCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """创建新案件。"""
    try:
        case = await case_service.create_case(
            db=db,
            case_number=body.case_number,
            name=body.name,
            description=body.description,
            operator=_get_client_ip(request),
            ip_address=_get_client_ip(request),
        )
        return _case_to_response(case)
    except ValueError as e:
        raise AppError(code="CASE_CREATE_ERROR", message=str(e), status_code=400)


@router.get("", response_model=CaseListResponse)
async def list_cases(
    status: CaseStatus | None = Query(None, description="按状态过滤"),
    skip: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取案件列表（分页）。"""
    cases, total = await case_service.list_cases(db=db, status=status, skip=skip, limit=limit)
    return CaseListResponse(
        items=[_case_to_response(c) for c in cases],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个案件详情。"""
    case = await case_service.get_case(db=db, case_id=case_id)
    if not case:
        raise AppError(code="CASE_NOT_FOUND", message=f"案件不存在: case_id={case_id}", status_code=404)
    return _case_to_response(case)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: int,
    body: CaseUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """更新案件信息。"""
    case = await case_service.update_case(
        db=db,
        case_id=case_id,
        name=body.name,
        description=body.description,
        status=body.status,
        operator=_get_client_ip(request),
        ip_address=_get_client_ip(request),
    )
    if not case:
        raise AppError(code="CASE_NOT_FOUND", message=f"案件不存在: case_id={case_id}", status_code=404)
    return _case_to_response(case)


@router.delete("/{case_id}")
async def delete_case(
    case_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """删除案件（级联删除关联数据）。"""
    success = await case_service.delete_case(
        db=db,
        case_id=case_id,
        operator=_get_client_ip(request),
        ip_address=_get_client_ip(request),
    )
    if not success:
        raise AppError(code="CASE_NOT_FOUND", message=f"案件不存在: case_id={case_id}", status_code=404)
    return {"message": "案件已删除"}


# ========== 工具函数 ==========

def _case_to_response(case) -> CaseResponse:
    """将 Case 模型转换为响应对象。"""
    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        name=case.name,
        description=case.description,
        status=case.status,
        created_at=case.created_at.isoformat() if case.created_at else "",
        updated_at=case.updated_at.isoformat() if case.updated_at else "",
    )


def _get_client_ip(request: Request) -> str:
    """获取客户端 IP 地址。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"