"""`POST /evaluate`를 실제 PostgreSQL과 가상 규칙·과목 데이터로 검증한다.

입학년도 2190과 모든 과목·출처는 가상이며 실제 교육과정이 아니다. 데이터는 flush만 하고
테스트가 끝나면 rollback한다.
"""

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, get_db
from app.main import app
from app.models import (
    Course,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    GraduationRequirement,
    NonCreditRequirement,
    RequirementCategory,
    RequirementCategoryCourse,
    SourceDocument,
)
from app.schemas.course_matching import CatalogCourse, CourseCatalogSnapshot
from app.schemas.transcripts import Course as TranscriptCourse
from app.services.course_matching import match_courses
from app.services.evaluation_input import merge_scope_matches, to_evaluation_courses
from app.services.sql_course_catalog import from_catalog_id, to_catalog_id

YEAR = 2190  # 가상 입학년도 (실제 데이터와 겹치지 않음)
TOTAL = {"engineering": 9, "general": 6}
AI_COURSES = ["가상AI1", "가상AI2", "가상AI3"]


@pytest.fixture
def client():
    """가상 규칙(YEAR/ai만)을 넣은 세션을 get_db 대신 주입한다."""
    with SessionLocal() as session:
        try:
            token = uuid4().hex[:12]
            source = SourceDocument(
                title="TEST evaluate",
                url=f"https://example.invalid/{token}/evaluate",
                retrieved_on=date(2099, 1, 1),
            )
            requirements = {
                program: GraduationRequirement(
                    admission_year=YEAR,
                    program=program,
                    sub_major="ai",
                    total_credits=TOTAL[program],
                )
                for program in ("engineering", "general")
            }
            ai_courses = [Course(name=name, credits=3) for name in AI_COURSES]
            # 같은 이름의 서로 다른 과목이 공학·일반 범위에 하나씩 있다.
            scoped = {
                "engineering": Course(name="가상모호", credits=3),
                "general": Course(name="가상모호", credits=3),
            }
            session.add_all([source, *requirements.values(), *ai_courses, *scoped.values()])
            session.flush()
            for program, requirement in requirements.items():
                group = CourseGroupRequirement(
                    requirement_id=requirement.requirement_id,
                    group_code="sub_major_required",
                    name="가상 세부전공필수",
                    min_courses=2,
                    source_id=source.source_id,
                )
                category = RequirementCategory(
                    requirement_id=requirement.requirement_id, category="TEST", min_credits=3
                )
                session.add_all([group, category])
                session.flush()
                session.add_all(
                    [
                        *[
                            CourseGroupRequirementCourse(
                                group_id=group.group_id, course_id=course.course_id
                            )
                            for course in ai_courses
                        ],
                        RequirementCategoryCourse(
                            category_id=category.category_id,
                            course_id=scoped[program].course_id,
                        ),
                    ]
                )
            session.add_all(
                NonCreditRequirement(
                    admission_year=YEAR,
                    sub_major="ai",
                    code=code,
                    label=f"가상 {code}",
                    input_field=field,
                    expected_value=True,
                    source_id=source.source_id,
                    source_locator="TEST",
                    reviewer="TEST_REVIEWER",
                    reviewed_on=date(2099, 1, 2),
                )
                for code, field in (("thesis", "thesis_passed"), ("topcit", "topcit_taken"))
            )
            session.flush()
            app.dependency_overrides[get_db] = lambda: session
            yield TestClient(app)
        finally:
            app.dependency_overrides.pop(get_db, None)
            session.rollback()


def _course(name, grade="A0", credits=3):
    return {
        "year": 2191,
        "term": "1",
        "course_code": None,
        "name": name,
        "category": "전선",
        "credits": credits,
        "grade": grade,
        "is_retake": False,
    }


def _request(program="engineering", courses=(), **overrides):
    body = {
        "admission_year": YEAR,
        "program": program,
        "sub_major": "ai",
        "thesis_passed": True,
        "topcit_taken": True,
        "courses": list(courses),
    }
    body.update(overrides)
    return body


def _common(body, code):
    return next(row for row in body["common_requirements"] if row["id"] == code)


def test_engineering_returns_engineering_and_general_results(client):
    response = client.post("/evaluate", json=_request("engineering"))
    assert response.status_code == 200
    body = response.json()
    assert [row["program"] for row in body["program_results"]] == ["engineering", "general"]
    assert [row["total"]["required"] for row in body["program_results"]] == [9, 6]
    # 공통 요건은 한 번만 나온다.
    assert [row["id"] for row in body["common_requirements"]].count("sub_major_required") == 1


def test_general_returns_general_result_only(client):
    response = client.post("/evaluate", json=_request("general"))
    assert response.status_code == 200
    assert [row["program"] for row in response.json()["program_results"]] == ["general"]


