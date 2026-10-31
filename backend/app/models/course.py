from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    course_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    credits: Mapped[int] = mapped_column(Integer, nullable=False)

    course_type: Mapped[str] = mapped_column(String(50), nullable=False)

    department: Mapped[str | None] = mapped_column(String(100), nullable=True)

    open_semesters: Mapped[str | None] = mapped_column(String(50), nullable=True)
