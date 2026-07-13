"""报告（Report）数据模型。"""

from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.models.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联案件 ID"
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="报告标题")
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="报告内容（JSON 结构）")
    html_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="HTML 报告路径")
    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="PDF 报告路径")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 关联
    case: Mapped["Case"] = relationship("Case", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, title='{self.title}')>"