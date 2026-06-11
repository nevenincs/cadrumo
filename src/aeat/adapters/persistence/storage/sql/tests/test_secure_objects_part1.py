"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._secure_objects_support import (
    UTC,
    Base,
    ClassificationError,
    EnvelopeVersionError,
    EphemeralMasterKeyProvider,
    Path,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectUnreadable,
    SecureObjectUnreadableError,
    SensitivityClass,
    Settings,
    StorageValidationError,
    _seed_under_key,
    create_engine_from_settings,
    datetime,
    logging,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


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
    ``Base.metadata.create_all``. Nullable is the canonical CREATE shape for
    these columns: a record without a prior revision legitimately carries no
    ``previous_*`` lineage, so the schema admits NULL by design.
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
            assert int(columns[column_name][3]) == 0, f"{column_name} must be nullable (canonical CREATE shape)"
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
            assert (
                repo.load(
                    namespace,
                    natural_key,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=3,
                )
                is not None
            )
            with sqlite3.connect(db_path) as con:
                con.execute(
                    "UPDATE secure_objects SET schema_version = ? WHERE namespace = ?",
                    (4, namespace),
                )
                (stored_lookup_digest,) = con.execute(
                    "SELECT hex(object_key) FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
                con.commit()

            with pytest.raises(EnvelopeVersionError) as raised:
                repo.load(
                    namespace,
                    natural_key,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=3,
                )
            rendered = str(raised.value)
            assert raised.value.translated_message == "errors.storage.namespace.schema_mismatch"
            assert raised.value.context == {
                "namespace": namespace,
                "schema_version": 4,
                "expected": 3,
            }
            assert natural_key not in rendered
            assert str(stored_lookup_digest).lower() not in rendered.lower()
        finally:
            engine.dispose()


def test_secure_object_load_classification_error_is_localized_and_redacted(tmp_path: Path) -> None:
    """Load-time classification failures do not expose natural or lookup keys."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "load-classification-redaction.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.load.classification"
        natural_key = "classification-secret-key"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"classification-redaction",
            )
            with sqlite3.connect(db_path) as con:
                con.execute(
                    "UPDATE secure_objects SET classification = ? WHERE namespace = ?",
                    (SensitivityClass.AUDIT.value, namespace),
                )
                (stored_lookup_digest,) = con.execute(
                    "SELECT hex(object_key) FROM secure_objects WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
                con.commit()

            with pytest.raises(ClassificationError) as raised:
                repo.load(
                    namespace,
                    natural_key,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                )
            rendered = str(raised.value)
            assert raised.value.translated_message == "errors.storage.namespace.classification_mismatch"
            assert raised.value.context == {
                "namespace": namespace,
                "classification": SensitivityClass.AUDIT.value,
                "expected": SensitivityClass.FINANCIAL.value,
            }
            assert natural_key not in rendered
            assert str(stored_lookup_digest).lower() not in rendered.lower()
        finally:
            engine.dispose()


def test_secure_object_raw_key_validation_errors_are_localized(tmp_path: Path) -> None:
    """Raw-key public helpers reject malformed digests with translated errors."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "raw-key-localized.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(StorageValidationError) as exists_raised:
                repo.exists_by_raw_key("aeat.test.raw", b"short")
            assert (
                exists_raised.value.translated_message
                == "errors.integrity.integrity_storage_secure_object_hashed_key_length"
            )
            assert exists_raised.value.context == {"length": 5}

            with pytest.raises(StorageValidationError) as save_raised:
                repo.save_with_raw_key(
                    namespace="aeat.test.raw",
                    hashed_object_key=b"short",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=b"payload",
                )
            assert (
                save_raised.value.translated_message
                == "errors.integrity.integrity_storage_secure_object_hashed_key_length"
            )
            assert save_raised.value.context == {"length": 5}
        finally:
            engine.dispose()


def test_secure_object_batch_size_validation_error_is_localized(tmp_path: Path) -> None:
    """Batch-size validation uses the translated storage-validation key."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "batch-size-localized.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(StorageValidationError) as raised:
                list(
                    repo.iter_records_with_failures(
                        "aeat.test.batch",
                        expected_class=SensitivityClass.FINANCIAL,
                        max_supported_version=1,
                        batch_size=0,
                    ),
                )
            assert raised.value.translated_message == "errors.integrity.integrity_storage_secure_object_batch_size"
            assert raised.value.context == {"batch_size": 0}
        finally:
            engine.dispose()


def test_list_records_fails_closed_when_any_row_is_unreadable(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A row written under master key K1 must fail default listing under K2.

    The default listing surface is fail-closed: it must not yield the
    readable subset if another row in the same namespace cannot be
    decrypted. ``iter_records_with_failures`` remains the opt-in
    diagnostic path for mixed readable/unreadable namespaces.
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

            with (
                caplog.at_level(logging.DEBUG, logger="aeat.adapters.persistence.storage.sql.secure_objects"),
                pytest.raises(SecureObjectUnreadableError) as raised,
            ):
                list(
                    repo.list_records(
                        namespace,
                        expected_class=SensitivityClass.FINANCIAL,
                        max_supported_version=1,
                    ),
                )

            assert raised.value.namespace == namespace
            assert raised.value.row_id >= 1
            assert any("refusing default list" in rec.message for rec in caplog.records), (
                f"expected debug diagnostics for fail-closed listing; got {[r.message for r in caplog.records]}"
            )
            explicit = list(
                repo.iter_records_with_failures(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                ),
            )
            assert len([item for item in explicit if isinstance(item, SecureObjectRecord)]) == 1
            assert len([item for item in explicit if isinstance(item, SecureObjectUnreadable)]) == 1
        finally:
            engine.dispose()


def test_list_records_does_not_yield_partial_subset_before_failure(tmp_path: Path) -> None:
    """The fail-closed list path buffers all readable rows before yielding."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "metadata-order.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.metadata.order"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="readable-row",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"readable-early-row",
            )
            with sqlite3.connect(db_path) as con:
                con.execute(
                    "UPDATE secure_objects SET classification = ? WHERE namespace = ?",
                    (SensitivityClass.AUDIT.value, namespace),
                )
            iterator = repo.list_records(
                namespace,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )

            with pytest.raises(SecureObjectUnreadableError):
                next(iterator)
        finally:
            engine.dispose()


