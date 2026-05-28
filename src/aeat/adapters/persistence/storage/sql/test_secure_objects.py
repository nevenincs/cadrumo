"""Tests for encrypted SQL byte-object persistence."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.classification import SensitivityClass
from .....core.config import Settings
from .. import EphemeralMasterKeyProvider
from .._namespace_registry import STORAGE_NAMESPACE_REGISTRY, WORKFLOW_STATE_NAMESPACE
from ..errors import (
    ClassificationError,
    EnvelopeVersionError,
    SecureObjectRevisionConflictError,
    StorageValidationError,
)
from ._orm import Base, SecureObjectRow
from .engine import create_engine_from_settings
from .secure_objects import (
    SecureObjectNamespaceIntegrity,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectUnreadable,
    SecureObjectWrite,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_secure_object_payload_is_encrypted_in_database(tmp_path: Path) -> None:
    """Sensitive payload bytes round-trip without plaintext landing in SQLite."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "secure.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            payload = b"SECURE_OBJECT_CANARY_tax_financial_payload"
            natural_key = "CSV1234-sensitive-natural-key"
            repo.save(
                namespace="aeat.test",
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=payload,
            )

            loaded = repo.load(
                "aeat.test",
                natural_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )
            assert loaded is not None
            assert loaded.payload == payload
            assert payload not in db_path.read_bytes()
            assert natural_key.encode("utf-8") not in db_path.read_bytes()

            with sqlite3.connect(db_path) as con:
                stored_key, stored = con.execute("SELECT object_key, payload FROM secure_objects").fetchone()
            assert isinstance(stored_key, bytes)
            assert len(stored_key) == 32
            assert natural_key.encode("utf-8") not in stored_key
            assert isinstance(stored, bytes)
            assert payload not in stored
        finally:
            engine.dispose()


def test_secure_object_record_roundtrip_preserves_full_record_fields(tmp_path: Path) -> None:
    """A decrypted record roundtrip must preserve every boundary field."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "record.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.record"
        natural_key = "record-key-non-default"
        written_at = datetime(2026, 5, 21, 10, 30, 0)
        payload = b"strict-record-roundtrip-payload"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=3,
                written_at=written_at,
                payload=payload,
            )
            with sqlite3.connect(db_path) as con:
                (stored_key,) = con.execute(
                    "SELECT object_key FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()

            loaded = repo.load(
                namespace,
                natural_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=3,
            )

            assert loaded == SecureObjectRecord(
                namespace=namespace,
                object_key=stored_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=3,
                written_at=written_at,
                payload=payload,
            )
        finally:
            engine.dispose()


def test_secure_object_table_materializes_revision_integrity_columns(tmp_path: Path) -> None:
    """Fresh SQL bootstrap creates nullable lineage and integrity columns.

    The check goes through SQLite's real table metadata after
    ``Base.metadata.create_all``. Nullability matters for this step
    because existing rows are backfilled by the later migration slice.
    """

    db_path = tmp_path / "revision-schema.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        with sqlite3.connect(db_path) as con:
            table_info = con.execute("PRAGMA table_info(secure_objects)").fetchall()

        columns = {str(row[1]): row for row in table_info}
        for column_name in (
            "revision_id",
            "previous_revision_id",
            "previous_payload_hash",
            "payload_hash",
            "ciphertext_hash",
            "revision_written_at",
            "write_provenance",
            "source_event_id",
            "conflict_policy",
        ):
            assert column_name in columns
            assert int(columns[column_name][3]) == 0, f"{column_name} must remain nullable until row backfill"
    finally:
        engine.dispose()


def test_secure_object_repository_bootstraps_old_table_revision_columns(tmp_path: Path) -> None:
    """Repository construction upgrades an old-shape table before ORM reads.

    The row is inserted through SQLAlchemy column types before the new
    columns exist, matching a database created by the previous mapper.
    Loading it through the current repository proves the bootstrap ran
    before the mapper tried to select the added columns.
    """

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "legacy-revision-bootstrap.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        payload = b"legacy-secure-object-payload"
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE secure_objects ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "namespace VARCHAR(128) NOT NULL, "
                    "object_key BLOB NOT NULL, "
                    "classification VARCHAR(32) NOT NULL, "
                    "schema_version INTEGER NOT NULL, "
                    "written_at DATETIME NOT NULL, "
                    "payload BLOB NOT NULL, "
                    "CONSTRAINT uq_secure_objects_identity UNIQUE (namespace, object_key)"
                    ")"
                )
                connection.execute(
                    SecureObjectRow.__table__.insert().values(
                        namespace="aeat.legacy.revision",
                        object_key="legacy-key",
                        classification=SensitivityClass.FINANCIAL.value,
                        schema_version=1,
                        written_at=datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC),
                        payload=payload,
                    )
                )

            repo = SecureObjectRepository(engine=engine)
            loaded = repo.load(
                "aeat.legacy.revision",
                "legacy-key",
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )

            assert loaded is not None
            assert loaded.payload == payload
            with sqlite3.connect(db_path) as con:
                columns = {str(row[1]) for row in con.execute("PRAGMA table_info(secure_objects)").fetchall()}
                revision_values = con.execute(
                    "SELECT revision_id, payload_hash, ciphertext_hash FROM secure_objects"
                ).fetchone()
            assert {"revision_id", "payload_hash", "ciphertext_hash"} <= columns
            assert revision_values == (None, None, None)
        finally:
            engine.dispose()


def test_secure_object_record_schema_version_mutation_breaks_roundtrip(tmp_path: Path) -> None:
    """A database-side metadata mutation must not still load as the original record."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "record-mutation.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.record.mutation"
        natural_key = "record-key"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=3,
                written_at=datetime(2026, 5, 21, 10, 35, 0, tzinfo=UTC),
                payload=b"mutation-sentinel-payload",
            )
            assert repo.load(
                namespace,
                natural_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=3,
            ) is not None
            with sqlite3.connect(db_path) as con:
                con.execute(
                    "UPDATE secure_objects SET schema_version = ? WHERE namespace = ?",
                    (4, namespace),
                )
                con.commit()

            with pytest.raises(EnvelopeVersionError, match="supports up to 3"):
                repo.load(
                    namespace,
                    natural_key,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=3,
                )
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
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
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


