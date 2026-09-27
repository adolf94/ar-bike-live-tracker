"""Alembic environment — wired to the same metadata/engine as selfhost.db."""

import os
import sys

from alembic import context
from sqlalchemy import pool

# Make selfhost modules importable regardless of cwd.
_THIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _THIS_DIR)

# Importing db builds the engine + metadata from DATABASE_URL / defaults.
import db  # noqa: E402  (backend/selfhost/db.py)

config = context.config

if config.config_file_name is not None:
    import logging  # noqa: E402

    logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://tracker:tracker@localhost:5432/biketracker",
)
# Alembic runs synchronously (psycopg2 works for DDL via a sync driver);
# swap asyncpg -> psycopg2 driver url without touching app settings.
SYNC_URL = DATABASE_URL.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", SYNC_URL)

target_metadata = db.Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a DB connection."""
    context.configure(
        url=SYNC_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a real connection."""
    connectable = config.attributes.get("connectable")
    if connectable is None:
        from sqlalchemy import engine_from_config

        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
