"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._secure_objects_support import (
    STORAGE_NAMESPACE_REGISTRY,
    UTC,
    WORKFLOW_STATE_NAMESPACE,
    Base,
    ClassificationError,
    EnvelopeVersionError,
    EphemeralMasterKeyProvider,
    Path,
    SecureObjectRepository,
    SecureObjectRevisionConflictError,
    SecureObjectWrite,
    SensitivityClass,
    Settings,
    StorageValidationError,
    create_engine_from_settings,
    datetime,
    hashlib,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


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
                    ),
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


def test_secure_object_save_with_raw_key_stale_expected_revision_refuses_without_overwrite(
    tmp_path: Path,
) -> None:
    """Raw-key CAS writes must not overwrite when the expected revision is stale."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "revision-cas-raw-key-stale.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        raw_key = b"y" * 32
        namespace = "aeat.revision.cas.raw.stale"
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
