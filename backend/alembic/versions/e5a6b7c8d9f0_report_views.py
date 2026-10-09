"""report views for querying reports in the cloud database console (app/report_views.sql)

Revision ID: e5a6b7c8d9f0
Revises: d4f1a2b3c4e5
Create Date: 2026-10-09 15:30:00

"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "e5a6b7c8d9f0"
down_revision: str | Sequence[str] | None = "d4f1a2b3c4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQL_FILE = Path(__file__).resolve().parents[2] / "app" / "report_views.sql"


def _statements() -> list[str]:
    lines = [ln for ln in SQL_FILE.read_text(encoding="utf-8").splitlines() if not ln.startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def _views() -> list[str]:
    return [s.split()[4] for s in _statements()]  # "CREATE OR REPLACE VIEW <name> AS …"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return  # local mode: use `make export-sqlite` instead (the views use Postgres JSON functions)
    for stmt in _statements():
        bind.exec_driver_sql(stmt)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    for name in reversed(_views()):
        bind.exec_driver_sql(f"DROP VIEW IF EXISTS {name}")
