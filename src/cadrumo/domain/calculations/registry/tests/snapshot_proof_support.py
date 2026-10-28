"""Proof-test support: republished copies of the published authority and cross-check observation."""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from .....core.hashing import sha256_hex
from .. import snapshot as snapshot_module
from ..authority_location import bundled_authority_descriptor_path
from ..authority_store import AUTHORITY_DATABASE_FORMAT, AuthorityDescriptor
from ..snapshot_proof import SNAPSHOT_PROOF_DDL, SNAPSHOT_PROOF_TABLES

_DESCRIPTOR_NAME = "authority.current.json"


def republished_authority(
    directory: Path,
    *,
    tables: tuple[str, ...] = SNAPSHOT_PROOF_TABLES,
    statements: tuple[tuple[str, tuple[object, ...]], ...] = (),
) -> Path:
    """Copy the published pair as the current format with exactly the named proof tables and rows.

    Whatever proof tables and rows the published database already records are
    dropped first, so the copy carries only what the caller names. The copy is
    republished under its own content address, so admission's digest check
    holds and only the proof tables decide. Returns the copy's descriptor path.
    """
    source = AuthorityDescriptor.read(bundled_authority_descriptor_path())
    directory.mkdir()
    staging = directory / "staged.sqlite3"
    shutil.copy2(bundled_authority_descriptor_path().parent / source.database, staging)
    connection = sqlite3.connect(staging)
    try:
        connection.execute("UPDATE authority_manifest SET format = ?", (AUTHORITY_DATABASE_FORMAT,))
        for table in reversed(SNAPSHOT_PROOF_TABLES):
            connection.execute(f"DROP TABLE IF EXISTS {table}")
        for table, ddl in zip(SNAPSHOT_PROOF_TABLES, SNAPSHOT_PROOF_DDL, strict=True):
            if table in tables:
                connection.execute(ddl)
        for statement, parameters in statements:
            connection.execute(statement, parameters)
        connection.commit()
    finally:
        connection.close()
    payload = staging.read_bytes()
    digest = sha256_hex(payload)
    staging.replace(directory / f"authority-{digest}.sqlite3")
    descriptor = AuthorityDescriptor(
        database=f"authority-{digest}.sqlite3",
        database_size=len(payload),
        database_sha256=digest,
        logical_generation=source.logical_generation,
    )
    (directory / _DESCRIPTOR_NAME).write_bytes(descriptor.to_bytes())
    return directory / _DESCRIPTOR_NAME


def count_cross_checks(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Wrap every registered cross-check so it counts its calls and still runs the real check.

    The returned list holds one counter per registry entry, in registry
    order. The wrapper replaces the registry for the test's duration only.
    """
    registry = snapshot_module._SNAPSHOT_CROSS_CHECKS
    counts = [0] * len(registry)

    def counted(index: int, run: Callable[..., None]) -> Callable[..., None]:
        def run_and_count(context: object) -> None:
            counts[index] += 1
            run(context)

        return run_and_count

    monkeypatch.setattr(
        snapshot_module,
        "_SNAPSHOT_CROSS_CHECKS",
        tuple(replace(check, run=counted(index, check.run)) for index, check in enumerate(registry)),
    )
    return counts
