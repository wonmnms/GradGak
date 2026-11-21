"""졸업요건 판정 엔진 (최소 버전, #17).

DB·FastAPI와 무관한 순수 함수다. 규칙 값은 모두 `get_rule_bundle()`이 반환한 dict에서
읽고, 여기에는 판정 절차와 아직 팀이 정하지 않은 정책의 임시 기본값만 둔다.
판정은 명시적 규칙으로만 하며 AI 추론을 쓰지 않는다.
"""

from dataclasses import dataclass

from app.schemas.evaluation import (
    STATUS_MET,
    STATUS_PENDING,
    STATUS_UNMET,
    CategoryResult,
    CourseGroupResult,
    CourseNotice,
    CreditResult,
    EvaluationCourse,
    EvaluationResult,
    GroupCourseResult,
    MissingCourse,
    NonCreditResult,
    ProgramResult,
)
from app.services.course_matching import normalize_course_name

# ---------------------------------------------------------------------------
# 정책 미결정 사항 (팀 결정 전 임시 기본값). 바꿀 때는 이 구역만 수정한다.
# ---------------------------------------------------------------------------

# 학점·이수를 인정하는 성적. 여기에 없는 값(F, NP, None/빈 값, "(삭제)", 알 수 없는 표기)은
# 모두 인정하지 않는다. 허용 목록 방식이라 모르는 표기는 보수적으로 제외된다.
RECOGNIZED_GRADES = frozenset({"A+", "A0", "B+", "B0", "C+", "C0", "D+", "D0", "P"})

# PDF(요청) 학점과 DB 학점이 다를 때의 기준: "request" | "catalog" | "min".
# 기본값 "request": 요청의 credits(실제 취득 학점)를 쓰고, DB 학점과 다르면 경고를 남긴다
# (docs/api-spec.md 열린 질문의 현재 안). "min"은 둘 중 작은 값, "catalog"는 DB 학점을 쓴다.
CREDIT_SOURCE = "request"

PENDING_CATEGORY_REASON = "영역 인정 과목 목록이 아직 없어 판정을 보류합니다."
PENDING_DATA_REASON = "규칙 데이터가 미완성이라 최종 충족으로 판정할 수 없습니다."
UNMATCHED_REASON = "과목 데이터에서 찾지 못했습니다."

# 매칭 실패 과목의 총학점 포함 (사용자 결정, 2026-11-15):
# 인정 성적이면 매칭 여부와 상관없이 요청 credits로 총학점에 포함한다.
# 그룹 판정에는 쓰지 않으며 unmatched_courses에도 계속 넣는다.
# course_id가 없으므로 course_code(있으면) 또는 정규화한 과목명으로 묶어 중복을 제거한다.
COUNT_UNMATCHED_IN_TOTAL = True

DELETED_GRADE = "(삭제)"


def grade_exclusion_reason(grade: str | None) -> str | None:
    """성적 때문에 인정하지 않으면 사유를, 인정하면 None을 반환한다."""
    normalized = (grade or "").strip()
    if normalized in RECOGNIZED_GRADES:
        return None
    if not normalized:
        return "성적이 없어(수강 예정 또는 빈 값) 학점·이수로 인정하지 않았습니다."
    return f"성적 '{normalized}'은(는) 학점·이수로 인정하지 않았습니다."


def resolve_credits(
    course: EvaluationCourse, catalog_credits: int | None
) -> tuple[float, str | None]:
    """판정에 쓸 학점과, 두 학점이 다를 때의 경고를 반환한다."""
    if catalog_credits is None or catalog_credits == course.credits:
        return course.credits, None
    warning = (
        f"{course.index}번 과목 '{course.name}'의 학점이 요청({course.credits})과 "
        f"과목 데이터({catalog_credits})에서 다릅니다."
    )
    if CREDIT_SOURCE == "request":
        return course.credits, warning
    if CREDIT_SOURCE == "catalog":
        return catalog_credits, warning
    return min(course.credits, catalog_credits), warning


def _course_key(course: EvaluationCourse) -> tuple:
    if course.course_id is not None:
        return ("id", course.course_id)
    if course.course_code:
        return ("code", course.course_code.strip())
    return ("name", normalize_course_name(course.name))


