"""졸업요건 판정 엔진 (최소 버전, #17).

DB·FastAPI와 무관한 순수 함수다. 규칙 값은 모두 `get_rule_bundle()`이 반환한 dict에서
읽고, 여기에는 판정 절차와 아직 팀이 정하지 않은 정책의 임시 기본값만 둔다.
판정은 명시적 규칙으로만 하며 AI 추론을 쓰지 않는다.
"""

from collections.abc import Mapping, Sequence
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
AMBIGUOUS_REASON = "같은 이름·학수번호의 과목 후보가 여러 개라 하나로 확정하지 못했습니다."
PROGRAM_LABELS = {"engineering": "공학", "general": "일반"}

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


def _is_retake_row(course: EvaluationCourse) -> bool:
    # 실제 성적 표기는 "C+(삭제)"처럼 원 성적 뒤에 "(삭제)"가 붙는다.
    return course.is_retake or (course.grade or "").strip().endswith(DELETED_GRADE)


def _group_courses(courses: list[EvaluationCourse]) -> dict[int, tuple]:
    """각 과목(`id(course)`)이 속한 같은 과목 그룹의 대표 키를 반환한다.

    매칭된 과목은 course_id로 묶는다. 매칭 실패 과목은 course_code가 같거나 정규화한
    과목명이 같으면 같은 그룹이다(한쪽에만 code가 있어도 이름이 같으면 묶음).
    매칭 행과 매칭 실패 행은 엔진이 카탈로그 code/name을 모르므로 묶지 않는다.
    """
    parent: dict[tuple, tuple] = {}

    def find(token: tuple) -> tuple:
        parent.setdefault(token, token)
        while parent[token] != token:
            parent[token] = parent[parent[token]]
            token = parent[token]
        return token

    def tokens(course: EvaluationCourse) -> list[tuple]:
        if course.course_id is not None:
            return [("id", course.course_id)]
        result = [("name", normalize_course_name(course.name))]
        if course.course_code and course.course_code.strip():
            result.append(("code", course.course_code.strip()))
        return result

    for course in courses:
        first, *rest = tokens(course)
        for token in rest:
            parent[find(token)] = find(first)
        find(first)
    return {id(course): find(tokens(course)[0]) for course in courses}


