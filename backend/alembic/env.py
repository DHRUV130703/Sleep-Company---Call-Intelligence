"""Alembic migration environment. The database URL comes from app.config, not alembic.ini."""

from logging.config import fileConfig

from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers every table on SQLModel.metadata)
from alembic import context
from app.db import get_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(get_engine().url),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,  # SQLite can't ALTER most things; batch mode rebuilds the table safely
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
