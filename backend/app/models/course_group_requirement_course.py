from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CourseGroupRequirementCourse(Base):
    __tablename__ = "course_group_requirement_courses"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("course_group_requirements.group_id"),
        primary_key=True,
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.course_id"),
        primary_key=True,
    )
