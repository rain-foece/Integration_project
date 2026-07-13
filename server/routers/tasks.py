"""任务创建/查询/取消路由。"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from server.models import get_db, TaskStatus
from server.services import task_service
from server.routers.error_handlers import AppError

router = APIRouter(prefix="/tasks", tags=["任务管理"])


# ========== Pydantic Schema ==========

class TaskCreateRequest(BaseModel):
    """创建任务请求。"""
    case_id: int = Field(..., description="关联案件 ID")
    tool_name: str = Field(..., min_length=1, max_length=128, description="工具名称")
    params: dict | None = Field(None, description="工具参数")
    evidence_id: int | None = Field(None, description="关联证据 ID")


class TaskResponse(BaseModel):
    """任务响应。"""
    id: int
    case_id: int
    evidence_id: int | None
    tool_name: str
    params: dict | None
    status: TaskStatus
    progress: int = 0
    result_path: str | None
    celery_task_id: str | None
    start_time: str | None
    end_time: str | None
    error_message: str | None
    created_at: str

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """任务列表响应。"""
    items: list[TaskResponse]
    total: int
    skip: int
    limit: int


# ========== 路由 ==========

@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """创建取证任务。

    任务创建后会经由 Celery 异步执行。
    """
    try:
        task = await task_service.create_task(
            db=db,
            case_id=body.case_id,
            tool_name=body.tool_name,
            params=body.params,
            evidence_id=body.evidence_id,
            operator=_get_client_ip(request),
            ip_address=_get_client_ip(request),
        )
        return _task_to_response(task)
    except ValueError as e:
        raise AppError(code="TASK_CREATE_ERROR", message=str(e), status_code=400)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    case_id: int | None = Query(None, description="按案件过滤"),
    status: TaskStatus | None = Query(None, description="按状态过滤"),
    tool_name: str | None = Query(None, description="按工具名称过滤"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取任务列表（分页）。"""
    tasks, total = await task_service.list_tasks(
        db=db,
        case_id=case_id,
        status=status,
        tool_name=tool_name,
        skip=skip,
        limit=limit,
    )
    return TaskListResponse(
        items=[_task_to_response(t) for t in tasks],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个任务详情。"""
    task = await task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise AppError(code="TASK_NOT_FOUND", message=f"任务不存在: task_id={task_id}", status_code=404)
    return _task_to_response(task)


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """取消任务（仅 pending/running 状态可取消）。"""
    success = await task_service.cancel_task(
        db=db,
        task_id=task_id,
        operator=_get_client_ip(request),
        ip_address=_get_client_ip(request),
    )
    if not success:
        raise AppError(
            code="TASK_CANCEL_FAILED",
            message=f"任务取消失败: task_id={task_id}（可能不存在或状态不允许取消）",
            status_code=400,
        )
    return {"message": "任务已取消"}


# ========== 工具函数 ==========

def _task_to_response(task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        case_id=task.case_id,
        evidence_id=task.evidence_id,
        tool_name=task.tool_name,
        params=task.params,
        status=task.status,
        progress=getattr(task, 'progress', 0),
        result_path=task.result_path,
        celery_task_id=task.celery_task_id,
        start_time=task.start_time.isoformat() if task.start_time else None,
        end_time=task.end_time.isoformat() if task.end_time else None,
        error_message=task.error_message,
        created_at=task.created_at.isoformat() if task.created_at else "",
    )


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"