def deduplicate_retakes(
    courses: list[EvaluationCourse],
    all_courses: list[EvaluationCourse] | None = None,
) -> tuple[list[EvaluationCourse], list, list[str]]:
    """같은 과목으로 묶이는 인정 행 중 재수강인 경우에만 1번만 남긴다.

    그룹 기준은 `_group_courses` 참고. 재수강 판단: 같은 그룹의 행(성적 때문에 제외된 행
    포함, `all_courses`) 중 하나라도 is_retake이거나 성적이 "(삭제)"로 끝나면 재수강으로
    본다. 재수강이면 재수강 표시가 있는 것을 우선, 그다음 학점이 작은 것(보수적)을 남긴다.
    재수강 표시가 없으면 반복 이수나 서로 다른 옛 과목이 같은 과목에 매칭된 경우일 수
    있으므로 모두 인정하고 경고만 남긴다. is_retake인데 같은 그룹에 다른 행(원 수강)이
    없으면 이전 과목명이 달라 중복 인정될 수 있으므로 경고한다.
    반환: (남긴 과목, 제외한 과목 목록[(과목, 사유)], 경고).
    """
    universe = all_courses or courses
    keys = _group_courses(universe)
    members: dict[tuple, list[EvaluationCourse]] = {}
    for c in universe:
        members.setdefault(keys[id(c)], []).append(c)
    groups: dict[tuple, list[EvaluationCourse]] = {}
    for course in courses:
        groups.setdefault(keys[id(course)], []).append(course)
    kept, dropped, warnings = [], [], []
    for course in universe:
        if course.is_retake and len(members[keys[id(course)]]) == 1:
            warnings.append(
                f"{course.index}번 과목('{course.name}')은 재수강으로 표시됐지만 원 수강 기록을 "
                "찾지 못했습니다. 이전 과목명이 다르면 학점이 중복 인정될 수 있으니 확인하세요."
            )
    for key, entries in groups.items():
        retake_rows = [c for c in members[key] if _is_retake_row(c)]
        if len(entries) == 1:
            kept.extend(entries)
        elif retake_rows:
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
            if not any(_is_retake_row(c) for c in entries):
                indexes = ", ".join(f"{c.index}번" for c in entries)
                sources = ", ".join(f"{c.index}번" for c in retake_rows)
                warnings.append(
                    f"{indexes} 과목('{entries[0].name}')은 성적 때문에 제외된 {sources} 행의 "
                    "재수강 표시를 근거로 한 번만 인정했습니다. 확인하세요."
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


@dataclass
class _Prepared:
    """한 프로그램 범위의 매칭 결과로 정리한 인정 과목과 안내."""

    recognized: _Recognized
    unmatched: list[CourseNotice]
    excluded: list[CourseNotice]
    warnings: list[str]


def _prepare(completed: list[EvaluationCourse], catalog: dict[int, int | None]) -> _Prepared:
    """성적·재수강·학점 정책을 적용해 인정 과목 id와 총학점을 구한다."""
    unmatched, excluded, warnings = [], [], []
    candidates = []
    for course in completed:
        if course.course_id is None:
            reason = AMBIGUOUS_REASON if course.ambiguous else UNMATCHED_REASON
            unmatched.append(CourseNotice(index=course.index, name=course.name, reason=reason))
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

    total_credits = 0.0
    for course in kept:
        if course.course_id is None:
            total_credits += course.credits
            continue
        credits, warning = resolve_credits(course, catalog.get(course.course_id))
        total_credits += credits
        if warning:
            warnings.append(warning)
    # 대체·인정 대상은 이수한 것으로 보되 학점은 원래 과목으로 한 번만 센다(위 합계).
    course_ids = {c.course_id for c in kept if c.course_id is not None}
    course_ids.update(target for c in kept for target in c.equivalent_course_ids)
    return _Prepared(_Recognized(course_ids, total_credits), unmatched, excluded, warnings)


def _program_label(program: str) -> str:
    return PROGRAM_LABELS.get(program, program)


def _merge_notices(per_program: dict[str, list[CourseNotice]]) -> list[CourseNotice]:
    """프로그램별 안내를 (index, 사유)로 중복 제거해 합친다.

    일부 프로그램에서만 나온 안내는 사유 앞에 어느 프로그램 기준인지 붙인다.
    """
    owners: dict[tuple[int, str], dict[str, CourseNotice]] = {}
    for program, notices in per_program.items():
        for notice in notices:
            owners.setdefault((notice.index, notice.reason), {})[program] = notice
    merged = []
    for owner in owners.values():
        if len(owner) == len(per_program):
            merged.append(next(iter(owner.values())))
            continue
        for program, notice in owner.items():
            reason = f"({_program_label(program)}프로그램 기준) {notice.reason}"
            merged.append(notice.model_copy(update={"reason": reason}))
    merged.sort(key=lambda notice: notice.index)
    return merged


def _merge_warnings(per_program: dict[str, list[str]]) -> list[str]:
    owners: dict[str, list[str]] = {}
    for program, warnings in per_program.items():
        for warning in warnings:
            if program not in owners.setdefault(warning, []):
                owners[warning].append(program)
    merged = []
    for warning, programs in owners.items():
        if len(programs) == len(per_program):
            merged.append(warning)
        else:
            labels = "·".join(_program_label(program) for program in programs)
            merged.append(f"({labels}프로그램 기준) {warning}")
    return merged


def evaluate(
    rule_bundle: dict,
    completed: Sequence[EvaluationCourse] | Mapping[str, Sequence[EvaluationCourse]],
    thesis_passed: bool,
    topcit_taken: bool,
) -> EvaluationResult:
    """rule_bundle(`get_rule_bundle()` 반환값)과 이수과목으로 졸업요건을 판정한다.

    `completed`는 프로그램별 매칭 결과다({"engineering": [...], "general": [...]}). 매칭 범위와
    verified 대체 관계가 프로그램마다 달라서, 각 프로그램 결과는 자기 범위의 과목으로만
    판정한다. 공통 요건은 `program_results`의 첫 항목(학생이 요청한 프로그램)의 과목으로
    판정한다. 리스트를 주면 모든 프로그램에 같은 과목을 쓴다.

    호출 계약: 완전히 같은 중복 행(PDF 중복·입력 실수)은 엔진이 구분하지 못한다. 호출자는
    매칭 모듈의 `duplicate_inputs`에 해당하는 행을 엔진에 넣기 전에 제외해야 한다
    (`evaluation_input.build_scope_inputs`가 한다).
    """
    programs = [row["program"] for row in rule_bundle["program_results"]]
    if isinstance(completed, Mapping):
        by_program = {program: list(completed[program]) for program in programs}
    else:
        by_program = {program: list(completed) for program in programs}
    catalog = _catalog_credits(rule_bundle)
    prepared = {program: _prepare(rows, catalog) for program, rows in by_program.items()}

    inputs = {"thesis_passed": thesis_passed, "topcit_taken": topcit_taken}
    common_ids = prepared[programs[0]].recognized.course_ids
    common = [
        _evaluate_group(row, common_ids)
        if "min_courses" in row
        else _evaluate_non_credit(row, inputs)
        for row in rule_bundle["common_requirements"]
    ]
    results = [
        _evaluate_program(p, prepared[p["program"]].recognized)
        for p in rule_bundle["program_results"]
    ]

    warnings = _merge_warnings({program: item.warnings for program, item in prepared.items()})
    statuses = [row.status for row in common] + [p.status for p in results]
    pending_data = list(rule_bundle.get("pending_data") or [])
    if not rule_bundle.get("data_complete", False):
        statuses.append(STATUS_PENDING)
        warnings.append(PENDING_DATA_REASON)

    return EvaluationResult(
        graduation_status=_combine(statuses),
        common_requirements=common,
        program_results=results,
        unmatched_courses=_merge_notices({p: item.unmatched for p, item in prepared.items()}),
        excluded_courses=_merge_notices({p: item.excluded for p, item in prepared.items()}),
        pending_data=pending_data,
        warnings=warnings,
    )
