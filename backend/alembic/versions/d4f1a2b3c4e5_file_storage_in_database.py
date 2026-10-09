"""file storage in the database (blobs, blob_parts) and worker heartbeat

Revision ID: d4f1a2b3c4e5
Revises: bbbbee1ddde7
Create Date: 2026-10-09 13:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (SQLModel column types)
from alembic import op

import app.db

revision: str = "d4f1a2b3c4e5"
down_revision: str | Sequence[str] | None = "bbbbee1ddde7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blobs",
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("parts", sa.Integer(), nullable=False),
        sa.Column("content_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "blob_parts",
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("key", "idx"),
    )
    op.create_table(
        "worker_heartbeats",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("beat_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
    op.drop_table("blob_parts")
    op.drop_table("blobs")