def test_list_records_skips_rows_sealed_under_a_prior_master_key(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A row written under master key K1 must not crash a list_records call under K2.

    The architectural defect this guards against: ``list_records`` used to
    materialise every row through the SQLAlchemy column processor in one
    pass, so a single ``InvalidTag`` (caused by a row written under a
    rotated master key) aborted the entire iteration. The fault-isolated
    iterator must skip the unreadable row and let the readable subset
    flow through, while emitting a structured warning.
    """
    db_path = tmp_path / "rotated.db"
    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()
    namespace = "aeat.test.rotation"

    # Seed a row under the OLD key, leaving the ciphertext at rest.
    _seed_under_key(
        db_path=db_path,
        provider=key_old,
        namespace=namespace,
        natural_key="row-under-old-key",
        payload=b"plaintext-from-old-generation",
    )

    # Reopen under the NEW key and add a row that ought to be readable.
    with key_new:
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="row-under-new-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"plaintext-from-current-generation",
            )

            with caplog.at_level(logging.WARNING, logger="aeat.adapters.persistence.storage.sql.secure_objects"):
                yielded = list(
                    repo.list_records(
                        namespace,
                        expected_class=SensitivityClass.FINANCIAL,
                        max_supported_version=1,
                    )
                )

            assert len(yielded) == 1
            assert yielded[0].payload == b"plaintext-from-current-generation"
            assert any("skipped 1 unreadable row" in rec.message for rec in caplog.records), (
                f"expected one structured warning summarising the skip count; got {[r.message for r in caplog.records]}"
            )
        finally:
            engine.dispose()


def test_iter_records_with_failures_yields_typed_outcomes_for_each_row(
    tmp_path: Path,
) -> None:
    """The fault-isolated iterator must yield one item per stored row.

    Two rows seeded under a rotated master key plus one row written
    under the current key must produce a triple of outcomes: two
    :class:`SecureObjectUnreadable` and one :class:`SecureObjectRecord`,
    in stable storage order. No exception escapes.
    """
    db_path = tmp_path / "mixed.db"
    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()
    namespace = "aeat.test.mixed"

    for natural_key, payload in (
        ("row-1-old", b"old-1-plaintext"),
        ("row-2-old", b"old-2-plaintext"),
    ):
        _seed_under_key(
            db_path=db_path,
            provider=key_old,
            namespace=namespace,
            natural_key=natural_key,
            payload=payload,
        )

    with key_new:
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine).save(
                namespace=namespace,
                object_key="row-3-new",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"new-3-plaintext",
            )

            items = list(
                SecureObjectRepository(engine=engine).iter_records_with_failures(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                )
            )

            assert len(items) == 3, f"expected one outcome per row; got {items}"
            unreadable = [item for item in items if isinstance(item, SecureObjectUnreadable)]
            loaded = [item for item in items if isinstance(item, SecureObjectRecord)]
            assert len(unreadable) == 2
            assert len(loaded) == 1
            assert loaded[0].payload == b"new-3-plaintext"
            for ghost in unreadable:
                assert ghost.namespace == namespace
                assert ghost.row_id > 0
                assert "tag verification failed" in ghost.reason.lower() or "decrypt" in ghost.reason.lower()
        finally:
            engine.dispose()


def test_iter_records_with_failures_returns_empty_on_empty_namespace(
    tmp_path: Path,
) -> None:
    """A namespace with no rows yields an empty iterator without raising."""
    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "empty.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            items = list(
                SecureObjectRepository(engine=engine).iter_records_with_failures(
                    "aeat.test.empty",
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                )
            )
            assert items == []
        finally:
            engine.dispose()


def test_list_records_only_emits_warning_when_unreadable_rows_exist(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No warning fires on a clean namespace; the warning is gated on real failures."""
    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "clean.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.clean"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="row-clean",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"clean-plaintext",
            )

            with caplog.at_level(logging.WARNING, logger="aeat.adapters.persistence.storage.sql.secure_objects"):
                yielded = list(
                    repo.list_records(
                        namespace,
                        expected_class=SensitivityClass.FINANCIAL,
                        max_supported_version=1,
                    )
                )

            assert len(yielded) == 1
            assert all("unreadable" not in rec.message for rec in caplog.records)
        finally:
            engine.dispose()


