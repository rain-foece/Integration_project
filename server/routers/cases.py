# 案件（Case）CRUD 路由

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from server.models import get_db, CaseStatus
from server.services import case_service
from server.routers.error_handlers import AppError, error_response

router = APIRouter(prefix="/cases", tags=["案件管理"])


# 创建案件请求
class CaseCreateRequest(BaseModel):
    case_number: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(None, max_length=2048)


# 更新案件请求
class CaseUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=2048)
    status: CaseStatus | None = Field(None)


# 案件响应
class CaseResponse(BaseModel):
    id: int
    case_number: str
    name: str
    description: str | None
    status: CaseStatus
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# 案件列表响应
class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    skip: int
    limit: int


# 创建新案件
@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    body: CaseCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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


# 获取案件列表（分页）
@router.get("", response_model=CaseListResponse)
async def list_cases(
    status: CaseStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    cases, total = await case_service.list_cases(db=db, status=status, skip=skip, limit=limit)
    return CaseListResponse(
        items=[_case_to_response(c) for c in cases],
        total=total,
        skip=skip,
        limit=limit,
    )


# 获取单个案件详情
@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
):
    case = await case_service.get_case(db=db, case_id=case_id)
    if not case:
        raise AppError(code="CASE_NOT_FOUND", message=f"案件不存在: case_id={case_id}", status_code=404)
    return _case_to_response(case)


# 更新案件信息
@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: int,
    body: CaseUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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


# 删除案件（级联删除关联数据）
@router.delete("/{case_id}")
async def delete_case(
    case_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    success = await case_service.delete_case(
        db=db,
        case_id=case_id,
        operator=_get_client_ip(request),
        ip_address=_get_client_ip(request),
    )
    if not success:
        raise AppError(code="CASE_NOT_FOUND", message=f"案件不存在: case_id={case_id}", status_code=404)
    return {"message": "案件已删除"}


# 将 Case 模型转换为响应对象
def _case_to_response(case) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        name=case.name,
        description=case.description,
        status=case.status,
        created_at=case.created_at.isoformat() if case.created_at else "",
        updated_at=case.updated_at.isoformat() if case.updated_at else "",
    )


# 获取客户端 IP 地址
def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
