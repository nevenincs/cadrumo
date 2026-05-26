"""Tests for encrypted SQL byte-object persistence."""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.classification import SensitivityClass
from .....core.config import SecretStoreBackend, Settings, override_settings
from .....domain.user_profile import UserProfileFact, UserProfileRecord
from .. import (
    Envelope,
    EphemeralMasterKeyProvider,
    UnsecuredMasterKeyProvider,
    activate_master_key_provider,
)
from ..crypto._encrypted_columns import EncryptedBytes
from ..errors import EnvelopeVersionError, StorageValidationError, UnsecuredModeRefusedError
from ..master_key._active_session import NoActiveBucketSessionError, activate_session
from ..master_key._bucket_session import BucketSession
from ._orm import Base
from .engine import create_engine_from_settings
from .secure_objects import (
    SecureObjectNamespaceIntegrity,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectUnreadable,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_USER_PROFILE_VALUE_NAMESPACE = "aeat.application.user_profile.value"


def _profile_payload(*, profile_id: str, tax_id: str) -> bytes:
    envelope = Envelope[UserProfileRecord](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.IDENTITY,
        payload=UserProfileRecord(
            profile_id=profile_id,
            display_name=profile_id,
            facts=(UserProfileFact(path="identity.tax_id", value=tax_id),),
        ),
    )
    return envelope.model_dump_json().encode("utf-8")


def test_secure_object_unreadable_is_public_sql_surface() -> None:
    """Adapter callers import unreadable-row diagnostics from the SQL package surface."""

    from . import SecureObjectUnreadable as PublicSecureObjectUnreadable

    assert PublicSecureObjectUnreadable is SecureObjectUnreadable


def test_secure_object_namespace_integrity_rejects_invalid_diagnostic_shape() -> None:
    """The namespace integrity diagnostic is strict at its construction boundary."""

    with pytest.raises(ValidationError, match="namespace"):
        SecureObjectNamespaceIntegrity(namespace="", readable=0, unreadable=0)
    with pytest.raises(ValidationError, match="readable"):
        SecureObjectNamespaceIntegrity(namespace="aeat.test", readable=-1, unreadable=0)
    with pytest.raises(ValidationError, match="unreadable"):
        SecureObjectNamespaceIntegrity(namespace="aeat.test", readable=0, unreadable=-1)


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


def test_unsecured_backend_refuses_real_profile_write(tmp_path: Path) -> None:
    provider = UnsecuredMasterKeyProvider()
    with override_settings(aeat_local_storage_root=tmp_path / "state"), provider:
        db_path = tmp_path / "unsecured-write.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(UnsecuredModeRefusedError) as excinfo:
                repo.save(
                    namespace=_USER_PROFILE_VALUE_NAMESPACE,
                    object_key="user-profile:operator",
                    classification=SensitivityClass.IDENTITY,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=_profile_payload(profile_id="operator", tax_id="12345678Z"),
                )
        finally:
            engine.dispose()

    assert "12345678Z" not in str(excinfo.value)


def test_unsecured_backend_refuses_real_cif_profile_write(tmp_path: Path) -> None:
    provider = UnsecuredMasterKeyProvider()
    with override_settings(aeat_local_storage_root=tmp_path / "state"), provider:
        db_path = tmp_path / "unsecured-cif-write.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(UnsecuredModeRefusedError) as excinfo:
                repo.save(
                    namespace=_USER_PROFILE_VALUE_NAMESPACE,
                    object_key="user-profile:company",
                    classification=SensitivityClass.IDENTITY,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=_profile_payload(profile_id="company", tax_id="B66012345"),
                )
        finally:
            engine.dispose()

    assert "B66012345" not in str(excinfo.value)


def test_unsecured_backend_refuses_malformed_profile_payload(tmp_path: Path) -> None:
    provider = UnsecuredMasterKeyProvider()
    with override_settings(aeat_local_storage_root=tmp_path / "state"), provider:
        db_path = tmp_path / "unsecured-malformed.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(UnsecuredModeRefusedError):
                repo.save(
                    namespace=_USER_PROFILE_VALUE_NAMESPACE,
                    object_key="user-profile:malformed",
                    classification=SensitivityClass.IDENTITY,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=b'{"payload": {"facts": []}}',
                )
        finally:
            engine.dispose()


@pytest.mark.parametrize(
    "payload",
    (
        b"not-json",
        b'{"payload": {"profile": {"tax_id": "12345678Z"}}}',
    ),
)
def test_unsecured_backend_refuses_unprovable_profile_payload_shapes(tmp_path: Path, payload: bytes) -> None:
    provider = UnsecuredMasterKeyProvider()
    with override_settings(aeat_local_storage_root=tmp_path / "state"), provider:
        db_path = tmp_path / "unsecured-unprovable.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(UnsecuredModeRefusedError) as excinfo:
                repo.save(
                    namespace=_USER_PROFILE_VALUE_NAMESPACE,
                    object_key="user-profile:unprovable",
                    classification=SensitivityClass.IDENTITY,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=payload,
                )
        finally:
            engine.dispose()

    assert "12345678Z" not in str(excinfo.value)


def test_unsecured_backend_allows_synthetic_profile_write(tmp_path: Path) -> None:
    provider = UnsecuredMasterKeyProvider()
    with override_settings(aeat_local_storage_root=tmp_path / "state"), provider:
        db_path = tmp_path / "unsecured-synthetic.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            repo.save(
                namespace=_USER_PROFILE_VALUE_NAMESPACE,
                object_key="user-profile:operator",
                classification=SensitivityClass.IDENTITY,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=_profile_payload(profile_id="operator", tax_id="00000000T"),
            )
            loaded = repo.load(
                _USER_PROFILE_VALUE_NAMESPACE,
                "user-profile:operator",
                expected_class=SensitivityClass.IDENTITY,
                max_supported_version=1,
            )
        finally:
            engine.dispose()

    assert loaded is not None


