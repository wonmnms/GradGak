"""`/evaluate` 입력 준비: 프로그램 범위별 매칭 결과를 판정 엔진 입력으로 바꾼다.

매칭 정책(`course_matching`)과 판정 정책(`evaluation`)은 바꾸지 않는다. 매칭 범위와
verified 대체 관계는 프로그램마다 따로 있으므로 범위끼리 합치지 않고, 프로그램마다
자기 범위의 결과로 엔진 입력을 만든다.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

from app.schemas.course_matching import CourseMatch, CourseMatchingResult
from app.schemas.evaluation import CourseNotice, EvaluationCourse
from app.schemas.transcripts import Course
from app.services.sql_course_catalog import from_catalog_id

Program = Literal["engineering", "general"]


def evaluation_scopes(program: Program) -> tuple[Program, ...]:
    """판정에 필요한 프로그램 범위. 공학은 공학·일반 요건을 모두 본다(api-spec 판정 범위)."""
    return ("engineering", "general") if program == "engineering" else ("general",)


def _to_evaluation_course(course: Course, match: CourseMatch) -> EvaluationCourse:
    matched = match.matched_course
    return EvaluationCourse(
        index=match.index,
        course_id=None if matched is None else from_catalog_id(matched.course_id),
        ambiguous=match.status == "ambiguous",
        # 이미 verified 관계만 로드된 단방향 1단계 결과다. 연쇄는 따라가지 않는다.
        equivalent_course_ids=[
            from_catalog_id(candidate.target.course_id)
            for candidate in match.equivalence_candidates
        ],
        name=course.name,
        course_code=course.course_code,
        credits=course.credits,
        grade=course.grade,
        category=course.category,
        is_retake=course.is_retake,
    )


def build_scope_inputs(
    courses: Sequence[Course], scope_results: Mapping[Program, CourseMatchingResult]
) -> tuple[dict[Program, list[EvaluationCourse]], list[CourseNotice]]:
    """프로그램별 엔진 입력과, 중복 입력으로 제외한 행의 안내를 반환한다.

    완전히 같은 입력 행(`duplicate_inputs`)은 엔진 입력에서 빼되 index는 요청 순서를
    그대로 유지한다. 중복 여부는 입력만으로 정해지므로 범위와 무관하다.
    """
    by_scope: dict[Program, list[EvaluationCourse]] = {}
    notices: dict[int, CourseNotice] = {}
    for program, result in scope_results.items():
        rows = result.ordered_results
        if [row.index for row in rows] != list(range(len(courses))):
            raise ValueError("Scope results must follow the request order")
        duplicates = {item.index: item.duplicate_of for item in result.duplicate_inputs}
        for index, duplicate_of in duplicates.items():
            notices[index] = CourseNotice(
                index=index,
                name=courses[index].name,
                reason=f"중복 입력: {duplicate_of}번 행과 같은 내용이라 한 번만 반영했습니다.",
            )
        by_scope[program] = [
            _to_evaluation_course(course, match)
            for course, match in zip(courses, rows, strict=True)
            if match.index not in duplicates
        ]
    return by_scope, [notices[index] for index in sorted(notices)]
