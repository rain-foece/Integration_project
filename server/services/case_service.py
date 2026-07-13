"""案件业务逻辑模块。"""

from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))  # 北京时间
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from server.models.case import Case, CaseStatus
from server.models.audit_log import AuditLog
from server.services.logging import get_logger

logger = get_logger(__name__)


async def create_case(
    db: AsyncSession,
    case_number: str,
    name: str,
    description: str | None = None,
    operator: str | None = None,
    ip_address: str | None = None,
) -> Case:
    """创建新案件。

    Args:
        db: 数据库会话
        case_number: 案件编号（唯一）
        name: 案件名称
        description: 案件描述
        operator: 操作人
        ip_address: 操作人 IP 地址

    Returns:
        创建的 Case 实例

    Raises:
        ValueError: 案件编号已存在
    """
    # 检查案件编号是否已存在
    existing = await db.execute(select(Case).where(Case.case_number == case_number))
    if existing.scalar_one_or_none():
        raise ValueError(f"案件编号已存在: {case_number}")

    case = Case(
        case_number=case_number,
        name=name,
        description=description,
        status=CaseStatus.OPEN,
    )
    db.add(case)
    await db.flush()

    # 记录审计日志
    audit = AuditLog(
        case_id=case.id,
        action="case_created",
        detail={"case_number": case_number, "name": name},
        operator=operator,
        ip_address=ip_address,
    )
    db.add(audit)
    await db.flush()

    logger.info(f"案件创建成功 | case_id={case.id}, case_number={case_number}")
    return case


async def get_case(db: AsyncSession, case_id: int) -> Case | None:
    """获取单个案件详情（含关联数据）。

    Args:
        db: 数据库会话
        case_id: 案件 ID

    Returns:
        Case 实例或 None
    """
    result = await db.execute(
        select(Case)
        .options(selectinload(Case.evidences), selectinload(Case.tasks), selectinload(Case.reports))
        .where(Case.id == case_id)
    )
    return result.scalar_one_or_none()


async def list_cases(
    db: AsyncSession,
    status: CaseStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Case], int]:
    """分页获取案件列表。

    Args:
        db: 数据库会话
        status: 按状态过滤（可选）
        skip: 偏移量
        limit: 每页数量

    Returns:
        (案件列表, 总数量)
    """
    query = select(Case)
    count_query = select(func.count(Case.id))

    if status:
        query = query.where(Case.status == status)
        count_query = count_query.where(Case.status == status)

    query = query.order_by(Case.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    cases = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return list(cases), total


async def update_case(
    db: AsyncSession,
    case_id: int,
    name: str | None = None,
    description: str | None = None,
    status: CaseStatus | None = None,
    operator: str | None = None,
    ip_address: str | None = None,
) -> Case | None:
    """更新案件信息。

    Args:
        db: 数据库会话
        case_id: 案件 ID
        name: 新名称
        description: 新描述
        status: 新状态
        operator: 操作人
        ip_address: 操作人 IP 地址

    Returns:
        更新后的 Case 实例或 None
    """
    case = await get_case(db, case_id)
    if not case:
        return None

    changes = {}
    if name is not None:
        case.name = name
        changes["name"] = name
    if description is not None:
        case.description = description
        changes["description"] = description
    if status is not None:
        case.status = status
        changes["status"] = status.value

    if changes:
        case.updated_at = datetime.now(CST)

        # 记录审计日志
        audit = AuditLog(
            case_id=case.id,
            action="case_updated",
            detail={"changes": changes},
            operator=operator,
            ip_address=ip_address,
        )
        db.add(audit)
        await db.flush()

    logger.info(f"案件更新成功 | case_id={case_id}, changes={changes}")
    return case


async def delete_case(
    db: AsyncSession,
    case_id: int,
    operator: str | None = None,
    ip_address: str | None = None,
) -> bool:
    """删除案件（级联删除关联证据、任务、报告）。

    Args:
        db: 数据库会话
        case_id: 案件 ID
        operator: 操作人
        ip_address: 操作人 IP 地址

    Returns:
        是否删除成功
    """
    case = await db.execute(select(Case).where(Case.id == case_id))
    case = case.scalar_one_or_none()
    if not case:
        return False

    # 记录审计日志（在删除前记录）
    audit = AuditLog(
        case_id=case_id,
        action="case_deleted",
        detail={"case_number": case.case_number, "name": case.name},
        operator=operator,
        ip_address=ip_address,
    )
    db.add(audit)
    await db.flush()

    await db.delete(case)
    await db.flush()

    logger.info(f"案件删除成功 | case_id={case_id}, case_number={case.case_number}")
    return True


