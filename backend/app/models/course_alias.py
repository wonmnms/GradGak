from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CourseAlias(Base):
    __tablename__ = "course_aliases"

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "alias_name",
            name="uq_course_alias",
        ),
    )

    alias_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.course_id"),
        nullable=False,
    )

    alias_name: Mapped[str] = mapped_column(String(200), nullable=False)
