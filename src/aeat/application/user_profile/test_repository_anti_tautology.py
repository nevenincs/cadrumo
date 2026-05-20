"""Anti-tautology proof for the user-profile encrypted boundary.

The companion ``test_repository_roundtrip.py`` asserts strict
pydantic equality across the save / load cycle of
:class:`UserProfileLifecycleRepository`. The risk that a
save-drops-X / load-re-defaults-X regression silently passes the
equality check (because the fixture used the default for X) is
real; this file exercises the negative case explicitly.

The test persists a populated :class:`UserProfileRecord`, decrypts
the SQL row's payload, mutates the JSON envelope to delete the
required ``display_name`` field, re-encrypts the mutated bytes, and
confirms the load side either raises
:class:`pydantic.ValidationError` (strict mode + extra='forbid')
or surfaces the mutation as inequality on the loaded record. If
neither outcome holds, every roundtrip test against the
user-profile boundary is tautological and the suite must be
re-audited.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base, SecureObjectRow
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...adapters.persistence.storage.sql.session import session_scope
from ...core.config import Settings
from ...domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
)
from ._repository import UserProfileLifecycleRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


# The immutable UUIDv4 profile identity, distinct from the label.
_PROFILE_UUID = "c7f3a1b2-9d4e-4a5f-8b6c-1e2d3f4a5b6c"


def _populated_record() -> UserProfileRecord:
    created = datetime(2024, 1, 4, 9, 0, 0, tzinfo=UTC)
    updated = datetime(2024, 6, 15, 14, 32, 17, tzinfo=UTC)
    return UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=2,
        profile_id=_PROFILE_UUID,
        display_name="Gergely Wootsch - 2024 IRPF",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(
                path="identity.given_name",
                value="Gergely",
                source="manual_cli",
            ),
            UserProfileFact(
                path="identity.tax_id",
                value="12345678Z",
                source="manual_cli",
            ),
        ),
        created_at=created,
        updated_at=updated,
        removed_at=None,
    )


def test_boundary_catches_simulated_field_drop_via_corrupted_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drop the required ``display_name`` field from the on-disk JSON
    envelope; the load path must refuse or surface inequality.

    The test:

      1. Saves a populated :class:`UserProfileRecord` through the
         real encrypted boundary.
      2. Reaches into SQLite, decrypts the row's payload, deletes the
         ``display_name`` key from the JSON envelope, re-encrypts the
         mutated bytes, and writes them back.
      3. Loads the record via the repository.

    Two outcomes prove the boundary is honest:

      * The load raises :class:`pydantic.ValidationError` (strict
        mode + ``extra='forbid'`` refuses the mutated shape).
      * The load returns a :class:`UserProfileRecord` that is
        strictly unequal to the original (the missing required
        field surfaces as a mismatch).

    If neither outcome holds (i.e. the load somehow returns the
    original-equal record despite the mutation), every roundtrip
    test against this boundary is tautological and must be
    re-audited.
    """

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            objects = SecureObjectRepository(engine=engine)

            original = _populated_record()
            # Inject the secure-object store so the lifecycle repo and
            # the direct corruption query below both address the same
            # database. Without the injection the repo self-resolves
            # to its own per-bucket database and the corruption query
            # would target an empty file.
            repo = UserProfileLifecycleRepository(bucket_id="probe-bucket", objects=objects)
            repo.save(original)

            baseline = repo.load(original.profile_id)
            assert baseline == original
            assert baseline.display_name == original.display_name

            # Reach into the encrypted row, mutate the JSON envelope to
            # drop the required ``display_name`` key, and let the
            # column-level encryption re-wrap on flush.
            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).limit(1)
                row = session.execute(stmt).scalar_one()
                decoded = json.loads(row.payload.decode("utf-8"))
                assert "display_name" in decoded["payload"], (
                    "fixture must serialise display_name into the envelope payload "
                    "for this test to be meaningful"
                )
                del decoded["payload"]["display_name"]
                row.payload = json.dumps(decoded).encode("utf-8")

            regression_caught = False
            try:
                mutated = repo.load(original.profile_id)
            except ValidationError:
                regression_caught = True
            else:
                assert mutated != original
                regression_caught = True

            assert regression_caught, (
                "boundary did not detect a deliberate field drop - every "
                "roundtrip test against the user-profile boundary is suspect "
                "and must be re-audited"
            )
        finally:
            engine.dispose()
