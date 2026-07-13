"""任务（Task）数据模型。"""

from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.models.database import Base
import enum


class TaskStatus(str, enum.Enum):
    """任务状态枚举。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联案件 ID"
    )
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidences.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联证据 ID"
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="工具名称")
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="工具参数（JSON）")
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status", create_constraint=True),
        default=TaskStatus.PENDING,
        nullable=False,
        comment="任务状态",
    )
    result_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="结果文件路径")
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="Celery 任务 ID")
    progress: Mapped[int] = mapped_column(default=0, nullable=False, comment="执行进度 0-100")
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="任务开始时间")
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="任务结束时间")
    error_message: Mapped[str | None] = mapped_column(String(4096), nullable=True, comment="错误信息")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 关联
    case: Mapped["Case"] = relationship("Case", back_populates="tasks")
    evidence: Mapped["Evidence | None"] = relationship("Evidence", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, tool='{self.tool_name}', status='{self.status}')>"