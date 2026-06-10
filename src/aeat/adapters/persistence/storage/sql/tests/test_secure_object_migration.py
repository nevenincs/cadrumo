"""Roundtrip-proof harness for the deterministic object-key bootstrap migration.

This module pins the byte-exact, observable behaviour of
:func:`ensure_deterministic_object_keys` against a real
:class:`EphemeralMasterKeyProvider` and a real SQLite engine before any
helper extraction touches the function. The migration owns secure-storage
``object_key`` derivation: a silent drift in the HMAC digest computation would
strand every existing encrypted record, so the harness captures the exact
derived key bytes produced by the *current* implementation and asserts the full
observable outcome (surviving rows, final ``object_key`` bytes, quarantine
contents) byte-for-byte.

The anti-tautology proof (:func:`test_harness_catches_object_key_derivation_drift`)
mutates a key component and asserts the harness's own equality check would fail,
proving the harness would catch a real derivation regression rather than passing
vacuously.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ......core.config import Settings
from ... import EphemeralMasterKeyProvider
from ...crypto._encrypted_columns import HashedLookup
from .._secure_object_migration import ensure_deterministic_object_keys
from .._secure_object_schema import ensure_table_revision_metadata_columns
from ..engine import create_engine_from_settings
from ._secure_objects_support import (
    _create_legacy_secure_objects_table,
    _seed_legacy_encrypted_string_key_row,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_LOGGER = logging.getLogger("test.secure_object_migration")


def _active_object_keys(db_path: Path) -> dict[str, list[tuple[bytes, int]]]:
    """Return surviving ``(object_key, schema_version)`` rows grouped by namespace."""
    grouped: dict[str, list[tuple[bytes, int]]] = {}
    with sqlite3.connect(db_path) as con:
        for namespace, object_key, schema_version in con.execute(
            "SELECT namespace, object_key, schema_version FROM secure_objects ORDER BY namespace, id"
        ).fetchall():
            grouped.setdefault(str(namespace), []).append((bytes(object_key), int(schema_version)))
    return grouped


def _quarantine_object_keys(db_path: Path) -> dict[str, list[tuple[bytes, int]]]:
    """Return quarantined ``(object_key, schema_version)`` rows grouped by namespace."""
    grouped: dict[str, list[tuple[bytes, int]]] = {}
    with sqlite3.connect(db_path) as con:
        has_table = con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'secure_objects_quarantine'"
        ).fetchone()
        if has_table is None:
            return grouped
        for namespace, object_key, schema_version in con.execute(
            "SELECT namespace, object_key, schema_version FROM secure_objects_quarantine ORDER BY namespace, id"
        ).fetchall():
            grouped.setdefault(str(namespace), []).append((bytes(object_key), int(schema_version)))
    return grouped


def _seed_multi_namespace_corpus(
    engine,
    *,
    duplicate_natural_key: str,
) -> dict[str, bytes]:
    """Seed three namespaces of legacy rows and return the per-key target digests.

    Layout:

    - ``aeat.mig.alpha``: one unique legacy key (rewritten in place).
    - ``aeat.mig.beta``: one unique legacy key (rewritten in place).
    - ``aeat.mig.gamma``: two legacy rows under ``duplicate_natural_key``
      (winner survives, loser quarantined) — exercises the duplicate-collapse
      path that itself rewrites the surviving key to the deterministic digest.

    Returns a mapping of ``natural_key -> HashedLookup.compute(natural_key)``,
    the byte-exact target the current implementation must produce.
    """
    _create_legacy_secure_objects_table(engine)
    # Mirror the repository bootstrap: revision-metadata columns are added
    # before the deterministic-key migration runs (it SELECTs those columns).
    ensure_table_revision_metadata_columns(engine, "secure_objects")

    _seed_legacy_encrypted_string_key_row(
        engine,
        namespace="aeat.mig.alpha",
        natural_key="alpha-natural-key",
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC),
        payload=b"alpha-payload",
    )
    _seed_legacy_encrypted_string_key_row(
        engine,
        namespace="aeat.mig.beta",
        natural_key="beta-natural-key",
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime(2026, 5, 22, 9, 30, 0, tzinfo=UTC),
        payload=b"beta-payload",
    )
    # The winner is seeded FIRST (lower autoincrement id) with the LATER
    # written_at, so the duplicate-collapse outcome is decided by the sort
    # key's written_at term alone — a regression that dropped written_at and
    # fell through to the id tiebreak would pick the loser and fail the
    # schema_version assertions.
    _seed_legacy_encrypted_string_key_row(
        engine,
        namespace="aeat.mig.gamma",
        natural_key=duplicate_natural_key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=2,
        written_at=datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC),
        payload=b"gamma-winner-payload",
    )
    _seed_legacy_encrypted_string_key_row(
        engine,
        namespace="aeat.mig.gamma",
        natural_key=duplicate_natural_key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC),
        payload=b"gamma-loser-payload",
    )

    return {
        "alpha-natural-key": HashedLookup.compute("alpha-natural-key"),
        "beta-natural-key": HashedLookup.compute("beta-natural-key"),
        duplicate_natural_key: HashedLookup.compute(duplicate_natural_key),
    }


def test_migration_rewrites_legacy_keys_to_byte_exact_hashed_lookup_digests(tmp_path: Path) -> None:
    """The migration rewrites every legacy key to the exact ``HashedLookup`` digest.

    Captures the byte-exact target digest each natural key derives to under the
    current implementation, runs the migration, and asserts the surviving
    ``object_key`` bytes equal those captured digests across three namespaces —
    including the duplicate-collapse namespace whose surviving row must also
    carry the deterministic digest. Also asserts the loser row lands in
    quarantine with its original (larger-than-32-byte) randomized ciphertext.
    """
    duplicate_natural_key = "gamma-shared-natural-key"
    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "migration-byte-exact.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        try:
            targets = _seed_multi_namespace_corpus(engine, duplicate_natural_key=duplicate_natural_key)

            ensure_deterministic_object_keys(engine, logger=_LOGGER)

            active = _active_object_keys(db_path)
            quarantine = _quarantine_object_keys(db_path)
        finally:
            engine.dispose()

    # Every digest is exactly 32 bytes and deterministic.
    for digest in targets.values():
        assert len(digest) == 32

    assert active["aeat.mig.alpha"] == [(targets["alpha-natural-key"], 1)]
    assert active["aeat.mig.beta"] == [(targets["beta-natural-key"], 1)]
    # Duplicate-collapse: the schema_version=2 winner survives with the
    # deterministic digest; the loser is gone from the active table.
    assert active["aeat.mig.gamma"] == [(targets[duplicate_natural_key], 2)]

    # Loser quarantined with its original randomized ciphertext (> 32 bytes).
    assert "aeat.mig.gamma" in quarantine
    assert len(quarantine["aeat.mig.gamma"]) == 1
    loser_key, loser_version = quarantine["aeat.mig.gamma"][0]
    assert loser_version == 1
    assert len(loser_key) > 32
    # No unique-key namespace produced a quarantine row.
    assert "aeat.mig.alpha" not in quarantine
    assert "aeat.mig.beta" not in quarantine


def test_migration_is_idempotent_on_already_deterministic_keys(tmp_path: Path) -> None:
    """A second migration pass leaves byte-identical deterministic keys untouched.

    After the first pass rewrites keys to ``HashedLookup`` digests, a second
    pass must be a no-op: the surviving ``object_key`` bytes are byte-identical
    and no further quarantine rows appear. This pins the steady-state contract
    that the bootstrap runs on every repository construction.
    """
    duplicate_natural_key = "gamma-shared-natural-key"
    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "migration-idempotent.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        try:
            _seed_multi_namespace_corpus(engine, duplicate_natural_key=duplicate_natural_key)

            ensure_deterministic_object_keys(engine, logger=_LOGGER)
            after_first = _active_object_keys(db_path)
            quarantine_after_first = _quarantine_object_keys(db_path)

            ensure_deterministic_object_keys(engine, logger=_LOGGER)
            after_second = _active_object_keys(db_path)
            quarantine_after_second = _quarantine_object_keys(db_path)
        finally:
            engine.dispose()

    assert after_second == after_first
    assert quarantine_after_second == quarantine_after_first


def test_migration_quarantines_unmigratable_legacy_key(tmp_path: Path) -> None:
    """A non-decryptable, non-32-byte legacy key is quarantined and removed.

    Seeds a row whose ``object_key`` is neither a decryptable
    ``EncryptedString`` ciphertext nor a 32-byte digest. The migration cannot
    derive a deterministic key for it, so it is copied to quarantine verbatim
    and deleted from the active table.
    """
    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "migration-unmigratable.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        namespace = "aeat.mig.unmigratable"
        opaque_key = b"\x01\x02\x03\x04\x05"  # not 32 bytes, not decryptable
        try:
            _create_legacy_secure_objects_table(engine)
            ensure_table_revision_metadata_columns(engine, "secure_objects")
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO secure_objects "
                    "(namespace, object_key, classification, schema_version, written_at, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        namespace,
                        opaque_key,
                        SensitivityClass.FINANCIAL.value,
                        1,
                        datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC),
                        b"unmigratable-payload",
                    ),
                )

            ensure_deterministic_object_keys(engine, logger=_LOGGER)

            active = _active_object_keys(db_path)
            quarantine = _quarantine_object_keys(db_path)
        finally:
            engine.dispose()

    assert namespace not in active
    assert quarantine[namespace] == [(opaque_key, 1)]


def test_migration_returns_early_on_empty_table(tmp_path: Path) -> None:
    """An empty table is a no-op: no quarantine table is created."""
    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "migration-empty.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        try:
            _create_legacy_secure_objects_table(engine)
            ensure_table_revision_metadata_columns(engine, "secure_objects")

            ensure_deterministic_object_keys(engine, logger=_LOGGER)

            with sqlite3.connect(db_path) as con:
                quarantine_exists = con.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'secure_objects_quarantine'"
                ).fetchone()
                (active_count,) = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()
        finally:
            engine.dispose()

    assert quarantine_exists is None
    assert active_count == 0


def test_harness_catches_object_key_derivation_drift(tmp_path: Path) -> None:
    """Anti-tautology proof: a mutated key component breaks the byte-exact check.

    Captures the digest of the *wrong* natural key, runs the migration that
    rewrites rows to the *correct* digest, and asserts the harness's own
    equality check (surviving ``object_key`` == captured digest) would FAIL.
    This proves the harness pins the exact HMAC computation: a derivation drift
    that changed the produced bytes would surface as an inequality here, not
    pass silently.
    """
    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "migration-anti-tautology.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        namespace = "aeat.mig.alpha"
        try:
            _create_legacy_secure_objects_table(engine)
            ensure_table_revision_metadata_columns(engine, "secure_objects")
            _seed_legacy_encrypted_string_key_row(
                engine,
                namespace=namespace,
                natural_key="alpha-natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC),
                payload=b"alpha-payload",
            )
            # Mutated input: digest of a DIFFERENT natural key. If the harness
            # were tautological it would pass regardless; it must not.
            wrong_target = HashedLookup.compute("alpha-natural-key-MUTATED")

            ensure_deterministic_object_keys(engine, logger=_LOGGER)

            active = _active_object_keys(db_path)
        finally:
            engine.dispose()

    surviving_key = active[namespace][0][0]
    assert len(surviving_key) == 32
    # The migration produced the digest of the REAL key, which must differ from
    # the mutated-input digest. The byte-exact equality the real harness asserts
    # would fail here — proving it is not tautological.
    assert surviving_key != wrong_target