def test_secure_object_repository_requires_active_session(tmp_path: Path) -> None:
    db_path = tmp_path / "no-session.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        repo = SecureObjectRepository(engine=engine)
        with pytest.raises(NoActiveBucketSessionError):
            repo.exists("aeat.test", "key")
    finally:
        engine.dispose()


def test_secure_object_save_many_empty_requires_active_session(tmp_path: Path) -> None:
    db_path = tmp_path / "empty-save-many.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        repo = SecureObjectRepository(engine=engine)
        with pytest.raises(NoActiveBucketSessionError):
            repo.save_many(())
    finally:
        engine.dispose()


def test_secure_object_repository_refuses_route_mismatched_active_bucket(tmp_path: Path) -> None:
    root = tmp_path / "state"
    bucket_a = root / "buckets" / "bucket-a" / "db" / "aeat.db"
    bucket_b = root / "buckets" / "bucket-b" / "db" / "aeat.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{bucket_b.as_posix()}"))
    Base.metadata.create_all(engine)
    session = BucketSession.open(
        bucket_id="bucket-a",
        kek=b"a" * 32,
        dek=b"b" * 32,
        idle_minutes=60,
        opened_at=datetime.now(UTC),
    )
    try:
        with override_settings(aeat_local_storage_root=root), activate_session(session):
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(StorageValidationError, match="active bucket session"):
                repo.save(
                    namespace="aeat.test.route",
                    object_key="key",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=b"payload",
                )
    finally:
        session.close()
        engine.dispose()
    assert not bucket_a.exists()


def test_secure_object_repository_refuses_root_fallback_write_under_active_bucket(tmp_path: Path) -> None:
    root = tmp_path / "state"
    db_path = root / "aeat.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    session = BucketSession.open(
        bucket_id="bucket-a",
        kek=b"a" * 32,
        dek=b"b" * 32,
        idle_minutes=60,
        opened_at=datetime.now(UTC),
    )
    try:
        with override_settings(aeat_local_storage_root=root), activate_session(session):
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(StorageValidationError, match="active bucket database"):
                repo.save(
                    namespace="aeat.test.route",
                    object_key="key",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=b"payload",
                )
    finally:
        session.close()
        engine.dispose()


def test_secure_object_quarantine_refuses_route_mismatched_active_bucket(tmp_path: Path) -> None:
    root = tmp_path / "state"
    db_path = root / "buckets" / "bucket-b" / "db" / "aeat.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    session = BucketSession.open(
        bucket_id="bucket-a",
        kek=b"a" * 32,
        dek=b"b" * 32,
        idle_minutes=60,
        opened_at=datetime.now(UTC),
    )
    try:
        with override_settings(aeat_local_storage_root=root), activate_session(session):
            repo = SecureObjectRepository(engine=engine)
            with pytest.raises(StorageValidationError, match="active bucket session"):
                repo.quarantine_unreadable_rows()
    finally:
        session.close()
        engine.dispose()


def test_unsecured_activation_refuses_bucket_with_real_profile(tmp_path: Path) -> None:
    root = tmp_path / "state"
    bucket_id = "operator"
    db_path = root / "buckets" / bucket_id / "db" / "aeat.db"
    with override_settings(
        aeat_local_storage_root=root,
        aeat_secret_store_backend=SecretStoreBackend.UNSECURED,
        aeat_allow_unencrypted="1",
    ):
        provider = UnsecuredMasterKeyProvider()
        with activate_master_key_provider(provider, fallback_bucket_id=bucket_id):
            engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
            Base.metadata.create_all(engine)
            try:
                repo = SecureObjectRepository(engine=engine)
                repo.save(
                    namespace=_USER_PROFILE_VALUE_NAMESPACE,
                    object_key="user-profile:operator",
                    classification=SensitivityClass.IDENTITY,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=_profile_payload(profile_id="operator", tax_id="00000000T"),
                )
                encrypted_real_payload = EncryptedBytes().process_bind_param(
                    _profile_payload(profile_id="operator", tax_id="12345678Z"),
                    engine.dialect,
                )
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        "UPDATE secure_objects SET payload = ? WHERE namespace = ?",
                        (encrypted_real_payload, _USER_PROFILE_VALUE_NAMESPACE),
                    )
            finally:
                engine.dispose()

        with (
            pytest.raises(UnsecuredModeRefusedError) as excinfo,
            activate_master_key_provider(UnsecuredMasterKeyProvider(), fallback_bucket_id=bucket_id),
        ):
            pass

    assert "12345678Z" not in str(excinfo.value)


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
            assert isinstance(stored_key, bytes)
            assert len(stored_key) == 32
            assert natural_key.encode("utf-8") not in stored_key

            loaded = repo.load(
                namespace,
                natural_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=3,
            )

            assert loaded == SecureObjectRecord(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=3,
                written_at=written_at,
                payload=payload,
            )
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
