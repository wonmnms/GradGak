"""Resolve transcript identities against a supplied, verified catalog snapshot.

This module has no DB or HTTP dependency. Identity matching never decides credit
recognition: explicit directional equivalences are returned only as metadata for
later, context-aware processing. Every transcript row, including failed grades,
retakes and exact duplicates, remains available in the result.
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.schemas.course_matching import (
    CatalogCourse,
    CourseCatalogSnapshot,
    CourseMatch,
    CourseMatchingResult,
    DuplicateInput,
    EquivalenceCandidate,
    MatchCandidate,
    MatchMethod,
    RepeatedCourseMatch,
)
from app.schemas.transcripts import Course
from app.services.course_catalog import CourseCatalogRepository


class CatalogValidationError(ValueError):
    """The supplied catalog has invalid identities or dangling relationships."""


def normalize_course_name(name: str) -> str:
    """Build a lookup key, retaining punctuation, digits and Unicode width.

    NFC supports canonically equivalent Hangul. Case folding and whitespace
    removal handle presentation changes without fuzzy or compatibility matching.
    The original transcript and catalog names are never rewritten.
    """
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", name).casefold())


# KLAS 학정번호: 학과코드(4)-난이도(1)-과목번호(4)-분반(2). 시간표는 학과코드가 다를 수 있어
# (`0000-1-0019-xx`) 가운데 과목번호만 비교한다. 이 형식이 아니면 번호를 추측하지 않는다.
_COURSE_CODE_PATTERN = re.compile(r"[0-9A-Za-z]{4}-[0-9A-Za-z]-([0-9A-Za-z]{4})-[0-9A-Za-z]{2}")


def extract_course_number(course_code: str) -> str | None:
    """Return the 4-character course number of a 학정번호, or None if the format differs.

    Only outer whitespace is stripped. Case and leading zeros are kept, and a bare
    4-character value is not guessed to be a course number.
    """
    found = _COURSE_CODE_PATTERN.fullmatch(course_code.strip())
    return found.group(1) if found else None


@dataclass
class _Evidence:
    methods: set[MatchMethod] = field(default_factory=set)
    documents: set[str] = field(default_factory=set)


@dataclass
class _CatalogIndex:
    courses: dict[str, CatalogCourse] = field(default_factory=dict)
    numbers: dict[str, set[str]] = field(default_factory=dict)
    names: dict[str, dict[str, _Evidence]] = field(default_factory=dict)
    equivalences: dict[str, dict[str, set[str]]] = field(default_factory=dict)


def _index_catalog(catalog: CourseCatalogSnapshot) -> _CatalogIndex:
    index = _CatalogIndex()
    for course in catalog.courses:
        if course.course_id in index.courses:
            raise CatalogValidationError("과목 데이터에 중복된 과목 ID가 있습니다.")
        index.courses[course.course_id] = course
        for number in course.course_numbers:
            index.numbers.setdefault(number, set()).add(course.course_id)
        evidence = index.names.setdefault(normalize_course_name(course.name), {}).setdefault(
            course.course_id, _Evidence()
        )
        evidence.methods.add("name")

    for alias in catalog.aliases:
        if alias.course_id not in index.courses:
            raise CatalogValidationError("과목명 별칭이 존재하지 않는 과목 ID를 참조합니다.")
        evidence = index.names.setdefault(normalize_course_name(alias.name), {}).setdefault(
            alias.course_id, _Evidence()
        )
        evidence.methods.add("alias")
        evidence.documents.add(alias.source_document)

    for relation in catalog.equivalences:
        if (
            relation.source_course_id not in index.courses
            or relation.target_course_id not in index.courses
        ):
            raise CatalogValidationError("대체·인정 관계가 존재하지 않는 과목 ID를 참조합니다.")
        if relation.source_course_id == relation.target_course_id:
            raise CatalogValidationError("대체·인정 관계의 출발 과목과 대상 과목이 같습니다.")
        documents = index.equivalences.setdefault(relation.source_course_id, {}).setdefault(
            relation.target_course_id, set()
        )
        documents.add(relation.source_document)
    return index


def _find_candidates(course: Course, index: _CatalogIndex) -> tuple[str, list[MatchCandidate]]:
    if course.course_code is not None:
        # A present but unknown/malformed/ambiguous code must not silently fall back to a name.
        number = extract_course_number(course.course_code)
        candidates = [
            MatchCandidate(
                course=index.courses[course_id].model_copy(deep=True), matched_by=["course_number"]
            )
            for course_id in sorted(index.numbers.get(number, set()) if number else set())
        ]
        return "course_number", candidates

    candidates = []
    evidence_by_id = index.names.get(normalize_course_name(course.name), {})
    for course_id, evidence in sorted(evidence_by_id.items()):
        candidates.append(
            MatchCandidate(
                course=index.courses[course_id].model_copy(deep=True),
                matched_by=[method for method in ("name", "alias") if method in evidence.methods],
                source_documents=sorted(evidence.documents),
            )
        )
    return "name", candidates


def _equivalence_candidates(course_id: str, index: _CatalogIndex) -> list[EquivalenceCandidate]:
    # Neither infer reverse relationships nor follow chains or collapse identities.
    return [
        EquivalenceCandidate(
            source_course_id=course_id,
            target=index.courses[target_id].model_copy(deep=True),
            source_documents=sorted(documents),
        )
        for target_id, documents in sorted(index.equivalences.get(course_id, {}).items())
    ]


def _reason(lookup: str, candidates: list[MatchCandidate], course_code: str | None) -> str:
    if not candidates:
        if lookup == "course_number":
            if extract_course_number(course_code or "") is None:
                return (
                    "학정번호 형식(학과코드-난이도-과목번호-분반)이 아니어서 "
                    "과목번호를 확인하지 못했습니다."
                )
            return (
                "학정번호의 과목번호에 해당하는 과목을 찾지 못했습니다. "
                "입력과 과목 데이터를 확인해 주세요."
            )
        return "과목명 또는 확인된 별칭에 해당하는 과목을 찾지 못했습니다."
    if len(candidates) > 1:
        if lookup == "course_number":
            return "같은 과목번호에 해당하는 과목이 여러 개여서 확정하지 못했습니다."
        return "과목명 또는 별칭에 해당하는 과목이 여러 개여서 확정하지 못했습니다."
    if lookup == "course_number":
        return "학정번호의 과목번호로 과목을 찾았습니다."
    if "name" in candidates[0].matched_by:
        return "과목명으로 과목을 찾았습니다."
    return "확인된 과목명 별칭으로 과목을 찾았습니다."


def _input_fingerprint(course: Course) -> tuple:
    """Exact equality of the eight validated input fields, not course identity."""
    return (
        course.year,
        course.term,
        course.course_code,
        course.name,
        course.category,
        course.credits,
        course.grade,
        course.is_retake,
    )


def match_courses(
    courses: Sequence[Course], catalog: CourseCatalogSnapshot
) -> CourseMatchingResult:
    """Match each input once, separating unknown, ambiguous and repeated inputs.

    The repository/caller must supply a curriculum-scoped catalog with verified
    aliases and equivalences. These functions never invent such relationships or
    select a candidate using grades, credits or graduation requirements.
    """
    index = _index_catalog(catalog)
    groups: dict[str, list[CourseMatch]] = {"matched": [], "unmatched": [], "ambiguous": []}
    first_seen: dict[tuple, int] = {}
    duplicates = []
    repeated_indices: dict[str, list[int]] = defaultdict(list)

    for position, course in enumerate(courses):
        fingerprint = _input_fingerprint(course)
        duplicate_of = first_seen.get(fingerprint)
        if duplicate_of is None:
            first_seen[fingerprint] = position
        else:
            duplicates.append(DuplicateInput(index=position, duplicate_of=duplicate_of))

        lookup, candidates = _find_candidates(course, index)
        if len(candidates) == 1:
            status = "matched"
            selected = candidates[0].course
            equivalences = _equivalence_candidates(selected.course_id, index)
            repeated_indices[selected.course_id].append(position)
        elif candidates:
            status, selected, equivalences = "ambiguous", None, []
        else:
            status, selected, equivalences = "unmatched", None, []
        groups[status].append(
            CourseMatch(
                index=position,
                original=course.model_copy(deep=True),
                status=status,
                lookup=lookup,
                matched_course=selected,
                candidates=candidates,
                reason=_reason(lookup, candidates, course.course_code),
                equivalence_candidates=equivalences,
                duplicate_of=duplicate_of,
            )
        )

    repeated = [
        RepeatedCourseMatch(course_id=course_id, indices=positions)
        for course_id, positions in sorted(repeated_indices.items())
        if len(positions) > 1
    ]
    return CourseMatchingResult(
        matched=groups["matched"],
        unmatched=groups["unmatched"],
        ambiguous=groups["ambiguous"],
        duplicate_inputs=duplicates,
        repeated_matches=repeated,
    )


def match_courses_from_repository(
    courses: Sequence[Course],
    repository: CourseCatalogRepository,
    *,
    admission_year: int,
) -> CourseMatchingResult:
    """Load one snapshot for the supplied admission year, propagating failures.

    The caller provides the student's admission year explicitly; transcript
    course years do not determine curriculum scope.
    """
    return match_courses(courses, repository.load_snapshot(admission_year=admission_year))
