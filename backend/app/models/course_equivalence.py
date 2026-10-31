from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CourseEquivalence(Base):
    __tablename__ = "course_equivalences"

    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "completed_course_id",
            "recognized_course_id",
            name="uq_course_equivalence_scope",
        ),
        CheckConstraint(
            "completed_course_id <> recognized_course_id",
            name="ck_course_equivalence_different_courses",
        ),
    )

    equivalence_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("graduation_requirements.requirement_id"),
        nullable=False,
    )

    completed_course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.course_id"),
        nullable=False,
    )

    recognized_course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.course_id"),
        nullable=False,
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
