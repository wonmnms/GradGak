from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RequirementCategoryCourse(Base):
    __tablename__ = "requirement_category_courses"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_categories.category_id"),
        primary_key=True,
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.course_id"),
        primary_key=True,
    )
