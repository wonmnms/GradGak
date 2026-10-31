"""Port for a future DB adapter; no SQLAlchemy table definitions are assumed."""

from typing import Protocol

from app.schemas.course_matching import CourseCatalogSnapshot


class CourseCatalogRepository(Protocol):
    def load_snapshot(self) -> CourseCatalogSnapshot:
        """Return a single curriculum-scoped catalog and verified relations.

        The adapter owns DB identity conversion, curriculum/department/year
        filtering, applicable equivalence scope and source verification. A DB
        failure should propagate rather than masquerade as unmatched courses.
        """
        ...
