"""Workspaces: one app, separate data. Each sign-in account belongs to a workspace; each workspace has
its own database (in the same CockroachDB cluster or another one). Nothing is shared between workspaces.

    workspace "main"  → DATABASE_URL (the original database)
    other workspaces  → WORKSPACE_DATABASES, JSON: {"ashish": "postgresql://…/limezip_ashish?…"}
    who is in which   → APP_USERS, JSON: {"name@company.com": {"password": "…", "workspace": "ashish"}}
                        (a plain "password" value means workspace "main")

How it works: the sign-in check (auth.py) sets `current_workspace` for each request; db.get_engine()
returns that workspace's database, so every query, file and job stays inside it. The background worker
goes through each workspace in turn. Several people can share a workspace (a team) by naming the same one.

Commands: `make migrate` (every workspace's database), `make workspace name=<name>` (a new one).
"""

import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from app.config import get_settings

log = logging.getLogger("workspaces")

MAIN = "main"
current_workspace: ContextVar[str] = ContextVar("current_workspace", default=MAIN)


def database_urls() -> dict[str, str]:
    """{workspace: database URL}, "main" first."""
    s = get_settings()
    extra: dict[str, str] = {}
    if s.workspace_databases.strip():
        try:
            extra = {str(k): str(v) for k, v in json.loads(s.workspace_databases).items()}
        except (ValueError, AttributeError):
            log.error('WORKSPACE_DATABASES is not valid JSON like {"name": "postgresql://…"}')
    return {MAIN: s.db_url, **{k: v for k, v in extra.items() if k != MAIN}}


def names() -> list[str]:
    return list(database_urls())


def database_url(workspace: str) -> str:
    urls = database_urls()
    if workspace not in urls:
        raise LookupError(f"workspace {workspace!r} has no database in WORKSPACE_DATABASES")
    return urls[workspace]


@contextmanager
def in_workspace(workspace: str) -> Iterator[None]:
    """Run a block of code against one workspace's database (used by the worker and CLI tools)."""
    token = current_workspace.set(workspace)
    try:
        yield
    finally:
        current_workspace.reset(token)


def migrate_all() -> None:
    """Apply database changes (Alembic) to every workspace's database."""
    backend = Path(__file__).resolve().parents[1]
    for ws, url in database_urls().items():
        print(f"Updating workspace {ws!r}…", flush=True)
        env = {**os.environ, "DATABASE_URL": url}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend, check=True, env=env)


def create(name: str) -> None:
    """A new, empty database `limezip_<name>` in the main database's cluster, with all tables.
    Then add it to WORKSPACE_DATABASES and assign people to it in APP_USERS."""
    from sqlalchemy import create_engine

    from app.db import engine_url

    main_url = get_settings().db_url
    if "/defaultdb" not in main_url:
        sys.exit("DATABASE_URL must point at the cluster's defaultdb to create workspaces next to it.")
    with create_engine(engine_url(main_url)).connect() as c:
        c.exec_driver_sql(f"CREATE DATABASE IF NOT EXISTS limezip_{name}")
        c.commit()
    url = main_url.replace("/defaultdb", f"/limezip_{name}", 1)
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend, check=True, env=env)
    print(f"Created database limezip_{name} with all tables.")
    print(
        f'Add to WORKSPACE_DATABASES: "{name}": "<DATABASE_URL with /limezip_{name} instead of /defaultdb>"'
    )


def main() -> None:
    """python -m app.workspaces migrate          → update every workspace's database
    python -m app.workspaces create <name>    → a new workspace database (letters, digits, _)"""
    if sys.argv[1:] == ["migrate"]:
        migrate_all()
    elif len(sys.argv) == 3 and sys.argv[1] == "create" and sys.argv[2].isidentifier():
        create(sys.argv[2].lower())
    else:
        sys.exit("Usage: python -m app.workspaces migrate | create <name>")


if __name__ == "__main__":
    main()
