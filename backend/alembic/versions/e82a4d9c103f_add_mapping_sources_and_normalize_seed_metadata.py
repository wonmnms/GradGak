"""Link mapping evidence and normalize existing official seed metadata.

Revision ID: e82a4d9c103f
Revises: b56e01a23d49
"""

from datetime import date

import sqlalchemy as sa

from alembic import op

revision = "e82a4d9c103f"
down_revision = "b56e01a23d49"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("course_aliases", "course_equivalences"):
        op.add_column(table, sa.Column("source_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_source", table, "source_documents", ["source_id"], ["source_id"]
        )
    # Only metadata emitted by the old official seeds is changed. No academic rule is inferred.
    for table in ("requirement_sources", "non_credit_requirements"):
        op.execute(
            sa.text(f"UPDATE {table} SET reviewer = :new WHERE reviewer = :old").bindparams(
                new="김남주", old="사용자 원본 대조 확인 (이 채팅)"
            )
        )
    for old, new in (
        ("2024학번 학점표만 사용자 원본 대조 완료.", "2024학번 학점표만 김남주 원본 대조 완료."),
        (
            "사용자가 5과목명과 각각 3학점을 원본 대조함.",
            "김남주가 5과목명과 각각 3학점을 원본 대조함.",
        ),
    ):
        op.execute(
            sa.text(
                "UPDATE source_documents SET note = replace(note, :old, :new) "
                "WHERE position(:old in note) > 0"
            ).bindparams(old=old, new=new)
        )
    # These seven names were emitted without a department by the old engineering seed.
    # Limit the backfill to its exact official source snapshot and unknown course codes.
    source_url = (
        "https://cs.kw.ac.kr/program/requirement.php?"
        "admin_mode=read&make=&no=2975&page=1&search=&site_type=3"
    )
    course_names = (
        "C프로그래밍",
        "고급C프로그래밍및설계",
        "스마트사회와인공지능",
        "공학설계입문",
        "이산수학",
        "산학협력캡스톤설계1",
        "산학협력캡스톤설계2",
    )

    courses = sa.table(
        "courses",
        sa.column("name", sa.String()),
        sa.column("department", sa.String()),
        sa.column("source_id", sa.Integer()),
        sa.column("course_code", sa.String()),
    )
    sources = sa.table(
        "source_documents",
        sa.column("source_id", sa.Integer()),
        sa.column("url", sa.String()),
        sa.column("retrieved_on", sa.Date()),
    )
    op.execute(
        courses.update()
        .where(
            courses.c.department.is_(None),
            courses.c.course_code.is_(None),
            courses.c.name.in_(course_names),
            courses.c.source_id.in_(
                sa.select(sources.c.source_id).where(
                    sources.c.url == source_url, sources.c.retrieved_on == date(2026, 10, 31)
                )
            ),
        )
        .values(department="소프트웨어학부")
    )


def downgrade():
    # Keep corrected audit metadata; rolling back schema must not erase attribution.
    for table in ("course_equivalences", "course_aliases"):
        op.drop_constraint(f"fk_{table}_source", table, type_="foreignkey")
        op.drop_column(table, "source_id")