def _is_retake_row(course: EvaluationCourse) -> bool:
    return course.is_retake or (course.grade or "").strip() == DELETED_GRADE


def deduplicate_retakes(
    courses: list[EvaluationCourse],
    all_courses: list[EvaluationCourse] | None = None,
) -> tuple[list[EvaluationCourse], list, list[str]]:
    """같은 과목으로 묶이는 인정 행 중 재수강인 경우에만 1번만 남긴다.

    과목 키: course_id, 없으면 course_code, 없으면 정규화한 과목명.
    재수강 판단: 같은 키의 행(성적 때문에 제외된 행 포함, `all_courses`) 중 하나라도
    is_retake이거나 "(삭제)" 성적이면 재수강으로 본다. 재수강이면 재수강 표시가 있는 것을
    우선, 그다음 학점이 작은 것(보수적)을 남긴다. 재수강 표시가 없으면 반복 이수나 서로 다른
    옛 과목이 같은 과목에 매칭된 경우일 수 있으므로 모두 인정하고 경고만 남긴다.
    반환: (남긴 과목, 제외한 과목 목록[(과목, 사유)], 경고).
    """
    retake_keys = {_course_key(c) for c in (all_courses or courses) if _is_retake_row(c)}
    groups: dict[tuple, list[EvaluationCourse]] = {}
    for course in courses:
        groups.setdefault(_course_key(course), []).append(course)
    kept, dropped, warnings = [], [], []
    for key, entries in groups.items():
        if len(entries) == 1:
            kept.extend(entries)
        elif key in retake_keys:
            keep = min(entries, key=lambda c: (not c.is_retake, c.credits, c.index))
            kept.append(keep)
            for other in entries:
                if other is not keep:
                    dropped.append(
                        (
                            other,
                            f"같은 과목({keep.index}번)과 중복되어 학점을 한 번만 인정했습니다.",
                        )
                    )
        else:
            kept.extend(entries)
            indexes = ", ".join(f"{c.index}번" for c in entries)
            warnings.append(
                f"{indexes} 과목('{entries[0].name}')이 재수강 표시 없이 중복되었습니다. "
                "모두 인정했으니 확인하세요."
            )
    kept.sort(key=lambda c: c.index)
    return kept, dropped, warnings


# ---------------------------------------------------------------------------
# 판정 절차
# ---------------------------------------------------------------------------


@dataclass
class _Recognized:
    course_ids: set[int]
    total_credits: float


def _combine(statuses: list[str]) -> str:
    if STATUS_UNMET in statuses:
        return STATUS_UNMET
    if STATUS_PENDING in statuses:
        return STATUS_PENDING
    return STATUS_MET


def _catalog_credits(rule_bundle: dict) -> dict[int, int | None]:
    # 한계: 과목 그룹에 속한 과목의 DB 학점만 알 수 있다. 그래서 학점 불일치 검사는
    # 그룹 과목에만 적용되고, 그룹 밖 과목은 항상 요청 학점을 그대로 쓴다.
    groups = [row for row in rule_bundle["common_requirements"] if "min_courses" in row]
    for program in rule_bundle["program_results"]:
        groups.extend(program["course_groups"])
    return {course["course_id"]: course["credits"] for g in groups for course in g["courses"]}


def _evaluate_group(group: dict, completed_ids: set[int]) -> CourseGroupResult:
    courses = [
        GroupCourseResult(
            course_code=course["course_code"],
            name=course["name"],
            completed=course["course_id"] in completed_ids,
        )
        for course in group["courses"]
    ]
    done = sum(course.completed for course in courses)
    return CourseGroupResult(
        id=group["code"],
        label=group["label"],
        status=STATUS_MET if done >= group["min_courses"] else STATUS_UNMET,
        required_count=group["min_courses"],
        completed_count=done,
        courses=courses,
    )


def _evaluate_non_credit(rule: dict, inputs: dict[str, bool]) -> NonCreditResult:
    field = rule["input_field"]
    if field not in inputs:
        raise ValueError(f"Unknown input_field in rule: {field}")
    met = inputs[field] == rule["expected_value"]
    return NonCreditResult(
        id=rule["code"], label=rule["label"], status=STATUS_MET if met else STATUS_UNMET
    )