def test_iter_all_records_raw_yields_every_row_without_decryption(tmp_path: Path) -> None:
    """The raw iterator returns on-wire ciphertext + metadata across namespaces."""

    from .secure_objects import SecureObjectRawRow

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "raw.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            now = datetime.now(UTC)
            repo.save(
                namespace="aeat.alpha",
                object_key="key-a-1",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=now,
                payload=b"payload-a-1",
            )
            repo.save(
                namespace="aeat.beta",
                object_key="key-b-1",
                classification=SensitivityClass.SESSION,
                schema_version=1,
                written_at=now,
                payload=b"payload-b-1",
            )
            repo.save(
                namespace="aeat.alpha",
                object_key="key-a-2",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=now,
                payload=b"payload-a-2",
            )

            rows = list(repo.iter_all_records_raw())

            assert len(rows) == 3
            assert all(isinstance(row, SecureObjectRawRow) for row in rows)
            namespaces = [row.namespace for row in rows]
            # Ordered by (namespace ASC, object_key ASC); the three rows
            # yield as aeat.alpha (x2) then aeat.beta (x1).
            assert namespaces == ["aeat.alpha", "aeat.alpha", "aeat.beta"]
            for row in rows:
                assert len(row.payload) > 0
                assert row.payload not in (b"payload-a-1", b"payload-a-2", b"payload-b-1"), (
                    "iter_all_records_raw must return on-wire ciphertext, not plaintext"
                )
                assert row.classification in {"financial", "session"}
                assert row.schema_version == 1
        finally:
            engine.dispose()


