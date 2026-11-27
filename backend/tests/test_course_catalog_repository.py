"""실제 PostgreSQL에서 가상 데이터로 과목 카탈로그 DB 어댑터의 범위·검증 필터를 확인한다."""

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Course,
    CourseAlias,
    CourseEquivalence,
    CourseGroupRequirement,
    CourseGroupRequirementCourse,
    CourseNumber,
    GraduationRequirement,
    RequirementCategory,
    RequirementCategoryCourse,
    RequirementSource,
    SourceDocument,
)
from app.schemas.transcripts import Course as TranscriptCourse
from app.services.course_matching import match_courses
from app.services.sql_course_catalog import SqlCourseCatalogRepository


@dataclass
class CatalogData:
    session: Session
    sub_major: str
    courses: dict[str, Course]
    sources: dict[str, SourceDocument]
    requirements: dict[str, GraduationRequirement]

    def cid(self, key: str) -> str:
        return str(self.courses[key].course_id)

    def repo(self, program: str = "engineering") -> SqlCourseCatalogRepository:
        return SqlCourseCatalogRepository(self.session, program=program, sub_major=self.sub_major)


@pytest.fixture
def catalog_data():
    with SessionLocal() as session:
        try:
            token = uuid4().hex[:12]
            sub_major = f"TEST-{token}"
            requirements = {
                program: GraduationRequirement(
                    admission_year=2024, program=program, sub_major=sub_major, total_credits=10
                )
                for program in ("engineering", "general")
            }
            # mapped: 공학 영역 과목, grouped: 공학 그룹 과목, old: 대체 관계의 이수 과목,
            # general_only: 일반 그룹에만 있는 과목, unmapped: 어떤 범위에도 없는 과목
            courses = {
                "mapped": Course(course_code=None, name="가상 새과목"),
                "grouped": Course(course_code=None, name="가상 그룹과목"),
                "old": Course(course_code=None, name="가상 옛과목"),
                "general_only": Course(course_code=None, name="가상 일반과목"),
                "unmapped": Course(course_code=None, name="가상 무관과목"),
            }
            sources = {
                key: SourceDocument(
                    title=f"TEST {key}",
                    url=f"https://example.invalid/{token}/{key}",
                    retrieved_on=date(2099, 1, 1),
                )
                for key in (
                    "verified",
                    "pending",
                    "rejected",
                    "unreviewed",
                    "general_verified",
                )
            }
            session.add_all([*requirements.values(), *courses.values(), *sources.values()])
            session.flush()
            eng, gen = requirements["engineering"], requirements["general"]

            category = RequirementCategory(
                requirement_id=eng.requirement_id, category="TEST", min_credits=3
            )
            groups = {
                req: CourseGroupRequirement(
                    requirement_id=req.requirement_id, group_code="TEST", name="TEST", min_courses=1
                )
                for req in (eng, gen)
            }
            session.add_all([category, *groups.values()])
            session.flush()
            session.add_all(
                [
                    RequirementCategoryCourse(
                        category_id=category.category_id,
                        course_id=courses["mapped"].course_id,
                    ),
                    CourseGroupRequirementCourse(
                        group_id=groups[eng].group_id, course_id=courses["grouped"].course_id
                    ),
                    CourseGroupRequirementCourse(
                        group_id=groups[gen].group_id,
                        course_id=courses["general_only"].course_id,
                    ),
                    *[
                        RequirementSource(
                            requirement_id=req.requirement_id,
                            source_id=sources[key].source_id,
                            locator="TEST",
                            review_status=status,
                            reviewer="TEST_REVIEWER" if status == "verified" else None,
                            reviewed_on=date(2099, 1, 2) if status == "verified" else None,
                        )
                        for req, key, status in (
                            (eng, "verified", "verified"),
                            (eng, "pending", "pending"),
                            (eng, "rejected", "rejected"),
                            (gen, "general_verified", "verified"),
                        )
                    ],
                ]
            )
            session.flush()
            yield CatalogData(session, sub_major, courses, sources, requirements)
        finally:
            session.rollback()


