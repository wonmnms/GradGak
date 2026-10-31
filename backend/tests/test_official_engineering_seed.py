"""공학 필수과목·캡스톤 택1·하위 학점 조건의 저장 및 조회 검증."""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Course,
    CourseGroupRequirementCourse,
    GraduationRequirement,
    RequirementCategory,
)
from app.seed_official_ai_group import seed_verified_ai_group
from app.seed_official_common import seed_verified_common_rules
from app.seed_official_engineering import (
    CAPSTONE_COURSES,
    REQUIRED_COURSES,
    _attach_parent,
    seed_verified_engineering_rules,
)
from app.services.rule_repository import get_rule_bundle


@pytest.fixture
def engineering_db():
    with SessionLocal() as session:
        try:
            seed_verified_ai_group(session)
            seed_verified_common_rules(session)
            seed_verified_engineering_rules(session)
            yield session
        finally:
            session.rollback()


def test_required_groups_are_repeatable_and_link_exact_courses(engineering_db):
    first = seed_verified_engineering_rules(engineering_db)
    second = seed_verified_engineering_rules(engineering_db)
    assert [row.group_id for row in first] == [row.group_id for row in second]
    assert len(second) == 12
    for group in second:
        courses = engineering_db.scalars(
            select(Course)
            .join(CourseGroupRequirementCourse)
            .where(CourseGroupRequirementCourse.group_id == group.group_id)
        ).all()
        expected = (
            set(CAPSTONE_COURSES)
            if group.group_code == "required_capstone"
            else {dict(REQUIRED_COURSES)[group.group_code]}
        )
        assert {course.name for course in courses} == expected
        assert len(courses) == len(expected)
        assert group.min_courses == 1
        assert all(course.credits is None and course.course_code is None for course in courses)


def test_nested_credits_are_returned_as_subconditions(engineering_db):
    bundle = get_rule_bundle(engineering_db, 2024, "engineering", "ai")
    categories = {row["code"]: row for row in bundle["program_results"][0]["categories"]}
    assert categories["basic_math_science"]["min_credits"] == 12
    assert categories["basic_math"]["min_credits"] == 6
    assert categories["basic_science"]["min_credits"] == 3
    assert categories["basic_math"]["parent_code"] == "basic_math_science"
    assert categories["basic_science"]["parent_code"] == "basic_math_science"
    assert categories["engineering_design"]["parent_code"] == "engineering_subject"


def test_engineering_required_groups_are_not_applied_to_general(engineering_db):
    engineering = get_rule_bundle(engineering_db, 2024, "engineering", "software")
    assert len(engineering["program_results"][0]["course_groups"]) == 6
    general = get_rule_bundle(engineering_db, 2024, "general", "software")
    assert general["program_results"][0]["course_groups"] == []


def test_parent_from_another_requirement_is_rejected(engineering_db):
    requirements = engineering_db.scalars(
        select(GraduationRequirement).filter_by(admission_year=2024, program="engineering")
    ).all()
    first, second = requirements
    child = engineering_db.execute(
        select(RequirementCategory).filter_by(
            requirement_id=first.requirement_id, category="basic_math"
        )
    ).scalar_one()
    wrong_parent = engineering_db.execute(
        select(RequirementCategory).filter_by(
            requirement_id=second.requirement_id, category="basic_math_science"
        )
    ).scalar_one()
    with pytest.raises(ValueError, match="another requirement"):
        _attach_parent(child, wrong_parent)


def test_self_parent_is_rejected(engineering_db):
    category = engineering_db.scalars(
        select(RequirementCategory).filter_by(category="basic_math")
    ).first()
    with pytest.raises(ValueError, match="own parent"):
        _attach_parent(category, category)