def test_iter_all_records_raw_returns_empty_iterator_for_empty_table(tmp_path: Path) -> None:
    """No rows persisted → iterator yields nothing without raising."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "empty.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            rows = list(repo.iter_all_records_raw())
            assert rows == []
        finally:
            engine.dispose()


def test_iter_all_records_raw_does_not_attempt_decryption_under_rotated_master_key(tmp_path: Path) -> None:
    """Rows sealed under a different master key still yield via raw iterator.

    The raw iterator is the outbound sync coordinator's path; mirroring
    must work even when the in-process master key cannot decrypt the
    payload (e.g., during a rotation window or on a freshly-bootstrapped
    machine before key recovery completes).
    """

    seed_provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "rotated.db"
    _seed_under_key(
        db_path=db_path,
        provider=seed_provider,
        namespace="aeat.rotated",
        natural_key="rotated-key",
        payload=b"rotated-payload",
    )
    # Switch to a fresh master key the seeded payload was NOT encrypted under.
    with EphemeralMasterKeyProvider():
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        try:
            rows = list(SecureObjectRepository(engine=engine).iter_all_records_raw())
            assert len(rows) == 1
            # The ciphertext bytes are returned verbatim; no DecryptionError.
            assert rows[0].namespace == "aeat.rotated"
        finally:
            engine.dispose()


def test_quarantine_unreadable_rows_preserves_revision_metadata(tmp_path: Path) -> None:
    """Quarantine copies lineage and integrity fields with unreadable ciphertext.

    The source row is sealed under an old key, then annotated with
    non-default revision metadata before reopening under a different key.
    Quarantine must archive the opaque row without dropping the metadata
    that later sync and repair flows rely on.
    """

    seed_provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "quarantine-metadata.db"
    namespace = "aeat.quarantine.metadata"
    _seed_under_key(
        db_path=db_path,
        provider=seed_provider,
        namespace=namespace,
        natural_key="quarantine-key",
        payload=b"quarantine-metadata-payload",
    )
    metadata_values = {
        "revision_id": "a" * 64,
        "previous_revision_id": "b" * 64,
        "previous_payload_hash": "c" * 64,
        "payload_hash": "d" * 64,
        "ciphertext_hash": "e" * 64,
        "revision_written_at": "2026-05-22T12:30:00+00:00",
        "write_provenance": "test:quarantine-metadata",
        "source_event_id": "event-2026-05-22-001",
        "conflict_policy": "last-write-wins",
    }
    with sqlite3.connect(db_path) as con:
        con.execute(
            "UPDATE secure_objects SET "
            "revision_id = :revision_id, "
            "previous_revision_id = :previous_revision_id, "
            "previous_payload_hash = :previous_payload_hash, "
            "payload_hash = :payload_hash, "
            "ciphertext_hash = :ciphertext_hash, "
            "revision_written_at = :revision_written_at, "
            "write_provenance = :write_provenance, "
            "source_event_id = :source_event_id, "
            "conflict_policy = :conflict_policy "
            "WHERE namespace = :namespace",
            {**metadata_values, "namespace": namespace},
        )

    with EphemeralMasterKeyProvider():
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        try:
            report = SecureObjectRepository(engine=engine).quarantine_unreadable_rows()

            assert report == (
                SecureObjectNamespaceIntegrity(
                    namespace=namespace,
                    readable=0,
                    unreadable=1,
                ),
            )
            with sqlite3.connect(db_path) as con:
                archived = con.execute(
                    "SELECT revision_id, previous_revision_id, previous_payload_hash, payload_hash, "
                    "ciphertext_hash, revision_written_at, write_provenance, source_event_id, "
                    "conflict_policy FROM secure_objects_quarantine"
                ).fetchone()
                (remaining,) = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()
            assert archived == tuple(metadata_values.values())
            assert remaining == 0
        finally:
            engine.dispose()


def test_secure_object_save_writes_revision_integrity_metadata(tmp_path: Path) -> None:
    """A save writes storage-level revision and integrity metadata to disk."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-write.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        payload = b"revision-integrity-payload"
        written_at = datetime(2026, 5, 22, 13, 0, 0, tzinfo=UTC)
        try:
            SecureObjectRepository(engine=engine).save(
                namespace="aeat.revision.write",
                object_key="revision-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=2,
                written_at=written_at,
                payload=payload,
                write_provenance="test:revision-write",
                source_event_id="event-write-001",
            )

            with sqlite3.connect(db_path) as con:
                row = con.execute(
                    "SELECT revision_id, previous_revision_id, previous_payload_hash, payload_hash, "
                    "ciphertext_hash, revision_written_at, write_provenance, source_event_id, "
                    "conflict_policy, payload FROM secure_objects"
                ).fetchone()

            assert len(row[0]) == 64
            assert row[1] is None
            assert row[2] is None
            assert row[3] == hashlib.sha256(payload).hexdigest()
            assert row[4] == hashlib.sha256(row[9]).hexdigest()
            assert row[5] is not None
            assert row[6] == "test:revision-write"
            assert row[7] == "event-write-001"
            assert row[8] == "last-write-wins"
        finally:
            engine.dispose()


