"""출처 차이로 같은 과목을 중복 생성하지 않는지 검증한다."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Course, CourseAlias, CourseEquivalence, SourceDocument
from app.seed_courses import ensure_course


@pytest.fixture
def identity_data():
    with SessionLocal() as session:
        try:
            token = uuid4().hex
            sources = [
                SourceDocument(
                    title="TEST",
                    url=f"https://example.invalid/{token}/{i}",
                    retrieved_on=date(2099, 1, 1),
                )
                for i in range(2)
            ]
            session.add_all(sources)
            session.flush()
            yield session, sources, token
        finally:
            session.rollback()


def test_different_sources_reuse_same_course(identity_data):
    session, sources, token = identity_data
    first = ensure_course(
        session, name=token, department="TEST", source_id=sources[0].source_id, credits=3
    )
    second = ensure_course(
        session, name=token, department="TEST", source_id=sources[1].source_id, credits=3
    )
    assert first.course_id == second.course_id
    assert second.source_id == sources[0].source_id


def test_known_code_candidate_is_reused(identity_data):
    session, sources, token = identity_data
    course = Course(name=token, department="TEST", course_code=token[:20], credits=3)
    session.add(course)
    session.flush()
    assert (
        ensure_course(
            session, name=token, department="TEST", source_id=sources[0].source_id, credits=3
        ).course_id
        == course.course_id
    )


def test_ambiguous_identity_stops(identity_data):
    session, sources, token = identity_data
    session.add_all([Course(name=token, department="TEST") for _ in range(2)])
    session.flush()
    with pytest.raises(ValueError, match="Ambiguous"):
        ensure_course(session, name=token, department="TEST", source_id=sources[0].source_id)


def test_conflicting_credits_stops(identity_data):
    session, sources, token = identity_data
    ensure_course(session, name=token, department="TEST", source_id=sources[0].source_id, credits=3)
    with pytest.raises(ValueError, match="credits"):
        ensure_course(
            session, name=token, department="TEST", source_id=sources[1].source_id, credits=2
        )


@pytest.mark.parametrize("model", [CourseAlias, CourseEquivalence])
def test_mapping_source_rejects_missing_document(identity_data, model):
    session, _, token = identity_data
    from app.models import GraduationRequirement

    courses = [Course(name=f"{token}-{i}") for i in range(2)]
    requirement = GraduationRequirement(
        admission_year=2099, program="TEST", sub_major=token, total_credits=10
    )
    session.add_all([*courses, requirement])
    session.flush()
    values = {"source_id": -2147483648}
    if model is CourseAlias:
        values.update(course_id=courses[0].course_id, alias_name=token)
    else:
        values.update(
            requirement_id=requirement.requirement_id,
            completed_course_id=courses[0].course_id,
            recognized_course_id=courses[1].course_id,
        )
    session.add(model(**values))
    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.pgcode == "23503"


@pytest.mark.parametrize("model", [CourseAlias, CourseEquivalence])
def test_mapping_evidence_can_be_joined(identity_data, model):
    session, sources, token = identity_data
    from app.models import GraduationRequirement

    courses = [Course(name=f"{token}-{i}") for i in range(2)]
    requirement = GraduationRequirement(
        admission_year=2099, program="TEST", sub_major=token, total_credits=10
    )
    session.add_all([*courses, requirement])
    session.flush()
    values = {"source_id": sources[0].source_id}
    if model is CourseAlias:
        values.update(course_id=courses[0].course_id, alias_name=token)
    else:
        values.update(
            requirement_id=requirement.requirement_id,
            completed_course_id=courses[0].course_id,
            recognized_course_id=courses[1].course_id,
        )
    row = model(**values)
    session.add(row)
    session.flush()
    from sqlalchemy import select

    assert (
        session.scalar(select(SourceDocument).join(model).where(model.source_id == row.source_id))
        == sources[0]
    )
