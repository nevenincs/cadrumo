"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from ._secure_objects_support import (
    UTC,
    Path,
    SecureObjectNamespaceDefinition,
    SecureObjectNamespaceIntegrity,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectRevisionConflictError,
    SecureObjectUnreadable,
    SecureObjectWrite,
    SensitivityClass,
    StorageCustodyDisposition,
    StorageHierarchyRegistry,
    StorageNamespaceScope,
    StorageValidationError,
    ValidationError,
    _seed_under_key,
    datetime,
    event,
    hashlib,
    logging,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@contextmanager
def _ephemeral_secure_repo_at(
    db_path: Path,
) -> Iterator[tuple[Any, SecureObjectRepository]]:
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
) -> Iterator[tuple[Path, Any, SecureObjectRepository]]:
    db_path = tmp_path / database_name
    with _ephemeral_secure_repo_at(db_path) as (engine, repo):
        yield db_path, engine, repo


def test_iter_records_with_failures_yields_registry_schema_drift(tmp_path: Path) -> None:
    """Registry-bound row schema drift surfaces as a typed unreadable outcome."""

    with _ephemeral_secure_repo(tmp_path, "registry-schema-drift.db") as (_, engine, repo):
        namespace = "cadrumo-test.registry.schema"
        registry = StorageHierarchyRegistry(
            namespaces=(
                SecureObjectNamespaceDefinition(
                    key="test_registry_schema",
                    namespace=namespace,
                    owner="aeat-test",
                    sensitivity=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    object_key_grammar="{id}",
                    scope=StorageNamespaceScope.PROFILE_LOCAL,
                    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
                ),
            ),
            paths=(),
        )
        repo.save(
            namespace=namespace,
            object_key="schema-row",
            classification=SensitivityClass.FINANCIAL,
            schema_version=2,
            written_at=datetime.now(UTC),
            payload=b"schema-row",
        )

        outcomes = list(
            SecureObjectRepository(engine=engine, namespace_registry=registry).iter_records_with_failures(
                namespace,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=2,
            ),
        )

        assert len(outcomes) == 1
        assert isinstance(outcomes[0], SecureObjectUnreadable)
        assert outcomes[0].schema_version == 2
        assert "schema" in outcomes[0].reason


def test_iter_records_with_failures_returns_empty_on_empty_namespace(
    tmp_path: Path,
) -> None:
    """A namespace with no rows yields an empty iterator without raising."""
    with _ephemeral_secure_repo(tmp_path, "empty.db") as (_, _, repo):
        items = list(
            repo.iter_records_with_failures(
                "cadrumo-test.empty",
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            ),
        )
        assert items == []


def test_iter_records_with_failures_yields_older_schema_drift(tmp_path: Path) -> None:
    """Rows below the current version are unreadable without migration."""
    from ......core.i18n import tr

    with _ephemeral_secure_repo(tmp_path, "older-schema-drift.db") as (_, _, repo):
        namespace = "cadrumo-test.older.schema"
        repo.save(
            namespace=namespace,
            object_key="older-row",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"older-row",
        )

        outcomes = list(
            repo.iter_records_with_failures(
                namespace,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=2,
            ),
        )

        assert len(outcomes) == 1
        assert isinstance(outcomes[0], SecureObjectUnreadable)
        assert outcomes[0].schema_version == 1
        assert outcomes[0].reason == tr(
            "errors.storage.namespace.schema_upgrade_path_missing",
            namespace=namespace,
            schema_version=1,
            expected=2,
            missing_from_version=1,
        )


def test_iter_records_with_failures_applies_bounded_batch_execution(tmp_path: Path) -> None:
    """The explicit diagnostic iterator executes its row scan with a bounded batch size."""

    with _ephemeral_secure_repo(tmp_path, "bounded-batches.db") as (_, engine, repo):
        namespace = "cadrumo-test.bounded.batches"
        captured_options: list[dict[str, object]] = []

        def capture_listing_execution(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            context: Any,
            _executemany: bool,
        ) -> None:
            if "FROM secure_objects WHERE namespace" in statement:
                captured_options.append(dict(context.execution_options))

        event.listen(engine, "before_cursor_execute", capture_listing_execution)
        try:
            for index in range(5):
                repo.save(
                    namespace=namespace,
                    object_key=f"row-{index}",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=f"payload-{index}".encode(),
                )

            outcomes = list(
                repo.iter_records_with_failures(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                    batch_size=2,
                ),
            )

            assert len(outcomes) == 5
            assert all(isinstance(item, SecureObjectRecord) for item in outcomes)
            assert any(
                options.get("yield_per") == 2 and options.get("stream_results") is True for options in captured_options
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture_listing_execution)