def test_secure_object_overwrite_links_previous_revision_metadata(tmp_path: Path) -> None:
    """Overwrites preserve the previous storage revision reference and payload hash."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-overwrite.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.revision.overwrite"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="overwrite-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 14, 0, 0, tzinfo=UTC),
                payload=b"first-revision-payload",
                write_provenance="test:first-write",
            )
            with sqlite3.connect(db_path) as con:
                first_revision_id, first_payload_hash = con.execute(
                    "SELECT revision_id, payload_hash FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()

            repo.save(
                namespace=namespace,
                object_key="overwrite-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 14, 5, 0, tzinfo=UTC),
                payload=b"second-revision-payload",
                write_provenance="test:second-write",
            )

            with sqlite3.connect(db_path) as con:
                row = con.execute(
                    "SELECT revision_id, previous_revision_id, previous_payload_hash, payload_hash, "
                    "write_provenance FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
            assert row[0] != first_revision_id
            assert row[1] == first_revision_id
            assert row[2] == first_payload_hash
            assert row[3] == hashlib.sha256(b"second-revision-payload").hexdigest()
            assert row[4] == "test:second-write"
        finally:
            engine.dispose()


def test_secure_object_overwrite_of_legacy_row_derives_previous_payload_hash(tmp_path: Path) -> None:
    """A first overwrite after schema bootstrap links to the legacy plaintext hash."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-legacy-overwrite.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        legacy_payload = b"legacy-before-revision-metadata"
        namespace = "aeat.revision.legacy"
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE secure_objects ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "namespace VARCHAR(128) NOT NULL, "
                    "object_key BLOB NOT NULL, "
                    "classification VARCHAR(32) NOT NULL, "
                    "schema_version INTEGER NOT NULL, "
                    "written_at DATETIME NOT NULL, "
                    "payload BLOB NOT NULL, "
                    "CONSTRAINT uq_secure_objects_identity UNIQUE (namespace, object_key)"
                    ")"
                )
                connection.execute(
                    SecureObjectRow.__table__.insert().values(
                        namespace=namespace,
                        object_key="legacy-overwrite-key",
                        classification=SensitivityClass.FINANCIAL.value,
                        schema_version=1,
                        written_at=datetime(2026, 5, 22, 15, 0, 0, tzinfo=UTC),
                        payload=legacy_payload,
                    )
                )

            SecureObjectRepository(engine=engine).save(
                namespace=namespace,
                object_key="legacy-overwrite-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 15, 10, 0, tzinfo=UTC),
                payload=b"post-bootstrap-overwrite",
            )

            with sqlite3.connect(db_path) as con:
                previous_revision_id, previous_payload_hash = con.execute(
                    "SELECT previous_revision_id, previous_payload_hash FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
            assert previous_revision_id is None
            assert previous_payload_hash == hashlib.sha256(legacy_payload).hexdigest()
        finally:
            engine.dispose()


def test_secure_object_save_many_writes_revision_metadata(tmp_path: Path) -> None:
    """Batched writes carry revision metadata for each persisted row."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-save-many.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine).save_many(
                (
                    SecureObjectWrite(
                        namespace="aeat.revision.batch",
                        object_key="batch-a",
                        classification=SensitivityClass.FINANCIAL,
                        schema_version=1,
                        written_at=datetime(2026, 5, 22, 16, 0, 0, tzinfo=UTC),
                        payload=b"batch-payload-a",
                        write_provenance="test:batch",
                        source_event_id="batch-event-a",
                    ),
                    SecureObjectWrite(
                        namespace="aeat.revision.batch",
                        object_key="batch-b",
                        classification=SensitivityClass.FINANCIAL,
                        schema_version=1,
                        written_at=datetime(2026, 5, 22, 16, 1, 0, tzinfo=UTC),
                        payload=b"batch-payload-b",
                        write_provenance="test:batch",
                        source_event_id="batch-event-b",
                    ),
                )
            )

            with sqlite3.connect(db_path) as con:
                rows = con.execute(
                    "SELECT revision_id, payload_hash, write_provenance, source_event_id, conflict_policy "
                    "FROM secure_objects WHERE namespace = ? ORDER BY source_event_id",
                    ("aeat.revision.batch",),
                ).fetchall()
            assert len(rows) == 2
            assert all(len(row[0]) == 64 for row in rows)
            assert [row[1] for row in rows] == [
                hashlib.sha256(b"batch-payload-a").hexdigest(),
                hashlib.sha256(b"batch-payload-b").hexdigest(),
            ]
            assert [row[2] for row in rows] == ["test:batch", "test:batch"]
            assert [row[3] for row in rows] == ["batch-event-a", "batch-event-b"]
            assert [row[4] for row in rows] == ["last-write-wins", "last-write-wins"]
        finally:
            engine.dispose()


def test_secure_object_save_with_raw_key_writes_revision_metadata(tmp_path: Path) -> None:
    """Raw-key archive restore writes the same metadata as natural-key saves."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-raw-key.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        raw_key = bytes(range(32))
        payload = b"raw-key-revision-payload"
        try:
            SecureObjectRepository(engine=engine).save_with_raw_key(
                namespace="aeat.revision.raw",
                hashed_object_key=raw_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 17, 0, 0, tzinfo=UTC),
                payload=payload,
                write_provenance="test:raw-key",
                source_event_id="raw-key-event",
            )

            with sqlite3.connect(db_path) as con:
                row = con.execute(
                    "SELECT object_key, revision_id, payload_hash, write_provenance, source_event_id "
                    "FROM secure_objects WHERE namespace = ?",
                    ("aeat.revision.raw",),
                ).fetchone()
            assert row[0] == raw_key
            assert len(row[1]) == 64
            assert row[2] == hashlib.sha256(payload).hexdigest()
            assert row[3] == "test:raw-key"
            assert row[4] == "raw-key-event"
        finally:
            engine.dispose()


