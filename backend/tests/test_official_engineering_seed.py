"""공학 필수과목·캡스톤 택1·하위 학점 조건과 일반 캡스톤 택1의 저장 및 조회 검증."""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Course,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    GraduationRequirement,
    RequirementCategory,
    RequirementSource,
    SourceDocument,
)
from app.seed_official_ai_group import seed_verified_ai_group
from app.seed_official_common import seed_verified_common_rules
from app.seed_official_credits import SOURCE_URL
from app.seed_official_engineering import (
    BYLAW_RETRIEVED_ON,
    BYLAW_URL,
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
    # 공학 6개 x 2 세부전공 + 일반 캡스톤 1개 x 2 세부전공
    assert len(second) == 14
    assert sum(group.group_code == "required_capstone" for group in second) == 4
    linked_course_ids = []
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
        linked_course_ids.extend(course.course_id for course in courses)
    assert len(linked_course_ids) == 18
    assert len(set(linked_course_ids)) == 7


def test_nested_credits_are_returned_as_subconditions(engineering_db):
    bundle = get_rule_bundle(engineering_db, 2024, "engineering", "ai")
    categories = {row["code"]: row for row in bundle["program_results"][0]["categories"]}
    assert categories["basic_math_science"]["min_credits"] == 12
    assert categories["basic_math"]["min_credits"] == 6
    assert categories["basic_science"]["min_credits"] == 3
    assert categories["basic_math"]["parent_code"] == "basic_math_science"
    assert categories["basic_science"]["parent_code"] == "basic_math_science"
    assert categories["engineering_design"]["parent_code"] == "engineering_subject"


@pytest.mark.parametrize("sub_major", ["software", "ai"])
def test_general_gets_only_capstone_group(engineering_db, sub_major):
    engineering = get_rule_bundle(engineering_db, 2024, "engineering", sub_major)
    eng_result, general_result = engineering["program_results"]
    assert len(eng_result["course_groups"]) == 6
    eng_capstone = next(g for g in eng_result["course_groups"] if g["code"] == "required_capstone")
    general_groups = general_result["course_groups"]
    # 공학 필수 이수 5과목은 일반에 넣지 않는다. 캡스톤 택1만 같은 두 과목으로 연결한다.
    assert [g["code"] for g in general_groups] == ["required_capstone"]
    capstone = general_groups[0]
    assert capstone["min_courses"] == 1
    assert {c["name"] for c in capstone["courses"]} == set(CAPSTONE_COURSES)
    assert capstone["courses"] == eng_capstone["courses"]
    assert "general_program_capstone_applicability" not in engineering["pending_data"]
    # 일반만 선택해도 같은 그룹이 일반 범위에 나온다. 공통 요건으로 올리지 않는다.
    general_only = get_rule_bundle(engineering_db, 2024, "general", sub_major)
    assert general_only["program_results"][0]["course_groups"] == general_groups
    assert all(row["code"] != "required_capstone" for row in general_only["common_requirements"])

    # 일반 그룹은 이수내규, 공학 그룹은 학부 졸업요건 안내를 출처로 가리킨다.
    bylaw = engineering_db.get(SourceDocument, capstone["source_id"])
    assert (bylaw.url, bylaw.retrieved_on) == (BYLAW_URL, BYLAW_RETRIEVED_ON)
    assert engineering_db.get(SourceDocument, eng_capstone["source_id"]).url == SOURCE_URL
    review = engineering_db.get(
        RequirementSource, (general_result["requirement_id"], capstone["source_id"])
    )
    assert review.review_status == "verified"
    assert review.reviewer == "원용"
    assert review.reviewed_on == BYLAW_RETRIEVED_ON


def test_conflicting_general_capstone_group_stops_seed(engineering_db):
    general = engineering_db.execute(
        select(GraduationRequirement).filter_by(
            admission_year=2024, program="general", sub_major="software"
        )
    ).scalar_one()
    group = engineering_db.execute(
        select(CourseGroupRequirement).filter_by(
            requirement_id=general.requirement_id, group_code="required_capstone"
        )
    ).scalar_one()
    group.min_courses = 2
    engineering_db.flush()
    with pytest.raises(ValueError, match="CourseGroupRequirement conflicts"):
        seed_verified_engineering_rules(engineering_db)


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