def test_list_records_yields_records_when_every_row_is_readable(tmp_path: Path) -> None:
    """Readable namespaces still yield records through the default list path."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "readable-list.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace="aeat.test.readable.list",
                object_key="readable-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"readable-list-payload",
            )

            yielded = list(
                repo.list_records(
                    "aeat.test.readable.list",
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                ),
            )

            assert [record.payload for record in yielded] == [b"readable-list-payload"]
        finally:
            engine.dispose()


def test_list_records_rejects_unreadable_row_before_readable_subset(
    tmp_path: Path,
) -> None:
    """The exception surfaces even when a readable row was also stored."""

    db_path = tmp_path / "rotated-readable.db"
    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()
    namespace = "aeat.test.rotation.readable"

    _seed_under_key(
        db_path=db_path,
        provider=key_old,
        namespace=namespace,
        natural_key="row-under-old-key",
        payload=b"plaintext-from-old-generation",
    )

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

            with pytest.raises(SecureObjectUnreadableError):
                list(
                    repo.list_records(
                        namespace,
                        expected_class=SensitivityClass.FINANCIAL,
                        max_supported_version=1,
                    ),
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
                ),
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


def test_iter_records_with_failures_yields_metadata_contract_failures(tmp_path: Path) -> None:
    """Row-level metadata failures surface as typed unreadable outcomes."""

    with EphemeralMasterKeyProvider():
        db_path = tmp_path / "metadata-failures.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        namespace = "aeat.test.metadata.failures"
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=namespace,
                object_key="classification-row",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"classification-row",
            )
            repo.save(
                namespace=namespace,
                object_key="schema-row",
                classification=SensitivityClass.FINANCIAL,
                schema_version=2,
                written_at=datetime.now(UTC),
                payload=b"schema-row",
            )
            with sqlite3.connect(db_path) as con:
                con.execute(
                    "UPDATE secure_objects SET classification = ? WHERE namespace = ? AND schema_version = ?",
                    (SensitivityClass.AUDIT.value, namespace, 1),
                )

            outcomes = list(
                repo.iter_records_with_failures(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                ),
            )

            assert len(outcomes) == 2
            assert all(isinstance(item, SecureObjectUnreadable) for item in outcomes)
            reasons = {item.reason for item in outcomes if isinstance(item, SecureObjectUnreadable)}
            assert any("classification" in reason for reason in reasons)
            assert any("schema version" in reason for reason in reasons)
        finally:
            engine.dispose()