def test_secure_object_write_rejects_conflict_policy_until_cas_contract_exists() -> None:
    """S29 records the actual LWW policy; S30 owns public CAS policy selection."""

    with pytest.raises(ValidationError):
        SecureObjectWrite(
            namespace="aeat.revision.policy",
            object_key="policy-key",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime(2026, 5, 22, 18, 0, 0, tzinfo=UTC),
            payload=b"policy-payload",
            conflict_policy="compare-and-swap",
        )


def test_secure_object_save_with_expected_revision_updates_only_current_row(tmp_path: Path) -> None:
    """Expected-revision writes update when the stored revision still matches."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-cas-success.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.revision.cas"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="cas-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 19, 0, 0, tzinfo=UTC),
                payload=b"cas-before",
            )
            with sqlite3.connect(db_path) as con:
                (first_revision_id,) = con.execute(
                    "SELECT revision_id FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()

            repo.save(
                namespace=namespace,
                object_key="cas-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 19, 5, 0, tzinfo=UTC),
                payload=b"cas-after",
                expected_revision_id=first_revision_id,
            )

            with sqlite3.connect(db_path) as con:
                revision_id, previous_revision_id, payload_hash, conflict_policy = con.execute(
                    "SELECT revision_id, previous_revision_id, payload_hash, conflict_policy "
                    "FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
            assert revision_id != first_revision_id
            assert previous_revision_id == first_revision_id
            assert payload_hash == hashlib.sha256(b"cas-after").hexdigest()
            assert conflict_policy == "compare-and-swap"
        finally:
            engine.dispose()


def test_secure_object_save_with_stale_expected_revision_refuses_without_overwrite(tmp_path: Path) -> None:
    """A stale expected revision must not overwrite the current secure object."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-cas-stale.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.revision.cas.stale"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="cas-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 20, 0, 0, tzinfo=UTC),
                payload=b"current-payload",
            )
            with sqlite3.connect(db_path) as con:
                before = con.execute(
                    "SELECT revision_id, payload_hash FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()

            with pytest.raises(SecureObjectRevisionConflictError) as raised:
                repo.save(
                    namespace=namespace,
                    object_key="cas-key",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime(2026, 5, 22, 20, 5, 0, tzinfo=UTC),
                    payload=b"stale-overwrite",
                    expected_revision_id="f" * 64,
                )

            assert raised.value.context == {
                "namespace": namespace,
                "expected_revision_id": "f" * 64,
                "current_revision_id": before[0],
            }
            assert raised.value.translated_message == "errors.fail.fail_storage_secure_object_revision_conflict"
            with sqlite3.connect(db_path) as con:
                after = con.execute(
                    "SELECT revision_id, payload_hash FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
            assert after == before
        finally:
            engine.dispose()


def test_secure_object_save_with_expected_revision_refuses_missing_row(tmp_path: Path) -> None:
    """A CAS write must not create a missing object for a stale expected revision."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-cas-missing.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.revision.cas.missing"
        try:
            with pytest.raises(SecureObjectRevisionConflictError) as raised:
                SecureObjectRepository(engine=engine).save(
                    namespace=namespace,
                    object_key="missing-key",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime(2026, 5, 22, 20, 30, 0, tzinfo=UTC),
                    payload=b"must-not-create",
                    expected_revision_id="a" * 64,
                )

            assert raised.value.context == {
                "namespace": namespace,
                "expected_revision_id": "a" * 64,
                "current_revision_id": "",
            }
            with sqlite3.connect(db_path) as con:
                (row_count,) = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()
            assert row_count == 0
        finally:
            engine.dispose()


def test_secure_object_save_many_revision_conflict_rolls_back_batch(tmp_path: Path) -> None:
    """A CAS conflict in a batch rolls back sibling writes in the unit of work."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-cas-batch.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.revision.cas.batch"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="existing-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 21, 0, 0, tzinfo=UTC),
                payload=b"existing-payload",
            )

            with pytest.raises(SecureObjectRevisionConflictError):
                repo.save_many(
                    (
                        SecureObjectWrite(
                            namespace=namespace,
                            object_key="new-key",
                            classification=SensitivityClass.FINANCIAL,
                            schema_version=1,
                            written_at=datetime(2026, 5, 22, 21, 5, 0, tzinfo=UTC),
                            payload=b"must-roll-back",
                        ),
                        SecureObjectWrite(
                            namespace=namespace,
                            object_key="existing-key",
                            classification=SensitivityClass.FINANCIAL,
                            schema_version=1,
                            written_at=datetime(2026, 5, 22, 21, 6, 0, tzinfo=UTC),
                            payload=b"stale-batch-overwrite",
                            expected_revision_id="e" * 64,
                        ),
                    )
                )

            with sqlite3.connect(db_path) as con:
                rows = con.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN payload_hash = ? THEN 1 ELSE 0 END) "
                    "FROM secure_objects WHERE namespace = ?",
                    (hashlib.sha256(b"existing-payload").hexdigest(), namespace),
                ).fetchone()
            assert rows == (1, 1)
        finally:
            engine.dispose()