def test_ai_sub_major_required_met(client):
    courses = [_course(AI_COURSES[0]), _course(AI_COURSES[1])]
    body = client.post("/evaluate", json=_request("general", courses)).json()
    group = _common(body, "sub_major_required")
    assert group["status"] == "met"
    assert group["completed_count"] == 2
    assert body["unmatched_courses"] == []
    assert body["program_results"][0]["total"] == {
        "required": 6,
        "earned": 6,
        "remaining": 0,
        "status": "met",
    }
    # 충족 못 한 요건은 없지만 영역 학점·규칙 데이터가 미완성이라 최종 판정은 보류다(엔진 정책).
    assert body["graduation_status"] == "pending"


def test_ai_sub_major_required_unmet_and_failed_grade_excluded(client):
    courses = [_course(AI_COURSES[0]), _course(AI_COURSES[1], grade="F")]
    body = client.post("/evaluate", json=_request("general", courses)).json()
    group = _common(body, "sub_major_required")
    assert group["status"] == "unmet"
    assert group["completed_count"] == 1
    assert [row["index"] for row in body["excluded_courses"]] == [1]
    assert body["graduation_status"] == "unmet"


def test_unmatched_course_is_reported_and_counted_in_total(client):
    courses = [_course(AI_COURSES[0]), _course("가상없는과목", credits=2)]
    body = client.post("/evaluate", json=_request("general", courses)).json()
    assert body["unmatched_courses"] == [
        {"index": 1, "name": "가상없는과목", "reason": "과목 데이터에서 찾지 못했습니다."}
    ]
    assert body["program_results"][0]["total"]["earned"] == 5
    assert _common(body, "sub_major_required")["completed_count"] == 1


def test_course_matching_different_ids_across_scopes_is_unmatched(client):
    courses = [_course("가상모호")]
    engineering = client.post("/evaluate", json=_request("engineering", courses)).json()
    assert [row["index"] for row in engineering["unmatched_courses"]] == [0]
    # 일반 범위 하나만 보면 같은 과목명이 하나의 과목으로 매칭된다.
    general = client.post("/evaluate", json=_request("general", courses)).json()
    assert general["unmatched_courses"] == []
    assert general["program_results"][0]["total"]["earned"] == 3


def test_unsupported_admission_year(client):
    response = client.post("/evaluate", json=_request(admission_year=1901))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "UNSUPPORTED_ADMISSION_YEAR"
    assert detail["message"]


def test_supported_year_without_scope_is_unsupported_scope(client):
    response = client.post("/evaluate", json=_request(sub_major="software"))
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNSUPPORTED_SCOPE"


@pytest.mark.parametrize(
    "overrides",
    [
        {"program": "invalid"},
        {"sub_major": "data"},
        {"thesis_passed": None},
        {"courses": [{"name": "가상"}]},
    ],
)
def test_invalid_request_is_422(client, overrides):
    assert client.post("/evaluate", json=_request(**overrides)).status_code == 422


def test_missing_field_is_422(client):
    body = _request()
    del body["topcit_taken"]
    assert client.post("/evaluate", json=body).status_code == 422


# --- 범위 합치기 (DB 없이) ---------------------------------------------------


def _transcript(name):
    return TranscriptCourse(
        year=2191, term="1", name=name, category="전선", credits=3, grade="A0", is_retake=False
    )


def _snapshot(*courses):
    return CourseCatalogSnapshot(
        courses=[CatalogCourse(course_id=cid, name=name) for cid, name in courses]
    )


INPUTS = [
    _transcript(name) for name in ("가상같음", "가상다름", "가상한쪽", "가상모호", "가상없음")
]
ENGINEERING = _snapshot(("1", "가상같음"), ("2", "가상다름"), ("4", "가상모호"), ("5", "가상모호"))
GENERAL = _snapshot(("1", "가상같음"), ("3", "가상다름"), ("6", "가상한쪽"), ("7", "가상모호"))


def test_merge_scope_matches_rules():
    merged = merge_scope_matches(
        [match_courses(INPUTS, ENGINEERING), match_courses(INPUTS, GENERAL)]
    )
    assert [(m.index, m.status, m.course_id) for m in merged] == [
        (0, "matched", "1"),  # 같은 id → 그 id
        (1, "ambiguous", None),  # 범위마다 다른 id → 모호
        (2, "matched", "6"),  # 한 범위에서만 매칭 → 그 id
        (3, "ambiguous", None),  # 한 범위에서라도 모호 → 모호
        (4, "unmatched", None),
    ]
    completed = to_evaluation_courses(INPUTS, merged)
    assert [course.course_id for course in completed] == [1, None, 6, None, None]


def test_merge_single_scope_keeps_matching_result():
    merged = merge_scope_matches([match_courses(INPUTS, GENERAL)])
    assert [m.course_id for m in merged] == ["1", "3", "6", "7", None]


def test_merge_rejects_misaligned_scope_results():
    with pytest.raises(ValueError):
        merge_scope_matches([])
    with pytest.raises(ValueError):
        merge_scope_matches([match_courses(INPUTS, GENERAL), match_courses(INPUTS[:2], GENERAL)])


def test_from_catalog_id_is_strict_inverse():
    assert from_catalog_id(to_catalog_id(42)) == 42
    for value in ("042", " 42", "+42", "4.2", "abc", ""):
        with pytest.raises(ValueError):
            from_catalog_id(value)
