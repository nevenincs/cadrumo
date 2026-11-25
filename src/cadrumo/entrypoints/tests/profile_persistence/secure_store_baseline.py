"""Snapshot and restore a seeded secure-object store between tests of one module.

A module-scoped runtime profile pays the key-derivation and schema cost once.
A plain table wipe would also drop the sealed profile record, which lives in the
same table, so a seeded baseline is captured once and restored verbatim before
each test. Every test then starts from the identical seeded rows and nothing a
previous test wrote survives.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, delete, insert, select
from sqlalchemy import inspect as sa_inspect

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.reopened_runtime_profile import (
    DurableRuntimeProfile,
    reopened_runtime_profile,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

_TABLES = ("secure_objects", "secure_objects_quarantine")


@dataclass(frozen=True, slots=True)
class SecureStoreBaseline:
    """Exact rows of every secure-object table at the moment of capture."""

    rows: dict[str, tuple[dict[str, Any], ...]]


def _reflected(repository: SecureObjectRepository) -> dict[str, Table]:
    engine = repository.engine
    metadata = MetaData()
    present = sa_inspect(engine)
    return {name: Table(name, metadata, autoload_with=engine) for name in _TABLES if present.has_table(name)}


def capture_secure_store_baseline(repository: SecureObjectRepository) -> SecureStoreBaseline:
    """Read every secure-object row so the store can later be returned to this state."""
    captured: dict[str, tuple[dict[str, Any], ...]] = {}
    with repository.engine.connect() as connection:
        for name, table in _reflected(repository).items():
            captured[name] = tuple(dict(row) for row in connection.execute(select(table)).mappings())
    return SecureStoreBaseline(rows=captured)


def restore_secure_store_baseline(repository: SecureObjectRepository, baseline: SecureStoreBaseline) -> None:
    """Replace the store's contents with the captured rows in one transaction."""
    tables = _reflected(repository)
    with repository.engine.begin() as connection:
        for name, rows in baseline.rows.items():
            connection.execute(delete(tables[name]))
            if rows:
                connection.execute(insert(tables[name]), list(rows))


@dataclass(frozen=True, slots=True)
class SeededDurableProfile:
    """A provisioned, seeded bucket on disk plus its captured rows; no live global context."""

    durable: DurableRuntimeProfile
    baseline: SecureStoreBaseline


def provision_seeded_profile(
    tmp_path: Path, bucket_id: str, seed: Callable[[TestRuntimeProfile], None]
) -> SeededDurableProfile:
    """Pay registration once, seed, capture the rows and close every process-global context."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        seed(profile)
        baseline = capture_secure_store_baseline(profile.repository)
        durable = DurableRuntimeProfile(storage_root=profile.storage_root, bucket_id=profile.bucket_id)
    return SeededDurableProfile(durable=durable, baseline=baseline)


@contextmanager
def reopened_seeded_profile(seeded: SeededDurableProfile) -> Generator[TestRuntimeProfile]:
    """Enter settings and a session for one test, with the store back at its seeded rows."""
    with reopened_runtime_profile(
        seeded.durable, prepare=lambda repository: restore_secure_store_baseline(repository, seeded.baseline)
    ) as profile:
        yield profile