def test_secure_object_save_with_raw_key_supports_expected_revision(tmp_path: Path) -> None:
    """Raw-key archive writes use the same expected-revision conflict contract."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-cas-raw-key.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        raw_key = b"x" * 32
        namespace = "aeat.revision.cas.raw"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save_with_raw_key(
                namespace=namespace,
                hashed_object_key=raw_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 22, 0, 0, tzinfo=UTC),
                payload=b"raw-before",
            )
            with sqlite3.connect(db_path) as con:
                (first_revision_id,) = con.execute(
                    "SELECT revision_id FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()

            repo.save_with_raw_key(
                namespace=namespace,
                hashed_object_key=raw_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 22, 5, 0, tzinfo=UTC),
                payload=b"raw-after",
                expected_revision_id=first_revision_id,
            )

            with sqlite3.connect(db_path) as con:
                previous_revision_id, conflict_policy = con.execute(
                    "SELECT previous_revision_id, conflict_policy FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
            assert previous_revision_id == first_revision_id
            assert conflict_policy == "compare-and-swap"
        finally:
            engine.dispose()


def test_peek_metadata_matches_the_saved_row(tmp_path: Path) -> None:
    """`peek_metadata` reports a row's wire-envelope columns without
    decrypting the payload; the namespace, classification,
    schema_version, and written_at it returns must match what was
    saved, and the byte_length must be the non-empty ciphertext size."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "peek.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.peek"
        written_at = datetime(2026, 5, 21, 9, 15, 0)
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="peek-key-non-default",
                classification=SensitivityClass.FINANCIAL,
                schema_version=4,
                written_at=written_at,
                payload=b"peek-metadata-payload-bytes",
            )

            metadata = repo.peek_metadata(namespace, "peek-key-non-default")

            assert metadata is not None
            assert metadata.namespace == namespace
            assert metadata.classification == SensitivityClass.FINANCIAL.value
            assert metadata.schema_version == 4
            assert metadata.written_at == written_at
            assert metadata.byte_length > 0
        finally:
            engine.dispose()


