"""테스트용 가상 데이터 저장·조회. 공식 졸업요건 데이터가 아님."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Course,
    GraduationRequirement,
    RequirementCategory,
    RequirementCategoryCourse,
)


def get_or_create(session, model, keys, defaults=None):
    obj = session.scalar(select(model).filter_by(**keys))
    if obj is None:
        obj = model(**keys, **(defaults or {}))
        session.add(obj)
        session.flush()
    return obj


def main():
    # 하나의 트랜잭션: 모두 성공하면 저장, 오류가 나면 전체 취소.
    with SessionLocal.begin() as session:
        requirement = get_or_create(
            session,
            GraduationRequirement,
            {
                "admission_year": 2099,
                "program": "TEST",
                "sub_major": "TEST_MAJOR",
            },
            {"total_credits": 10},
        )

        category = get_or_create(
            session,
            RequirementCategory,
            {
                "requirement_id": requirement.requirement_id,
                "category": "TEST_CATEGORY",
            },
            {
                "min_credits": 3,
                "note": "Fictional demo data only",
            },
        )

        course = get_or_create(
            session,
            Course,
            {"course_code": "TEST-DEMO-001"},
            {
                "name": "TEST Demo Course",
                "credits": 3,
                "course_type": "TEST",
            },
        )

        get_or_create(
            session,
            RequirementCategoryCourse,
            {
                "category_id": category.category_id,
                "course_id": course.course_id,
            },
        )

    print("Demo data saved.")

    # 저장 후 새 세션으로 테이블 4개를 연결해 조회.
    with SessionLocal() as session:
        stmt = (
            select(
                GraduationRequirement.admission_year,
                GraduationRequirement.program,
                RequirementCategory.category,
                Course.course_code,
                Course.name,
                Course.credits,
            )
            .select_from(GraduationRequirement)
            .join(RequirementCategory)
            .join(RequirementCategoryCourse)
            .join(Course)
            .where(
                GraduationRequirement.admission_year == 2099,
                GraduationRequirement.program == "TEST",
                GraduationRequirement.sub_major == "TEST_MAJOR",
                Course.course_code == "TEST-DEMO-001",
            )
        )
        for row in session.execute(stmt):
            print(tuple(row))


if __name__ == "__main__":
    main()
