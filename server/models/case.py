# 案件（Case）数据模型

from datetime import datetime
from sqlalchemy import String, DateTime, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.models.database import Base
import enum


# 案件状态枚举
class CaseStatus(str, enum.Enum):
    OPEN = "open"
    ANALYZING = "analyzing"
    CLOSED = "closed"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="案件编号")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="案件名称")
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True, comment="案件描述")
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status", create_constraint=True),
        default=CaseStatus.OPEN,
        nullable=False,
        comment="案件状态",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关联
    evidences: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="case", lazy="selectin")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="case", lazy="selectin")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="case", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Case(id={self.id}, case_number='{self.case_number}', status='{self.status}')>"
