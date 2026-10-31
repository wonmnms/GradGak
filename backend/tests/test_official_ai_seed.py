"""공식 과목 그룹 적재의 범위·재실행·미확인 정보 처리를 검증한다."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound

from app.db import SessionLocal
from app.models import Course, CourseGroupRequirementCourse
from app.seed_official_ai_group import AI_COURSES, seed_verified_ai_group
from app.seed_official_credits import ensure_record


def test_ai_group_seed_links_exactly_five_courses_and_is_repeatable():
    with SessionLocal() as session:
        try:
            first = seed_verified_ai_group(session)
            second = seed_verified_ai_group(session)
            assert [group.group_id for group in first] == [group.group_id for group in second]
            assert len(second) == 2
            for group in second:
                rows = session.scalars(
                    select(Course)
                    .join(CourseGroupRequirementCourse)
                    .where(CourseGroupRequirementCourse.group_id == group.group_id)
                ).all()
                assert group.min_courses == 3
                assert group.source_id is not None
                assert len(rows) == 5
                assert {course.name for course in rows} == set(AI_COURSES)
                assert all(course.credits == 3 and course.source_id is not None for course in rows)
                # 이 시드는 미확인 학수번호나 이수구분을 만들어 넣지 않는다.
                assert all(
                    course.course_code is None and course.course_type is None for course in rows
                )
        finally:
            session.rollback()


def test_different_unknown_course_codes_can_coexist():
    with SessionLocal() as session:
        try:
            courses = [Course(name=f"TEST Unknown {uuid4().hex}", credits=3) for _ in range(2)]
            session.add_all(courses)
            session.flush()
            assert courses[0].course_id != courses[1].course_id
            assert all(course.course_code is None for course in courses)
        finally:
            session.rollback()


def test_name_based_seed_stops_if_course_identity_is_ambiguous():
    with SessionLocal() as session:
        try:
            keys = {"name": f"TEST Ambiguous {uuid4().hex}", "department": "TEST"}
            session.add_all([Course(**keys, credits=3), Course(**keys, credits=3)])
            session.flush()
            with pytest.raises(MultipleResultsFound):
                ensure_record(session, Course, keys, {"credits": 3})
        finally:
            session.rollback()
