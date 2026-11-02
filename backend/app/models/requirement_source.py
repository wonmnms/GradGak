from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RequirementSource(Base):
    """졸업요건 범위별 자료 근거와 사람의 원본 대조 결과."""

    __tablename__ = "requirement_sources"

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending', 'verified', 'needs_clarification', 'rejected')",
            name="ck_requirement_source_review_status",
        ),
        CheckConstraint(
            "review_status <> 'verified' OR "
            "(reviewer IS NOT NULL AND length(trim(reviewer)) > 0 "
            "AND reviewed_on IS NOT NULL)",
            name="ck_requirement_source_verified_review",
        ),
    )

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("graduation_requirements.requirement_id"), primary_key=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source_documents.source_id"), primary_key=True
    )
    locator: Mapped[str] = mapped_column(String(500), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", server_default="pending"
    )
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
