"""Port for converting scoped ORM records into DB-independent matching DTOs."""

from typing import Protocol

from app.schemas.course_matching import CourseCatalogSnapshot


class CourseCatalogRepository(Protocol):
    def load_snapshot(self, admission_year: int) -> CourseCatalogSnapshot:
        """Return a single curriculum-scoped catalog and verified relations.

        admission_year is the student's curriculum year, not a course's year.
        The adapter owns DB identity conversion and source verification. Other
        scope (department/program/sub-major) must be supplied explicitly by the
        adapter's context before it filters applicable equivalences. A DB failure
        should propagate rather than masquerade as unmatched courses.
        """
        ...
