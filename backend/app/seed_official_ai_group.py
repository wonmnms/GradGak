"""원본 대조가 끝난 인공지능 세부전공필수 5과목 중 3과목 규칙만 적재한다."""

from datetime import date

from sqlalchemy import select, text

from app.db import SessionLocal
from app.models import (
    Course,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    GraduationRequirement,
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

DEPARTMENT = "소프트웨어학부"
CURRICULUM_URL = "https://www.kw.ac.kr/ko/univ/ai02_4.jsp"
# 딥러닝실습 학점의 근거. 박준영(2026-11-15)·김남주(2026-11-16) 대조기록 참조.
COURSE_TABLE_URL = "https://www.kw.ac.kr/include/Download.jsp?fuid=35550&ano=53646"
COURSE_TABLE_RETRIEVED_ON = date(2026, 11, 15)
DEEP_LEARNING_LAB_REVIEW_DATE = date(2026, 11, 16)
DEEP_LEARNING_LAB = "딥러닝실습"
AI_COURSE_CREDITS = {
    "인공지능": 3,
    "빅데이터처리및응용": 3,
    "컴퓨터비전": 3,
    "기계학습": 3,
    DEEP_LEARNING_LAB: 2,
}
AI_COURSES = tuple(AI_COURSE_CREDITS)
GROUP_CODE = "sub_major_required"

CURRICULUM_NOTE = (
    "김남주가 2026-10-31 5과목명과 학점 표기를 원본 대조함. 딥러닝실습 행은 머리글이 "
    "'시수|학점'이나 값 순서가 교과과정표의 '학점|시간'과 같아 판단 불가(박준영 대조기록 "
    "02-B08)이므로 딥러닝실습 학점의 근거로 쓰지 않음. "
    "학수번호·이수구분·개설학기는 검증하지 않았으며 추정하지 않음."
)
CURRICULUM_REVIEW_NOTE = (
    "검증 범위: 위 5과목명 및 딥러닝실습을 제외한 4과목의 각 3학점. 딥러닝실습 학점은 "
    "2024 교과과정표 근거 기록 참조. 과목 그룹 조건은 "
    "그룹의 source_id가 가리키는 졸업요건 안내 및 docs/data-verification.md 참조. "
    "학수번호·이수구분·개설학기는 미확인. 공학·일반 공통 규칙이므로 "
    "두 프로그램에 같은 그룹을 저장하며 판정 시 공통 요건은 한 번만 검사."
)
COURSE_TABLE_REVIEW_NOTE = (
    "검증 범위: 딥러닝실습 2학점에 한정. 박준영(2026-11-15)이 이 표 173행과 2026-1 "
    "강의시간표 PDF 36쪽(2학점·3시수)을 직접 확인. 김남주(2026-11-16)가 이수내규에서 "
    "2학점·설계 2학점을 확인(대조기록 01, 이수내규의 URL·위치는 기록에 없음). "
    "기존 값 3학점(ai02_4.jsp 웹 표 근거)을 정정함. 학수번호는 미검증이므로 NULL 유지."
)

# 2026-11-16 정정 이전 시드가 저장한 값. 이 값과 정확히 같을 때만 정정한다.
LEGACY_CURRICULUM_NOTE = (
    "김남주가 5과목명과 각각 3학점을 원본 대조함. "
    "학수번호·이수구분·개설학기는 검증하지 않았으며 추정하지 않음."
)
LEGACY_CURRICULUM_REVIEW_NOTE = (
    "검증 범위: 위 5과목명 및 각 3학점. 과목 그룹 조건은 "
    "그룹의 source_id가 가리키는 졸업요건 안내 및 docs/data-verification.md 참조. "
    "학수번호·이수구분·개설학기는 미확인. 공학·일반 공통 규칙이므로 "
    "두 프로그램에 같은 그룹을 저장하며 판정 시 공통 요건은 한 번만 검사."
)
LEGACY_DEEP_LEARNING_LAB_CREDITS = 3


def _replace_legacy_note(session, model, keys, legacy_note, note):
    """기존 레코드의 note가 정정 전 문구와 정확히 같을 때만 새 문구로 바꾼다."""
    record = session.execute(select(model).filter_by(**keys)).scalar_one_or_none()
    if record is not None and record.note == legacy_note:
        record.note = note
        session.flush()


def _correct_deep_learning_lab_credits(session, *, curriculum_source, course_table_source):
    """정정 전 시드가 만든 딥러닝실습 3학점만 2학점으로 바꾼다.

    학점이 3이고 출처가 ai02_4.jsp 교육과정 자료인 경우만 정정한다.
    그 밖의 값은 건드리지 않으며, 다르면 이후 ensure_course가 충돌로 중단한다.
    """
    session.execute(text("LOCK TABLE courses IN SHARE ROW EXCLUSIVE MODE"))
    course = session.execute(
        select(Course).filter_by(name=DEEP_LEARNING_LAB, department=DEPARTMENT)
    ).scalar_one_or_none()
    if (
        course is not None
        and course.credits == LEGACY_DEEP_LEARNING_LAB_CREDITS
        and course.source_id == curriculum_source.source_id
    ):
        course.credits = AI_COURSE_CREDITS[DEEP_LEARNING_LAB]
        course.source_id = course_table_source.source_id
        session.flush()


def seed_verified_ai_group(session):
    requirements = seed_verified_credit_rules(session)
    rule_source = session.execute(
        select(SourceDocument).filter_by(url=SOURCE_URL, retrieved_on=REVIEW_DATE)
    ).scalar_one()
    curriculum_keys = {"url": CURRICULUM_URL, "retrieved_on": REVIEW_DATE}
    _replace_legacy_note(
        session, SourceDocument, curriculum_keys, LEGACY_CURRICULUM_NOTE, CURRICULUM_NOTE
    )
    curriculum_source = ensure_record(
        session,
        SourceDocument,
        curriculum_keys,
        {"title": "광운대학교 소프트웨어학부 교육과정", "note": CURRICULUM_NOTE},
    )
    course_table_source = ensure_record(
        session,
        SourceDocument,
        {"url": COURSE_TABLE_URL, "retrieved_on": COURSE_TABLE_RETRIEVED_ON},
        {
            "title": "광운대학교 2024 교과과정표",
            "note": "박준영이 2026-11-15 [2024학년도] 173행 딥러닝실습 2학점·3시간을 "
            "직접 확인함. 이 시드는 이 자료를 딥러닝실습 학점에만 사용함.",
        },
    )
    _correct_deep_learning_lab_credits(
        session, curriculum_source=curriculum_source, course_table_source=course_table_source
    )
    course_sources = {name: curriculum_source for name in AI_COURSES}
    course_sources[DEEP_LEARNING_LAB] = course_table_source
    courses = [
        ensure_course(
            session,
            name=name,
            department=DEPARTMENT,
            source_id=course_sources[name].source_id,
            credits=credits,
        )
        for name, credits in AI_COURSE_CREDITS.items()
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
        curriculum_review_keys = {
            "requirement_id": requirement.requirement_id,
            "source_id": curriculum_source.source_id,
        }
        _replace_legacy_note(
            session,
            RequirementSource,
            curriculum_review_keys,
            LEGACY_CURRICULUM_REVIEW_NOTE,
            CURRICULUM_REVIEW_NOTE,
        )
        ensure_record(
            session,
            RequirementSource,
            curriculum_review_keys,
            {
                "locator": "교육과정 표 / 인공지능·빅데이터처리및응용·컴퓨터비전·"
                "기계학습·딥러닝실습",
                "review_status": "verified",
                "reviewer": "김남주",
                "reviewed_on": REVIEW_DATE,
                "note": CURRICULUM_REVIEW_NOTE,
            },
        )
        ensure_record(
            session,
            RequirementSource,
            {
                "requirement_id": requirement.requirement_id,
                "source_id": course_table_source.source_id,
            },
            {
                "locator": "소프트웨어학부 [2024학년도] 173행 딥러닝실습 (학점 2·시간 3)",
                "review_status": "verified",
                "reviewer": "박준영, 김남주",
                "reviewed_on": DEEP_LEARNING_LAB_REVIEW_DATE,
                "note": COURSE_TABLE_REVIEW_NOTE,
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
