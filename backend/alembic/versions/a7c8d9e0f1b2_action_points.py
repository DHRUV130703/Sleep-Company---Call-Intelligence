"""next actions as short points (actions.points) instead of a line to read out

Revision ID: a7c8d9e0f1b2
Revises: f6b7c8d9e0a1
Create Date: 2026-10-18 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c8d9e0f1b2"
down_revision: str | Sequence[str] | None = "f6b7c8d9e0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("actions") as batch:
        batch.add_column(sa.Column("points", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("actions") as batch:
        batch.drop_column("points")
