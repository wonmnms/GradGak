"""실제 PostgreSQL의 중복 방지·외래키 제약조건 테스트."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import (
    Course,
    CourseNumber,
    GraduationRequirement,
    RequirementCategory,
    SourceDocument,
)


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


@pytest.fixture
def number_base(db):
    token = uuid4().hex
    courses = [Course(name=f"TEST number {i}") for i in range(2)]
    source = SourceDocument(
        title="TEST", url=f"https://example.invalid/{token}", retrieved_on=date(2099, 1, 1)
    )
    db.add_all([*courses, source])
    db.flush()
    # 실제 과목번호와 겹치지 않도록 영문 Z로 시작하는 가상 번호를 쓴다.
    return courses, source, f"Z{token[:3]}"


def _number(courses, source, number, index=0, **changes):
    values = {
        "course_id": courses[index].course_id,
        "course_number": number,
        "source_id": source.source_id,
    }
    values.update(changes)
    return CourseNumber(**values)


def test_course_can_hold_several_numbers_and_defaults_to_pending(db, number_base):
    courses, source, token = number_base
    rows = [_number(courses, source, f"Y{token[:2]}{i}") for i in range(2)]
    db.add_all(rows)
    db.flush()
    assert [row.review_status for row in rows] == ["pending", "pending"]


def test_same_course_number_on_two_courses_is_rejected(db, number_base):
    courses, source, token = number_base
    db.add(_number(courses, source, token))
    db.flush()
    db.add(_number(courses, source, token, index=1))
    with pytest.raises(IntegrityError) as error:
        db.flush()
    assert error.value.orig.pgcode == "23505"


@pytest.mark.parametrize("bad", ["019", "00-9", "가나다라", " 019"])
def test_course_number_format_is_checked(db, number_base, bad):
    courses, source, _ = number_base
    db.add(_number(courses, source, bad))
    with pytest.raises(IntegrityError) as error:
        db.flush()
    assert error.value.orig.pgcode == "23514"


def test_verified_course_number_needs_reviewer_and_date(db, number_base):
    courses, source, token = number_base
    db.add(_number(courses, source, token, review_status="verified"))
    with pytest.raises(IntegrityError) as error:
        db.flush()
    assert error.value.orig.pgcode == "23514"


def test_course_number_review_status_is_restricted(db, number_base):
    courses, source, token = number_base
    db.add(_number(courses, source, token, review_status="done"))
    with pytest.raises(IntegrityError) as error:
        db.flush()
    assert error.value.orig.pgcode == "23514"
