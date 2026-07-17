"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ._secure_objects_support import (
    STORAGE_NAMESPACE_REGISTRY,
    UTC,
    WORKFLOW_STATE_NAMESPACE,
    Base,
    ClassificationError,
    EnvelopeVersionError,
    Path,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectRevisionConflictError,
    SecureObjectUnreadable,
    SecureObjectUnreadableError,
    SecureObjectWrite,
    SensitivityClass,
    Settings,
    StorageValidationError,
    create_engine_from_settings,
    datetime,
    event,
    hashlib,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@contextmanager
def _ephemeral_secure_repo(
    tmp_path: Path,
    database_name: str,
) -> Iterator[tuple[Path, Any, SecureObjectRepository]]:
    with EphemeralMasterKeyProvider():
        db_path = tmp_path / database_name
        engine = create_engine_from_settings(Settings(cadrumo_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            yield db_path, engine, SecureObjectRepository(engine=engine)
        finally:
            engine.dispose()


def test_secure_object_save_many_revision_conflict_rolls_back_batch(tmp_path: Path) -> None:
    """A CAS conflict in a batch rolls back sibling writes in the unit of work."""

    with _ephemeral_secure_repo(tmp_path, "revision-cas-batch.db") as (db_path, _, repo):
        namespace = "cadrumo.revision.cas.batch"
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
                ),
            )

        with sqlite3.connect(db_path) as con:
            rows = con.execute(
                "SELECT COUNT(*), SUM(CASE WHEN payload_hash = ? THEN 1 ELSE 0 END) "
                "FROM secure_objects WHERE namespace = ?",
                (hashlib.sha256(b"existing-payload").hexdigest(), namespace),
            ).fetchone()
        assert rows == (1, 1)


def test_secure_object_save_with_raw_key_supports_expected_revision(tmp_path: Path) -> None:
    """Raw-key archive writes use the same expected-revision conflict contract."""

    with _ephemeral_secure_repo(tmp_path, "revision-cas-raw-key.db") as (db_path, _, repo):
        raw_key = b"x" * 32
        namespace = "cadrumo.revision.cas.raw"
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


def test_secure_object_save_with_raw_key_stale_expected_revision_refuses_without_overwrite(
    tmp_path: Path,
) -> None:
    """Raw-key CAS writes must not overwrite when the expected revision is stale."""

    with _ephemeral_secure_repo(tmp_path, "revision-cas-raw-key-stale.db") as (db_path, _, repo):
        raw_key = b"y" * 32
        namespace = "cadrumo.revision.cas.raw.stale"
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
            payload=b"raw-current",
        )
        with sqlite3.connect(db_path) as con:
            before = con.execute(
                "SELECT revision_id, payload_hash FROM secure_objects WHERE namespace = ?",
                (namespace,),
            ).fetchone()

        with pytest.raises(SecureObjectRevisionConflictError) as raised:
            repo.save_with_raw_key(
                namespace=namespace,
                hashed_object_key=raw_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 22, 22, 10, 0, tzinfo=UTC),
                payload=b"raw-stale-overwrite",
                expected_revision_id=first_revision_id,
            )

        assert raised.value.context == {
            "namespace": namespace,
            "expected_revision_id": first_revision_id,
            "current_revision_id": before[0],
        }
        assert raised.value.translated_message == "errors.fail.fail_storage_secure_object_revision_conflict"
        with sqlite3.connect(db_path) as con:
            after = con.execute(
                "SELECT revision_id, payload_hash FROM secure_objects WHERE namespace = ?",
                (namespace,),
            ).fetchone()
        assert after == before
        assert after[1] == hashlib.sha256(b"raw-current").hexdigest()


