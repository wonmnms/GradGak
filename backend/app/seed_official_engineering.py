"""원본 대조된 공학 필수 이수·캡스톤 택1·수학/과학 최소 학점과 일반 캡스톤 택1만 적재한다.

공학프로그램: 학부 졸업요건 안내의 공학 표 근거로 필수 이수 5과목, 캡스톤 택1,
수학·기초과학 하위 학점과 설계의 부모 영역을 저장한다.
일반프로그램: 이수내규 제6조②(캡스톤설계 심사 통과)를 공학과 같은 캡스톤 택1 그룹으로
저장한다. 공학 필수 이수 5과목과 수학·과학 하위 조건은 일반에 넣지 않는다.
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
CAPSTONE_GROUP_CODE = "required_capstone"
CAPSTONE_GROUP_NAME = "산학협력캡스톤설계1·2 중 1과목"

# 일반프로그램 캡스톤 그룹의 근거. 원용 2026-11-26 원문 확인.
BYLAW_URL = "https://cs.kw.ac.kr/engineering_certify/complete_bylaw.php"
BYLAW_RETRIEVED_ON = date(2026, 11, 26)
BYLAW_REVIEWER = "원용"
BYLAW_NOTE = (
    "원용이 2026-11-26 제2장 일반 프로그램 제6조②('캡스톤설계 심사를 통과하여야 한다')와 "
    "제3조③(캡스톤설계 교과목 운영)을 직접 확인함. 이 시드는 이 자료를 일반프로그램 "
    "캡스톤 그룹에만 사용함."
)
BYLAW_REVIEW_NOTE = (
    "검증 범위: 일반프로그램 캡스톤 택1 그룹에 한정. 원문은 '캡스톤설계 심사 통과'만 "
    "규정하며 산학협력캡스톤설계1·2 과목명 택1은 학부 졸업요건 안내의 공학 표에만 직접 "
    "기재됨. 일반 그룹의 과목 매핑은 제6조②·제3조③과 확인자(원용, 재학생)의 확인에 근거. "
    "졸업논문(작품) '가' 판정은 별도 비학점 요건으로 유지."
)


def _attach_parent(category, parent):
    if category.requirement_id != parent.requirement_id:
        raise ValueError("Parent category belongs to another requirement")
    if category.category_id == parent.category_id:
        raise ValueError("A category cannot be its own parent")
    if category.parent_category_id not in (None, parent.category_id):
        raise ValueError("Existing category parent conflicts")
    category.parent_category_id = parent.category_id


def _ensure_group(session, requirement, code, label, course_ids, source_id):
    group = ensure_record(
        session,
        CourseGroupRequirement,
        {"requirement_id": requirement.requirement_id, "group_code": code},
        {"name": label, "min_courses": 1, "source_id": source_id},
    )
    for course_id in course_ids:
        ensure_record(
            session,
            CourseGroupRequirementCourse,
            {"group_id": group.group_id, "course_id": course_id},
            {},
        )
    return group


def _seed_general_capstone(session, requirement, courses, bylaw):
    ensure_record(
        session,
        RequirementSource,
        {"requirement_id": requirement.requirement_id, "source_id": bylaw.source_id},
        {
            "locator": "제2장 일반 프로그램 제6조② / 제3조③",
            "review_status": "verified",
            "reviewer": BYLAW_REVIEWER,
            "reviewed_on": BYLAW_RETRIEVED_ON,
            "note": BYLAW_REVIEW_NOTE,
        },
    )
    return _ensure_group(
        session,
        requirement,
        CAPSTONE_GROUP_CODE,
        CAPSTONE_GROUP_NAME,
        [courses[name].course_id for name in CAPSTONE_COURSES],
        bylaw.source_id,
    )


def seed_verified_engineering_rules(session):
    requirements = seed_verified_credit_rules(session)
    source = session.execute(
        select(SourceDocument).filter_by(url=SOURCE_URL, retrieved_on=REVIEW_DATE)
    ).scalar_one()
    bylaw = ensure_record(
        session,
        SourceDocument,
        {"url": BYLAW_URL, "retrieved_on": BYLAW_RETRIEVED_ON},
        {"title": "컴퓨터소프트웨어 프로그램 이수내규(2024.7.15 개정)", "note": BYLAW_NOTE},
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
            groups.append(_seed_general_capstone(session, requirement, courses, bylaw))
            continue
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
            (CAPSTONE_GROUP_CODE, CAPSTONE_GROUP_NAME, list(CAPSTONE_COURSES))
        ]
        for code, label, names in group_specs:
            course_ids = [courses[name].course_id for name in names]
            groups.append(
                _ensure_group(session, requirement, code, label, course_ids, source.source_id)
            )
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
            f"Saved/reused {len(groups)} course groups ({links} group-course links) "
            "and 4 credit subcategories."
        )
    print("Course codes, credits, aliases and recognition lists are not inferred.")


if __name__ == "__main__":
    main()