def _add_alias(data: CatalogData, course: str, name: str, source: str | None) -> None:
    source_id = None if source is None else data.sources[source].source_id
    data.session.add(
        CourseAlias(course_id=data.courses[course].course_id, alias_name=name, source_id=source_id)
    )
    data.session.flush()


def _add_equivalence(
    data: CatalogData, program: str, completed: str, recognized: str, source: str | None
) -> None:
    data.session.add(
        CourseEquivalence(
            requirement_id=data.requirements[program].requirement_id,
            completed_course_id=data.courses[completed].course_id,
            recognized_course_id=data.courses[recognized].course_id,
            source_id=None if source is None else data.sources[source].source_id,
        )
    )
    data.session.flush()


def _add_number(
    data: CatalogData, course: str, number: str, status: str, source: str = "verified"
) -> None:
    data.session.add(
        CourseNumber(
            course_id=data.courses[course].course_id,
            course_number=number,
            source_id=data.sources[source].source_id,
            review_status=status,
            reviewer="TEST_REVIEWER" if status == "verified" else None,
            reviewed_on=date(2099, 1, 2) if status == "verified" else None,
        )
    )
    data.session.flush()


def test_snapshot_carries_only_verified_course_numbers_of_scoped_courses(catalog_data):
    data = catalog_data
    _add_number(data, "mapped", "1183", "verified")
    _add_number(data, "mapped", "A001", "pending")
    _add_number(data, "mapped", "A002", "needs_clarification")
    _add_number(data, "mapped", "A003", "rejected")
    _add_number(data, "grouped", "0019", "verified")
    _add_number(data, "unmapped", "0020", "verified")

    snapshot = data.repo().load_snapshot(2024)

    by_id = {course.course_id: course for course in snapshot.courses}
    assert by_id[data.cid("mapped")].course_numbers == ["1183"]
    assert by_id[data.cid("grouped")].course_numbers == ["0019"]
    assert data.cid("unmapped") not in by_id


def test_verified_number_matches_klas_course_code_with_other_department(catalog_data):
    data = catalog_data
    _add_number(data, "mapped", "0019", "verified")
    _add_number(data, "grouped", "0020", "pending")

    def transcript(code: str) -> TranscriptCourse:
        return TranscriptCourse(
            year=2031,
            term="1",
            course_code=code,
            name="무관",
            category="전선",
            credits=3,
            grade="A0",
            is_retake=False,
        )

    result = match_courses(
        [transcript("I030-1-0019-02"), transcript("0000-1-0019-xx"), transcript("I030-1-0020-01")],
        data.repo().load_snapshot(2024),
    )

    assert [row.matched_course.course_id for row in result.matched] == [data.cid("mapped")] * 2
    assert [row.index for row in result.unmatched] == [2]


def test_converts_orm_rows_with_one_id_rule(catalog_data):
    data = catalog_data
    _add_alias(data, "mapped", "가상 이전이름", "verified")
    _add_equivalence(data, "engineering", "old", "mapped", "verified")

    snapshot = data.repo().load_snapshot(2024)

    by_id = {course.course_id: course for course in snapshot.courses}
    assert set(by_id) == {data.cid("mapped"), data.cid("grouped"), data.cid("old")}
    assert all(course.course_numbers == [] for course in by_id.values())
    assert by_id[data.cid("old")].name == "가상 옛과목"
    [alias] = snapshot.aliases
    assert alias.name == "가상 이전이름"
    assert alias.course_id == data.cid("mapped")
    assert alias.source_document == data.sources["verified"].url
    [relation] = snapshot.equivalences
    assert relation.source_course_id == data.cid("old")
    assert relation.target_course_id == data.cid("mapped")
    assert relation.source_document == data.sources["verified"].url


