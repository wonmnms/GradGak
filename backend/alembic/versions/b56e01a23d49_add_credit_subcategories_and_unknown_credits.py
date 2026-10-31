"""Add nested credit requirements and preserve unknown course credits.

Revision ID: b56e01a23d49
Revises: a94c820f6e31
"""

import sqlalchemy as sa

from alembic import op

revision = "b56e01a23d49"
down_revision = "a94c820f6e31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("courses", "credits", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "requirement_categories", sa.Column("parent_category_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_requirement_category_parent",
        "requirement_categories",
        "requirement_categories",
        ["parent_category_id"],
        ["category_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_requirement_category_parent", "requirement_categories", type_="foreignkey"
    )
    op.drop_column("requirement_categories", "parent_category_id")
    # 미확인 학점을 실제 자료로 채워야 NOT NULL로 되돌릴 수 있다.
    op.alter_column("courses", "credits", existing_type=sa.Integer(), nullable=False)
