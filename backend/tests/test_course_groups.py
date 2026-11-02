"""과목 그룹 저장·조회 및 최소 이수 개수 제약조건 테스트."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import (
    Course,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    GraduationRequirement,
)


@pytest.fixture
def db():
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.rollback()


def make_requirement(db):
    requirement = GraduationRequirement(
        admission_year=2099,
        program="TEST",
        sub_major=f"TEST-{uuid4().hex}",
        total_credits=10,
    )
    db.add(requirement)
    db.flush()
    return requirement


def test_group_courses_can_be_saved_and_queried(db):
    requirement = make_requirement(db)

    group = CourseGroupRequirement(
        requirement_id=requirement.requirement_id,
        group_code="TEST_GROUP",
        name="TEST Choose at least two courses",
        min_courses=2,
    )
    db.add(group)
    db.flush()

    expected_codes = set()

    for number in range(3):
        code = f"TEST-{uuid4().hex[:20]}"
        expected_codes.add(code)

        course = Course(
            course_code=code,
            name=f"TEST Group Course {number}",
            credits=3,
            course_type="TEST",
        )
        db.add(course)
        db.flush()

        db.add(
            CourseGroupRequirementCourse(
                group_id=group.group_id,
                course_id=course.course_id,
            )
        )

    db.flush()

    stmt = (
        select(CourseGroupRequirement.min_courses, Course.course_code)
        .select_from(CourseGroupRequirement)
        .join(CourseGroupRequirementCourse)
        .join(Course)
        .where(CourseGroupRequirement.requirement_id == requirement.requirement_id)
    )
    rows = db.execute(stmt).all()

    assert len(rows) == 3
    assert {row.course_code for row in rows} == expected_codes
    assert all(row.min_courses == 2 for row in rows)


@pytest.mark.parametrize("invalid_count", [0, -1])
def test_nonpositive_min_courses_is_rejected(db, invalid_count):
    requirement = make_requirement(db)

    db.add(
        CourseGroupRequirement(
            requirement_id=requirement.requirement_id,
            group_code="TEST_INVALID",
            name="TEST Invalid Group",
            min_courses=invalid_count,
        )
    )

    with pytest.raises(IntegrityError) as error:
        db.flush()

    # PostgreSQL: CHECK 제약조건 위반
    assert error.value.orig.pgcode == "23514"
