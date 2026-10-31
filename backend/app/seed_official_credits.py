"""사용자가 원본 대조한 2024학번 학점표만 적재한다. 전체 졸업규칙은 아니다."""

from datetime import date

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    GraduationRequirement,
    RequirementCategory,
    RequirementSource,
    SourceDocument,
)

SOURCE_URL = (
    "https://cs.kw.ac.kr/program/requirement.php?"
    "admin_mode=read&make=&no=2975&page=1&search=&site_type=3"
)
REVIEW_DATE = date(2026, 10, 31)
CREDIT_RULES = {
    "engineering": (
        ("required_general", 1, "필수교양. 대상 과목 및 면제 조건은 별도 확인 필요."),
        ("balanced_general", 30, "균형교양. 영역·과목 수 세부 조건은 별도 확인 필요."),
        ("basic_math_science", 12, "수리와자연·기초교양. 수학·과학별 하위 조건 별도 확인."),
        ("engineering_subject", 60, "공학주제. 설계 12학점을 포함한다."),
        ("engineering_design", 12, "공학주제 60학점의 부분집합. 별도 학점으로 더하지 않는다."),
    ),
    "general": (
        ("required_general", 1, "필수교양. 대상 과목 및 면제 조건은 별도 확인 필요."),
        ("balanced_general", 30, "균형교양. 영역·과목 수 세부 조건은 별도 확인 필요."),
        ("major", 60, "단일전공 기준. 프로그램별 과목 인정 목록은 별도 확인 필요."),
    ),
}


def ensure_record(session, model, keys, values):
    """동일 레코드는 재사용하고 값이 다르면 중단한다. 기존 값은 변경하지 않는다."""
    record = session.execute(select(model).filter_by(**keys)).scalar_one_or_none()
    if record is None:
        record = model(**keys, **values)
        session.add(record)
        session.flush()
        return record

    for name, expected in values.items():
        if getattr(record, name) != expected:
            raise ValueError(f"Existing {model.__name__} conflicts at {keys}: {name}")
    return record


def seed_verified_credit_rules(session):
    source = ensure_record(
        session,
        SourceDocument,
        {"url": SOURCE_URL, "retrieved_on": REVIEW_DATE},
        {
            "title": "공학/일반 졸업이수요건 안내(2026ver)",
            "note": "2024학번 학점표만 사용자 원본 대조 완료. 전체 규칙 검증 완료가 아님.",
        },
    )
    requirements = []
    for program, categories in CREDIT_RULES.items():
        for sub_major in ("software", "ai"):
            requirement = ensure_record(
                session,
                GraduationRequirement,
                {"admission_year": 2024, "program": program, "sub_major": sub_major},
                {"total_credits": 133},
            )
            requirements.append(requirement)
            for category, credits, note in categories:
                ensure_record(
                    session,
                    RequirementCategory,
                    {"requirement_id": requirement.requirement_id, "category": category},
                    {"min_credits": credits, "note": note},
                )
            ensure_record(
                session,
                RequirementSource,
                {"requirement_id": requirement.requirement_id, "source_id": source.source_id},
                {
                    "locator": f"{'공학' if program == 'engineering' else '일반'}프로그램 / "
                    "2024학번 입학자 행 (일반은 단일전공 기준)",
                    "review_status": "verified",
                    "reviewer": "사용자 원본 대조 확인 (이 채팅)",
                    "reviewed_on": REVIEW_DATE,
                    "note": "검증 범위는 총학점·이번에 입력한 영역별 학점 값만 해당. "
                    "공학 선택 시 일반 요건도 별도 적용해야 함. 필수과목, 공통 요건, "
                    "과목 인정 목록 및 교양 세부 조건은 별도 검증·구현 필요. "
                    "일반프로그램의 기초교양 별도 기준은 입력하지 않음.",
                },
            )
    return requirements


def main():
    with SessionLocal.begin() as session:
        seed_verified_credit_rules(session)
    print("Verified 2024 credit-table values saved (partial rule set).")

    with SessionLocal() as session:
        rows = session.execute(
            select(
                GraduationRequirement.program,
                GraduationRequirement.sub_major,
                GraduationRequirement.total_credits,
                RequirementCategory.category,
                RequirementCategory.min_credits,
            )
            .join(RequirementCategory)
            .where(
                GraduationRequirement.admission_year == 2024,
                GraduationRequirement.program.in_(CREDIT_RULES),
                GraduationRequirement.sub_major.in_(("software", "ai")),
            )
            .order_by(
                GraduationRequirement.program,
                GraduationRequirement.sub_major,
                RequirementCategory.category,
            )
        )
        for row in rows:
            print(tuple(row))


if __name__ == "__main__":
    main()
