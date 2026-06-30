"""Unit tests for the usage-ratio persistence service (#259).

Post-USAGE-001 the service routes through the substrate's encrypted-
object backend; every test here exercises the round-trip against a
real active-profile SQLite runtime.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import Envelope, SensitivityClass
from ....adapters.persistence.storage.errors import StorageValidationError
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...categories import SpendingCategory
from .. import (
    UsageRatioPersistenceError,
    UsageRatioProfile,
    load_usage_ratios,
    save_usage_ratios,
    usage_ratios_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_A_ID = "73737373-7373-4373-8373-737373737301"
_BUCKET_B_ID = "73737373-7373-4373-8373-737373737302"


@pytest.fixture(autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A_ID) as profile:
        yield profile


def _database_bytes(profile: TestRuntimeProfile) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(profile.paths.db_dir / "aeat.db")


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    """A missing file yields an empty profile (the virgin state)."""
    target = tmp_path / "missing.json"
    assert not target.exists()
    assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == UsageRatioProfile()


def test_save_does_not_create_requested_plaintext_file(
    tmp_path: Path,
    _runtime_profile: TestRuntimeProfile,
) -> None:
    """``save_usage_ratios`` stores in the secure database, not at ``path``."""
    target = tmp_path / "a" / "b" / "ratios.json"
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    save_usage_ratios(profile, bucket_id=_BUCKET_A_ID)
    assert not target.exists()
    assert (_runtime_profile.paths.db_dir / "aeat.db").exists()


def test_save_round_trips(tmp_path: Path) -> None:
    """A saved profile reloads identically through the encrypted envelope."""
    tmp_path / "ratios.json"
    profile = UsageRatioProfile(
        ratios={
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21"),
            SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6"),
        },
    )
    save_usage_ratios(profile, bucket_id=_BUCKET_A_ID)
    assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == profile


def test_profiles_are_scoped_by_bucket(tmp_path: Path) -> None:
    first = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    second = UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6")})
    save_usage_ratios(first, bucket_id=_BUCKET_A_ID)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_B_ID):
        save_usage_ratios(second, bucket_id=_BUCKET_B_ID)
        assert load_usage_ratios(bucket_id=_BUCKET_B_ID) == second

    assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == first


def test_default_repository_refuses_bucket_route_mismatch() -> None:
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})

    with pytest.raises(StorageValidationError, match=r"route does not match|storage runtime is not ready"):
        save_usage_ratios(profile, bucket_id=_BUCKET_B_ID)

    with pytest.raises(StorageValidationError, match=r"route does not match|storage runtime is not ready"):
        load_usage_ratios(bucket_id=_BUCKET_B_ID)


def test_save_replaces_previous_payload(tmp_path: Path) -> None:
    """Successive saves replace the payload without leaving ``.tmp`` debris."""
    tmp_path / "ratios.json"
    first = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    second = first.with_ratio(SpendingCategory.TELEFONIA_MOVIL, Decimal("0.6"))
    save_usage_ratios(first, bucket_id=_BUCKET_A_ID)
    save_usage_ratios(second, bucket_id=_BUCKET_A_ID)
    assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == second
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_writes_encrypted_database_object(_runtime_profile: TestRuntimeProfile) -> None:
    """The database record is encrypted at FINANCIAL class."""
    plaintext_ratio = Decimal("0.213579")
    profile = UsageRatioProfile(
        ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: plaintext_ratio},
    )
    save_usage_ratios(profile, bucket_id=_BUCKET_A_ID)
    on_disk = _database_bytes(_runtime_profile)
    assert b"secure_objects" in on_disk
    assert b"financial" in on_disk
    assert str(plaintext_ratio).encode("ascii") not in on_disk
    assert b"suministros_home_office_luz" not in on_disk
    assert b"profile" not in on_disk


def test_load_corrupt_secure_object_raises_persistence_error(_runtime_profile: TestRuntimeProfile) -> None:
    """A malformed encrypted payload surfaces as :class:`UsageRatioPersistenceError`."""
    _runtime_profile.repository.save(
        namespace="aeat.domain.usage_ratios",
        object_key=usage_ratios_object_key(_BUCKET_A_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=b"{not-json",
    )
    with pytest.raises(UsageRatioPersistenceError) as exc_info:
        load_usage_ratios(bucket_id=_BUCKET_A_ID)
    assert isinstance(exc_info.value.__cause__, ValidationError)
    assert "Invalid JSON" in str(exc_info.value)


def test_load_non_utf8_secure_object_raises_persistence_error(_runtime_profile: TestRuntimeProfile) -> None:
    """Non-UTF-8 encrypted payload bytes stay on the domain persistence surface."""
    _runtime_profile.repository.save(
        namespace="aeat.domain.usage_ratios",
        object_key=usage_ratios_object_key(_BUCKET_A_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=b"\xff",
    )
    with pytest.raises(UsageRatioPersistenceError, match="invalid UTF-8") as exc_info:
        load_usage_ratios(bucket_id=_BUCKET_A_ID)
    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)


def test_load_inner_classification_mismatch_raises_persistence_error(
    _runtime_profile: TestRuntimeProfile,
) -> None:
    envelope = Envelope[UsageRatioProfile](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.CACHE,
        payload=UsageRatioProfile(),
    )
    _runtime_profile.repository.save(
        namespace="aeat.domain.usage_ratios",
        object_key=usage_ratios_object_key(_BUCKET_A_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    with pytest.raises(UsageRatioPersistenceError, match="classification"):
        load_usage_ratios(bucket_id=_BUCKET_A_ID)


def test_load_inner_schema_version_mismatch_raises_persistence_error(
    _runtime_profile: TestRuntimeProfile,
) -> None:
    envelope = Envelope[UsageRatioProfile](
        schema_version=2,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.FINANCIAL,
        payload=UsageRatioProfile(),
    )
    _runtime_profile.repository.save(
        namespace="aeat.domain.usage_ratios",
        object_key=usage_ratios_object_key(_BUCKET_A_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    with pytest.raises(UsageRatioPersistenceError, match="version"):
        load_usage_ratios(bucket_id=_BUCKET_A_ID)


def test_save_target_directory_is_ignored_by_secure_backend(tmp_path: Path) -> None:
    """The historical path argument no longer controls persistence."""
    target = tmp_path / "ratios-as-dir"
    target.mkdir()
    profile = UsageRatioProfile()
    save_usage_ratios(profile, bucket_id=_BUCKET_A_ID)
    assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == profile
    assert list(tmp_path.glob("*.tmp")) == []


def test_blank_bucket_id_rejected() -> None:
    with pytest.raises(UsageRatioPersistenceError, match="bucket_id"):
        load_usage_ratios(bucket_id=" ")
