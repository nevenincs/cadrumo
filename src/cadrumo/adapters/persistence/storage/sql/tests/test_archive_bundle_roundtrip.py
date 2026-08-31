"""Strict roundtrip across the ciphertext-mirror archive boundary.

The outbound sync coordinator walks every persisted row through
:meth:`SecureObjectRepository.iter_all_records_raw` and mirrors the
on-wire ciphertext to a remote storage provider without ever decrypting.
A restore-into-fresh-store path uses
:meth:`SecureObjectRepository.save_with_raw_key` to upsert each row's
**plaintext** payload back under the captured HMAC digest, so a
post-restore :meth:`SecureObjectRepository.load` call against the
natural key locates it again.

This file asserts the two halves of that contract independently and
together:

* ``iter_all_records_raw`` enumerates every persisted row with the
  HMAC digest, the namespace, the classification, the schema version,
  and the encrypted on-wire payload bytes — all fields the bundle
  mirror needs.
* ``save_with_raw_key`` accepts plaintext bytes keyed by a
  pre-computed HMAC and upserts; a subsequent
  ``load(namespace, natural_key, ...)`` resolves the row by
  re-hashing the natural key under the same master key.

A regression in any layer surfaces as a strict ``bytes`` inequality
or a ``None`` return from ``load``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ......core.classification.policies import SensitivityClass
from ......tests.master_key import EphemeralMasterKeyProvider
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from .._orm import Base
from ..secure_objects import SecureObjectRawRow, SecureObjectRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_archive_bundle_round_trips_three_rows(tmp_path: Path) -> None:
    """Three rows survive save -> iter_all_records_raw -> wipe -> save_with_raw_key -> load.

    The restore pass inserts the original plaintext payloads through
    :meth:`save_with_raw_key` (since the column encrypts on insert);
    the raw-row walk's ``payload`` is the on-wire ciphertext intended
    for a remote mirror, not for direct re-insertion under the same
    column encryption. The bundle metadata that survives the
    cipher-text mirror — namespace, classification, schema_version,
    written_at, and crucially the 32-byte HMAC digest — is what
    enables the restore.
    """

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "archive-bundle.db"
        engine = bootstrap_sqlite_engine(db_path)
        try:
            repo = SecureObjectRepository(engine=engine)
            rows = _ARCHIVE_BUNDLE_FIXTURE_ROWS

            _save_archive_bundle_rows(repo, rows=rows)
            bundle = tuple(repo.iter_all_records_raw())
            _assert_raw_bundle_is_ciphertext(bundle, rows=rows)
            bundle_by_namespace = _index_bundle_by_namespace(bundle)

            _wipe_and_recreate_secure_objects_table(engine, repo=repo)
            _restore_rows_under_hashed_keys(repo, rows=rows, bundle_by_namespace=bundle_by_namespace)

            _assert_rows_load_back_through_natural_keys(repo, rows=rows)
        finally:
            engine.dispose()


_ARCHIVE_BUNDLE_FIXTURE_ROWS: tuple[tuple[str, str, SensitivityClass, int, bytes], ...] = (
    (
        "cadrumo-test.filing.drafts",
        "draft-2025-1T-303-zzz",
        SensitivityClass.FINANCIAL,
        3,
        b"ENVELOPE_BYTES_FINANCIAL_303",
    ),
    (
        "cadrumo-test.justificantes",
        "ABCD1234EFGH5678",
        SensitivityClass.AUDIT,
        1,
        b"ENVELOPE_BYTES_AUDIT_JUSTIFICANTE",
    ),
    (
        "cadrumo-test.sessions",
        "/profile/active/aeat-session",
        SensitivityClass.SESSION,
        1,
        b"ENVELOPE_BYTES_SESSION_STATE",
    ),
)


def _save_archive_bundle_rows(
    repo: SecureObjectRepository,
    *,
    rows: tuple[tuple[str, str, SensitivityClass, int, bytes], ...],
) -> None:
    """Save original rows under natural keys."""
    for namespace, natural_key, classification, schema_version, payload in rows:
        repo.save(
            namespace=namespace,
            object_key=natural_key,
            classification=classification,
            schema_version=schema_version,
            written_at=datetime.now(UTC),
            payload=payload,
        )


def _assert_raw_bundle_is_ciphertext(
    bundle: tuple[SecureObjectRawRow, ...],
    *,
    rows: tuple[tuple[str, str, SensitivityClass, int, bytes], ...],
) -> None:
    """Assert the iter_all_records_raw walk yields ciphertext + HMAC keys.

    Every raw row carries a 32-byte HMAC digest of the natural key
    and a ``bytes`` payload that MUST be the on-wire ciphertext.
    A regression that bypassed the column encryptor would leak one
    of the plaintext sentinels into ``raw.payload``; the inclusion
    check below catches that class of failure.
    """
    assert len(bundle) == len(rows)
    for raw in bundle:
        assert len(raw.object_key) == 32, "HMAC digest must be 32 bytes"
        assert isinstance(raw.payload, bytes)
        for _, _, _, _, plaintext in rows:
            assert plaintext not in raw.payload


def _index_bundle_by_namespace(
    bundle: tuple[SecureObjectRawRow, ...],
) -> dict[str, dict[bytes, SecureObjectRawRow]]:
    """Index the raw bundle by ``(namespace, hashed_object_key)``.

    The restore loop pairs each plaintext payload to its HMAC
    digest through this index; the one-row-per-namespace fixture
    shape makes the lookup deterministic.
    """
    bundle_by_namespace: dict[str, dict[bytes, SecureObjectRawRow]] = {}
    for raw in bundle:
        bundle_by_namespace.setdefault(raw.namespace, {})[raw.object_key] = raw
    return bundle_by_namespace


def _wipe_and_recreate_secure_objects_table(engine: Engine, *, repo: SecureObjectRepository) -> None:
    """Drop the table, recreate it empty, and assert the raw walk yields nothing."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    assert tuple(repo.iter_all_records_raw()) == ()


def _restore_rows_under_hashed_keys(
    repo: SecureObjectRepository,
    *,
    rows: tuple[tuple[str, str, SensitivityClass, int, bytes], ...],
    bundle_by_namespace: dict[str, dict[bytes, SecureObjectRawRow]],
) -> None:
    """Replay each plaintext under the captured HMAC digest via save_with_raw_key."""
    for namespace, _natural_key, classification, schema_version, payload in rows:
        ns_entries = bundle_by_namespace[namespace]
        assert len(ns_entries) == 1
        hashed_key = next(iter(ns_entries))
        raw = ns_entries[hashed_key]
        repo.save_with_raw_key(
            namespace=namespace,
            hashed_object_key=hashed_key,
            classification=classification,
            schema_version=schema_version,
            written_at=raw.written_at,
            payload=payload,
        )


def _assert_rows_load_back_through_natural_keys(
    repo: SecureObjectRepository,
    *,
    rows: tuple[tuple[str, str, SensitivityClass, int, bytes], ...],
) -> None:
    """Load each row back through its natural key and assert payload + class + version."""
    for namespace, natural_key, classification, schema_version, payload in rows:
        loaded = repo.load(
            namespace,
            natural_key,
            expected_class=classification,
            max_supported_version=schema_version,
        )
        assert loaded is not None, f"row {natural_key!r} did not survive the bundle round-trip"
        assert loaded.payload == payload
        assert loaded.classification is classification
        assert loaded.schema_version == schema_version
