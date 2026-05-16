"""Strict roundtrip across the user-profile lifecycle + snapshot repos.

Two IDENTITY-class encrypted namespaces are exercised:

- ``aeat.application.user_profile.value`` — live aggregate per
  ``(bucket_id, profile_id)``.
- ``aeat.application.user_profile.snapshot`` — immutable filing
  snapshot per ``(bucket_id, snapshot_id)``.

Anti-tautology: the fixture populates every defaultable field on
:class:`UserProfileRecord` with non-default values
(``schema_version=2``, multi-fact tuple with explicit
``valid_from``/``valid_to``, distinct ``created_at`` ahead of
``updated_at``). A drift silently dropping facts or lifecycle
metadata would surface as inequality on the loaded record.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ...domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    UserProfileStatus,
)
from ._repository import UserProfileLifecycleRepository, UserProfileSnapshotRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_record() -> UserProfileRecord:
    created = datetime(2024, 1, 4, 9, 0, 0, tzinfo=UTC)
    updated = datetime(2024, 6, 15, 14, 32, 17, tzinfo=UTC)
    return UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=2,
        profile_id="contributor.gw-2024",
        display_name="Gergely Wootsch - 2024 IRPF",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(
                path="identity.given_name",
                value="Gergely",
                source="manual_cli",
            ),
            UserProfileFact(
                path="identity.family_name",
                value="Wootsch",
                source="manual_cli",
            ),
            UserProfileFact(
                path="residency.municipality_code",
                value="28079",
                source="aeat_sede_pull",
                valid_from=date(2023, 1, 1),
                valid_to=date(2024, 12, 31),
            ),
            UserProfileFact(
                path="vat.recargo_equivalencia.applied",
                value=False,
                source="manual_cli",
            ),
            UserProfileFact(
                path="irpf.minimum_personal_amount",
                value=Decimal("5550.00"),
                source="aeat_workbook_2024",
                valid_from=date(2024, 1, 1),
            ),
        ),
        created_at=created,
        updated_at=updated,
    )


def test_user_profile_value_and_snapshot_survive_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UserProfileRecord + UserProfileSnapshot roundtrip through both repos."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "user-profile-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        bucket_id = "profile-bucket-A"
        lifecycle = UserProfileLifecycleRepository(bucket_id=bucket_id)
        snapshots = UserProfileSnapshotRepository(bucket_id=bucket_id)

        original_record = _populated_record()
        lifecycle.save(original_record)
        loaded_record = lifecycle.load(original_record.profile_id)

        assert loaded_record == original_record
        assert len(loaded_record.facts) == 5
        assert tuple(f.path for f in loaded_record.facts) == (
            "identity.given_name",
            "identity.family_name",
            "residency.municipality_code",
            "vat.recargo_equivalencia.applied",
            "irpf.minimum_personal_amount",
        )
        # The Decimal fact survives JSON round-trip strictly.
        assert loaded_record.facts[-1].value == Decimal("5550.00")
        assert loaded_record.facts[-1].valid_from == date(2024, 1, 1)
        assert loaded_record.schema_version == 2

        original_snapshot = UserProfileSnapshot.from_profile(loaded_record)
        snapshots.save(original_snapshot)
        loaded_snapshot = snapshots.load(original_snapshot.snapshot_id)

        assert loaded_snapshot == original_snapshot
        # The canonical hash binds the snapshot identity to its facts;
        # a silent fact drop on save would break it.
        assert loaded_snapshot.canonical_hash == original_snapshot.canonical_hash
        assert len(loaded_snapshot.facts) == 5
    finally:
        engine.dispose()
        override_master_key_provider(None)
