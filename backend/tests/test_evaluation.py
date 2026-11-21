"""판정 엔진 단위 테스트. DB 없이 rule_bundle dict를 직접 만든다. 과목·값은 모두 가상이다."""

import pytest

from app.schemas.evaluation import (
    STATUS_MET,
    STATUS_PENDING,
    STATUS_UNMET,
    CourseGroupResult,
    EvaluationCourse,
)
from app.services import evaluation
from app.services.evaluation import evaluate

TOTAL = 20  # 가상 총학점

# 가상 과목: 1~5 세부전공필수 그룹, 11~12 단일 필수, 21~22 택1 그룹, 90 일반 과목
SUB_MAJOR_COURSES = [
    {"course_id": i, "course_code": None, "name": f"가상세부{i}", "credits": 3, "source_id": 1}
    for i in range(1, 6)
]


def _course(course_id, name):
    return {"course_id": course_id, "course_code": None, "name": name, "credits": None}


def _non_credit():
    return [
        {
            "code": "thesis",
            "label": "가상 논문",
            "input_field": "thesis_passed",
            "expected_value": True,
            "source_id": 1,
        },
        {
            "code": "topcit",
            "label": "가상 TOPCIT",
            "input_field": "topcit_taken",
            "expected_value": True,
            "source_id": 1,
        },
    ]


def _program(program):
    groups = []
    if program == "engineering":
        groups = [
            {
                "code": "required_a",
                "label": "필수 이수: 가상필수A",
                "min_courses": 1,
                "source_id": 1,
                "courses": [_course(11, "가상필수A")],
            },
            {
                "code": "required_b",
                "label": "필수 이수: 가상필수B",
                "min_courses": 1,
                "source_id": 1,
                "courses": [_course(12, "가상필수B")],
            },
            {
                "code": "required_capstone",
                "label": "가상캡스톤 택1",
                "min_courses": 1,
                "source_id": 1,
                "courses": [_course(21, "가상캡스톤1"), _course(22, "가상캡스톤2")],
            },
        ]
    return {
        "program": program,
        "requirement_id": 1 if program == "engineering" else 2,
        "total_credits": TOTAL,
        "categories": [
            {"code": "virtual_area", "min_credits": 6, "parent_code": None, "note": None}
        ],
        "course_groups": groups,
    }


def make_bundle(program="engineering", sub_major="ai", data_complete=False):
    programs = ["engineering", "general"] if program == "engineering" else ["general"]
    common = []
    if sub_major == "ai":
        common.append(
            {
                "code": "sub_major_required",
                "label": "가상 세부전공필수",
                "min_courses": 3,
                "source_id": 1,
                "courses": SUB_MAJOR_COURSES,
            }
        )
    common.extend(_non_credit())
    return {
        "admission_year": 2099,
        "sub_major": sub_major,
        "program_results": [_program(p) for p in programs],
        "common_requirements": common,
        "data_complete": data_complete,
        "pending_data": [] if data_complete else ["virtual_pending"],
    }


def courses(*specs):
    """specs: (course_id, credits, grade[, is_retake])"""
    result = []
    for index, spec in enumerate(specs):
        course_id, credits, grade, *rest = spec
        result.append(
            EvaluationCourse(
                index=index,
                course_id=course_id,
                name=f"가상과목{index}",
                credits=credits,
                grade=grade,
                is_retake=rest[0] if rest else False,
            )
        )
    return result


def full_engineering_courses():
    return courses((1, 3, "A+"), (2, 3, "A0"), (3, 3, "B+"), (11, 3, "A0"), (12, 3, "P"),
                   (21, 3, "B0"), (90, 2, "C0"))  # fmt: skip


def common_by_id(result):
    return {row.id: row for row in result.common_requirements}


# --- 프로그램 범위 ----------------------------------------------------------


@pytest.mark.parametrize("sub_major", ["software", "ai"])
def test_engineering_returns_engineering_then_general(sub_major):
    result = evaluate(make_bundle("engineering", sub_major), [], True, True)
    assert [p.program for p in result.program_results] == ["engineering", "general"]


@pytest.mark.parametrize("sub_major", ["software", "ai"])
def test_general_returns_only_general(sub_major):
    result = evaluate(make_bundle("general", sub_major), [], True, True)
    assert [p.program for p in result.program_results] == ["general"]
    assert result.program_results[0].course_groups == []


def test_software_has_no_sub_major_group():
    result = evaluate(make_bundle("general", "software"), [], True, True)
    assert set(common_by_id(result)) == {"thesis", "topcit"}


def test_ai_has_sub_major_group_once():
    result = evaluate(make_bundle("engineering", "ai"), [], True, True)
    ids = [row.id for row in result.common_requirements]
    assert ids.count("sub_major_required") == 1


# --- 그룹 경계값 ------------------------------------------------------------


