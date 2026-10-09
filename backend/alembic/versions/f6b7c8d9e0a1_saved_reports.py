"""saved report files with public links (reports table)

Revision ID: f6b7c8d9e0a1
Revises: e5a6b7c8d9f0
Create Date: 2026-10-09 16:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (SQLModel column types)
from alembic import op

import app.db

revision: str = "f6b7c8d9e0a1"
down_revision: str | Sequence[str] | None = "e5a6b7c8d9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("format", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("scope_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_built_at", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_token", "reports", ["token"], unique=True)
    op.create_index("ix_reports_scope_hash", "reports", ["scope_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reports_scope_hash", table_name="reports")
    op.drop_index("ix_reports_token", table_name="reports")
    op.drop_table("reports")
