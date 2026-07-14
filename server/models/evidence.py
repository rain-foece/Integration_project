# 证据（Evidence）数据模型

from datetime import datetime
from sqlalchemy import String, DateTime, BigInteger, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.models.database import Base


class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联案件 ID"
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, comment="证据文件名称")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, comment="文件存储路径")
    file_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="文件类型/扩展名")
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="SHA-256 哈希值")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="文件大小（字节）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 关联
    case: Mapped["Case"] = relationship("Case", back_populates="evidences")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="evidence", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, name='{self.name}', sha256='{self.sha256_hash[:8]}...')>"
