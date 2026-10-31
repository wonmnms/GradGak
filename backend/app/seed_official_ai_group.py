"""사용자 대조가 끝난 인공지능 세부전공필수 5과목 중 3과목 규칙만 적재한다."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Course,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    GraduationRequirement,
    RequirementSource,
    SourceDocument,
)
from app.seed_official_credits import (
    REVIEW_DATE,
    SOURCE_URL,
    ensure_record,
    seed_verified_credit_rules,
)

CURRICULUM_URL = "https://www.kw.ac.kr/ko/univ/ai02_4.jsp"
AI_COURSES = ("인공지능", "빅데이터처리및응용", "컴퓨터비전", "기계학습", "딥러닝실습")
GROUP_CODE = "sub_major_required"


def seed_verified_ai_group(session):
    requirements = seed_verified_credit_rules(session)
    rule_source = session.execute(
        select(SourceDocument).filter_by(url=SOURCE_URL, retrieved_on=REVIEW_DATE)
    ).scalar_one()
    curriculum_source = ensure_record(
        session,
        SourceDocument,
        {"url": CURRICULUM_URL, "retrieved_on": REVIEW_DATE},
        {
            "title": "광운대학교 소프트웨어학부 교육과정",
            "note": "사용자가 5과목명과 각각 3학점을 원본 대조함. "
            "학수번호·이수구분·개설학기는 검증하지 않았으며 추정하지 않음.",
        },
    )
    courses = [
        ensure_record(
            session,
            Course,
            {"department": "소프트웨어학부", "name": name},
            {"credits": 3, "source_id": curriculum_source.source_id},
        )
        for name in AI_COURSES
    ]
    groups = []
    for requirement in requirements:
        if requirement.sub_major != "ai":
            continue
        group = ensure_record(
            session,
            CourseGroupRequirement,
            {"requirement_id": requirement.requirement_id, "group_code": GROUP_CODE},
            {
                "name": "인공지능전공 세부전공필수 (지정 5과목 중 3과목 이상)",
                "min_courses": 3,
                "source_id": rule_source.source_id,
            },
        )
        for course in courses:
            ensure_record(
                session,
                CourseGroupRequirementCourse,
                {"group_id": group.group_id, "course_id": course.course_id},
                {},
            )
        ensure_record(
            session,
            RequirementSource,
            {
                "requirement_id": requirement.requirement_id,
                "source_id": curriculum_source.source_id,
            },
            {
                "locator": "교육과정 표 / 인공지능·빅데이터처리및응용·컴퓨터비전·"
                "기계학습·딥러닝실습",
                "review_status": "verified",
                "reviewer": "사용자 원본 대조 확인 (이 채팅)",
                "reviewed_on": REVIEW_DATE,
                "note": "검증 범위: 위 5과목명 및 각 3학점. 과목 그룹 조건은 "
                "그룹의 source_id가 가리키는 졸업요건 안내 및 docs/data-verification.md 참조. "
                "학수번호·이수구분·개설학기는 미확인. 공학·일반 공통 규칙이므로 "
                "두 프로그램에 같은 그룹을 저장하며 판정 시 공통 요건은 한 번만 검사.",
            },
        )
        groups.append(group)
    return groups


def main():
    with SessionLocal.begin() as session:
        seed_verified_ai_group(session)
    print("AI group saved: choose at least 3 of 5 courses; course codes remain unknown.")
    with SessionLocal() as session:
        rows = session.execute(
            select(
                GraduationRequirement.program,
                CourseGroupRequirement.min_courses,
                Course.name,
                Course.credits,
                Course.course_code,
            )
            .select_from(GraduationRequirement)
            .join(CourseGroupRequirement)
            .join(CourseGroupRequirementCourse)
            .join(Course)
            .where(
                GraduationRequirement.admission_year == 2024,
                GraduationRequirement.sub_major == "ai",
                GraduationRequirement.program.in_(("engineering", "general")),
                CourseGroupRequirement.group_code == GROUP_CODE,
            )
            .order_by(GraduationRequirement.program, Course.name)
        )
        for row in rows:
            print(tuple(row))


if __name__ == "__main__":
    main()
