"""Unit tests for the usage-ratio persistence service (#259).

Post-USAGE-001 the service routes through the substrate's encrypted-
object backend; every test here exercises the round-trip against a
real SQLite database under an :class:`EphemeralMasterKeyProvider`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    Envelope,
    EphemeralMasterKeyProvider,
    SecretStore,
    SensitivityClass,
    override_secret_store,
)
from aeat.adapters.persistence.storage.sql import create_engine_from_settings
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.core.config import Settings
from aeat.domain.categories import SpendingCategory
from aeat.domain.usage_ratios import (
    UsageRatioPersistenceError,
    UsageRatioProfile,
    load_usage_ratios,
    save_usage_ratios,
    usage_ratios_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.fixture(autouse=True)
def _patch_secret_store(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        blob_store = EncryptedBlobStore(
            root_dir=tmp_path / "blobs-secret",
            master_key_provider=provider,
        )
        secret_store = SecretStore(
            store_dir=tmp_path / "secrets",
            blob_store=blob_store,
            master_key_provider=provider,
        )
        override_secret_store(secret_store)
        try:
            yield
        finally:
            override_secret_store(None)


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"))
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def secure_objects(secure_engine: Engine) -> SecureObjectRepository:
    return SecureObjectRepository(engine=secure_engine)


def _database_bytes(tmp_path: Path) -> bytes:
    return (tmp_path / "aeat.db").read_bytes()


def test_load_missing_returns_empty(tmp_path: Path, secure_objects: SecureObjectRepository) -> None:
    """A missing file yields an empty profile (the virgin state)."""
    target = tmp_path / "missing.json"
    assert not target.exists()
    assert load_usage_ratios(bucket_id="bucket-a", objects=secure_objects) == UsageRatioProfile()


def test_save_does_not_create_requested_plaintext_file(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    """``save_usage_ratios`` stores in the secure database, not at ``path``."""
    target = tmp_path / "a" / "b" / "ratios.json"
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    save_usage_ratios(profile, bucket_id="bucket-a", objects=secure_objects)
    assert not target.exists()
    assert (tmp_path / "aeat.db").exists()


def test_save_round_trips(tmp_path: Path, secure_objects: SecureObjectRepository) -> None:
    """A saved profile reloads identically through the encrypted envelope."""
    tmp_path / "ratios.json"
    profile = UsageRatioProfile(
        ratios={
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21"),
            SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6"),
        }
    )
    save_usage_ratios(profile, bucket_id="bucket-a", objects=secure_objects)
    assert load_usage_ratios(bucket_id="bucket-a", objects=secure_objects) == profile


def test_profiles_are_scoped_by_bucket(tmp_path: Path, secure_objects: SecureObjectRepository) -> None:
    first = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    second = UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6")})
    save_usage_ratios(first, bucket_id="bucket-a", objects=secure_objects)
    save_usage_ratios(second, bucket_id="bucket-b", objects=secure_objects)
    assert load_usage_ratios(bucket_id="bucket-a", objects=secure_objects) == first
    assert load_usage_ratios(bucket_id="bucket-b", objects=secure_objects) == second


def test_save_replaces_previous_payload(tmp_path: Path, secure_objects: SecureObjectRepository) -> None:
    """Successive saves replace the payload without leaving ``.tmp`` debris."""
    tmp_path / "ratios.json"
    first = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    second = first.with_ratio(SpendingCategory.TELEFONIA_MOVIL, Decimal("0.6"))
    save_usage_ratios(first, bucket_id="bucket-a", objects=secure_objects)
    save_usage_ratios(second, bucket_id="bucket-a", objects=secure_objects)
    assert load_usage_ratios(bucket_id="bucket-a", objects=secure_objects) == second
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_writes_encrypted_database_object(tmp_path: Path, secure_objects: SecureObjectRepository) -> None:
    """The database record is encrypted at FINANCIAL class."""
    tmp_path / "ratios.json"
    profile = UsageRatioProfile(
        ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")},
    )
    save_usage_ratios(profile, bucket_id="bucket-a", objects=secure_objects)
    on_disk = _database_bytes(tmp_path)
    assert b"secure_objects" in on_disk
    assert b"financial" in on_disk
    assert b"0.21" not in on_disk
    assert b"suministros_home_office_luz" not in on_disk
    assert b"profile" not in on_disk


def test_load_corrupt_secure_object_raises_persistence_error(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    """A malformed encrypted payload surfaces as :class:`UsageRatioPersistenceError`."""
    tmp_path / "bad.json"
    secure_objects.save(
        namespace="aeat.domain.usage_ratios",
        object_key=usage_ratios_object_key("bucket-a"),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=b"{not-json",
    )
    with pytest.raises(UsageRatioPersistenceError):
        load_usage_ratios(bucket_id="bucket-a", objects=secure_objects)


def test_load_inner_classification_mismatch_raises_persistence_error(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    envelope = Envelope[UsageRatioProfile](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.CACHE,
        payload=UsageRatioProfile(),
    )
    secure_objects.save(
        namespace="aeat.domain.usage_ratios",
        object_key=usage_ratios_object_key("bucket-a"),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    with pytest.raises(UsageRatioPersistenceError, match="classification"):
        load_usage_ratios(bucket_id="bucket-a", objects=secure_objects)


def test_load_inner_schema_version_mismatch_raises_persistence_error(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    envelope = Envelope[UsageRatioProfile](
        schema_version=2,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.FINANCIAL,
        payload=UsageRatioProfile(),
    )
    secure_objects.save(
        namespace="aeat.domain.usage_ratios",
        object_key=usage_ratios_object_key("bucket-a"),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    with pytest.raises(UsageRatioPersistenceError, match="version"):
        load_usage_ratios(bucket_id="bucket-a", objects=secure_objects)


def test_save_target_directory_is_ignored_by_secure_backend(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    """The historical path argument no longer controls persistence."""
    target = tmp_path / "ratios-as-dir"
    target.mkdir()
    profile = UsageRatioProfile()
    save_usage_ratios(profile, bucket_id="bucket-a", objects=secure_objects)
    assert load_usage_ratios(bucket_id="bucket-a", objects=secure_objects) == profile
    assert list(tmp_path.glob("*.tmp")) == []


def test_blank_bucket_id_rejected() -> None:
    with pytest.raises(UsageRatioPersistenceError, match="bucket_id"):
        load_usage_ratios(bucket_id=" ")
