"""가상 자료로 출처 저장과 검증 기록 제약조건을 검사한다."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import GraduationRequirement, RequirementSource, SourceDocument


@pytest.fixture
def source_data():
    with SessionLocal() as session:
        try:
            token = uuid4().hex
            requirement = GraduationRequirement(
                admission_year=2099,
                program="TEST",
                sub_major=f"TEST-{token}",
                total_credits=10,
            )
            source = SourceDocument(
                title="TEST Fictional Source",
                url=f"https://example.invalid/test/{token}",
                retrieved_on=date(2099, 1, 1),
                note="Fictional data for automated tests only",
            )
            session.add_all([requirement, source])
            session.flush()
            yield session, requirement, source
        finally:
            session.rollback()


def test_review_defaults_to_pending(source_data):
    session, requirement, source = source_data
    review = RequirementSource(
        requirement_id=requirement.requirement_id,
        source_id=source.source_id,
        locator="TEST section",
    )
    session.add(review)
    session.flush()
    session.refresh(review)

    assert review.review_status == "pending"
    assert review.reviewer is None
    assert review.reviewed_on is None


def test_verified_review_can_be_saved_with_reviewer_and_date(source_data):
    session, requirement, source = source_data
    review = RequirementSource(
        requirement_id=requirement.requirement_id,
        source_id=source.source_id,
        locator="TEST section",
        review_status="verified",
        reviewer="TEST_REVIEWER",
        reviewed_on=date(2099, 1, 2),
    )
    session.add(review)
    session.flush()
    session.refresh(review)

    assert review.review_status == "verified"
    assert review.reviewer == "TEST_REVIEWER"
    assert review.reviewed_on == date(2099, 1, 2)


@pytest.mark.parametrize(
    ("reviewer", "reviewed_on"),
    [
        (None, date(2099, 1, 2)),
        ("", date(2099, 1, 2)),
        ("   ", date(2099, 1, 2)),
        ("TEST_REVIEWER", None),
    ],
)
def test_verified_review_requires_reviewer_and_date(source_data, reviewer, reviewed_on):
    session, requirement, source = source_data
    session.add(
        RequirementSource(
            requirement_id=requirement.requirement_id,
            source_id=source.source_id,
            locator="TEST section",
            review_status="verified",
            reviewer=reviewer,
            reviewed_on=reviewed_on,
        )
    )

    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.pgcode == "23514"


def test_unknown_review_status_is_rejected(source_data):
    session, requirement, source = source_data
    session.add(
        RequirementSource(
            requirement_id=requirement.requirement_id,
            source_id=source.source_id,
            locator="TEST section",
            review_status="not_a_valid_status",
        )
    )

    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.pgcode == "23514"


def test_duplicate_source_url_and_retrieval_date_is_rejected(source_data):
    session, _, source = source_data
    session.add(
        SourceDocument(
            title="TEST Duplicate Source",
            url=source.url,
            retrieved_on=source.retrieved_on,
        )
    )

    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.pgcode == "23505"
