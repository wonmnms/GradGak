"""`POST /evaluate`를 실제 PostgreSQL과 가상 규칙·과목 데이터로 검증한다.

입학년도 2190과 모든 과목·출처는 가상이며 실제 교육과정이 아니다. 외부 트랜잭션 안의
SAVEPOINT 세션을 쓰므로 라우터나 서비스가 commit해도 테스트 끝에 모두 되돌린다.
"""

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, engine, get_db
from app.main import app
from app.models import (
    Course,
    CourseEquivalence,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    CourseNumber,
    GraduationRequirement,
    NonCreditRequirement,
    RequirementCategory,
    RequirementCategoryCourse,
    RequirementSource,
    SourceDocument,
)
from app.services import evaluation
from app.services.course_matching import CatalogValidationError
from app.services.sql_course_catalog import from_catalog_id, to_catalog_id

YEAR = 2190  # 가상 입학년도 (실제 데이터와 겹치지 않음)
TOTAL = {"engineering": 9, "general": 6}
AI_COURSES = ["가상AI1", "가상AI2", "가상AI3"]


@pytest.fixture
def client():
    """가상 규칙(YEAR/ai만)을 넣은 세션을 get_db 대신 주입한다."""
    with engine.connect() as connection:
        outer = connection.begin()
        session = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")
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
            # 범위별로 다르게 보이는 과목: 공학에만 있는 과목, 일반 범위에서만 모호한 과목,
            # 공학 범위에서만 verified 대체 관계가 있는 옛 과목.
            eng_only = Course(name="가상공학전용", credits=3)
            amb_eng = Course(name="가상일반모호", credits=3)
            amb_gen = [Course(name="가상일반모호", credits=3) for _ in range(2)]
            old = Course(name="가상옛과목", credits=3)
            session.add_all(
                [
                    source,
                    *requirements.values(),
                    *ai_courses,
                    *scoped.values(),
                    eng_only,
                    amb_eng,
                    *amb_gen,
                    old,
                ]
            )
            session.flush()
            # 가상 인정 과목번호: 학정번호 형식 입력으로 두 범위에서 같은 과목으로 매칭된다.
            session.add(
                CourseNumber(
                    course_id=ai_courses[2].course_id,
                    course_number="Z901",
                    source_id=source.source_id,
                    review_status="verified",
                    reviewer="TEST_REVIEWER",
                    reviewed_on=date(2099, 1, 2),
                )
            )
            engineering = requirements["engineering"]
            session.add(
                RequirementSource(
                    requirement_id=engineering.requirement_id,
                    source_id=source.source_id,
                    locator="TEST",
                    review_status="verified",
                    reviewer="TEST_REVIEWER",
                    reviewed_on=date(2099, 1, 2),
                )
            )
            session.add(
                CourseEquivalence(
                    requirement_id=engineering.requirement_id,
                    completed_course_id=old.course_id,
                    recognized_course_id=ai_courses[1].course_id,
                    source_id=source.source_id,
                )
            )
            session.add_all(
                CourseGroupRequirement(
                    requirement_id=engineering.requirement_id,
                    group_code=code,
                    name=f"가상 {code}",
                    min_courses=1,
                    source_id=source.source_id,
                )
                for code in ("eng_only", "eng_amb")
            )
            session.flush()
            eng_groups = {
                group.group_code: group
                for group in session.query(CourseGroupRequirement).filter_by(
                    requirement_id=engineering.requirement_id
                )
            }
            session.add_all(
                [
                    CourseGroupRequirementCourse(
                        group_id=eng_groups["eng_only"].group_id, course_id=eng_only.course_id
                    ),
                    CourseGroupRequirementCourse(
                        group_id=eng_groups["eng_amb"].group_id, course_id=amb_eng.course_id
                    ),
                ]
            )
            general_category = RequirementCategory(
                requirement_id=requirements["general"].requirement_id,
                category="TEST_GENERAL",
                min_credits=3,
            )
            session.add(general_category)
            session.flush()
            session.add_all(
                RequirementCategoryCourse(
                    category_id=general_category.category_id, course_id=course.course_id
                )
                for course in amb_gen
            )
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
            session.close()
            outer.rollback()


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


def test_same_name_in_each_scope_matches_per_program(client):
    courses = [_course("가상모호")]
    body = client.post("/evaluate", json=_request("engineering", courses)).json()
    # 범위마다 다른 과목이어도 각 프로그램은 자기 범위의 매칭으로 인정한다.
    assert body["unmatched_courses"] == []
    assert [row["total"]["earned"] for row in body["program_results"]] == [3, 3]
    general = client.post("/evaluate", json=_request("general", courses)).json()
    assert general["unmatched_courses"] == []
    assert general["program_results"][0]["total"]["earned"] == 3


def _group(program_result, code):
    return next(g for g in program_result["course_groups"] if g["id"] == code)


