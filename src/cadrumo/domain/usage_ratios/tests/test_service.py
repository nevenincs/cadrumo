"""Unit tests for the usage-ratio persistence service.

The service routes through the substrate's encrypted-object backend;
every test here exercises the round-trip against a real active-profile
SQLite runtime.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from ....adapters.persistence.profile.usage_ratios import load_usage_ratios, save_usage_ratios
from ....adapters.persistence.storage import Envelope, SensitivityClass, StorageRuntimeReadinessCode
from ....adapters.persistence.storage.errors import StorageValidationError
from ....core import StorageCategory, storage_path
from ....core.directory_scan import scan_directory
from ....core.identity import BucketId
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...categories import SpendingCategory
from .. import (
    UsageRatioPersistenceError,
    UsageRatioProfile,
    usage_ratio_bucket_lock,
    usage_ratios_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_A_ID = "73737373-7373-4373-8373-737373737301"
_BUCKET_B_ID = "73737373-7373-4373-8373-737373737302"
_SECURE_OBJECT_WRITTEN_AT = datetime(2026, 5, 27, 9, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A_ID) as profile:
        yield profile


def _database_bytes(profile: TestRuntimeProfile) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(profile.paths.database_file)


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
    assert _runtime_profile.paths.database_file.exists()


def test_save_persists_only_to_the_secure_database_object(
    _runtime_profile: TestRuntimeProfile,
) -> None:
    """A saved profile never reaches the plaintext ``financial/usage-ratios.json`` leaf.

    Sibling to ``test_save_does_not_create_requested_plaintext_file`` above,
    but that test checks an arbitrary caller-chosen path
    (``tmp_path / "a" / "b" / "ratios.json"``) rather than the real
    taxonomy-declared location -- it would still pass even if
    ``save_usage_ratios`` wrote to :data:`StorageCategory.USAGE_RATIOS`'s
    real subpath, since that path is never checked. This test closes that
    gap: :data:`StorageCategory.USAGE_RATIOS` now declares no consumer at
    all. Its only one was the master-key rotation sweep, deleted with the
    shared-master model it belonged to, and even then that module only walked
    the location looking for an ``.envelope.json`` file to re-encrypt -- it
    was a sweep, never a writer.
    The module docstring states "no plaintext profile JSON or envelope file
    lands on disk"; this proves it against the accessor-resolved path
    itself, so a future taxonomy subpath move is tracked automatically
    instead of silently passing vacuously against a stale path.
    """
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.30")})
    save_usage_ratios(profile, bucket_id=_BUCKET_A_ID)

    assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == profile
    assert not storage_path(StorageCategory.USAGE_RATIOS).exists()


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

    # Assert the TYPED readiness code, not rendered prose. ``str(exc)`` on this
    # boundary is the translation key by design -- the operator-facing message
    # is rendered downstream -- so a prose match here was matching the key and
    # would pass equally on an absent session, which is a different refusal
    # with a different remedy. The code discriminates them; prose cannot.
    for call in (
        lambda: save_usage_ratios(profile, bucket_id=_BUCKET_B_ID),
        lambda: load_usage_ratios(bucket_id=_BUCKET_B_ID),
    ):
        with pytest.raises(StorageValidationError) as raised:
            call()
        assert raised.value.context["readiness_code"] == StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH.value


def test_save_replaces_previous_payload(tmp_path: Path) -> None:
    """Successive saves replace the payload without leaving ``.tmp`` debris."""
    tmp_path / "ratios.json"
    first = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    second = first.with_ratio(SpendingCategory.TELEFONIA_MOVIL, Decimal("0.6"))
    save_usage_ratios(first, bucket_id=_BUCKET_A_ID)
    save_usage_ratios(second, bucket_id=_BUCKET_A_ID)
    assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == second
    assert list(scan_directory(tmp_path, pattern="*.tmp")) == []


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
    # The MODEL identity, not the bare word "profile": secure-object rows carry
    # their namespace and record type in clear so the store can address them, and
    # this bucket now also holds cadrumo.application.user_profile.value and
    # cadrumo.profile-record.v2 rows. Asserting the bare word passed only while no
    # profile-namespaced row happened to share the database, and would now fail on
    # another feature persisting correctly. Probed the file to confirm every hit is
    # addressing metadata surrounded by ciphertext, with the ratio and the category
    # token still absent above.
    assert b"UsageRatioProfile" not in on_disk


@pytest.mark.parametrize(
    ("payload", "message", "cause_type", "detail"),
    (
        (b"{not-json", None, ValidationError, "Invalid JSON"),
        (b"\xff", "invalid UTF-8", UnicodeDecodeError, None),
    ),
)
def test_load_malformed_secure_object_raises_persistence_error(
    _runtime_profile: TestRuntimeProfile,
    payload: bytes,
    message: str | None,
    cause_type: type[BaseException],
    detail: str | None,
) -> None:
    """Malformed encrypted payload bytes stay on the domain persistence surface."""
    _runtime_profile.repository.save(
        namespace="cadrumo.domain.usage_ratios",
        object_key=usage_ratios_object_key(_BUCKET_A_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_SECURE_OBJECT_WRITTEN_AT,
        payload=payload,
    )
    with pytest.raises(UsageRatioPersistenceError, match=message) as exc_info:
        load_usage_ratios(bucket_id=_BUCKET_A_ID)
    assert isinstance(exc_info.value.__cause__, cause_type)
    if detail is not None:
        assert detail in str(exc_info.value)


def test_load_inner_classification_mismatch_raises_persistence_error(
    _runtime_profile: TestRuntimeProfile,
) -> None:
    envelope = Envelope[UsageRatioProfile](
        schema_version=1,
        written_at=_SECURE_OBJECT_WRITTEN_AT,
        classification=SensitivityClass.CACHE,
        payload=UsageRatioProfile(),
    )
    _runtime_profile.repository.save(
        namespace="cadrumo.domain.usage_ratios",
        object_key=usage_ratios_object_key(_BUCKET_A_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_SECURE_OBJECT_WRITTEN_AT,
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    with pytest.raises(UsageRatioPersistenceError, match="classification"):
        load_usage_ratios(bucket_id=_BUCKET_A_ID)


def test_load_inner_schema_version_mismatch_raises_persistence_error(
    _runtime_profile: TestRuntimeProfile,
) -> None:
    envelope = Envelope[UsageRatioProfile](
        schema_version=2,
        written_at=_SECURE_OBJECT_WRITTEN_AT,
        classification=SensitivityClass.FINANCIAL,
        payload=UsageRatioProfile(),
    )
    _runtime_profile.repository.save(
        namespace="cadrumo.domain.usage_ratios",
        object_key=usage_ratios_object_key(_BUCKET_A_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_SECURE_OBJECT_WRITTEN_AT,
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
    assert list(scan_directory(tmp_path, pattern="*.tmp")) == []


def test_blank_bucket_id_rejected() -> None:
    with pytest.raises(UsageRatioPersistenceError, match="bucket_id"):
        load_usage_ratios(bucket_id=" ")


class TestCanonicalBucketIdentity:
    """Usage-ratio storage owns the same bucket identity as every other consumer.

    The key and lock helpers stripped and rejected blanks for themselves but
    never consumed the canonical ``BucketId`` alias, so they also accepted
    identifiers past its 128-character cap. A 129-character bucket could own a
    persisted usage-ratio row and a lock target that no other bucket consumer
    would address the same way.
    """

    _OVERLENGTH = "b" * 129

    def test_object_key_refuses_an_overlength_bucket(self) -> None:
        """The canonical alias caps identifiers at 128 characters."""
        assert TypeAdapter(BucketId).validate_python("b" * 128) == "b" * 128
        with pytest.raises(ValidationError):
            TypeAdapter(BucketId).validate_python(self._OVERLENGTH)
        with pytest.raises(UsageRatioPersistenceError, match="bucket_id"):
            usage_ratios_object_key(self._OVERLENGTH)

    @pytest.mark.parametrize("bad", ["", "   ", "\t\n", "b" * 129, "b" * 500])
    def test_persistence_refuses_a_non_canonical_bucket(self, bad: str) -> None:
        """The refusal reaches both durable paths, not only the key helper."""
        with pytest.raises(UsageRatioPersistenceError, match="bucket_id"):
            load_usage_ratios(bucket_id=bad)
        with pytest.raises(UsageRatioPersistenceError, match="bucket_id"):
            save_usage_ratios(UsageRatioProfile(), bucket_id=bad)

    def test_lock_target_refuses_a_non_canonical_bucket(self) -> None:
        with (
            pytest.raises(UsageRatioPersistenceError, match="bucket_id"),
            usage_ratio_bucket_lock(self._OVERLENGTH),
        ):
            pytest.fail("an uncanonicalizable bucket must not take a lock")

    def test_object_key_uses_the_canonical_spelling(self) -> None:
        """A padded id addresses the same row as its canonical form."""
        assert usage_ratios_object_key(f"  {_BUCKET_A_ID}  ") == usage_ratios_object_key(_BUCKET_A_ID)
        assert usage_ratios_object_key(_BUCKET_A_ID) == f"profile:{_BUCKET_A_ID}"

    def test_canonical_bucket_still_round_trips(self) -> None:
        """The guard must not refuse a legitimate profile."""
        profile = UsageRatioProfile()
        save_usage_ratios(profile, bucket_id=_BUCKET_A_ID)

        assert load_usage_ratios(bucket_id=_BUCKET_A_ID) == profile

    def test_distinct_buckets_keep_distinct_keys(self) -> None:
        """Canonicalisation must not merge two genuinely different buckets."""
        assert usage_ratios_object_key(_BUCKET_A_ID) != usage_ratios_object_key(_BUCKET_B_ID)
