"""SQLAlchemy ORM 모델."""

from app.models.base import Base
from app.models.course import Course
from app.models.course_alias import CourseAlias
from app.models.course_equivalence import CourseEquivalence
from app.models.course_group_requirement import CourseGroupRequirement
from app.models.course_group_requirement_course import CourseGroupRequirementCourse
from app.models.graduation_requirement import GraduationRequirement
from app.models.non_credit_requirement import NonCreditRequirement
from app.models.requirement_category import RequirementCategory
from app.models.requirement_category_course import RequirementCategoryCourse
from app.models.requirement_source import RequirementSource
from app.models.source_document import SourceDocument

__all__ = [
    "Base",
    "Course",
    "CourseGroupRequirement",
    "CourseGroupRequirementCourse",
    "GraduationRequirement",
    "RequirementCategory",
    "RequirementCategoryCourse",
    "CourseAlias",
    "CourseEquivalence",
    "RequirementSource",
    "SourceDocument",
    "NonCreditRequirement",
]