def test_engineering_only_course_counts_for_engineering_not_general(client):
    body = client.post("/evaluate", json=_request("engineering", [_course("가상공학전용")])).json()
    engineering, general = body["program_results"]
    assert _group(engineering, "eng_only")["completed_count"] == 1
    assert general["course_groups"] == []
    # 일반 범위에서는 찾지 못했으므로 일반 기준 안내가 붙는다. 총학점은 둘 다 요청 학점으로 센다.
    assert body["unmatched_courses"] == [
        {
            "index": 0,
            "name": "가상공학전용",
            "reason": "(일반프로그램 기준) " + evaluation.UNMATCHED_REASON,
        }
    ]
    assert [row["total"]["earned"] for row in body["program_results"]] == [3, 3]


def test_ambiguity_in_one_scope_does_not_drop_course_from_other_scope(client):
    body = client.post("/evaluate", json=_request("engineering", [_course("가상일반모호")])).json()
    engineering, general = body["program_results"]
    # 일반 범위에서는 후보가 둘이라 모호하지만 공학 범위에서는 하나로 확정된다.
    assert _group(engineering, "eng_amb")["completed_count"] == 1
    assert body["unmatched_courses"] == [
        {
            "index": 0,
            "name": "가상일반모호",
            "reason": "(일반프로그램 기준) " + evaluation.AMBIGUOUS_REASON,
        }
    ]
    assert general["total"]["earned"] == 3


def test_ambiguous_and_unmatched_reasons_differ(client):
    courses = [_course("가상일반모호"), _course("가상없는과목")]
    body = client.post("/evaluate", json=_request("general", courses)).json()
    reasons = {row["index"]: row["reason"] for row in body["unmatched_courses"]}
    assert reasons == {0: evaluation.AMBIGUOUS_REASON, 1: evaluation.UNMATCHED_REASON}
    assert evaluation.AMBIGUOUS_REASON != evaluation.UNMATCHED_REASON


def test_verified_equivalence_satisfies_required_course_once(client):
    # 옛 과목은 공학 범위에서만 verified 관계로 가상AI2를 대신한다.
    courses = [_course(AI_COURSES[0]), _course("가상옛과목")]
    body = client.post("/evaluate", json=_request("engineering", courses)).json()
    group = _common(body, "sub_major_required")
    assert group["status"] == "met"
    assert [row["completed"] for row in group["courses"]] == [True, True, False]
    # 학점은 원래 과목으로 한 번씩만 센다(대체 대상 학점이 더해지지 않는다).
    assert body["program_results"][0]["total"]["earned"] == 6
    # 일반만 요청하면 공학 범위 관계는 쓰이지 않는다.
    general = client.post("/evaluate", json=_request("general", courses)).json()
    assert _common(general, "sub_major_required")["status"] == "unmet"


def test_duplicate_input_rows_are_excluded(client):
    row = _course(AI_COURSES[0])
    body = client.post("/evaluate", json=_request("general", [row, row])).json()
    assert body["excluded_courses"] == [
        {
            "index": 1,
            "name": AI_COURSES[0],
            "reason": "중복 입력: 0번 행과 같은 내용이라 한 번만 반영했습니다.",
        }
    ]
    assert body["program_results"][0]["total"]["earned"] == 3
    assert body["warnings"] == [evaluation.PENDING_DATA_REASON]


def test_catalog_defect_is_500_invalid_rule_data(client, monkeypatch):
    secret = "내부 과목 ID 123"

    def broken(*args, **kwargs):
        raise CatalogValidationError(secret)

    monkeypatch.setattr("app.routers.evaluate.match_courses", broken)
    response = client.post("/evaluate", json=_request("general"))
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_RULE_DATA"
    assert secret not in response.text


def test_incomplete_rule_data_is_500_not_unsupported_scope(client):
    # 범위(2190/ai)는 있는데 공통 비학점 규칙이 하나 빠진 경우
    session = app.dependency_overrides[get_db]()
    session.query(NonCreditRequirement).filter_by(admission_year=YEAR, code="topcit").delete()
    session.flush()
    response = client.post("/evaluate", json=_request("general"))
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "INVALID_RULE_DATA"


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


def test_from_catalog_id_is_strict_inverse():
    assert from_catalog_id(to_catalog_id(42)) == 42
    for value in ("042", " 42", "+42", "4.2", "abc", ""):
        with pytest.raises(ValueError):
            from_catalog_id(value)


def test_course_code_with_course_number_matches_in_both_scopes(client):
    original = {**_course("이름은 달라도 무관"), "course_code": "I030-1-Z901-02"}
    body = client.post("/evaluate", json=_request("engineering", [original])).json()
    assert body["unmatched_courses"] == []
    assert _common(body, "sub_major_required")["completed_count"] == 1
    assert [row["total"]["earned"] for row in body["program_results"]] == [3, 3]
    # 학과코드·분반이 달라도 같은 과목번호면 같은 과목이다.
    other = {**original, "course_code": "0000-1-Z901-xx"}
    general = client.post("/evaluate", json=_request("general", [other])).json()
    assert general["unmatched_courses"] == []
    assert _common(general, "sub_major_required")["completed_count"] == 1


def test_malformed_course_code_is_unmatched_even_if_name_matches(client):
    original = {**_course(AI_COURSES[2]), "course_code": "Z901"}
    body = client.post("/evaluate", json=_request("general", [original])).json()
    assert [row["index"] for row in body["unmatched_courses"]] == [0]
    assert _common(body, "sub_major_required")["completed_count"] == 0