def test_secure_object_load_many_matches_repeated_single_loads_and_uses_one_targeted_query(
    tmp_path: Path,
) -> None:
    """Targeted batch load returns the same readable rows as repeated single loads."""

    with _ephemeral_secure_repo(tmp_path, "load-many-readable.db") as (_, engine, repo):
        namespace = "cadrumo.batch.readable"
        rows = {
            "row-a": b"payload-a",
            "row-b": b"payload-b",
            "row-c": b"payload-c",
        }
        for offset, (object_key, payload) in enumerate(rows.items()):
            repo.save(
                namespace=namespace,
                object_key=object_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 23, 9, offset, 0, tzinfo=UTC),
                payload=payload,
            )

        requested = ("row-c", "row-missing", "row-a")
        expected = {
            record.object_key: record.payload
            for object_key in requested
            for record in (
                repo.load(
                    namespace,
                    object_key,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                ),
            )
            if record is not None
        }

        statements: list[str] = []

        def collect_statement(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", collect_statement)
        try:
            loaded = tuple(
                repo.load_many(
                    namespace,
                    requested,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                ),
            )
        finally:
            event.remove(engine, "before_cursor_execute", collect_statement)

    assert {record.object_key: record.payload for record in loaded} == expected
    assert {record.payload for record in loaded} == {b"payload-a", b"payload-c"}
    assert b"payload-b" not in {record.payload for record in loaded}
    targeted_selects = [
        statement
        for statement in statements
        if "FROM secure_objects WHERE namespace = ?" in statement and "object_key IN" in statement
    ]
    assert len(targeted_selects) == 1


def test_secure_object_load_many_failure_paths_match_single_load_contracts(tmp_path: Path) -> None:
    """Targeted batch load keeps readable rows and schema failures visible."""

    with _ephemeral_secure_repo(tmp_path, "load-many-failures.db") as (_, _, repo):
        namespace = "cadrumo.batch.failures"
        repo.save(
            namespace=namespace,
            object_key="readable-row",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime(2026, 5, 23, 10, 0, 0, tzinfo=UTC),
            payload=b"readable-payload",
        )
        repo.save(
            namespace=namespace,
            object_key="schema-row",
            classification=SensitivityClass.FINANCIAL,
            schema_version=2,
            written_at=datetime(2026, 5, 23, 10, 5, 0, tzinfo=UTC),
            payload=b"future-schema-payload",
        )

        single = repo.load(
            namespace,
            "readable-row",
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )
        assert single is not None
        with pytest.raises(EnvelopeVersionError):
            repo.load(
                namespace,
                "schema-row",
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )

        items = tuple(
            repo.iter_many_with_failures(
                namespace,
                ("schema-row", "readable-row", "missing-row"),
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            ),
        )

        with pytest.raises(SecureObjectUnreadableError):
            tuple(
                repo.load_many(
                    namespace,
                    ("schema-row", "readable-row"),
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                ),
            )

    readable = [item for item in items if isinstance(item, SecureObjectRecord)]
    unreadable = [item for item in items if isinstance(item, SecureObjectUnreadable)]
    assert len(readable) == 1
    assert readable[0].payload == single.payload
    assert len(unreadable) == 1
    from ......core.i18n import tr

    assert unreadable[0].schema_version == 2
    assert unreadable[0].reason == tr(
        "errors.storage.namespace.schema_version_from_future",
        namespace="cadrumo.batch.failures",
        schema_version=2,
        expected=1,
    )


def test_peek_metadata_matches_the_saved_row(tmp_path: Path) -> None:
    """`peek_metadata` reports a row's wire-envelope columns without
    decrypting the payload; the namespace, classification,
    schema_version, and written_at it returns must match what was
    saved, and the byte_length must be the non-empty ciphertext size."""

    with _ephemeral_secure_repo(tmp_path, "peek.db") as (_, _, repo):
        namespace = "cadrumo-test.peek"
        written_at = datetime(2026, 5, 21, 9, 15, 0)
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


def test_peek_metadata_reflects_on_disk_schema_version_drift(tmp_path: Path) -> None:
    """Anti-tautology: `peek_metadata` reads the row's actual on-disk
    columns. Rewrite ``schema_version`` directly in SQLite and assert
    the peeked value tracks the mutation — if `peek_metadata` returned
    a cached or hard-coded version, on-disk drift would be invisible."""

    with _ephemeral_secure_repo(tmp_path, "peek-drift.db") as (db_path, _, repo):
        namespace = "cadrumo-test.peek.drift"
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


def test_two_repositories_writing_one_key_converge_to_a_single_row(tmp_path: Path) -> None:
    """Two independent SecureObjectRepository instances writing the same
    namespace + object_key converge to one row, last-write-wins.

    `save` is an upsert: a second writer of one logical object must
    replace the first in place, never fork it into divergent rows. The
    deterministic end state — one row carrying the later write — is the
    serialization contract; a duplicate-insert regression would leave
    two divergent ciphertexts under the same logical key."""

    with _ephemeral_secure_repo(tmp_path, "converge.db") as (db_path, engine, _):
        namespace = "cadrumo-test.converge"
        natural_key = "shared-object-key"
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


def test_registry_bound_repository_rejects_unregistered_namespace_on_write(tmp_path: Path) -> None:
    """Runtime-bound secure-object writes must use a registered namespace."""

    with _ephemeral_secure_repo(tmp_path, "policy-unregistered.db") as (db_path, engine, _):
        repo = SecureObjectRepository(engine=engine, namespace_registry=STORAGE_NAMESPACE_REGISTRY)

        with pytest.raises(StorageValidationError) as raised:
            repo.save(
                namespace="cadrumo-test.unregistered.runtime",
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


def test_registry_bound_repository_rejects_wrong_write_classification_and_schema(tmp_path: Path) -> None:
    """The namespace registry, not the caller, is authoritative for write policy."""

    with _ephemeral_secure_repo(tmp_path, "policy-write-contract.db") as (db_path, engine, _):
        namespace = WORKFLOW_STATE_NAMESPACE.namespace
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

        assert classification_error.value.translated_message == "errors.storage.namespace.classification_mismatch"

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


def test_registry_bound_repository_rejects_reader_class_not_declared_by_registry(tmp_path: Path) -> None:
    """A caller cannot widen a registered namespace to a different sensitivity on read."""

    with _ephemeral_secure_repo(tmp_path, "policy-read-class.db") as (_, engine, _):
        namespace = WORKFLOW_STATE_NAMESPACE.namespace
        object_key = WORKFLOW_STATE_NAMESPACE.require_default_object_key()
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


def test_registry_bound_repository_rejects_on_disk_schema_newer_than_registry(tmp_path: Path) -> None:
    """Registry policy catches stored schema drift even if the reader claims support."""

    with _ephemeral_secure_repo(tmp_path, "policy-read-schema.db") as (_, engine, _):
        namespace = WORKFLOW_STATE_NAMESPACE.namespace
        object_key = WORKFLOW_STATE_NAMESPACE.require_default_object_key()
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
        assert raised.value.translated_message == "errors.storage.namespace.schema_version_from_future"


def test_repository_refuses_former_product_namespace_before_read_write_delete_or_list(tmp_path: Path) -> None:
    """Former product namespaces never reach SQL or mutate current rows."""
    with _ephemeral_secure_repo(tmp_path, "former-namespace-refusal.db") as (db_path, _, repo):
        current_namespace = "cadrumo-test.namespace.refusal.current"
        former_namespace = "aeat-test.namespace.refusal.former"
        repo.save(
            namespace=current_namespace,
            object_key="sentinel",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"current-sentinel-bytes",
        )

        with pytest.raises(StorageValidationError) as read_error:
            repo.exists(former_namespace, "sentinel")
        with pytest.raises(StorageValidationError) as list_error:
            repo.list_keys(former_namespace)
        with pytest.raises(StorageValidationError) as write_error:
            repo.save(
                namespace=former_namespace,
                object_key="forbidden",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"must-not-be-written",
            )
        with pytest.raises(StorageValidationError) as delete_error:
            repo.delete(former_namespace, "sentinel")

        for error in (read_error, list_error, write_error, delete_error):
            assert error.value.translated_message == "errors.storage.namespace.unregistered"
            assert error.value.context is not None
            assert error.value.context["reason"] == "former_product_namespace"

        loaded = repo.load(
            current_namespace,
            "sentinel",
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )
        assert loaded is not None
        assert loaded.payload == b"current-sentinel-bytes"
        with sqlite3.connect(db_path) as connection:
            rows = connection.execute("SELECT namespace FROM secure_objects ORDER BY namespace").fetchall()
        assert rows == [(current_namespace,)]