def _missing_courses(group: dict, completed_ids: set[int]) -> list[MissingCourse]:
    """모든 과목이 필수인 그룹(min_courses == 과목 수)에서 아직 안 들은 과목만 반환한다."""
    if group["min_courses"] != len(group["courses"]):
        return []
    return [
        MissingCourse(course_code=c["course_code"], name=c["name"], credits=c["credits"])
        for c in group["courses"]
        if c["course_id"] not in completed_ids
    ]


def _evaluate_program(program: dict, recognized: _Recognized) -> ProgramResult:
    required = program["total_credits"]
    earned = recognized.total_credits
    total = CreditResult(
        required=required,
        earned=earned,
        remaining=max(required - earned, 0),
        status=STATUS_MET if earned >= required else STATUS_UNMET,
    )
    categories = [
        CategoryResult(
            id=row["code"],
            label=row["code"],
            required=row["min_credits"],
            earned=None,
            remaining=None,
            status=STATUS_PENDING,
            reason=PENDING_CATEGORY_REASON,
        )
        for row in program["categories"]
    ]
    groups = [_evaluate_group(g, recognized.course_ids) for g in program["course_groups"]]
    missing = [
        course
        for g in program["course_groups"]
        for course in _missing_courses(g, recognized.course_ids)
    ]
    status = _combine([total.status] + [c.status for c in categories] + [g.status for g in groups])
    return ProgramResult(
        program=program["program"],
        status=status,
        total=total,
        categories=categories,
        course_groups=groups,
        missing_required_courses=missing,
    )


def evaluate(
    rule_bundle: dict,
    completed: list[EvaluationCourse],
    thesis_passed: bool,
    topcit_taken: bool,
) -> EvaluationResult:
    """rule_bundle(`get_rule_bundle()` 반환값)과 이수과목으로 졸업요건을 판정한다."""
    unmatched, excluded, warnings = [], [], []
    candidates = []
    for course in completed:
        if course.course_id is None:
            unmatched.append(
                CourseNotice(index=course.index, name=course.name, reason=UNMATCHED_REASON)
            )
        reason = grade_exclusion_reason(course.grade)
        if reason is not None:
            excluded.append(CourseNotice(index=course.index, name=course.name, reason=reason))
            continue
        if course.course_id is None and not COUNT_UNMATCHED_IN_TOTAL:
            continue
        candidates.append(course)

    kept, dropped, dup_warnings = deduplicate_retakes(candidates, completed)
    warnings.extend(dup_warnings)
    excluded.extend(CourseNotice(index=c.index, name=c.name, reason=r) for c, r in dropped)
    excluded.sort(key=lambda notice: notice.index)

    catalog = _catalog_credits(rule_bundle)
    total_credits = 0.0
    for course in kept:
        if course.course_id is None:
            total_credits += course.credits
            continue
        credits, warning = resolve_credits(course, catalog.get(course.course_id))
        total_credits += credits
        if warning:
            warnings.append(warning)
    recognized = _Recognized(
        course_ids={c.course_id for c in kept if c.course_id is not None},
        total_credits=total_credits,
    )

    inputs = {"thesis_passed": thesis_passed, "topcit_taken": topcit_taken}
    common = [
        _evaluate_group(row, recognized.course_ids)
        if "min_courses" in row
        else _evaluate_non_credit(row, inputs)
        for row in rule_bundle["common_requirements"]
    ]
    programs = [_evaluate_program(p, recognized) for p in rule_bundle["program_results"]]

    statuses = [row.status for row in common] + [p.status for p in programs]
    pending_data = list(rule_bundle.get("pending_data") or [])
    if not rule_bundle.get("data_complete", False):
        statuses.append(STATUS_PENDING)
        warnings.append(PENDING_DATA_REASON)

    return EvaluationResult(
        graduation_status=_combine(statuses),
        common_requirements=common,
        program_results=programs,
        unmatched_courses=unmatched,
        excluded_courses=excluded,
        pending_data=pending_data,
        warnings=warnings,
    )
