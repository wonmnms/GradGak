from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CourseNumber(Base):
    """과목이 인정하는 4자리 과목번호와 사람의 원본 대조 결과.

    KLAS 학정번호 `학과코드-난이도-과목번호-분반`의 가운데 4자리(영숫자, 앞자리 0 보존)다.
    같은 번호가 두 과목에 걸리면 매칭이 모호해지므로 번호는 전체에서 유일하다.
    매칭에는 review_status='verified'인 행만 쓴다.
    """

    __tablename__ = "course_numbers"

    __table_args__ = (
        CheckConstraint(
            "course_number ~ '^[0-9A-Za-z]{4}$'",
            name="ck_course_number_format",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'verified', 'needs_clarification', 'rejected')",
            name="ck_course_number_review_status",
        ),
        CheckConstraint(
            "review_status <> 'verified' OR "
            "(reviewer IS NOT NULL AND length(trim(reviewer)) > 0 "
            "AND reviewed_on IS NOT NULL)",
            name="ck_course_number_verified_review",
        ),
    )

    course_number_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.course_id"), nullable=False)
    course_number: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_documents.source_id"), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", server_default="pending"
    )
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
