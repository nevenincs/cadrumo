"""Shared support for split adapter tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from ..secure_objects import SecureObjectRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@contextmanager
def _ephemeral_secure_repo_at(
    db_path: Path,
) -> Generator[tuple[Any, SecureObjectRepository]]:
    """Open ``db_path`` under a fresh, self-managed ephemeral key.

    This is intentionally distinct from :func:`_repo_at`: callers of the
    latter already own an active :class:`EphemeralMasterKeyProvider`, while
    this helper owns the provider lifecycle for a fresh-key reopen.
    """
    with EphemeralMasterKeyProvider():
        engine = bootstrap_sqlite_engine(db_path)
        try:
            yield engine, SecureObjectRepository(engine=engine)
        finally:
            engine.dispose()


@contextmanager
def _ephemeral_secure_repo(
    tmp_path: Path,
    database_name: str,
) -> Generator[tuple[Path, Any, SecureObjectRepository]]:
    """Open a filename-derived repository under a fresh ephemeral key.

    Yields ``(db_path, engine, repo)`` so callers can inspect the raw engine
    or reopen the same on-disk database under the same key.
    """
    db_path = tmp_path / database_name
    with _ephemeral_secure_repo_at(db_path) as (engine, repo):
        yield db_path, engine, repo


@contextmanager
def _repo_at(db_path: Path) -> Generator[SecureObjectRepository]:
    """Open a real :class:`SecureObjectRepository` against a fresh schema at ``db_path``."""
    engine = bootstrap_sqlite_engine(db_path)
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        engine.dispose()


def _seed_under_key(
    *,
    db_path: Path,
    provider: EphemeralMasterKeyProvider,
    namespace: str,
    natural_key: str,
    payload: bytes,
) -> None:
    """Seed one secure-object row through the public repository under ``provider``."""
    with provider:
        engine = bootstrap_sqlite_engine(db_path)
        try:
            SecureObjectRepository(engine=engine).save(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=payload,
            )
        finally:
            engine.dispose()
