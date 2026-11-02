"""실제 PostgreSQL의 중복 방지·외래키 제약조건 테스트."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Course, GraduationRequirement, RequirementCategory


@pytest.fixture
def db():
    with SessionLocal() as session:
        try:
            yield session
        finally:
            # 테스트에서 넣은 데이터는 저장하지 않는다.
            session.rollback()


def test_duplicate_course_code_is_rejected(db):
    code = f"TEST-{uuid4().hex[:20]}"

    db.add(
        Course(
            course_code=code,
            name="TEST First Course",
            credits=3,
            course_type="TEST",
        )
    )
    db.flush()

    db.add(
        Course(
            course_code=code,
            name="TEST Duplicate Course",
            credits=3,
            course_type="TEST",
        )
    )

    with pytest.raises(IntegrityError) as error:
        db.flush()

    # PostgreSQL: UNIQUE 제약조건 위반
    assert error.value.orig.pgcode == "23505"


def test_category_with_missing_requirement_is_rejected(db):
    max_id = db.scalar(select(func.max(GraduationRequirement.requirement_id)))
    missing_id = (max_id or 0) + 1

    db.add(
        RequirementCategory(
            requirement_id=missing_id,
            category="TEST_INVALID",
            min_credits=3,
        )
    )

    with pytest.raises(IntegrityError) as error:
        db.flush()

    # PostgreSQL: 외래키 제약조건 위반
    assert error.value.orig.pgcode == "23503"
