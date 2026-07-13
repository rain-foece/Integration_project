"""审计日志（AuditLog）数据模型。"""

from datetime import datetime
from sqlalchemy import String, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from server.models.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int | None] = mapped_column(
        nullable=True, index=True, comment="关联案件 ID"
    )
    action: Mapped[str] = mapped_column(String(256), nullable=False, comment="操作动作")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="操作详情（JSON）")
    operator: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="操作人")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, comment="操作人 IP 地址")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', operator='{self.operator}')>"