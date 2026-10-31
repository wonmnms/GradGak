"""DB의 규칙을 백엔드에 제공한다. 졸업 판정 계산이나 API 응답 DTO는 아니다."""

from sqlalchemy import select

from app.models import (
    Course,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    GraduationRequirement,
    NonCreditRequirement,
    RequirementCategory,
)


def get_rule_bundle(session, admission_year, program, sub_major):
    if program not in ("engineering", "general"):
        raise ValueError("Unsupported program")
    if sub_major not in ("software", "ai"):
        raise ValueError("Unsupported sub_major")
    programs = ("engineering", "general") if program == "engineering" else ("general",)
    program_results = []
    common = []
    common_group = None
    for selected_program in programs:
        requirement = session.execute(
            select(GraduationRequirement).filter_by(
                admission_year=admission_year,
                program=selected_program,
                sub_major=sub_major,
            )
        ).scalar_one_or_none()
        if requirement is None:
            raise LookupError(f"No rule scope: {admission_year}/{selected_program}/{sub_major}")
        categories = session.scalars(
            select(RequirementCategory)
            .where(RequirementCategory.requirement_id == requirement.requirement_id)
            .order_by(RequirementCategory.category)
        ).all()
        groups = session.scalars(
            select(CourseGroupRequirement)
            .where(CourseGroupRequirement.requirement_id == requirement.requirement_id)
            .order_by(CourseGroupRequirement.group_code)
        ).all()
        category_codes = {row.category_id: row.category for row in categories}
        if any(
            row.parent_category_id is not None and row.parent_category_id not in category_codes
            for row in categories
        ):
            raise LookupError("Category parent is outside the selected requirement")
        program_groups = []
        if sub_major == "ai" and not any(
            group.group_code == "sub_major_required" for group in groups
        ):
            raise LookupError(f"Missing AI course group for {selected_program}")
        for group in groups:
            courses = session.scalars(
                select(Course)
                .join(CourseGroupRequirementCourse)
                .where(CourseGroupRequirementCourse.group_id == group.group_id)
                .order_by(Course.course_id)
            ).all()
            if len(courses) < group.min_courses:
                raise LookupError(f"Incomplete course group: {group.group_id}")
            item = {
                "code": group.group_code,
                "label": group.name,
                "min_courses": group.min_courses,
                "source_id": group.source_id,
                "courses": [
                    {
                        "course_id": course.course_id,
                        "course_code": course.course_code,
                        "name": course.name,
                        "credits": course.credits,
                        "source_id": course.source_id,
                    }
                    for course in courses
                ],
            }
            if group.group_code == "sub_major_required":
                if common_group is not None and common_group != item:
                    raise LookupError("Conflicting common course group across programs")
                common_group = item
            else:
                program_groups.append(item)
        program_results.append(
            {
                "program": selected_program,
                "requirement_id": requirement.requirement_id,
                "total_credits": requirement.total_credits,
                "categories": [
                    {
                        "code": row.category,
                        "min_credits": row.min_credits,
                        "parent_code": category_codes.get(row.parent_category_id),
                        "note": row.note,
                    }
                    for row in categories
                ],
                "course_groups": program_groups,
            }
        )

    if sub_major == "ai":
        if common_group is None:
            raise LookupError("Missing AI common course group")
        common.append(common_group)
    non_credit = session.scalars(
        select(NonCreditRequirement)
        .filter_by(admission_year=admission_year, sub_major=sub_major)
        .order_by(NonCreditRequirement.code)
    ).all()
    if not {"thesis", "topcit"}.issubset({rule.code for rule in non_credit}):
        raise LookupError("Missing common non-credit rules")
    common.extend(
        {
            "code": rule.code,
            "label": rule.label,
            "input_field": rule.input_field,
            "expected_value": rule.expected_value,
            "source_id": rule.source_id,
        }
        for rule in non_credit
    )
    return {
        "admission_year": admission_year,
        "sub_major": sub_major,
        "program_results": program_results,
        "common_requirements": common,
        "data_complete": False,
        "pending_data": [
            "program_credit_mappings_and_category_course_lists",
            "general_education_subconditions_and_exemptions",
            "verified_course_codes_and_equivalences",
        ],
    }
