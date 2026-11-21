"""공식 과목 그룹 적재의 범위·재실행·미확인 정보 처리를 검증한다."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound

from app.db import SessionLocal
from app.models import Course, CourseGroupRequirementCourse, RequirementSource, SourceDocument
from app.seed_official_ai_group import (
    AI_COURSE_CREDITS,
    AI_COURSES,
    COURSE_TABLE_URL,
    CURRICULUM_NOTE,
    CURRICULUM_REVIEW_NOTE,
    CURRICULUM_URL,
    DEEP_LEARNING_LAB,
    LEGACY_CURRICULUM_NOTE,
    LEGACY_CURRICULUM_REVIEW_NOTE,
    seed_verified_ai_group,
)
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
                assert {course.name: course.credits for course in rows} == {
                    "인공지능": 3,
                    "빅데이터처리및응용": 3,
                    "컴퓨터비전": 3,
                    "기계학습": 3,
                    "딥러닝실습": 2,
                }
                sources = {
                    course.name: session.get(SourceDocument, course.source_id).url
                    for course in rows
                }
                assert sources.pop(DEEP_LEARNING_LAB) == COURSE_TABLE_URL
                assert set(sources.values()) == {CURRICULUM_URL}
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


def _source(session, url):
    return session.execute(select(SourceDocument).filter_by(url=url)).scalar_one()


def _deep_learning_lab(session):
    return session.execute(
        select(Course).filter_by(name=DEEP_LEARNING_LAB, department="소프트웨어학부")
    ).scalar_one()


def _restore_legacy_seed(session, groups):
    """2026-11-16 정정 이전 시드가 남긴 상태(딥러닝실습 3학점 등)로 되돌린다."""
    curriculum = _source(session, CURRICULUM_URL)
    course_table = _source(session, COURSE_TABLE_URL)
    course = _deep_learning_lab(session)
    course.credits = 3
    course.source_id = curriculum.source_id
    curriculum.note = LEGACY_CURRICULUM_NOTE
    for group in groups:
        reviews = session.scalars(
            select(RequirementSource).filter_by(requirement_id=group.requirement_id)
        ).all()
        for review in reviews:
            if review.source_id == curriculum.source_id:
                review.note = LEGACY_CURRICULUM_REVIEW_NOTE
            elif review.source_id == course_table.source_id:
                session.delete(review)
    session.flush()
    session.delete(course_table)
    session.flush()


def test_legacy_three_credit_seed_is_corrected_on_rerun():
    with SessionLocal() as session:
        try:
            groups = seed_verified_ai_group(session)
            _restore_legacy_seed(session, groups)
            assert _deep_learning_lab(session).credits == 3

            corrected = seed_verified_ai_group(session)
            seed_verified_ai_group(session)  # 정정 후 재실행도 그대로 통과해야 한다.

            course = _deep_learning_lab(session)
            course_table = _source(session, COURSE_TABLE_URL)
            curriculum = _source(session, CURRICULUM_URL)
            assert course.credits == AI_COURSE_CREDITS[DEEP_LEARNING_LAB] == 2
            assert course.source_id == course_table.source_id
            assert course.course_code is None
            assert curriculum.note == CURRICULUM_NOTE
            for group in corrected:
                reviews = {
                    review.source_id: review
                    for review in session.scalars(
                        select(RequirementSource).filter_by(requirement_id=group.requirement_id)
                    )
                }
                assert reviews[curriculum.source_id].note == CURRICULUM_REVIEW_NOTE
                table_review = reviews[course_table.source_id]
                assert table_review.review_status == "verified"
                assert table_review.reviewer == "박준영, 김남주"
            others = session.scalars(
                select(Course).where(Course.name.in_(AI_COURSES), Course.name != DEEP_LEARNING_LAB)
            ).all()
            assert len(others) == 4 and all(other.credits == 3 for other in others)
        finally:
            session.rollback()


@pytest.mark.parametrize("credits, use_curriculum_source", [(4, True), (3, False)])
def test_unexpected_deep_learning_lab_state_still_conflicts(credits, use_curriculum_source):
    with SessionLocal() as session:
        try:
            seed_verified_ai_group(session)
            course = _deep_learning_lab(session)
            course.credits = credits
            if use_curriculum_source:
                course.source_id = _source(session, CURRICULUM_URL).source_id
            session.flush()
            # 정정은 정정 전 시드가 만든 정확한 상태에만 적용하고 그 밖의 값은 덮어쓰지 않는다.
            with pytest.raises(ValueError, match="Existing Course conflicts"):
                seed_verified_ai_group(session)
        finally:
            session.rollback()
