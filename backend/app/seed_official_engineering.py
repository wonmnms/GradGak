"""원본 대조된 공학 필수 이수·캡스톤 택1·수학/과학 최소 학점만 적재한다."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Course,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    RequirementCategory,
    SourceDocument,
)
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


def _attach_parent(category, parent):
    if category.requirement_id != parent.requirement_id:
        raise ValueError("Parent category belongs to another requirement")
    if category.category_id == parent.category_id:
        raise ValueError("A category cannot be its own parent")
    if category.parent_category_id not in (None, parent.category_id):
        raise ValueError("Existing category parent conflicts")
    category.parent_category_id = parent.category_id


def seed_verified_engineering_rules(session):
    requirements = seed_verified_credit_rules(session)
    source = session.execute(
        select(SourceDocument).filter_by(url=SOURCE_URL, retrieved_on=REVIEW_DATE)
    ).scalar_one()
    course_names = [name for _, name in REQUIRED_COURSES] + list(CAPSTONE_COURSES)
    courses = {
        name: ensure_record(
            session,
            Course,
            {"name": name, "source_id": source.source_id},
            {},
        )
        for name in course_names
    }
    groups = []
    for requirement in requirements:
        if requirement.program != "engineering":
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
        print(f"Saved/reused {len(groups)} engineering groups and 4 credit subcategories.")
    print("Course codes, credits, aliases and recognition lists are not inferred.")


if __name__ == "__main__":
    main()
