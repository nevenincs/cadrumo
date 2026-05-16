"""Real-behavior tests for the 036 census snapshot service.

Anti-tautology: the fixture populates ``census_facts`` with both
``Decimal`` and ``str`` values (vivienda_office m2 are decimals;
the rest are short string literals or ISO date strings) so the
encrypted-store round-trip witnesses the ``_CensusFactValue = Decimal
| str`` union, the same drift pattern the borrador roundtrip test
covers.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import (
    create_engine_from_settings,
    dispose_engine,
)
from aeat.application.live._census import (
    CENSUS_SNAPSHOT_NAMESPACE,
    CensusSnapshot,
    CensusSnapshotRepository,
    CensusSnapshotService,
    CensusSnapshotState,
    census_snapshot_object_key,
    derive_census_snapshot_id,
)
from aeat.application.live._errors import LiveApplicationInputError
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_facts() -> dict[str, str]:
    return {
        "census.activity_start_date": "2024-01-15",
        "census.establecimiento_type": "propio",
        "census.elected_withholding_pct": "15",
        "contact.fiscal_address_cadastral_reference": "9872023VH5797S0001WX",
        "contact.fiscal_address_is_habitual_vivienda": "true",
        "vivienda_office.total_m2": "120.00",
        "vivienda_office.office_m2": "24.50",
    }


@pytest.fixture
def isolated_secure_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "census-snapshot.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    dispose_engine()
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    SecureObjectRepository(engine=engine)
    try:
        yield
    finally:
        engine.dispose()
        dispose_engine()
        override_master_key_provider(None)


def test_derive_census_snapshot_id_is_deterministic_over_canonical_inputs() -> None:
    """Two calls with identical inputs yield the same SHA-256 hex id;
    changing any of profile_id / captured_at / source_url / a fact
    value changes the id."""

    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    base_kwargs = dict(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml",
        census_facts=_populated_facts(),
    )
    base_id = derive_census_snapshot_id(**base_kwargs)
    assert len(base_id) == 64
    assert int(base_id, 16) >= 0

    # Identical inputs => identical id.
    assert derive_census_snapshot_id(**base_kwargs) == base_id

    # Different profile_id => different id.
    drift_kwargs = dict(base_kwargs, profile_id="other-operator")
    assert derive_census_snapshot_id(**drift_kwargs) != base_id

    # Different fact value => different id.
    drift_facts = dict(_populated_facts())
    drift_facts["census.elected_withholding_pct"] = "7"
    assert derive_census_snapshot_id(**dict(base_kwargs, census_facts=drift_facts)) != base_id


def test_census_snapshot_object_key_namespaces_by_bucket_and_snapshot() -> None:
    """The secure-object key embeds bucket and snapshot ids so the
    namespace cannot collide across buckets or snapshots."""

    key = census_snapshot_object_key("bucket-1", "snap-abc")
    assert key == "census-snapshot:bucket-1:snap-abc"
    with pytest.raises(LiveApplicationInputError, match=r"bucket_id"):
        census_snapshot_object_key("   ", "snap-abc")
    with pytest.raises(LiveApplicationInputError, match=r"snapshot_id"):
        census_snapshot_object_key("bucket-1", "   ")


def test_active_snapshot_cannot_carry_supersession_pointer() -> None:
    """The state-payload invariant refuses an ACTIVE snapshot that
    also names a successor; mirrors Borrador100 invariants verbatim."""

    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    snapshot_id = derive_census_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        census_facts={},
    )
    with pytest.raises(LiveApplicationInputError, match=r"active.*supersession"):
        CensusSnapshot(
            snapshot_id=snapshot_id,
            bucket_id="bucket-1",
            profile_id="operator",
            captured_at=captured_at,
            source_url="https://example/G313",
            state=CensusSnapshotState.ACTIVE,
            superseded_by_snapshot_id="another-snapshot-id",
        )


def test_superseded_snapshot_requires_successor_pointer() -> None:
    """A SUPERSEDED snapshot with no successor pointer is invalid."""

    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    snapshot_id = derive_census_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        census_facts={},
    )
    with pytest.raises(LiveApplicationInputError, match=r"superseded.*superseded_by"):
        CensusSnapshot(
            snapshot_id=snapshot_id,
            bucket_id="bucket-1",
            profile_id="operator",
            captured_at=captured_at,
            source_url="https://example/G313",
            state=CensusSnapshotState.SUPERSEDED,
        )


def test_census_snapshot_survives_encrypted_storage_roundtrip(
    isolated_secure_store: None,
) -> None:
    """The populated snapshot round-trips through the encrypted store
    preserving both Decimal and str fact values intact."""

    bucket_id = "operator-bucket"
    repo = CensusSnapshotRepository(bucket_id=bucket_id)
    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    facts = _populated_facts()
    snapshot_id = derive_census_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml",
        census_facts=facts,
    )
    original = CensusSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml",
        state=CensusSnapshotState.ACTIVE,
        census_facts=facts,
    )
    repo.save(original)
    loaded = repo.load(original.snapshot_id)

    # Compare via model_dump so datetime tzinfo identity (UTC singleton
    # vs pydantic-core TzInfo(0)) doesn't sabotage the round-trip
    # equality check; the values are semantically identical.
    assert loaded.model_dump(mode="json") == original.model_dump(mode="json")
    # Every fact value stays str (no numeric-looking string gets silently
    # coerced into Decimal by the union resolver).
    for key in (
        "census.elected_withholding_pct",
        "vivienda_office.total_m2",
        "vivienda_office.office_m2",
        "census.establecimiento_type",
    ):
        assert isinstance(loaded.census_facts[key], str), key
    assert loaded.census_facts["vivienda_office.total_m2"] == "120.00"
    assert loaded.census_facts["census.elected_withholding_pct"] == "15"


def test_capture_is_idempotent_for_structurally_identical_facts(
    isolated_secure_store: None,
) -> None:
    """Re-capturing the same facts at the same time is a no-op:
    snapshot_id is deterministic so the service returns the existing
    snapshot rather than persisting a duplicate."""

    service = CensusSnapshotService(bucket_id="operator-bucket")
    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    facts = _populated_facts()

    first = service.capture(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        census_facts=facts,
    )
    second = service.capture(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        census_facts=facts,
    )
    assert first.snapshot_id == second.snapshot_id
    assert first.state is CensusSnapshotState.ACTIVE
    # Both calls produce a single ACTIVE snapshot in the repo.
    snapshots = service.list_snapshots(state=CensusSnapshotState.ACTIVE)
    assert len(snapshots) == 1


def test_capture_auto_supersedes_prior_active_for_same_profile(
    isolated_secure_store: None,
) -> None:
    """A fresh capture for the same profile transitions the prior
    ACTIVE snapshot into SUPERSEDED with a successor pointer."""

    service = CensusSnapshotService(bucket_id="operator-bucket")
    facts_v1 = _populated_facts()
    facts_v2 = dict(facts_v1)
    facts_v2["census.elected_withholding_pct"] = "7"

    snapshot_v1 = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        census_facts=facts_v1,
    )
    snapshot_v2 = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 17, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        census_facts=facts_v2,
    )

    # v1 was superseded; v2 is the new ACTIVE.
    prior = service.resolve_snapshot(snapshot_v1.snapshot_id)
    assert prior.state is CensusSnapshotState.SUPERSEDED
    assert prior.superseded_by_snapshot_id == snapshot_v2.snapshot_id
    assert snapshot_v2.state is CensusSnapshotState.ACTIVE

    # latest_active returns v2.
    latest = service.latest_active(profile_id="operator")
    assert latest is not None
    assert latest.snapshot_id == snapshot_v2.snapshot_id


def test_capture_marks_older_snapshot_superseded_when_a_newer_active_exists(
    isolated_secure_store: None,
) -> None:
    """A capture older than the current ACTIVE is itself marked
    SUPERSEDED with a pointer to the newer ACTIVE — mirrors the
    Borrador100 out-of-order capture path."""

    service = CensusSnapshotService(bucket_id="operator-bucket")
    facts_newer = _populated_facts()
    facts_older = dict(facts_newer)
    facts_older["census.elected_withholding_pct"] = "1"

    newer = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 17, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        census_facts=facts_newer,
    )
    older = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 15, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        census_facts=facts_older,
    )

    assert older.state is CensusSnapshotState.SUPERSEDED
    assert older.superseded_by_snapshot_id == newer.snapshot_id
    assert service.latest_active(profile_id="operator").snapshot_id == newer.snapshot_id


def test_supersession_scopes_to_profile_id(isolated_secure_store: None) -> None:
    """Captures for different profile_ids in the same bucket do NOT
    supersede each other (multi-profile bucket isolation)."""

    service = CensusSnapshotService(bucket_id="shared-bucket")
    facts = _populated_facts()

    operator_a = service.capture(
        profile_id="operator-a",
        captured_at=datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        census_facts=facts,
    )
    operator_b = service.capture(
        profile_id="operator-b",
        captured_at=datetime(2026, 5, 16, 10, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        census_facts=facts,
    )

    # Both stay ACTIVE; neither references the other.
    assert operator_a.state is CensusSnapshotState.ACTIVE
    assert operator_b.state is CensusSnapshotState.ACTIVE
    refreshed_a = service.resolve_snapshot(operator_a.snapshot_id)
    assert refreshed_a.state is CensusSnapshotState.ACTIVE
    assert refreshed_a.superseded_by_snapshot_id is None


def test_discard_marks_snapshot_discarded_with_audit(
    isolated_secure_store: None,
) -> None:
    """The discard verb transitions a snapshot to DISCARDED with the
    operator label and timestamp captured for the audit trail."""

    service = CensusSnapshotService(bucket_id="operator-bucket")
    captured = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        census_facts=_populated_facts(),
    )

    discarded = service.discard(
        snapshot_id=captured.snapshot_id,
        discarded_by="operator",
        discard_reason="malformed elected_withholding_pct from sede",
    )
    assert discarded.state is CensusSnapshotState.DISCARDED
    assert discarded.discarded_by == "operator"
    assert "malformed" in discarded.discard_reason
    assert discarded.discarded_at is not None

    # latest_active for the profile returns None because the discarded
    # snapshot is no longer ACTIVE.
    assert service.latest_active(profile_id="operator") is None


def test_namespace_constant_matches_documented_value() -> None:
    """Boundary regression: the namespace string is documented in the
    ADR amendment and must not silently drift."""

    assert CENSUS_SNAPSHOT_NAMESPACE == "aeat.application.live.census_snapshot"
