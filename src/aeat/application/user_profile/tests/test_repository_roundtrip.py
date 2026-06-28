"""Strict roundtrip across the user-profile lifecycle + snapshot repos.

Two IDENTITY-class encrypted namespaces are exercised:

- ``aeat.application.user_profile.value`` — live aggregate keyed by
  the immutable UUIDv4 ``profile_id`` (one record per bucket).
- ``aeat.application.user_profile.snapshot`` — immutable filing
  snapshot per ``(profile_id, snapshot_id)``.

The profile identity is a generated UUIDv4, fully decoupled from the
operator-chosen ``display_name``. The fixture below uses a UUID
``profile_id`` and a distinct ``display_name`` so the roundtrip proves
both survive the encrypted boundary independently.

Anti-tautology: the fixture populates every defaultable field on
:class:`UserProfileRecord` with non-default values
(``schema_version=2``, multi-fact tuple with explicit
``valid_from``/``valid_to``, distinct ``created_at`` ahead of
``updated_at``). A drift silently dropping facts or lifecycle
metadata would surface as inequality on the loaded record.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import SensitivityClass
from ....domain.user_profile import (
    StoredProfileDriftError,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    UserProfileStatus,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._repository import (
    USER_PROFILE_SNAPSHOT_NAMESPACE,
    USER_PROFILE_VALUE_NAMESPACE,
    UserProfileLifecycleRepository,
    UserProfileSnapshotRepository,
    user_profile_snapshot_object_key,
    user_profile_value_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# A fixed UUIDv4 in the canonical hyphenated form: the immutable
# profile identity, deliberately distinct in shape from the
# operator-chosen display name.
_PROFILE_UUID = "c7f3a1b2-9d4e-4a5f-8b6c-1e2d3f4a5b6c"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="user-profile-repository-roundtrip-test",
    ) as profile:
        yield profile


def _populated_record() -> UserProfileRecord:
    created = datetime(2024, 1, 4, 9, 0, 0, tzinfo=UTC)
    updated = datetime(2024, 6, 15, 14, 32, 17, tzinfo=UTC)
    return UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=2,
        profile_id=_PROFILE_UUID,
        display_name="Persona Prueba - 2024 IRPF",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(
                path="identity.given_name",
                value="Persona",
                source="manual_cli",
            ),
            UserProfileFact(
                path="identity.family_name",
                value="Prueba",
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
                path="iva.recargo_equivalencia.applied",
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
    runtime_profile: TestRuntimeProfile,
) -> None:
    """UserProfileRecord + UserProfileSnapshot roundtrip through both repos."""

    profile_id = _PROFILE_UUID
    lifecycle = UserProfileLifecycleRepository(bucket_id=profile_id, objects=runtime_profile.repository)
    snapshots = UserProfileSnapshotRepository(bucket_id=profile_id, objects=runtime_profile.repository)

    original_record = _populated_record()
    lifecycle.save(original_record)
    loaded_record = lifecycle.load(original_record.profile_id)

    assert loaded_record == original_record
    # The UUID identity and the operator label survive the encrypted boundary as independent fields.
    assert loaded_record.profile_id == _PROFILE_UUID
    assert loaded_record.display_name == "Persona Prueba - 2024 IRPF"
    assert loaded_record.profile_id != loaded_record.display_name
    assert len(loaded_record.facts) == 5
    assert tuple(f.path for f in loaded_record.facts) == (
        "identity.given_name",
        "identity.family_name",
        "residency.municipality_code",
        "iva.recargo_equivalencia.applied",
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
    # The canonical hash binds the snapshot identity to its facts; a silent fact drop on save would break it.
    assert loaded_snapshot.canonical_hash == original_snapshot.canonical_hash
    assert len(loaded_snapshot.facts) == 5


def test_user_profile_active_with_removed_at_surfaces_at_load(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology proof: ACTIVE + removed_at must surface on load.

    :class:`UserProfileRecord` enforces a lifecycle invariant: ACTIVE
    profiles must NOT carry ``removed_at``; TOMBSTONED profiles MUST.
    A silent drift across the encrypted boundary that materialised
    ``removed_at`` on an ACTIVE record would corrupt the lifecycle
    state machine (the record would appear "soft-deleted" while
    still being reachable through the active-profile path).

    Persists an ACTIVE record, loads the encrypted boundary payload
    through the runtime repository, surgically stamps ``removed_at``
    into the JSON envelope without flipping ``status`` to TOMBSTONED,
    and asserts the load path catches the drift via the
    model_validator's lifecycle check.

    If this test passes silently with the rogue removed_at, the
    user-profile lifecycle boundary is tautological and the state
    machine is not actually enforced post-persistence.
    """

    bucket_id = runtime_profile.bucket_id
    lifecycle = UserProfileLifecycleRepository(bucket_id=bucket_id, objects=runtime_profile.repository)
    record = _populated_record()
    lifecycle.save(record)

    stored = runtime_profile.repository.load(
        USER_PROFILE_VALUE_NAMESPACE,
        user_profile_value_object_key(record.profile_id),
        expected_class=SensitivityClass.IDENTITY,
        max_supported_version=1,
    )
    assert stored is not None
    envelope = json.loads(stored.payload.decode("utf-8"))
    payload = envelope["payload"]
    assert payload["status"] == "active", "fixture must persist ACTIVE status for this proof test to be meaningful"
    # Stamp removed_at while keeping ACTIVE status. The lifecycle invariant must trip on load.
    payload["removed_at"] = "2024-12-15T10:00:00+00:00"
    runtime_profile.repository.save(
        namespace=stored.namespace,
        object_key=user_profile_value_object_key(record.profile_id),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(StoredProfileDriftError) as excinfo:
        UserProfileLifecycleRepository(bucket_id=bucket_id, objects=runtime_profile.repository).load(record.profile_id)
    assert excinfo.value.profile_id == record.profile_id
    assert isinstance(excinfo.value.original_exception, ValidationError)


def test_user_profile_snapshot_canonical_hash_drift_surfaces_at_load(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology proof: a snapshot whose facts drift from canonical_hash must surface.

    :class:`UserProfileSnapshot` carries a model_validator that
    re-derives the canonical_hash from the persisted facts and
    rejects any drift. The snapshot is the content-addressed
    proof-of-facts contract; a silently-mutated fact tuple with a
    stale hash would invalidate the audit trail for downstream
    filings.

    Persists a snapshot via the snapshots repository, loads the
    encrypted boundary payload through the runtime repository,
    surgically mutates one fact's value WITHOUT recomputing
    canonical_hash, and asserts the load path catches the drift via
    the model_validator's derived-hash check.

    If this test passes silently with the tampered fact, the
    canonical-hash guarantee is tautological — the persisted hash
    no longer proves the persisted facts.
    """

    profile_id = _PROFILE_UUID
    lifecycle = UserProfileLifecycleRepository(bucket_id=profile_id, objects=runtime_profile.repository)
    snapshots = UserProfileSnapshotRepository(bucket_id=profile_id, objects=runtime_profile.repository)
    record = _populated_record()
    lifecycle.save(record)
    snapshot = UserProfileSnapshot.from_profile(record)
    snapshots.save(snapshot)

    stored = runtime_profile.repository.load(
        USER_PROFILE_SNAPSHOT_NAMESPACE,
        user_profile_snapshot_object_key(profile_id, snapshot.snapshot_id),
        expected_class=SensitivityClass.IDENTITY,
        max_supported_version=1,
    )
    assert stored is not None
    envelope = json.loads(stored.payload.decode("utf-8"))
    payload = envelope["payload"]
    assert payload["facts"], (
        "fixture must serialise at least one fact onto the snapshot for this proof test to be meaningful"
    )
    # Mutate the first fact's value while leaving canonical_hash untouched.
    first_fact = payload["facts"][0]
    original_value = first_fact.get("value")
    mutated_value = (
        "tampered-string" if isinstance(original_value, str) and original_value != "tampered-string" else "drift-canary"
    )
    first_fact["value"] = mutated_value
    runtime_profile.repository.save(
        namespace=stored.namespace,
        object_key=user_profile_snapshot_object_key(profile_id, snapshot.snapshot_id),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(ValidationError):
        snapshots.load(snapshot.snapshot_id)
