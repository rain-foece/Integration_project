"""任务编排与调度业务逻辑模块。

使用 asyncio 后台任务直接执行工具适配器，不依赖 Celery/Redis。
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func, update

CST = timezone(timedelta(hours=8))  # 北京时间
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.task import Task, TaskStatus
from server.models.case import Case, CaseStatus
from server.models.evidence import Evidence
from server.models.audit_log import AuditLog
from server.adapters import get_adapter
from server.services.logging import get_logger

logger = get_logger(__name__)

# 全局任务追踪：task_id -> asyncio.Task
_running_tasks: dict[int, asyncio.Task] = {}


async def create_task(
    db: AsyncSession,
    case_id: int,
    tool_name: str,
    params: dict | None = None,
    evidence_id: int | None = None,
    operator: str | None = None,
    ip_address: str | None = None,
) -> Task:
    """创建并提交一个取证任务，直接通过 asyncio 后台执行。"""
    case = await db.execute(select(Case).where(Case.id == case_id))
    case = case.scalar_one_or_none()
    if not case:
        raise ValueError(f"案件不存在: case_id={case_id}")

    if evidence_id:
        evidence = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
        if not evidence.scalar_one_or_none():
            raise ValueError(f"证据不存在: evidence_id={evidence_id}")

    if case.status == CaseStatus.CLOSED:
        raise ValueError(f"案件已关闭，无法创建任务: case_id={case_id}")

    # 获取证据文件路径
    evidence_path = None
    if evidence_id:
        ev = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
        ev = ev.scalar_one_or_none()
        if ev:
            evidence_path = ev.file_path

    task = Task(
        case_id=case_id,
        evidence_id=evidence_id,
        tool_name=tool_name,
        params=params or {},
        status=TaskStatus.PENDING,
        progress=0,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    if case.status == CaseStatus.OPEN:
        case.status = CaseStatus.ANALYZING

    audit = AuditLog(
        case_id=case_id,
        action="task_created",
        detail={"task_id": task.id, "tool_name": tool_name, "evidence_id": evidence_id, "params": params},
        operator=operator,
        ip_address=ip_address,
    )
    db.add(audit)
    await db.flush()

    logger.info(f"任务创建成功 | case_id={case_id}, task_id={task.id}, tool_name={tool_name}")

    # 启动 asyncio 后台任务执行
    asyncio_task = asyncio.create_task(
        _execute_task(db, task, evidence_path, params or {})
    )
    _running_tasks[task.id] = asyncio_task

    return task


async def _execute_task(
    original_db: AsyncSession,
    task: Task,
    evidence_path: str | None,
    params: dict,
):
    """后台执行取证任务，更新状态和进度。"""
    from server.models.database import async_session_factory

    task_id = task.id
    async with async_session_factory() as db:
        try:
            # 更新为 RUNNING
            await db.execute(
                update(Task).where(Task.id == task_id).values(
                    status=TaskStatus.RUNNING,
                    progress=10,
                    start_time=datetime.now(CST),
                )
            )
            await db.commit()

            # 获取适配器
            adapter_cls = get_adapter(task.tool_name)
            if not adapter_cls:
                await _fail_task(db, task_id, f"工具未注册: {task.tool_name}")
                return

            adapter = adapter_cls()

            # 构建参数 → 自动映射 evidence_path 到常见的 file/input 参数名
            run_params = dict(params)
            if evidence_path:
                run_params.setdefault("file_path", evidence_path)
                run_params.setdefault("input", evidence_path)
                run_params.setdefault("file", evidence_path)
                run_params.setdefault("image", evidence_path)

            # 更新进度
            await db.execute(
                update(Task).where(Task.id == task_id).values(progress=30)
            )
            await db.commit()

            # 执行工具
            result = await adapter.run(run_params)

            if result.success:
                await db.execute(
                    update(Task).where(Task.id == task_id).values(
                        status=TaskStatus.COMPLETED,
                        progress=100,
                        end_time=datetime.now(CST),
                        result_path=json.dumps(result.data, ensure_ascii=False) if result.data else None,
                    )
                )
                await db.commit()
                logger.info(f"任务执行完成 | task_id={task_id}, tool_name={task.tool_name}, duration={result.duration}")
            else:
                await _fail_task(db, task_id, result.error or "未知错误")

        except Exception as e:
            await _fail_task(db, task_id, str(e))
        finally:
            _running_tasks.pop(task_id, None)


async def _fail_task(db: AsyncSession, task_id: int, error: str):
    """标记任务失败。"""
    await db.execute(
        update(Task).where(Task.id == task_id).values(
            status=TaskStatus.FAILED,
            progress=0,
            end_time=datetime.now(CST),
            error_message=error[:4000],
        )
    )
    await db.commit()
    logger.error(f"任务执行失败 | task_id={task_id}, error={error}")


async def get_task(db: AsyncSession, task_id: int) -> Task | None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def list_tasks(
    db: AsyncSession,
    case_id: int | None = None,
    status: TaskStatus | None = None,
    tool_name: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Task], int]:
    query = select(Task)
    count_query = select(func.count(Task.id))
    if case_id:
        query = query.where(Task.case_id == case_id)
        count_query = count_query.where(Task.case_id == case_id)
    if status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)
    if tool_name:
        query = query.where(Task.tool_name == tool_name)
        count_query = count_query.where(Task.tool_name == tool_name)
    query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    return list(tasks), total


async def update_task_status(
    db: AsyncSession,
    task_id: int,
    status: TaskStatus,
    result_path: str | None = None,
    error_message: str | None = None,
    celery_task_id: str | None = None,
) -> Task | None:
    task = await get_task(db, task_id)
    if not task:
        return None
    task.status = status
    if result_path is not None:
        task.result_path = result_path
    if error_message is not None:
        task.error_message = error_message
    if celery_task_id is not None:
        task.celery_task_id = celery_task_id
    if status == TaskStatus.RUNNING:
        task.start_time = datetime.now(CST)
    elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        task.end_time = datetime.now(CST)
    await db.flush()
    logger.info(f"任务状态更新 | task_id={task_id}, status={status.value}, tool_name={task.tool_name}")
    return task


async def cancel_task(
    db: AsyncSession,
    task_id: int,
    operator: str | None = None,
    ip_address: str | None = None,
) -> bool:
    task = await get_task(db, task_id)
    if not task:
        return False
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        return False

    # 取消 asyncio task
    asyncio_task = _running_tasks.pop(task_id, None)
    if asyncio_task and not asyncio_task.done():
        asyncio_task.cancel()

    task.status = TaskStatus.FAILED
    task.error_message = "任务已被用户取消"
    task.progress = 0
    task.end_time = datetime.now(CST)

    audit = AuditLog(
        case_id=task.case_id,
        action="task_cancelled",
        detail={"task_id": task_id, "tool_name": task.tool_name},
        operator=operator,
        ip_address=ip_address,
    )
    db.add(audit)
    await db.flush()

    logger.info(f"任务已取消 | task_id={task_id}, case_id={task.case_id}, tool_name={task.tool_name}")
    return True


