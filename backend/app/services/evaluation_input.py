"""`/evaluate` 입력 준비: 프로그램 범위별 매칭 결과를 합쳐 판정 엔진 입력으로 바꾼다.

매칭 정책(`course_matching`)과 판정 정책(`evaluation`)은 바꾸지 않는다. 여기서는
범위별 스냅샷의 결과를 한 행당 하나의 course_id로 합치는 규칙만 둔다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.schemas.course_matching import CourseMatchingResult
from app.schemas.evaluation import EvaluationCourse
from app.schemas.transcripts import Course
from app.services.sql_course_catalog import from_catalog_id

Program = Literal["engineering", "general"]


def evaluation_scopes(program: Program) -> tuple[Program, ...]:
    """판정에 필요한 프로그램 범위. 공학은 공학·일반 요건을 모두 본다(api-spec 판정 범위)."""
    return ("engineering", "general") if program == "engineering" else ("general",)


@dataclass(frozen=True)
class MergedMatch:
    index: int
    status: Literal["matched", "unmatched", "ambiguous"]
    course_id: str | None


def merge_scope_matches(scope_results: Sequence[CourseMatchingResult]) -> list[MergedMatch]:
    """같은 입력에 대한 범위별 매칭 결과를 행마다 하나로 합친다.

    course_id는 DB 전역 키이므로 범위가 달라도 같은 id면 같은 과목이다.
    - 어느 범위에서든 모호하면 모호하다(정체성이 확정되지 않음).
    - 매칭된 id가 범위마다 다르면 모호하다. 하나를 임의로 고르지 않는다.
    - 매칭된 id가 하나뿐이면 그 id를 쓴다(다른 범위에서 못 찾은 것은 상관없다).
    - 어느 범위에서도 못 찾으면 매칭 실패다.
    """
    if not scope_results:
        raise ValueError("At least one scope result is required")
    per_scope = [result.ordered_results for result in scope_results]
    if len({len(rows) for rows in per_scope}) != 1:
        raise ValueError("Scope results must cover the same input rows")

    merged = []
    for rows in zip(*per_scope, strict=True):
        index = rows[0].index
        if any(row.index != index for row in rows):
            raise ValueError("Scope results must cover the same input rows")
        ids = {row.matched_course.course_id for row in rows if row.status == "matched"}
        if any(row.status == "ambiguous" for row in rows) or len(ids) > 1:
            merged.append(MergedMatch(index=index, status="ambiguous", course_id=None))
        elif ids:
            merged.append(MergedMatch(index=index, status="matched", course_id=ids.pop()))
        else:
            merged.append(MergedMatch(index=index, status="unmatched", course_id=None))
    return merged


def to_evaluation_courses(
    courses: Sequence[Course], merged: Sequence[MergedMatch]
) -> list[EvaluationCourse]:
    """요청 과목과 합친 매칭 결과를 판정 엔진 입력으로 바꾼다. 실패·모호는 course_id=None."""
    if [match.index for match in merged] != list(range(len(courses))):
        raise ValueError("Merged matches must follow the request order")
    return [
        EvaluationCourse(
            index=match.index,
            course_id=None if match.course_id is None else from_catalog_id(match.course_id),
            name=course.name,
            course_code=course.course_code,
            credits=course.credits,
            grade=course.grade,
            category=course.category,
            is_retake=course.is_retake,
        )
        for course, match in zip(courses, merged, strict=True)
    ]