@pytest.mark.parametrize(
    ("taken", "expected"),
    [(2, STATUS_UNMET), (3, STATUS_MET), (5, STATUS_MET)],
)
def test_sub_major_group_boundary(taken, expected):
    completed = courses(*[(i, 3, "A0") for i in range(1, taken + 1)])
    group = common_by_id(evaluate(make_bundle("general", "ai"), completed, True, True))[
        "sub_major_required"
    ]
    assert isinstance(group, CourseGroupResult)
    assert group.status == expected
    assert group.completed_count == taken
    assert group.required_count == 3
    assert [c.completed for c in group.courses] == [i <= taken for i in range(1, 6)]


def test_engineering_groups_and_missing_required_courses():
    completed = courses((11, 3, "A0"))
    eng = evaluate(make_bundle("engineering", "software"), completed, True, True).program_results[0]
    groups = {g.id: g.status for g in eng.course_groups}
    assert groups == {
        "required_a": STATUS_MET,
        "required_b": STATUS_UNMET,
        "required_capstone": STATUS_UNMET,
    }
    # 택1 그룹 과목은 '필수과목 누락'에 넣지 않는다
    assert [m.name for m in eng.missing_required_courses] == ["가상필수B"]
    assert eng.status == STATUS_UNMET


def test_capstone_either_course_satisfies_group():
    for course_id in (21, 22):
        eng = evaluate(
            make_bundle("engineering", "software"), courses((course_id, 3, "A0")), True, True
        ).program_results[0]
        capstone = next(g for g in eng.course_groups if g.id == "required_capstone")
        assert capstone.status == STATUS_MET


# --- 논문·TOPCIT ------------------------------------------------------------


@pytest.mark.parametrize("thesis", [True, False])
@pytest.mark.parametrize("topcit", [True, False])
def test_thesis_topcit_combinations(thesis, topcit):
    result = evaluate(make_bundle("general", "software"), [], thesis, topcit)
    rows = common_by_id(result)
    assert rows["thesis"].status == (STATUS_MET if thesis else STATUS_UNMET)
    assert rows["topcit"].status == (STATUS_MET if topcit else STATUS_UNMET)


def test_unknown_input_field_is_rejected():
    bundle = make_bundle("general", "software")
    bundle["common_requirements"][0]["input_field"] = "unknown_field"
    with pytest.raises(ValueError, match="Unknown input_field"):
        evaluate(bundle, [], True, True)


# --- 총학점·영역 보류·최종 판정 ---------------------------------------------


def test_total_credits_and_categories_pending():
    result = evaluate(make_bundle("engineering", "ai"), full_engineering_courses(), True, True)
    for program in result.program_results:
        assert program.total.required == TOTAL
        assert program.total.earned == 20
        assert program.total.remaining == 0
        assert program.total.status == STATUS_MET
        assert all(c.status == STATUS_PENDING for c in program.categories)
        assert all(c.earned is None for c in program.categories)
        assert program.status == STATUS_PENDING
    # 판정 가능한 요건을 모두 충족해도 영역별 학점이 보류라 최종 충족이 아니다
    assert result.graduation_status == STATUS_PENDING
    assert result.pending_data == ["virtual_pending"]


def test_unmet_takes_precedence_over_pending():
    result = evaluate(make_bundle("engineering", "ai"), full_engineering_courses(), False, True)
    assert result.graduation_status == STATUS_UNMET


def test_total_credits_shortfall():
    result = evaluate(make_bundle("general", "software"), courses((90, 5, "A0")), True, True)
    total = result.program_results[0].total
    assert (total.earned, total.remaining, total.status) == (5, TOTAL - 5, STATUS_UNMET)


def test_data_complete_with_no_categories_can_be_met():
    bundle = make_bundle("engineering", "ai", data_complete=True)
    for program in bundle["program_results"]:
        program["categories"] = []
    result = evaluate(bundle, full_engineering_courses(), True, True)
    assert result.graduation_status == STATUS_MET


def test_incomplete_data_blocks_met_even_without_categories():
    bundle = make_bundle("engineering", "ai", data_complete=False)
    for program in bundle["program_results"]:
        program["categories"] = []
    result = evaluate(bundle, full_engineering_courses(), True, True)
    assert result.graduation_status == STATUS_PENDING
    assert evaluation.PENDING_DATA_REASON in result.warnings


# --- 성적 정책 --------------------------------------------------------------


@pytest.mark.parametrize("grade", ["F", "NP", None, "", "  ", "(삭제)", "X?"])
def test_non_recognized_grades_are_excluded(grade):
    completed = courses((1, 3, grade), (90, 3, "A0"))
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 3
    assert common_by_id(result)["sub_major_required"].completed_count == 0
    assert [n.index for n in result.excluded_courses] == [0]


def test_f_grade_does_not_complete_required_course():
    completed = courses((11, 3, "F"))
    eng = evaluate(make_bundle("engineering", "software"), completed, True, True).program_results[0]
    assert next(g for g in eng.course_groups if g.id == "required_a").status == STATUS_UNMET