def test_iter_records_with_failures_rejects_invalid_batch_size(tmp_path: Path) -> None:
    """Batch size must be positive before the diagnostic row scan starts."""

    with _ephemeral_secure_repo(tmp_path, "invalid-batch-size.db") as (_, _, repo):
        with pytest.raises(StorageValidationError) as raised:
            list(
                repo.iter_records_with_failures(
                    "cadrumo-test.invalid.batch",
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                    batch_size=0,
                ),
            )
        assert raised.value.translated_message == "errors.integrity.integrity_storage_secure_object_batch_size"
        assert raised.value.context == {"batch_size": 0}


def test_list_records_only_emits_warning_when_unreadable_rows_exist(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No warning fires on a clean namespace; the warning is gated on real failures."""
    with _ephemeral_secure_repo(tmp_path, "clean.db") as (_, _, repo):
        namespace = "cadrumo-test.clean"
        repo.save(
            namespace=namespace,
            object_key="row-clean",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"clean-plaintext",
        )

        with caplog.at_level(logging.WARNING, logger="cadrumo.adapters.persistence.storage.sql.secure_objects"):
            yielded = list(
                repo.list_records(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                ),
            )

        assert len(yielded) == 1
        assert all("unreadable" not in rec.message for rec in caplog.records)


def test_iter_all_records_raw_yields_every_row_without_decryption(tmp_path: Path) -> None:
    """The raw iterator returns on-wire ciphertext + metadata across namespaces."""

    from ..secure_objects import SecureObjectRawRow

    with _ephemeral_secure_repo(tmp_path, "raw.db") as (_, _, repo):
        now = datetime.now(UTC)
        repo.save(
            namespace="cadrumo.alpha",
            object_key="key-a-1",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=now,
            payload=b"payload-a-1",
        )
        repo.save(
            namespace="cadrumo.beta",
            object_key="key-b-1",
            classification=SensitivityClass.SESSION,
            schema_version=1,
            written_at=now,
            payload=b"payload-b-1",
        )
        repo.save(
            namespace="cadrumo.alpha",
            object_key="key-a-2",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=now,
            payload=b"payload-a-2",
        )

        rows = list(repo.iter_all_records_raw())
        alpha_rows = list(repo.iter_all_records_raw(namespace="cadrumo.alpha"))

        assert len(rows) == 3
        assert all(isinstance(row, SecureObjectRawRow) for row in rows)
        namespaces = [row.namespace for row in rows]
        # Ordered by (namespace ASC, object_key ASC); the three rows
        # yield as cadrumo.alpha (x2) then cadrumo.beta (x1).
        assert namespaces == ["cadrumo.alpha", "cadrumo.alpha", "cadrumo.beta"]
        assert [row.namespace for row in alpha_rows] == ["cadrumo.alpha", "cadrumo.alpha"]
        assert {row.object_key for row in alpha_rows} == {
            row.object_key for row in rows if row.namespace == "cadrumo.alpha"
        }
        for row in rows:
            assert len(row.payload) > 0
            assert row.payload not in (b"payload-a-1", b"payload-a-2", b"payload-b-1"), (
                "iter_all_records_raw must return on-wire ciphertext, not plaintext"
            )
            assert row.ciphertext_hash == hashlib.sha256(row.payload).hexdigest()
            assert row.revision_id is not None
            assert row.revision_written_at is not None
            assert row.classification in {"financial", "session"}
            assert row.schema_version == 1


def test_iter_all_records_raw_returns_empty_iterator_for_empty_table(tmp_path: Path) -> None:
    """No rows persisted → iterator yields nothing without raising."""

    with _ephemeral_secure_repo(tmp_path, "empty.db") as (_, _, repo):
        rows = list(repo.iter_all_records_raw())
        assert rows == []


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
        namespace="cadrumo.rotated",
        natural_key="rotated-key",
        payload=b"rotated-payload",
    )
    # Switch to a fresh master key the seeded payload was NOT encrypted under.
    with _ephemeral_secure_repo_at(db_path) as (_, repo):
        rows = list(repo.iter_all_records_raw())
        assert len(rows) == 1
        # The ciphertext bytes are returned verbatim; no DecryptionError.
        assert rows[0].namespace == "cadrumo.rotated"


def test_quarantine_unreadable_rows_preserves_revision_metadata(tmp_path: Path) -> None:
    """Quarantine copies lineage and integrity fields with unreadable ciphertext.

    The source row is sealed under an old key, then annotated with
    non-default revision metadata before reopening under a different key.
    Quarantine must archive the opaque row without dropping the metadata
    that later sync and repair flows rely on.
    """

    seed_provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "quarantine-metadata.db"
    namespace = "cadrumo.quarantine.metadata"
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

    with _ephemeral_secure_repo_at(db_path) as (_, repo):
        report = repo.quarantine_unreadable_rows()

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
                "conflict_policy FROM secure_objects_quarantine",
            ).fetchone()
            (remaining,) = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()
        assert archived == tuple(metadata_values.values())
        assert remaining == 0


def test_secure_object_save_writes_revision_integrity_metadata(tmp_path: Path) -> None:
    """A save writes storage-level revision and integrity metadata to disk."""

    with _ephemeral_secure_repo(tmp_path, "revision-write.db") as (db_path, _, repo):
        payload = b"revision-integrity-payload"
        written_at = datetime(2026, 5, 22, 13, 0, 0, tzinfo=UTC)
        repo.save(
            namespace="cadrumo.revision.write",
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
                "conflict_policy, payload FROM secure_objects",
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


def test_secure_object_overwrite_links_previous_revision_metadata(tmp_path: Path) -> None:
    """Overwrites preserve the previous storage revision reference and payload hash."""

    with _ephemeral_secure_repo(tmp_path, "revision-overwrite.db") as (db_path, _, repo):
        namespace = "cadrumo.revision.overwrite"
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


def test_secure_object_save_many_writes_revision_metadata(tmp_path: Path) -> None:
    """Batched writes carry revision metadata for each persisted row."""

    with _ephemeral_secure_repo(tmp_path, "revision-save-many.db") as (db_path, _, repo):
        repo.save_many(
            (
                SecureObjectWrite(
                    namespace="cadrumo.revision.batch",
                    object_key="batch-a",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime(2026, 5, 22, 16, 0, 0, tzinfo=UTC),
                    payload=b"batch-payload-a",
                    write_provenance="test:batch",
                    source_event_id="batch-event-a",
                ),
                SecureObjectWrite(
                    namespace="cadrumo.revision.batch",
                    object_key="batch-b",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime(2026, 5, 22, 16, 1, 0, tzinfo=UTC),
                    payload=b"batch-payload-b",
                    write_provenance="test:batch",
                    source_event_id="batch-event-b",
                ),
            ),
        )

        with sqlite3.connect(db_path) as con:
            rows = con.execute(
                "SELECT revision_id, payload_hash, write_provenance, source_event_id, conflict_policy "
                "FROM secure_objects WHERE namespace = ? ORDER BY source_event_id",
                ("cadrumo.revision.batch",),
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


def test_secure_object_save_with_raw_key_writes_revision_metadata(tmp_path: Path) -> None:
    """Raw-key archive restore writes the same metadata as natural-key saves."""

    with _ephemeral_secure_repo(tmp_path, "revision-raw-key.db") as (db_path, _, repo):
        raw_key = bytes(range(32))
        payload = b"raw-key-revision-payload"
        repo.save_with_raw_key(
            namespace="cadrumo.revision.raw",
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
                ("cadrumo.revision.raw",),
            ).fetchone()
        assert row[0] == raw_key
        assert len(row[1]) == 64
        assert row[2] == hashlib.sha256(payload).hexdigest()
        assert row[3] == "test:raw-key"
        assert row[4] == "raw-key-event"


def test_secure_object_write_rejects_conflict_policy_until_cas_contract_exists() -> None:
    """contract records the actual LWW policy; contract owns public CAS policy selection."""

    with pytest.raises(ValidationError):
        SecureObjectWrite(
            **cast(
                dict[str, Any],
                {
                    "namespace": "cadrumo.revision.policy",
                    "object_key": "policy-key",
                    "classification": SensitivityClass.FINANCIAL,
                    "schema_version": 1,
                    "written_at": datetime(2026, 5, 22, 18, 0, 0, tzinfo=UTC),
                    "payload": b"policy-payload",
                    "conflict_policy": "compare-and-swap",
                },
            ),
        )


def test_secure_object_save_with_expected_revision_updates_only_current_row(tmp_path: Path) -> None:
    """Expected-revision writes update when the stored revision still matches."""

    with _ephemeral_secure_repo(tmp_path, "revision-cas-success.db") as (db_path, _, repo):
        namespace = "cadrumo.revision.cas"
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


def test_secure_object_save_with_stale_expected_revision_refuses_without_overwrite(tmp_path: Path) -> None:
    """A stale expected revision must not overwrite the current secure object."""

    with _ephemeral_secure_repo(tmp_path, "revision-cas-stale.db") as (db_path, _, repo):
        namespace = "cadrumo.revision.cas.stale"
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


def test_secure_object_save_with_expected_revision_refuses_missing_row(tmp_path: Path) -> None:
    """A CAS write must not create a missing object for a stale expected revision."""

    with _ephemeral_secure_repo(tmp_path, "revision-cas-missing.db") as (db_path, _, repo):
        namespace = "cadrumo.revision.cas.missing"
        with pytest.raises(SecureObjectRevisionConflictError) as raised:
            repo.save(
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
