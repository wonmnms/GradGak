from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.graduation_requirement import GraduationRequirement


class RequirementCategory(Base):
    __tablename__ = "requirement_categories"

    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "category",
            name="uq_requirement_category",
        ),
    )

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("graduation_requirements.requirement_id"),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(String(50), nullable=False)

    min_credits: Mapped[int] = mapped_column(Integer, nullable=False)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    graduation_requirement: Mapped["GraduationRequirement"] = relationship("GraduationRequirement")