# --- 재수강 -----------------------------------------------------------------


def test_retake_after_f_counts_once():
    completed = courses((1, 3, "F"), (1, 3, "B0", True))
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 3
    assert common_by_id(result)["sub_major_required"].completed_count == 1


def test_duplicate_passing_entries_count_once():
    completed = courses((1, 3, "D0"), (1, 3, "A0", True))
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 3
    assert [n.index for n in result.excluded_courses] == [0]  # 재수강 표시된 1번을 남긴다


# --- 매칭 실패·학점 기준 -----------------------------------------------------


def test_unmatched_recognized_course_counts_in_total_with_warning():
    completed = [
        EvaluationCourse(index=0, course_id=None, name="가상미매칭", credits=3, grade="A0"),
        EvaluationCourse(index=1, course_id=90, name="가상일반", credits=3, grade="A0"),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert [(n.index, n.name) for n in result.unmatched_courses] == [(0, "가상미매칭")]
    assert result.program_results[0].total.earned == 6
    assert result.excluded_courses == []


def test_unmatched_course_is_not_used_for_groups():
    completed = [
        EvaluationCourse(index=0, course_id=None, name="가상세부1", credits=3, grade="A0"),
        EvaluationCourse(index=1, course_id=None, name="가상세부2", credits=3, grade="B0"),
    ]
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert common_by_id(result)["sub_major_required"].completed_count == 0
    assert result.program_results[0].total.earned == 6


@pytest.mark.parametrize("grade", ["F", "NP"])
def test_unmatched_failed_course_is_excluded_from_total(grade):
    completed = [
        EvaluationCourse(index=0, course_id=None, name="가상미매칭", credits=3, grade=grade),
        EvaluationCourse(index=1, course_id=90, name="가상일반", credits=3, grade="A0"),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert result.program_results[0].total.earned == 3
    assert [n.index for n in result.unmatched_courses] == [0]
    assert [n.index for n in result.excluded_courses] == [0]


def test_credit_mismatch_uses_request_credit_and_warns():
    completed = courses((1, 4, "A0"))  # 과목 데이터는 3학점
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 4
    assert any("학점이 요청" in w for w in result.warnings)


def test_credit_source_min_option(monkeypatch):
    monkeypatch.setattr(evaluation, "CREDIT_SOURCE", "min")
    result = evaluate(make_bundle("general", "ai"), courses((1, 4, "A0")), True, True)
    assert result.program_results[0].total.earned == 3
    assert any("학점이 요청" in w for w in result.warnings)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_evaluation_course_rejects_non_finite_credits(value):
    with pytest.raises(ValueError):
        EvaluationCourse(index=0, course_id=1, name="가상", credits=value, grade="A0")


def test_repeated_course_without_retake_mark_counts_both_and_warns():
    result = evaluate(
        make_bundle("general", "ai"), courses((90, 3, "A0"), (90, 3, "B0")), True, True
    )
    assert result.program_results[0].total.earned == 6
    assert result.excluded_courses == []
    assert any("재수강 표시 없이 중복" in w for w in result.warnings)


def test_deleted_grade_row_marks_retake():
    completed = courses((90, 3, "(삭제)"), (90, 3, "A0"), (90, 3, "B0"))
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 3


def test_unmatched_retake_counts_once():
    completed = [
        EvaluationCourse(index=0, course_id=None, name="가상 미매칭", credits=3, grade="D0"),
        EvaluationCourse(
            index=1, course_id=None, name="가상미매칭", credits=3, grade="A0", is_retake=True
        ),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert result.program_results[0].total.earned == 3
    assert [n.index for n in result.excluded_courses] == [0]


def test_unmatched_same_course_code_without_retake_counts_both_and_warns():
    completed = [
        EvaluationCourse(
            index=0, course_id=None, name="가상갑", credits=3, grade="A0", course_code="X1"
        ),
        EvaluationCourse(
            index=1, course_id=None, name="가상을", credits=3, grade="A0", course_code="X1"
        ),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert result.program_results[0].total.earned == 6
    assert any("재수강 표시 없이 중복" in w for w in result.warnings)


def test_unknown_catalog_credit_uses_request_credit():
    completed = courses((11, 2, "A0"))  # 과목 데이터 학점이 None
    eng = evaluate(make_bundle("engineering", "software"), completed, True, True).program_results[0]
    assert eng.total.earned == 2


def test_result_serializes_to_api_shape():
    data = evaluate(make_bundle("engineering", "ai"), [], True, True).model_dump()
    assert set(data) >= {
        "graduation_status",
        "common_requirements",
        "program_results",
        "unmatched_courses",
    }
    assert set(data["program_results"][0]) == {
        "program",
        "status",
        "total",
        "categories",
        "course_groups",
        "missing_required_courses",
    }
