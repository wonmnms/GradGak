from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NonCreditRequirement(Base):
    """학번·세부전공별 공통 규칙. 학생 개인의 통과·응시 상태는 저장하지 않는다."""

    __tablename__ = "non_credit_requirements"
    __table_args__ = (
        UniqueConstraint(
            "admission_year", "sub_major", "code", name="uq_non_credit_requirement_scope"
        ),
        CheckConstraint("length(trim(reviewer)) > 0", name="ck_non_credit_reviewer_nonempty"),
    )

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False)
    sub_major: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    input_field: Mapped[str] = mapped_column(String(50), nullable=False)
    expected_value: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_documents.source_id"), nullable=False)
    source_locator: Mapped[str] = mapped_column(String(500), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewed_on: Mapped[date] = mapped_column(Date, nullable=False)
