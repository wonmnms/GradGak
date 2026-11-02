"""공통요건 적재 및 프로그램별 DB 조회 경계를 실제 PostgreSQL에서 검증한다."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import NonCreditRequirement
from app.seed_official_ai_group import seed_verified_ai_group
from app.seed_official_common import seed_verified_common_rules
from app.services.rule_repository import get_rule_bundle


@pytest.fixture
def rules_db():
    with SessionLocal() as session:
        try:
            seed_verified_ai_group(session)
            seed_verified_common_rules(session)
            yield session
        finally:
            session.rollback()


def test_common_seed_reuses_four_rule_definitions(rules_db):
    first = seed_verified_common_rules(rules_db)
    second = seed_verified_common_rules(rules_db)
    assert [rule.rule_id for rule in first] == [rule.rule_id for rule in second]
    assert len(second) == 4
    assert {rule.input_field for rule in second} == {"thesis_passed", "topcit_taken"}
    assert all(rule.expected_value is True for rule in second)


@pytest.mark.parametrize("program", ["engineering", "general"])
@pytest.mark.parametrize("sub_major", ["software", "ai"])
def test_bundle_separates_program_rules_and_returns_common_rules_once(rules_db, program, sub_major):
    bundle = get_rule_bundle(rules_db, 2024, program, sub_major)
    expected_programs = ["engineering", "general"] if program == "engineering" else ["general"]
    assert [row["program"] for row in bundle["program_results"]] == expected_programs
    common_codes = [row["code"] for row in bundle["common_requirements"]]
    assert common_codes.count("thesis") == 1
    assert common_codes.count("topcit") == 1
    assert common_codes.count("sub_major_required") == (1 if sub_major == "ai" else 0)
    if sub_major == "ai":
        group = next(
            row for row in bundle["common_requirements"] if row["code"] == "sub_major_required"
        )
        assert group["min_courses"] == 3
        assert len(group["courses"]) == 5
    assert bundle["data_complete"] is False
    assert bundle["pending_data"]


def test_unknown_program_is_not_treated_as_general(rules_db):
    with pytest.raises(ValueError, match="Unsupported program"):
        get_rule_bundle(rules_db, 2024, "invalid", "ai")


def test_missing_year_does_not_fall_back_to_2024(rules_db):
    with pytest.raises(LookupError, match="No rule scope"):
        get_rule_bundle(rules_db, 1999, "general", "ai")


def test_missing_common_rule_is_reported(rules_db):
    rule = rules_db.execute(
        select(NonCreditRequirement).filter_by(admission_year=2024, sub_major="ai", code="topcit")
    ).scalar_one()
    rules_db.delete(rule)
    rules_db.flush()
    with pytest.raises(LookupError, match="Missing common non-credit"):
        get_rule_bundle(rules_db, 2024, "general", "ai")


def test_duplicate_common_rule_is_rejected(rules_db):
    rule = seed_verified_common_rules(rules_db)[0]
    rules_db.add(
        NonCreditRequirement(
            admission_year=rule.admission_year,
            sub_major=rule.sub_major,
            code=rule.code,
            label=rule.label,
            input_field=rule.input_field,
            expected_value=rule.expected_value,
            source_id=rule.source_id,
            source_locator=rule.source_locator,
            reviewer=rule.reviewer,
            reviewed_on=rule.reviewed_on,
        )
    )
    with pytest.raises(IntegrityError) as error:
        rules_db.flush()
    assert error.value.orig.pgcode == "23505"


def test_empty_common_rule_reviewer_is_rejected(rules_db):
    rule = seed_verified_common_rules(rules_db)[0]
    rule.reviewer = "   "
    with pytest.raises(IntegrityError) as error:
        rules_db.flush()
    assert error.value.orig.pgcode == "23514"
