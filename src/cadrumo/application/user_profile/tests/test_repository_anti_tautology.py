"""Anti-tautology proof for the user-profile encrypted boundary.

The companion ``test_repository_roundtrip.py`` asserts strict
pydantic equality across the save / load cycle of
:class:`UserProfileLifecycleRepository`. The risk that a
save-drops-X / load-re-defaults-X regression silently passes the
equality check (because the fixture used the default for X) is
real; this file exercises the negative case explicitly.

The test persists a populated :class:`UserProfileRecord`, loads the
encrypted boundary payload through the runtime repository, mutates the
JSON envelope to delete the required ``display_name`` field, writes
the mutated bytes back, and confirms the load side raises
:class:`pydantic.ValidationError`. If the mutation loads cleanly, every
roundtrip test against the user-profile boundary is tautological and
the suite must be re-audited.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage import SensitivityClass
from ....domain.user_profile import (
    StoredProfileDriftError,
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._repository import (
    USER_PROFILE_VALUE_NAMESPACE,
    UserProfileLifecycleRepository,
    user_profile_value_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# The immutable UUIDv4 profile identity, distinct from the label.
_PROFILE_UUID = "c7f3a1b2-9d4e-4a5f-8b6c-1e2d3f4a5b6c"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="user-profile-repository-anti-tautology-test",
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
                path="identity.tax_id",
                value="taxpayer-alpha",
                source="manual_cli",
            ),
        ),
        created_at=created,
        updated_at=updated,
        removed_at=None,
    )


def test_boundary_catches_simulated_field_drop_via_corrupted_payload(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Drop the required ``display_name`` field from the on-disk JSON
    envelope; the load path must refuse.

    The test:

      1. Saves a populated :class:`UserProfileRecord` through the
         real encrypted boundary.
      2. Loads the encrypted boundary payload through the runtime
         repository, deletes the ``display_name`` key from the JSON
         envelope, and writes the mutated bytes back.
      3. Loads the record via the repository.

    The load must raise :class:`StoredProfileDriftError`; if it
    returns despite the mutation, every roundtrip test against this
    boundary is tautological and must be re-audited.
    """

    original = _populated_record()
    repo = UserProfileLifecycleRepository(
        bucket_id=runtime_profile.bucket_id,
        objects=runtime_profile.repository,
    )
    repo.save(original)

    baseline = repo.load(original.profile_id)
    assert baseline == original
    assert baseline.display_name == original.display_name

    stored = runtime_profile.repository.load(
        USER_PROFILE_VALUE_NAMESPACE,
        user_profile_value_object_key(original.profile_id),
        expected_class=SensitivityClass.IDENTITY,
        max_supported_version=1,
    )
    assert stored is not None
    decoded = json.loads(stored.payload.decode("utf-8"))
    assert "display_name" in decoded["payload"], (
        "fixture must serialise display_name into the envelope payload for this test to be meaningful"
    )
    del decoded["payload"]["display_name"]
    runtime_profile.repository.save(
        namespace=stored.namespace,
        object_key=user_profile_value_object_key(original.profile_id),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=json.dumps(decoded).encode("utf-8"),
    )

    with pytest.raises(StoredProfileDriftError):
        repo.load(original.profile_id)
