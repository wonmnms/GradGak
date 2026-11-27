"""원본 대조된 공학 필수 이수·캡스톤 택1·수학/과학 최소 학점을 적재한다.

공학프로그램: 학부 졸업요건 안내의 공학 표 근거로 필수 이수 5과목, 캡스톤 택1,
수학·기초과학 하위 학점과 설계의 부모 영역을 저장한다.
일반프로그램: 과목 그룹을 만들지 않는다. 이수내규 제2장 제6조②의 캡스톤설계 심사 통과는
공통 비학점 요건 졸업논문(작품) '가' 판정(thesis)으로 반영된 것으로 보고,
그 근거만 이수내규의 requirement_sources 기록으로 남긴다.
"""

from datetime import date

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    RequirementCategory,
    RequirementSource,
    SourceDocument,
)
from app.seed_courses import ensure_course
from app.seed_official_credits import (
    REVIEW_DATE,
    SOURCE_URL,
    ensure_record,
    seed_verified_credit_rules,
)

REQUIRED_COURSES = (
    ("required_c_programming", "C프로그래밍"),
    ("required_advanced_c", "고급C프로그래밍및설계"),
    ("required_smart_ai", "스마트사회와인공지능"),
    ("required_engineering_design_intro", "공학설계입문"),
    ("required_discrete_math", "이산수학"),
)
CAPSTONE_COURSES = ("산학협력캡스톤설계1", "산학협력캡스톤설계2")

BYLAW_URL = "https://cs.kw.ac.kr/engineering_certify/complete_bylaw.php"
BYLAW_RETRIEVED_ON = date(2026, 11, 26)
BYLAW_TITLE = "컴퓨터소프트웨어 프로그램 이수내규(2024.7.15 개정)"
BYLAW_NOTE = "컴퓨터소프트웨어 프로그램 이수내규(2024.7.15 개정). 원용이 2026-11-26 조회·확인."
BYLAW_LOCATOR = "제2장 일반 프로그램 제6조② / 제1장 제3조③"
BYLAW_REVIEWER = "원용"
BYLAW_REVIEW_NOTE = (
    "제6조② 캡스톤설계 심사 통과는 공통 비학점 요건 졸업논문(작품) '가' 판정(thesis)으로 "
    "반영. 일반 교과과정에서 산학협력캡스톤설계1·2는 전선(인증 공필)이므로 "
    "일반프로그램 과목 그룹으로 넣지 않음."
)


def _attach_parent(category, parent):
    if category.requirement_id != parent.requirement_id:
        raise ValueError("Parent category belongs to another requirement")
    if category.category_id == parent.category_id:
        raise ValueError("A category cannot be its own parent")
    if category.parent_category_id not in (None, parent.category_id):
        raise ValueError("Existing category parent conflicts")
    category.parent_category_id = parent.category_id


def _reject_leftover_general_capstone(session, requirements):
    """이전 시드가 만든 일반 캡스톤 그룹이 남아 있으면 지우지 않고 중단한다.

    이전 시드의 이수내규 출처 note가 지금 값과 달라서, 출처를 기록하기 전에 검사해야
    이 메시지로 멈춘다.
    """
    for requirement in requirements:
        if requirement.program != "general":
            continue
        leftover = session.execute(
            select(CourseGroupRequirement).filter_by(
                requirement_id=requirement.requirement_id, group_code="required_capstone"
            )
        ).scalar_one_or_none()
        if leftover is not None:
            raise ValueError(
                f"General program has a capstone course group: {requirement.requirement_id}"
            )


def _record_general_capstone_basis(session, requirement, bylaw):
    """일반프로그램의 캡스톤설계 심사 근거만 기록한다. 과목 그룹은 만들지 않는다."""
    ensure_record(
        session,
        RequirementSource,
        {"requirement_id": requirement.requirement_id, "source_id": bylaw.source_id},
        {
            "locator": BYLAW_LOCATOR,
            "review_status": "verified",
            "reviewer": BYLAW_REVIEWER,
            "reviewed_on": BYLAW_RETRIEVED_ON,
            "note": BYLAW_REVIEW_NOTE,
        },
    )


def seed_verified_engineering_rules(session):
    requirements = seed_verified_credit_rules(session)
    source = session.execute(
        select(SourceDocument).filter_by(url=SOURCE_URL, retrieved_on=REVIEW_DATE)
    ).scalar_one()
    _reject_leftover_general_capstone(session, requirements)
    bylaw = ensure_record(
        session,
        SourceDocument,
        {"url": BYLAW_URL, "retrieved_on": BYLAW_RETRIEVED_ON},
        {"title": BYLAW_TITLE, "note": BYLAW_NOTE},
    )
    course_names = [name for _, name in REQUIRED_COURSES] + list(CAPSTONE_COURSES)
    courses = {
        name: ensure_course(
            session, name=name, department="소프트웨어학부", source_id=source.source_id
        )
        for name in course_names
    }
    groups = []
    for requirement in requirements:
        if requirement.program == "general":
            _record_general_capstone_basis(session, requirement, bylaw)
            continue
        elif requirement.program != "engineering":
            raise ValueError(f"Unexpected program: {requirement.program}")
        categories = {
            row.category: row
            for row in session.scalars(
                select(RequirementCategory).filter_by(requirement_id=requirement.requirement_id)
            )
        }
        basic = categories["basic_math_science"]
        for code, credits in (("basic_math", 6), ("basic_science", 3)):
            child = ensure_record(
                session,
                RequirementCategory,
                {"requirement_id": requirement.requirement_id, "category": code},
                {
                    "min_credits": credits,
                    "note": "수학·기초과학 합계 12학점의 하위 조건. 별도 가산하지 않음. "
                    "영역 인정 과목 목록은 추가 확인 필요.",
                },
            )
            _attach_parent(child, basic)
        _attach_parent(categories["engineering_design"], categories["engineering_subject"])

        group_specs = [(code, f"필수 이수: {name}", [name]) for code, name in REQUIRED_COURSES] + [
            ("required_capstone", "산학협력캡스톤설계1·2 중 1과목", list(CAPSTONE_COURSES))
        ]
        for code, label, names in group_specs:
            group = ensure_record(
                session,
                CourseGroupRequirement,
                {"requirement_id": requirement.requirement_id, "group_code": code},
                {"name": label, "min_courses": 1, "source_id": source.source_id},
            )
            for name in names:
                ensure_record(
                    session,
                    CourseGroupRequirementCourse,
                    {"group_id": group.group_id, "course_id": courses[name].course_id},
                    {},
                )
            groups.append(group)
    session.flush()
    return groups


def main():
    with SessionLocal.begin() as session:
        groups = seed_verified_engineering_rules(session)
        links = sum(
            len(
                session.scalars(
                    select(CourseGroupRequirementCourse).filter_by(group_id=group.group_id)
                ).all()
            )
            for group in groups
        )
        print(
            f"Saved/reused {len(groups)} engineering groups ({links} group-course links), "
            "4 credit subcategories and 2 general-program bylaw review records."
        )
    print("Course codes, credits, aliases and recognition lists are not inferred.")


if __name__ == "__main__":
    main()
