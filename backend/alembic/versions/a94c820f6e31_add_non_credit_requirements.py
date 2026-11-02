"""Add common non-credit rule definitions without storing student results.

Revision ID: a94c820f6e31
Revises: d73a1e94c621
"""

import sqlalchemy as sa

from alembic import op

revision = "a94c820f6e31"
down_revision = "d73a1e94c621"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "non_credit_requirements",
        sa.Column("rule_id", sa.Integer(), primary_key=True),
        sa.Column("admission_year", sa.Integer(), nullable=False),
        sa.Column("sub_major", sa.String(50), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("input_field", sa.String(50), nullable=False),
        sa.Column("expected_value", sa.Boolean(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_locator", sa.String(500), nullable=False),
        sa.Column("reviewer", sa.String(100), nullable=False),
        sa.Column("reviewed_on", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source_documents.source_id"]),
        sa.UniqueConstraint(
            "admission_year", "sub_major", "code", name="uq_non_credit_requirement_scope"
        ),
        sa.CheckConstraint("length(trim(reviewer)) > 0", name="ck_non_credit_reviewer_nonempty"),
    )


def downgrade() -> None:
    op.drop_table("non_credit_requirements")