def test_peek_metadata_reflects_on_disk_schema_version_drift(tmp_path: Path) -> None:
    """Anti-tautology: `peek_metadata` reads the row's actual on-disk
    columns. Rewrite ``schema_version`` directly in SQLite and assert
    the peeked value tracks the mutation — if `peek_metadata` returned
    a cached or hard-coded version, on-disk drift would be invisible."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "peek-drift.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.peek.drift"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="drift-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 21, 8, 0, 0),
                payload=b"drift-payload",
            )
            before = repo.peek_metadata(namespace, "drift-key")
            assert before is not None and before.schema_version == 1

            with sqlite3.connect(db_path) as con:
                con.execute(
                    "UPDATE secure_objects SET schema_version = 9 WHERE namespace = ?",
                    (namespace,),
                )

            after = repo.peek_metadata(namespace, "drift-key")
            assert after is not None
            assert after.schema_version == 9
        finally:
            engine.dispose()


def test_two_repositories_writing_one_key_converge_to_a_single_row(tmp_path: Path) -> None:
    """Two independent SecureObjectRepository instances writing the same
    namespace + object_key converge to one row, last-write-wins.

    `save` is an upsert: a second writer of one logical object must
    replace the first in place, never fork it into divergent rows. The
    deterministic end state — one row carrying the later write — is the
    serialization contract; a duplicate-insert regression would leave
    two divergent ciphertexts under the same logical key."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "converge.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.converge"
        natural_key = "shared-object-key"
        try:
            SecureObjectRepository(engine=engine).save(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 21, 7, 0, 0),
                payload=b"first-writer-payload",
            )
            SecureObjectRepository(engine=engine).save(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=2,
                written_at=datetime(2026, 5, 21, 8, 0, 0),
                payload=b"second-writer-payload",
            )

            loaded = SecureObjectRepository(engine=engine).load(
                namespace,
                natural_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=2,
            )
            assert loaded is not None
            assert loaded.payload == b"second-writer-payload"
            assert loaded.schema_version == 2

            with sqlite3.connect(db_path) as con:
                (row_count,) = con.execute(
                    "SELECT COUNT(*) FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
            assert row_count == 1
        finally:
            engine.dispose()


def test_registry_bound_repository_rejects_unregistered_namespace_on_write(tmp_path: Path) -> None:
    """Runtime-bound secure-object writes must use a registered namespace."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "policy-unregistered.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine, namespace_registry=STORAGE_NAMESPACE_REGISTRY)

            with pytest.raises(StorageValidationError) as raised:
                repo.save(
                    namespace="aeat.test.unregistered.runtime",
                    object_key="policy-key",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=b"policy-payload",
                )

            assert raised.value.translated_message == "errors.storage.namespace.unregistered"
            with sqlite3.connect(db_path) as con:
                (row_count,) = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()
            assert row_count == 0
        finally:
            engine.dispose()


def test_registry_bound_repository_rejects_wrong_write_classification_and_schema(tmp_path: Path) -> None:
    """The namespace registry, not the caller, is authoritative for write policy."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "policy-write-contract.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = WORKFLOW_STATE_NAMESPACE.namespace
        try:
            repo = SecureObjectRepository(engine=engine, namespace_registry=STORAGE_NAMESPACE_REGISTRY)

            with pytest.raises(ClassificationError) as classification_error:
                repo.save(
                    namespace=namespace,
                    object_key=WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
                    classification=SensitivityClass.SESSION,
                    schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                    written_at=datetime.now(UTC),
                    payload=b"wrong-class",
                )

            assert (
                classification_error.value.translated_message
                == "errors.storage.namespace.classification_mismatch"
            )

            with pytest.raises(EnvelopeVersionError) as schema_error:
                repo.save(
                    namespace=namespace,
                    object_key=WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
                    classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                    schema_version=WORKFLOW_STATE_NAMESPACE.schema_version + 1,
                    written_at=datetime.now(UTC),
                    payload=b"wrong-schema",
                )

            assert schema_error.value.translated_message == "errors.storage.namespace.schema_mismatch"
            with sqlite3.connect(db_path) as con:
                (row_count,) = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()
            assert row_count == 0
        finally:
            engine.dispose()


def test_registry_bound_repository_rejects_reader_class_not_declared_by_registry(tmp_path: Path) -> None:
    """A caller cannot widen a registered namespace to a different sensitivity on read."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "policy-read-class.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = WORKFLOW_STATE_NAMESPACE.namespace
        object_key = WORKFLOW_STATE_NAMESPACE.require_default_object_key()
        try:
            repo = SecureObjectRepository(engine=engine, namespace_registry=STORAGE_NAMESPACE_REGISTRY)
            repo.save(
                namespace=namespace,
                object_key=object_key,
                classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                written_at=datetime.now(UTC),
                payload=b"registered-payload",
            )

            with pytest.raises(ClassificationError) as raised:
                repo.load(
                    namespace,
                    object_key,
                    expected_class=SensitivityClass.SESSION,
                    max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                )
            assert raised.value.translated_message == "errors.storage.namespace.classification_mismatch"
        finally:
            engine.dispose()


def test_registry_bound_repository_rejects_on_disk_schema_newer_than_registry(tmp_path: Path) -> None:
    """Registry policy catches stored schema drift even if the reader claims support."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "policy-read-schema.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = WORKFLOW_STATE_NAMESPACE.namespace
        object_key = WORKFLOW_STATE_NAMESPACE.require_default_object_key()
        try:
            unbound_repo = SecureObjectRepository(engine=engine)
            unbound_repo.save(
                namespace=namespace,
                object_key=object_key,
                classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                schema_version=WORKFLOW_STATE_NAMESPACE.schema_version + 1,
                written_at=datetime.now(UTC),
                payload=b"future-schema-payload",
            )

            registry_bound_repo = SecureObjectRepository(engine=engine, namespace_registry=STORAGE_NAMESPACE_REGISTRY)
            with pytest.raises(EnvelopeVersionError) as raised:
                registry_bound_repo.load(
                    namespace,
                    object_key,
                    expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
                    max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version + 1,
                )
            assert raised.value.translated_message == "errors.storage.namespace.schema_mismatch"
        finally:
            engine.dispose()
