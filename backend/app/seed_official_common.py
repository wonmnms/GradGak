"""사람이 대조한 공통 비학점 요건의 규칙 정의만 저장한다."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import NonCreditRequirement, SourceDocument
from app.seed_official_credits import (
    REVIEW_DATE,
    SOURCE_URL,
    ensure_record,
    seed_verified_credit_rules,
)

COMMON_RULES = (
    ("thesis", "졸업논문(작품) 제출 및 '가' 판정", "thesis_passed"),
    ("topcit", "TOPCIT 응시", "topcit_taken"),
)


def seed_verified_common_rules(session):
    seed_verified_credit_rules(session)
    source = session.execute(
        select(SourceDocument).filter_by(url=SOURCE_URL, retrieved_on=REVIEW_DATE)
    ).scalar_one()
    rules = []
    for sub_major in ("software", "ai"):
        for code, label, input_field in COMMON_RULES:
            rule = ensure_record(
                session,
                NonCreditRequirement,
                {"admission_year": 2024, "sub_major": sub_major, "code": code},
                {
                    "label": label,
                    "input_field": input_field,
                    "expected_value": True,
                    "source_id": source.source_id,
                    "source_locator": "졸업요건 안내 / 공학·일반 공통 1~3번 중 졸업논문 및 TOPCIT",
                    "reviewer": "사용자 원본 대조 확인 (이 채팅)",
                    "reviewed_on": REVIEW_DATE,
                },
            )
            rules.append(rule)
    return rules


def main():
    with SessionLocal.begin() as session:
        seed_verified_common_rules(session)
    print("Saved 4 common rule definitions; no individual student results stored.")
    with SessionLocal() as session:
        rows = session.execute(
            select(
                NonCreditRequirement.sub_major,
                NonCreditRequirement.code,
                NonCreditRequirement.input_field,
                NonCreditRequirement.expected_value,
            )
            .where(NonCreditRequirement.admission_year == 2024)
            .order_by(NonCreditRequirement.sub_major, NonCreditRequirement.code)
        )
        for row in rows:
            print(tuple(row))


if __name__ == "__main__":
    main()
