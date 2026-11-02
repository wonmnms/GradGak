from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CourseGroupRequirement(Base):
    __tablename__ = "course_group_requirements"

    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "group_code",
            name="uq_course_group_scope",
        ),
        CheckConstraint(
            "min_courses > 0",
            name="ck_course_group_min_courses_positive",
        ),
    )

    group_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("graduation_requirements.requirement_id"),
        nullable=False,
    )

    group_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    min_courses: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_documents.source_id"), nullable=True
    )
