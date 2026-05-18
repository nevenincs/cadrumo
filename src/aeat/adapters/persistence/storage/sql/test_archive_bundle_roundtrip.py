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

from .....core.classification import SensitivityClass
from .....core.config import Settings
from .. import EphemeralMasterKeyProvider
from ._orm import Base
from .engine import create_engine_from_settings
from .secure_objects import SecureObjectRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_archive_bundle_round_trips_three_rows(tmp_path: Path) -> None:
    """Three rows survive save -> iter_all_records_raw -> wipe -> save_with_raw_key -> load.

    The restore phase passes the original plaintext payloads into
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
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)

            rows = (
                (
                    "aeat.test.filing.drafts",
                    "draft-2025-1T-303-zzz",
                    SensitivityClass.FINANCIAL,
                    3,
                    b"ENVELOPE_BYTES_FINANCIAL_303",
                ),
                (
                    "aeat.test.justificantes",
                    "ABCD1234EFGH5678",
                    SensitivityClass.AUDIT,
                    1,
                    b"ENVELOPE_BYTES_AUDIT_JUSTIFICANTE",
                ),
                (
                    "aeat.test.sessions",
                    "/profile/active/aeat-session",
                    SensitivityClass.SESSION,
                    1,
                    b"ENVELOPE_BYTES_SESSION_STATE",
                ),
            )

            # Phase 1: original saves under natural keys.
            for namespace, natural_key, classification, schema_version, payload in rows:
                repo.save(
                    namespace=namespace,
                    object_key=natural_key,
                    classification=classification,
                    schema_version=schema_version,
                    written_at=datetime.now(UTC),
                    payload=payload,
                )

            # Phase 2: walk every row as opaque ciphertext + hashed key.
            # The raw walk yields the on-wire ciphertext payload alongside
            # the HMAC of the natural key. The HMAC digest is what the
            # restore needs; the ciphertext payload is what the remote
            # mirror would consume.
            bundle = tuple(repo.iter_all_records_raw())
            assert len(bundle) == len(rows)
            for raw in bundle:
                assert len(raw.object_key) == 32, "HMAC digest must be 32 bytes"
                assert isinstance(raw.payload, bytes)
                # The on-wire payload IS ciphertext: it must not contain the
                # plaintext sentinel bytes. (A regression that bypassed the
                # column encryptor would leak the sentinel.)
                for _, _, _, _, plaintext in rows:
                    assert plaintext not in raw.payload

            # Index the bundle by (namespace, hashed_object_key) so the
            # restore loop can pair each plaintext to its HMAC digest.
            bundle_by_namespace: dict[str, dict[bytes, object]] = {}
            for raw in bundle:
                bundle_by_namespace.setdefault(raw.namespace, {})[raw.object_key] = raw

            # Phase 3: nuke the table and rebuild. The restore replays each
            # original plaintext payload under the captured HMAC digest;
            # the column re-encrypts on insert.
            Base.metadata.drop_all(engine)
            Base.metadata.create_all(engine)
            assert tuple(repo.iter_all_records_raw()) == ()

            # Re-derive each row's HMAC by walking iter_all_records_raw of
            # the original engine state; since we already captured `bundle`
            # before the wipe, we pair up by namespace + natural-key
            # ordering. A real restore would index the bundle on disk and
            # pair by namespace + a stable inner key; for the test, the
            # one-row-per-namespace shape lets us match deterministically.
            for namespace, _natural_key, classification, schema_version, payload in rows:
                # The bundle has exactly one row per namespace in this fixture.
                ns_entries = bundle_by_namespace[namespace]
                assert len(ns_entries) == 1
                hashed_key = next(iter(ns_entries))
                raw = ns_entries[hashed_key]
                repo.save_with_raw_key(
                    namespace=namespace,
                    hashed_object_key=hashed_key,
                    classification=classification,
                    schema_version=schema_version,
                    written_at=raw.written_at,  # type: ignore[attr-defined]
                    payload=payload,
                )

            # Phase 4: load back under the original natural keys.
            # save_with_raw_key restores the row at the same HMAC digest
            # the original save() produced (because the master key is
            # the same), so load() (which re-derives the HMAC of the
            # natural key) finds the row.
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
        finally:
            engine.dispose()
