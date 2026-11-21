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
from app.services.evaluation import evaluate as evaluate_by_program

TOTAL = 20  # 가상 총학점


def evaluate(bundle, completed, thesis_passed, topcit_taken):
    """리스트면 모든 프로그램에 같은 과목을 준다(엔진은 프로그램별 Mapping만 받는다)."""
    if not isinstance(completed, dict):
        completed = {row["program"]: completed for row in bundle["program_results"]}
    return evaluate_by_program(bundle, completed, thesis_passed, topcit_taken)


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


@pytest.mark.parametrize("grade", ["F", "NP", None, "", "  ", "C+(삭제)", "(삭제)", "X?"])
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
    completed = courses((90, 3, "C+(삭제)"), (90, 3, "A0"), (90, 3, "B0"))
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 3


def test_deleted_grade_with_original_grade_dedups_same_course_id():
    completed = courses((5, 3, "C+(삭제)", False), (5, 3, "B0", False), (5, 3, "A0", False))
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 3


def test_unmatched_rows_group_by_name_even_if_only_one_has_code():
    completed = [
        EvaluationCourse(
            index=0, course_id=None, name="X과목", credits=3, grade="D0", course_code="A1"
        ),
        EvaluationCourse(
            index=1, course_id=None, name="X과목", credits=3, grade="A0", is_retake=True
        ),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert result.program_results[0].total.earned == 3
    assert not any("원 수강 기록을 찾지 못했습니다" in w for w in result.warnings)


def test_retake_without_original_warns_when_matched_and_unmatched_differ():
    completed = [
        EvaluationCourse(index=0, course_id=None, name="컴퓨팅사고", credits=3, grade="D0"),
        EvaluationCourse(
            index=1, course_id=7, name="스마트사회와인공지능", credits=3, grade="A0", is_retake=True
        ),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert (
        "1번 과목('스마트사회와인공지능')은 재수강으로 표시됐지만 원 수강 기록을 찾지 못했습니다. "
        "이전 과목명이 다르면 학점이 중복 인정될 수 있으니 확인하세요."
    ) in result.warnings


def test_retake_flag_only_on_excluded_row_warns_when_merging():
    completed = courses((90, 3, "D+(삭제)", True), (90, 3, "A0"), (90, 3, "B0"))
    result = evaluate(make_bundle("general", "ai"), completed, True, True)
    assert result.program_results[0].total.earned == 3
    assert any("제외된 0번 행의 재수강 표시" in w for w in result.warnings)


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


# --- 프로그램별 입력·대체 관계·모호 사유 -------------------------------------------


def test_per_program_input_uses_own_scope_courses():
    bundle = make_bundle("engineering", "software")
    # 공학 범위에서만 가상필수A(11)로 매칭, 일반 범위에서는 매칭 실패
    by_program = {
        "engineering": courses((11, 3, "A0")),
        "general": [
            EvaluationCourse(index=0, course_id=None, name="가상과목0", credits=3, grade="A0")
        ],
    }
    result = evaluate(bundle, by_program, True, True)
    eng, general = result.program_results
    assert {g.id: g.status for g in eng.course_groups}["required_a"] == STATUS_MET
    assert general.course_groups == []
    assert [n.reason for n in result.unmatched_courses] == [
        f"(일반프로그램 기준) {evaluation.UNMATCHED_REASON}"
    ]


def test_equivalent_course_ids_complete_group_without_extra_credits():
    # 90번 과목이 verified 관계로 필수 11번을 대신한다. 학점은 90번 기준 3점뿐이다.
    completed = [
        EvaluationCourse(
            index=0,
            course_id=90,
            name="가상옛과목",
            credits=3,
            grade="A0",
            equivalent_course_ids=[11],
        )
    ]
    eng = evaluate(make_bundle("engineering", "software"), completed, True, True).program_results[0]
    assert {g.id: g.status for g in eng.course_groups}["required_a"] == STATUS_MET
    assert eng.total.earned == 3


def test_equivalence_is_not_applied_for_failed_grade():
    completed = [
        EvaluationCourse(
            index=0,
            course_id=90,
            name="가상옛과목",
            credits=3,
            grade="F",
            equivalent_course_ids=[11],
        )
    ]
    eng = evaluate(make_bundle("engineering", "software"), completed, True, True).program_results[0]
    assert {g.id: g.status for g in eng.course_groups}["required_a"] == STATUS_UNMET


def test_ambiguous_reason_differs_from_unmatched():
    completed = [
        EvaluationCourse(
            index=0, course_id=None, name="가상모호", credits=3, grade="A0", ambiguous=True
        ),
        EvaluationCourse(index=1, course_id=None, name="가상없음", credits=3, grade="A0"),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert [n.reason for n in result.unmatched_courses] == [
        evaluation.AMBIGUOUS_REASON,
        evaluation.UNMATCHED_REASON,
    ]


def test_equivalent_target_fills_only_one_group_slot():
    # 그룹 {1,2}에서 min 2. 과목 1만 이수하고 1→2 대체 관계가 있어도 1칸만 채운다.
    bundle = make_bundle("general", "ai")
    bundle["common_requirements"][0]["courses"] = SUB_MAJOR_COURSES[:2]
    bundle["common_requirements"][0]["min_courses"] = 2
    completed = [
        EvaluationCourse(
            index=0,
            course_id=1,
            name="가상세부1",
            credits=3,
            grade="A0",
            equivalent_course_ids=[2, 3],
        )
    ]
    group = common_by_id(evaluate(bundle, completed, True, True))["sub_major_required"]
    assert group.status == STATUS_UNMET
    assert group.completed_count == 1


def test_original_and_equivalent_both_kept_warns():
    completed = [
        EvaluationCourse(
            index=0,
            course_id=90,
            name="가상옛과목",
            credits=3,
            grade="A0",
            equivalent_course_ids=[11],
        ),
        EvaluationCourse(index=1, course_id=11, name="가상필수A", credits=3, grade="A0"),
    ]
    result = evaluate(make_bundle("general", "software"), completed, True, True)
    assert result.program_results[0].total.earned == 6
    assert sum("대체·인정 관계" in w for w in result.warnings) == 1


def test_missing_program_input_is_rejected():
    with pytest.raises(ValueError, match="missing programs"):
        evaluate_by_program(make_bundle("engineering", "ai"), {"general": []}, True, True)
