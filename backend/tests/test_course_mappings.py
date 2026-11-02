"""실제 PostgreSQL에서 가상 과목의 별칭·대체 인정 규칙을 검증한다."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Course, CourseAlias, CourseEquivalence, GraduationRequirement


@pytest.fixture
def mapping_data():
    with SessionLocal() as session:
        try:
            token = uuid4().hex[:16]
            courses = [
                Course(
                    course_code=f"TEST-{token}-{index}",
                    name=f"TEST Course {index}",
                    credits=3,
                    course_type="TEST",
                )
                for index in range(2)
            ]
            requirements = [
                GraduationRequirement(
                    admission_year=2099,
                    program=program,
                    sub_major=f"TEST-{token}",
                    total_credits=10,
                )
                for program in ("TEST_A", "TEST_B")
            ]
            session.add_all([*courses, *requirements])
            session.flush()
            yield session, courses, requirements
        finally:
            session.rollback()


def test_alias_lookup_returns_linked_course(mapping_data):
    session, courses, _ = mapping_data
    alias = f"TEST Previous Name {uuid4().hex}"
    session.add(CourseAlias(course_id=courses[0].course_id, alias_name=alias))
    session.flush()

    result = session.scalars(
        select(Course).join(CourseAlias).where(CourseAlias.alias_name == alias)
    ).all()

    assert [course.course_id for course in result] == [courses[0].course_id]


def test_duplicate_alias_for_same_course_is_rejected(mapping_data):
    session, courses, _ = mapping_data
    values = {"course_id": courses[0].course_id, "alias_name": "TEST Duplicate"}
    session.add(CourseAlias(**values))
    session.flush()
    session.add(CourseAlias(**values))

    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.pgcode == "23505"


def test_same_alias_can_return_multiple_candidates(mapping_data):
    session, courses, _ = mapping_data
    alias = f"TEST Ambiguous Name {uuid4().hex}"
    session.add_all(
        [CourseAlias(course_id=course.course_id, alias_name=alias) for course in courses]
    )
    session.flush()

    result = session.scalars(
        select(Course.course_id).join(CourseAlias).where(CourseAlias.alias_name == alias)
    ).all()
    assert set(result) == {course.course_id for course in courses}


@pytest.mark.parametrize(
    ("requirement_index", "completed_index", "recognized_index", "expected"),
    [(0, 0, 1, True), (0, 1, 0, False), (1, 0, 1, False)],
)
def test_equivalence_lookup_respects_scope_and_direction(
    mapping_data, requirement_index, completed_index, recognized_index, expected
):
    session, courses, requirements = mapping_data
    session.add(
        CourseEquivalence(
            requirement_id=requirements[0].requirement_id,
            completed_course_id=courses[0].course_id,
            recognized_course_id=courses[1].course_id,
        )
    )
    session.flush()

    result = session.scalar(
        select(CourseEquivalence.equivalence_id).where(
            CourseEquivalence.requirement_id == requirements[requirement_index].requirement_id,
            CourseEquivalence.completed_course_id == courses[completed_index].course_id,
            CourseEquivalence.recognized_course_id == courses[recognized_index].course_id,
        )
    )
    assert (result is not None) == expected


def test_duplicate_equivalence_is_rejected(mapping_data):
    session, courses, requirements = mapping_data
    values = {
        "requirement_id": requirements[0].requirement_id,
        "completed_course_id": courses[0].course_id,
        "recognized_course_id": courses[1].course_id,
    }
    session.add(CourseEquivalence(**values))
    session.flush()
    session.add(CourseEquivalence(**values))

    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.pgcode == "23505"


def test_self_equivalence_is_rejected(mapping_data):
    session, courses, requirements = mapping_data
    session.add(
        CourseEquivalence(
            requirement_id=requirements[0].requirement_id,
            completed_course_id=courses[0].course_id,
            recognized_course_id=courses[0].course_id,
        )
    )

    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.pgcode == "23514"
