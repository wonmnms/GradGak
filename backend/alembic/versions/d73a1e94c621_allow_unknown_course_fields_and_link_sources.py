"""Allow unknown course fields and link course/group source documents.

Revision ID: d73a1e94c621
Revises: 3b761ccade13
"""

import sqlalchemy as sa

from alembic import op

revision = "d73a1e94c621"
down_revision = "3b761ccade13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("courses", "course_code", existing_type=sa.String(30), nullable=True)
    op.alter_column("courses", "course_type", existing_type=sa.String(50), nullable=True)
    op.add_column("courses", sa.Column("source_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_courses_source", "courses", "source_documents", ["source_id"], ["source_id"]
    )
    op.add_column("course_group_requirements", sa.Column("source_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_course_groups_source",
        "course_group_requirements",
        "source_documents",
        ["source_id"],
        ["source_id"],
    )


def downgrade() -> None:
    # NULL인 미확인 값을 먼저 실제 자료로 보완해야 NOT NULL로 되돌릴 수 있다.
    op.drop_constraint("fk_course_groups_source", "course_group_requirements", type_="foreignkey")
    op.drop_column("course_group_requirements", "source_id")
    op.drop_constraint("fk_courses_source", "courses", type_="foreignkey")
    op.drop_column("courses", "source_id")
    op.alter_column("courses", "course_type", existing_type=sa.String(50), nullable=False)
    op.alter_column("courses", "course_code", existing_type=sa.String(30), nullable=False)
