from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GraduationRequirement(Base):
    __tablename__ = "graduation_requirements"

    __table_args__ = (
        UniqueConstraint(
            "admission_year",
            "program",
            "sub_major",
            name="uq_graduation_requirements_scope",
        ),
    )

    requirement_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    admission_year: Mapped[int] = mapped_column(Integer, nullable=False)

    program: Mapped[str] = mapped_column(String(20), nullable=False)

    sub_major: Mapped[str] = mapped_column(String(50), nullable=False)

    total_credits: Mapped[int] = mapped_column(Integer, nullable=False)
