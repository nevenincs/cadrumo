"""Alembic environment for the aeat storage layer.

Reads the database URL from :class:`aeat.config.Settings` (unless it has been
injected into the Alembic config by a programmatic caller such as
:mod:`aeat.storage.migrations_api`) and uses
:data:`aeat.storage._orm.metadata` as the autogenerate target.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from aeat.config import load_settings
from aeat.logging import get_logger
from aeat.storage import _orm
from aeat.storage.engine import _ensure_sqlite_parent

_log = get_logger(__name__)

config = context.config

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", load_settings().aeat_database_url)

# Make `alembic upgrade head` work from a fresh clone where the default
# SQLite file's parent directory (e.g. `var/`) does not yet exist.
_ensure_sqlite_parent(config.get_main_option("sqlalchemy.url") or "")

target_metadata = _orm.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live engine built from the Alembic config."""
    section = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
