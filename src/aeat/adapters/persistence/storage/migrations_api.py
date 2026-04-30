"""Programmatic Alembic wrappers.

A thin facade over Alembic so callers (CLI, tests) do not reach into its
private API. The Alembic config is loaded from the repo-root ``alembic.ini``
and the SQLAlchemy URL is injected from the provided engine.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from ....core.logging import get_logger
from .errors import MigrationError

_log = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


def _make_config(engine: Engine) -> Config:
    """Build an Alembic :class:`~alembic.config.Config` bound to ``engine``.

    The engine is injected via ``config.attributes['connection']`` so that
    :mod:`migrations.env` can reuse it instead of creating a fresh one. This
    matters for ``sqlite:///:memory:`` URLs and for engines that carry
    per-connection listeners (e.g. ``PRAGMA foreign_keys=ON``).
    """
    if not _ALEMBIC_INI.exists():
        raise MigrationError(f"alembic.ini not found at {_ALEMBIC_INI}")
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", str(engine.url))
    config.attributes["connection"] = engine
    return config


def upgrade_to_head(engine: Engine) -> None:
    """Run ``alembic upgrade head`` against ``engine``.

    Args:
        engine: SQLAlchemy engine to migrate.

    Raises:
        MigrationError: If Alembic raises during the upgrade.
    """
    config = _make_config(engine)
    try:
        command.upgrade(config, "head")
    except Exception as exc:  # pragma: no cover - surfaced to callers
        raise MigrationError(f"alembic upgrade head failed: {exc}") from exc
    _log.debug("alembic upgrade head complete for url=%s", engine.url)


def downgrade_to_base(engine: Engine) -> None:
    """Run ``alembic downgrade base`` against ``engine``.

    Args:
        engine: SQLAlchemy engine to migrate.

    Raises:
        MigrationError: If Alembic raises during the downgrade.
    """
    config = _make_config(engine)
    try:
        command.downgrade(config, "base")
    except Exception as exc:  # pragma: no cover - surfaced to callers
        raise MigrationError(f"alembic downgrade base failed: {exc}") from exc
    _log.debug("alembic downgrade base complete for url=%s", engine.url)


def round_trip_migrations(engine: Engine) -> None:
    """Apply head → base → head on ``engine``.

    Used by the migration round-trip unit test to ensure every revision is
    reversible.

    Args:
        engine: SQLAlchemy engine to migrate.
    """
    upgrade_to_head(engine)
    downgrade_to_base(engine)
    upgrade_to_head(engine)