def test_excludes_courses_outside_requirement_scope(catalog_data):
    data = catalog_data
    _add_alias(data, "unmapped", "가상 무관별칭", "verified")

    engineering = data.repo("engineering").load_snapshot(2024)
    general = data.repo("general").load_snapshot(2024)

    eng_ids = {course.course_id for course in engineering.courses}
    assert data.cid("unmapped") not in eng_ids
    assert data.cid("general_only") not in eng_ids
    assert engineering.aliases == []
    assert [course.course_id for course in general.courses] == [data.cid("general_only")]


def test_excludes_equivalences_of_other_requirement_scope(catalog_data):
    data = catalog_data
    _add_equivalence(data, "general", "old", "general_only", "general_verified")

    engineering = data.repo("engineering").load_snapshot(2024)
    general = data.repo("general").load_snapshot(2024)

    assert engineering.equivalences == []
    assert data.cid("old") not in {course.course_id for course in engineering.courses}
    assert [(r.source_course_id, r.target_course_id) for r in general.equivalences] == [
        (data.cid("old"), data.cid("general_only"))
    ]


@pytest.mark.parametrize(
    "source",
    [
        None,  # 출처 미확인
        "unreviewed",  # SourceDocument만 연결, 검증 기록 없음
        "pending",
        "rejected",
        "general_verified",  # 다른 졸업요건 범위에서만 검증됨
    ],
)
def test_excludes_unverified_aliases_and_equivalences(catalog_data, source):
    data = catalog_data
    _add_alias(data, "mapped", "가상 미검증별칭", source)
    _add_equivalence(data, "engineering", "grouped", "mapped", source)

    snapshot = data.repo().load_snapshot(2024)

    assert snapshot.aliases == []
    assert snapshot.equivalences == []


def test_scope_arguments_are_required(catalog_data):
    session = catalog_data.session
    with pytest.raises(TypeError):
        SqlCourseCatalogRepository(session)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        SqlCourseCatalogRepository(session, program="engineering")  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        SqlCourseCatalogRepository(session, program=" ", sub_major=catalog_data.sub_major)
    with pytest.raises(ValueError):
        SqlCourseCatalogRepository(session, program="engineering", sub_major=None)  # type: ignore[arg-type]
    repo = catalog_data.repo()
    with pytest.raises(TypeError):
        repo.load_snapshot()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        repo.load_snapshot("2024")  # type: ignore[arg-type]
    with pytest.raises(LookupError):
        repo.load_snapshot(2023)


def test_db_errors_propagate():
    engine = create_engine("postgresql+psycopg2://postgres:postgres@127.0.0.1:1/none")
    try:
        with Session(engine) as session:
            repo = SqlCourseCatalogRepository(session, program="engineering", sub_major="TEST")
            with pytest.raises(OperationalError):
                repo.load_snapshot(2024)
    finally:
        engine.dispose()


def test_match_courses_end_to_end(catalog_data):
    data = catalog_data
    _add_alias(data, "mapped", "가상 이전이름", "verified")
    _add_equivalence(data, "engineering", "old", "mapped", "verified")
    _add_number(data, "mapped", "0019", "verified", "verified")

    def transcript(name: str, code: str | None = None) -> TranscriptCourse:
        return TranscriptCourse(
            year=2031,
            term="1",
            course_code=code,
            name=name,
            category="전선",
            credits=3,
            grade="A0",
            is_retake=False,
        )

    inputs = [
        transcript("가상 이전이름"),
        transcript("가상옛과목"),
        transcript("가상 무관과목"),
        transcript("무관", "I030-1-0019-02"),
    ]
    result = match_courses(inputs, data.repo().load_snapshot(2024))

    assert [row.matched_course.course_id for row in result.matched] == [
        data.cid("mapped"),
        data.cid("old"),
        data.cid("mapped"),
    ]
    assert result.matched[0].candidates[0].matched_by == ["alias"]
    [equivalence] = result.matched[1].equivalence_candidates
    assert equivalence.target.course_id == data.cid("mapped")
    assert equivalence.source_documents == [data.sources["verified"].url]
    assert [row.index for row in result.unmatched] == [2]
