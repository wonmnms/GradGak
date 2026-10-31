from datetime import date

from sqlalchemy import Date, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SourceDocument(Base):
    """조회 시점별 학사자료 출처. 조회 자체는 사람의 검증 완료를 뜻하지 않는다."""

    __tablename__ = "source_documents"

    __table_args__ = (UniqueConstraint("url", "retrieved_on", name="uq_source_document_snapshot"),)

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    retrieved_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
