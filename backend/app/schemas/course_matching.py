"""DB-independent matching DTOs, not ORM models or a new HTTP contract.

A catalog snapshot must be scoped to the intended curriculum by its repository.
Alias/equivalence records must come from verified sources; these types do not
assert that a student is eligible for graduation or credit recognition.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.transcripts import Course as TranscriptCourse

NonEmptyText = Annotated[str, Field(min_length=1, strict=True)]
MatchMethod = Literal["course_code", "name", "alias"]


class _MatchingModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class CatalogCourse(_MatchingModel):
    """Only identity fields are required; course_id is an opaque adapter key."""

    course_id: NonEmptyText
    course_code: NonEmptyText | None = None
    name: NonEmptyText


class CourseAlias(_MatchingModel):
    name: NonEmptyText
    course_id: NonEmptyText
    source_document: NonEmptyText


class CourseEquivalence(_MatchingModel):
    """Explicit one-hop direction; eligibility must be scoped by the repository."""

    source_course_id: NonEmptyText
    target_course_id: NonEmptyText
    source_document: NonEmptyText


class CourseCatalogSnapshot(_MatchingModel):
    courses: list[CatalogCourse]
    aliases: list[CourseAlias] = Field(default_factory=list)
    equivalences: list[CourseEquivalence] = Field(default_factory=list)


class MatchCandidate(_MatchingModel):
    course: CatalogCourse
    matched_by: list[MatchMethod]
    source_documents: list[str] = Field(default_factory=list)


class EquivalenceCandidate(_MatchingModel):
    source_course_id: NonEmptyText
    target: CatalogCourse
    source_documents: list[str]


class CourseMatch(_MatchingModel):
    index: int = Field(ge=0)
    original: TranscriptCourse
    status: Literal["matched", "unmatched", "ambiguous"]
    lookup: Literal["course_code", "name"]
    matched_course: CatalogCourse | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)
    reason: str
    equivalence_candidates: list[EquivalenceCandidate] = Field(default_factory=list)
    duplicate_of: int | None = Field(default=None, ge=0)


class DuplicateInput(_MatchingModel):
    index: int = Field(ge=0)
    duplicate_of: int = Field(ge=0)


class RepeatedCourseMatch(_MatchingModel):
    course_id: NonEmptyText
    indices: list[int]


class CourseMatchingResult(_MatchingModel):
    matched: list[CourseMatch] = Field(default_factory=list)
    unmatched: list[CourseMatch] = Field(default_factory=list)
    ambiguous: list[CourseMatch] = Field(default_factory=list)
    duplicate_inputs: list[DuplicateInput] = Field(default_factory=list)
    repeated_matches: list[RepeatedCourseMatch] = Field(default_factory=list)

    @property
    def ordered_results(self) -> list[CourseMatch]:
        """Return every original row once in input order, including failures."""
        return sorted(self.matched + self.unmatched + self.ambiguous, key=lambda item: item.index)
