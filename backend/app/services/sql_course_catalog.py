"""SQLAlchemy adapter that builds one requirement-scoped matching catalog.

Kept separate from ``course_catalog`` so the matching service stays free of DB
imports. One instance reads exactly one ``GraduationRequirement`` scope
(admission_year/program/sub_major). An engineering evaluation needs both the
engineering and general scopes, so the caller loads one snapshot per scope;
merging them would leak requirement-specific equivalences across programs.

Verification rule: an alias or equivalence is included only when its
``source_id`` has a ``RequirementSource`` row with ``review_status='verified'``
for this scope's requirement. A linked ``SourceDocument`` alone is not proof
of human review, and a NULL ``source_id`` means unconfirmed evidence.
"""

from pydantic import ValidationError
from sqlalchemy import and_, select, union
from sqlalchemy.orm import Session

from app.models import (
    Course,
    CourseAlias,
    CourseEquivalence,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    GraduationRequirement,
    RequirementCategory,
    RequirementCategoryCourse,
    RequirementSource,
    SourceDocument,
)
from app.schemas.course_matching import (
    CatalogCourse,
    CourseCatalogSnapshot,
)
from app.schemas.course_matching import (
    CourseAlias as AliasDTO,
)
from app.schemas.course_matching import (
    CourseEquivalence as EquivalenceDTO,
)
from app.services.rule_errors import InvalidRuleDataError
from app.services.rule_repository import RuleScopeNotFound

VERIFIED = "verified"


def to_catalog_id(course_id: int) -> str:
    """The single int -> opaque str rule used for courses, aliases and relations."""
    return str(course_id)


def from_catalog_id(catalog_id: str) -> int:
    """Inverse of ``to_catalog_id``; rejects any string it would not produce."""
    course_id = int(catalog_id)
    if to_catalog_id(course_id) != catalog_id:
        raise ValueError(f"Not a catalog id: {catalog_id!r}")
    return course_id


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


class SqlCourseCatalogRepository:
    """``CourseCatalogRepository`` over one graduation requirement scope.

    The session lifetime belongs to the caller. DB errors propagate unchanged.
    """

    def __init__(self, session: Session, *, program: str, sub_major: str) -> None:
        self._session = session
        self._program = _require_text("program", program)
        self._sub_major = _require_text("sub_major", sub_major)

    def load_snapshot(self, admission_year: int) -> CourseCatalogSnapshot:
        if isinstance(admission_year, bool) or not isinstance(admission_year, int):
            raise TypeError("admission_year must be an int")
        requirement_id = self._requirement_id(admission_year)

        equivalence_rows = self._session.execute(
            select(CourseEquivalence, SourceDocument.url)
            .join(SourceDocument, SourceDocument.source_id == CourseEquivalence.source_id)
            .join(
                RequirementSource,
                and_(
                    RequirementSource.requirement_id == CourseEquivalence.requirement_id,
                    RequirementSource.source_id == CourseEquivalence.source_id,
                ),
            )
            .where(
                CourseEquivalence.requirement_id == requirement_id,
                RequirementSource.review_status == VERIFIED,
            )
            .order_by(CourseEquivalence.equivalence_id)
        ).all()

        course_ids = set(self._session.scalars(self._curriculum_course_ids(requirement_id)))
        for relation, _ in equivalence_rows:
            # A verified relation's completed course (often an old course) must be
            # matchable, so both endpoints join the catalog.
            course_ids.update((relation.completed_course_id, relation.recognized_course_id))

        courses = self._session.scalars(
            select(Course).where(Course.course_id.in_(course_ids)).order_by(Course.course_id)
        ).all()
        alias_rows = self._session.execute(
            select(CourseAlias, SourceDocument.url)
            .join(SourceDocument, SourceDocument.source_id == CourseAlias.source_id)
            .join(RequirementSource, RequirementSource.source_id == CourseAlias.source_id)
            .where(
                RequirementSource.requirement_id == requirement_id,
                RequirementSource.review_status == VERIFIED,
                CourseAlias.course_id.in_(course_ids),
            )
            .order_by(CourseAlias.alias_id)
        ).all()

        try:
            return CourseCatalogSnapshot(
                courses=[
                    CatalogCourse(
                        course_id=to_catalog_id(course.course_id),
                        course_code=course.course_code,
                        name=course.name,
                    )
                    for course in courses
                ],
                aliases=[
                    AliasDTO(
                        name=alias.alias_name,
                        course_id=to_catalog_id(alias.course_id),
                        source_document=url,
                    )
                    for alias, url in alias_rows
                ],
                equivalences=[
                    EquivalenceDTO(
                        source_course_id=to_catalog_id(relation.completed_course_id),
                        target_course_id=to_catalog_id(relation.recognized_course_id),
                        source_document=url,
                    )
                    for relation, url in equivalence_rows
                ],
            )
        except ValidationError as exc:
            raise InvalidRuleDataError("Invalid catalog rows") from exc

    def _requirement_id(self, admission_year: int) -> int:
        requirement_id = self._session.scalar(
            select(GraduationRequirement.requirement_id).filter_by(
                admission_year=admission_year, program=self._program, sub_major=self._sub_major
            )
        )
        if requirement_id is None:
            # Never substitute another admission year or program.
            raise RuleScopeNotFound(
                f"No requirement scope: {admission_year}/{self._program}/{self._sub_major}"
            )
        return requirement_id

    @staticmethod
    def _curriculum_course_ids(requirement_id: int):
        """Courses the requirement maps through categories or course groups."""
        return union(
            select(RequirementCategoryCourse.course_id)
            .join(
                RequirementCategory,
                RequirementCategory.category_id == RequirementCategoryCourse.category_id,
            )
            .where(RequirementCategory.requirement_id == requirement_id),
            select(CourseGroupRequirementCourse.course_id)
            .join(
                CourseGroupRequirement,
                CourseGroupRequirement.group_id == CourseGroupRequirementCourse.group_id,
            )
            .where(CourseGroupRequirement.requirement_id == requirement_id),
        )
