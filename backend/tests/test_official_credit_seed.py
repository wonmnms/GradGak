"""검증된 초기 학점 데이터의 반복 적재·충돌 처리를 검증한다."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import GraduationRequirement, RequirementCategory, RequirementSource, SourceDocument
from app.seed_official_credits import (
    CREDIT_RULES,
    SOURCE_URL,
    ensure_record,
    seed_verified_credit_rules,
)


def test_credit_seed_is_repeatable_and_contains_only_reviewed_scopes():
    with SessionLocal() as session:
        try:
            first = seed_verified_credit_rules(session)
            second = seed_verified_credit_rules(session)
            ids = [item.requirement_id for item in second]
            assert ids == [item.requirement_id for item in first]
            assert len(set(ids)) == 4
            assert {(item.program, item.sub_major) for item in second} == {
                ("engineering", "software"),
                ("engineering", "ai"),
                ("general", "software"),
                ("general", "ai"),
            }
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(RequirementCategory)
                    .where(
                        RequirementCategory.requirement_id.in_(ids),
                        RequirementCategory.category.in_(
                            {code for rows in CREDIT_RULES.values() for code, _, _ in rows}
                        ),
                    )
                )
                == 16
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(RequirementSource)
                    .join(SourceDocument)
                    .where(
                        RequirementSource.requirement_id.in_(ids),
                        RequirementSource.review_status == "verified",
                        SourceDocument.url == SOURCE_URL,
                    )
                )
                == 4
            )
            general_ids = [item.requirement_id for item in second if item.program == "general"]
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(RequirementCategory)
                    .where(
                        RequirementCategory.requirement_id.in_(general_ids),
                        RequirementCategory.category == "basic_math_science",
                    )
                )
                == 0
            )
        finally:
            session.rollback()


def test_seed_conflict_does_not_overwrite_existing_value():
    with SessionLocal() as session:
        try:
            keys = {
                "admission_year": 2099,
                "program": "TEST",
                "sub_major": f"TEST-{uuid4().hex}",
            }
            record = ensure_record(session, GraduationRequirement, keys, {"total_credits": 10})
            with pytest.raises(ValueError, match="conflicts"):
                ensure_record(session, GraduationRequirement, keys, {"total_credits": 11})
            session.refresh(record)
            assert record.total_credits == 10
        finally:
            session.rollback()
