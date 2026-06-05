"""Real-behavior tests for the 036 censo snapshot service.

Anti-tautology: ``censo_facts`` is a ``Mapping[str, str]`` — the
narrowing to ``str``-only avoids the ``Decimal | str`` coercion trap
that silently turned enum literals like ``"15"`` into ``Decimal("15")``
on JSON round-trip. Roundtrip tests pin that numeric-looking strings
stay strings; SUPERSEDED / DISCARDED metadata triples are roundtripped
from fixture-built (not service-built) snapshots so the validator
invariants are proven to survive the secure-store boundary.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import pytest

from ....adapters.persistence.storage import LIVE_CENSO_SNAPSHOT_NAMESPACE
from ....core.config import Settings
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._censo import (
    CENSO_SNAPSHOT_NAMESPACE,
    CensoSnapshot,
    CensoSnapshotRepository,
    CensoSnapshotService,
    SnapshotLifecycleState,
    censo_snapshot_object_key,
    derive_censo_snapshot_id,
)
from .._errors import LiveApplicationInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SESSION_BUCKET_ID = "ephemeral"
_G313_URL = (
    f"{Settings.external_constants().aeat.domains.sede}"
    f"{Settings.external_constants().aeat.sede_paths.censo_g313_launcher}"
)


class _DeriveKwargs(TypedDict):
    profile_id: str
    captured_at: datetime
    source_url: str
    censo_facts: Mapping[str, str]


def _populated_facts() -> dict[str, str]:
    return {
        "censo.activity_start_date": "2024-01-15",
        "censo.establecimiento_type": "propio",
        "censo.elected_withholding_pct": "15",
        "contact.fiscal_address_cadastral_reference": "9872023VH5797S0001WX",
        "contact.fiscal_address_is_habitual_vivienda": "true",
        "vivienda_office.total_m2": "120.00",
        "vivienda_office.office_m2": "24.50",
    }


@pytest.fixture
def isolated_secure_store(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        yield profile


def test_derive_censo_snapshot_id_is_deterministic_over_canonical_inputs() -> None:
    """Two calls with identical inputs yield the same SHA-256 hex id;
    changing any of profile_id / captured_at / source_url / a fact
    value changes the id."""

    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    base_kwargs: _DeriveKwargs = {
        "profile_id": "operator",
        "captured_at": captured_at,
        "source_url": _G313_URL,
        "censo_facts": _populated_facts(),
    }
    base_id = derive_censo_snapshot_id(**base_kwargs)
    assert len(base_id) == 64
    assert int(base_id, 16) >= 0

    # Identical inputs => identical id.
    assert derive_censo_snapshot_id(**base_kwargs) == base_id

    # Different profile_id => different id.
    drift_kwargs: _DeriveKwargs = {**base_kwargs, "profile_id": "other-operator"}
    assert derive_censo_snapshot_id(**drift_kwargs) != base_id

    # Different fact value => different id.
    drift_facts = dict(_populated_facts())
    drift_facts["censo.elected_withholding_pct"] = "7"
    drift_fact_kwargs: _DeriveKwargs = {**base_kwargs, "censo_facts": drift_facts}
    assert derive_censo_snapshot_id(**drift_fact_kwargs) != base_id


def test_censo_snapshot_object_key_namespaces_by_bucket_and_snapshot() -> None:
    """The secure-object key embeds bucket and snapshot ids so the
    namespace cannot collide across buckets or snapshots."""

    key = censo_snapshot_object_key("bucket-1", "snap-abc")
    assert key == "censo-snapshot:bucket-1:snap-abc"
    with pytest.raises(LiveApplicationInputError, match=r"bucket_id"):
        censo_snapshot_object_key("   ", "snap-abc")
    with pytest.raises(LiveApplicationInputError, match=r"snapshot_id"):
        censo_snapshot_object_key("bucket-1", "   ")


def test_active_snapshot_cannot_carry_supersession_pointer() -> None:
    """The state-payload invariant refuses an ACTIVE snapshot that
    also names a successor; mirrors Borrador100 invariants verbatim."""

    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    snapshot_id = derive_censo_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        censo_facts={},
    )
    with pytest.raises(LiveApplicationInputError, match=r"active.*supersession"):
        CensoSnapshot(
            snapshot_id=snapshot_id,
            bucket_id="bucket-1",
            profile_id="operator",
            captured_at=captured_at,
            source_url="https://example/G313",
            state=SnapshotLifecycleState.ACTIVE,
            superseded_by_snapshot_id="another-snapshot-id",
        )


def test_superseded_snapshot_requires_successor_pointer() -> None:
    """A SUPERSEDED snapshot with no successor pointer is invalid."""

    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    snapshot_id = derive_censo_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        censo_facts={},
    )
    with pytest.raises(LiveApplicationInputError, match=r"superseded.*superseded_by"):
        CensoSnapshot(
            snapshot_id=snapshot_id,
            bucket_id="bucket-1",
            profile_id="operator",
            captured_at=captured_at,
            source_url="https://example/G313",
            state=SnapshotLifecycleState.SUPERSEDED,
        )


def test_censo_snapshot_survives_encrypted_storage_roundtrip(
    isolated_secure_store: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """The populated snapshot round-trips through the encrypted store
    preserving both Decimal and str fact values intact."""

    bucket_id = "operator-bucket"
    repo = CensoSnapshotRepository(bucket_id=bucket_id)
    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    facts = _populated_facts()
    snapshot_id = derive_censo_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url=_G313_URL,
        censo_facts=facts,
    )
    original = CensoSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        profile_id="operator",
        captured_at=captured_at,
        source_url=_G313_URL,
        state=SnapshotLifecycleState.ACTIVE,
        censo_facts=facts,
    )
    repo.save(original)
    loaded = repo.load(original.snapshot_id)

    assert (isolated_secure_store.storage_root / "buckets" / bucket_id / "db" / "aeat.db").is_file()
    # Compare via model_dump so datetime tzinfo identity (UTC singleton
    # vs pydantic-core TzInfo(0)) doesn't sabotage the round-trip
    # equality check; the values are semantically identical.
    assert loaded.model_dump(mode="json") == original.model_dump(mode="json")
    # Every fact value stays str (no numeric-looking string gets silently
    # coerced into Decimal by the union resolver).
    for key in (
        "censo.elected_withholding_pct",
        "vivienda_office.total_m2",
        "vivienda_office.office_m2",
        "censo.establecimiento_type",
    ):
        assert isinstance(loaded.censo_facts[key], str), key
    assert loaded.censo_facts["vivienda_office.total_m2"] == "120.00"
    assert loaded.censo_facts["censo.elected_withholding_pct"] == "15"


def test_capture_is_idempotent_for_structurally_identical_facts(
    isolated_secure_store: None,
) -> None:
    """Re-capturing the same facts at the same time is a no-op:
    snapshot_id is deterministic so the service returns the existing
    snapshot rather than persisting a duplicate."""

    service = CensoSnapshotService(bucket_id="operator-bucket")
    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    facts = _populated_facts()

    first = service.capture(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        censo_facts=facts,
    )
    second = service.capture(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        censo_facts=facts,
    )
    assert first.snapshot_id == second.snapshot_id
    assert first.state is SnapshotLifecycleState.ACTIVE
    # Both calls produce a single ACTIVE snapshot in the repo.
    snapshots = service.list_snapshots(state=SnapshotLifecycleState.ACTIVE)
    assert len(snapshots) == 1


def test_capture_auto_supersedes_prior_active_for_same_profile(
    isolated_secure_store: None,
) -> None:
    """A fresh capture for the same profile transitions the prior
    ACTIVE snapshot into SUPERSEDED with a successor pointer."""

    service = CensoSnapshotService(bucket_id="operator-bucket")
    facts_v1 = _populated_facts()
    facts_v2 = dict(facts_v1)
    facts_v2["censo.elected_withholding_pct"] = "7"

    snapshot_v1 = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        censo_facts=facts_v1,
    )
    snapshot_v2 = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 17, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        censo_facts=facts_v2,
    )

    # v1 was superseded; v2 is the new ACTIVE.
    prior = service.resolve_snapshot(snapshot_v1.snapshot_id)
    assert prior.state is SnapshotLifecycleState.SUPERSEDED
    assert prior.superseded_by_snapshot_id == snapshot_v2.snapshot_id
    assert snapshot_v2.state is SnapshotLifecycleState.ACTIVE

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

    service = CensoSnapshotService(bucket_id="operator-bucket")
    facts_newer = _populated_facts()
    facts_older = dict(facts_newer)
    facts_older["censo.elected_withholding_pct"] = "1"

    newer = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 17, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        censo_facts=facts_newer,
    )
    older = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 15, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        censo_facts=facts_older,
    )

    assert older.state is SnapshotLifecycleState.SUPERSEDED
    assert older.superseded_by_snapshot_id == newer.snapshot_id
    latest_active = service.latest_active(profile_id="operator")
    assert latest_active is not None
    assert latest_active.snapshot_id == newer.snapshot_id


def test_supersession_scopes_to_profile_id(isolated_secure_store: None) -> None:
    """Captures for different profile_ids in the same bucket do NOT
    supersede each other (multi-profile bucket isolation)."""

    service = CensoSnapshotService(bucket_id="shared-bucket")
    facts = _populated_facts()

    operator_a = service.capture(
        profile_id="operator-a",
        captured_at=datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        censo_facts=facts,
    )
    operator_b = service.capture(
        profile_id="operator-b",
        captured_at=datetime(2026, 5, 16, 10, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        censo_facts=facts,
    )

    # Both stay ACTIVE; neither references the other.
    assert operator_a.state is SnapshotLifecycleState.ACTIVE
    assert operator_b.state is SnapshotLifecycleState.ACTIVE
    refreshed_a = service.resolve_snapshot(operator_a.snapshot_id)
    assert refreshed_a.state is SnapshotLifecycleState.ACTIVE
    assert refreshed_a.superseded_by_snapshot_id is None


def test_discard_marks_snapshot_discarded_with_audit(
    isolated_secure_store: None,
) -> None:
    """The discard verb transitions a snapshot to DISCARDED with the
    operator label and timestamp captured for the audit trail."""

    service = CensoSnapshotService(bucket_id="operator-bucket")
    captured = service.capture(
        profile_id="operator",
        captured_at=datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC),
        source_url="https://example/G313",
        censo_facts=_populated_facts(),
    )

    discarded = service.discard(
        snapshot_id=captured.snapshot_id,
        discarded_by="operator",
        discard_reason="malformed elected_withholding_pct from sede",
    )
    assert discarded.state is SnapshotLifecycleState.DISCARDED
    assert discarded.discarded_by == "operator"
    assert "malformed" in discarded.discard_reason
    assert discarded.discarded_at is not None

    # latest_active for the profile returns None because the discarded
    # snapshot is no longer ACTIVE.
    assert service.latest_active(profile_id="operator") is None


def test_namespace_constant_uses_storage_registry() -> None:
    """Boundary regression: snapshot persistence must use the registry entry."""

    assert LIVE_CENSO_SNAPSHOT_NAMESPACE.namespace == CENSO_SNAPSHOT_NAMESPACE


def test_fixture_built_superseded_snapshot_roundtrips_with_successor_pointer(
    isolated_secure_store: None,
) -> None:
    """A SUPERSEDED snapshot built directly (not via the service) must
    round-trip preserving ``superseded_by_snapshot_id``. The service-
    path tests above never exercise the field on a load — they read it
    after a save the service itself performs in the same memory image."""

    bucket_id = "operator-bucket"
    repo = CensoSnapshotRepository(bucket_id=bucket_id)
    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    facts = _populated_facts()
    snapshot_id = derive_censo_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        censo_facts=facts,
    )
    successor_id = "f" * 64
    original = CensoSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        state=SnapshotLifecycleState.SUPERSEDED,
        censo_facts=facts,
        superseded_by_snapshot_id=successor_id,
    )
    repo.save(original)
    loaded = repo.load(original.snapshot_id)

    assert loaded.state is SnapshotLifecycleState.SUPERSEDED
    assert loaded.superseded_by_snapshot_id == successor_id


def test_fixture_built_discarded_snapshot_roundtrips_with_full_audit_triple(
    isolated_secure_store: None,
) -> None:
    """A DISCARDED snapshot built directly must round-trip all three
    discard-audit fields (``discarded_at``, ``discarded_by``,
    ``discard_reason``). A save that drops any of them would leave them
    at their default — the model_validator would raise on load."""

    bucket_id = "operator-bucket"
    repo = CensoSnapshotRepository(bucket_id=bucket_id)
    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    discarded_at = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
    facts = _populated_facts()
    snapshot_id = derive_censo_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        censo_facts=facts,
    )
    original = CensoSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        state=SnapshotLifecycleState.DISCARDED,
        censo_facts=facts,
        discarded_at=discarded_at,
        discarded_by="operator",
        discard_reason="malformed elected_withholding_pct from sede",
    )
    repo.save(original)
    loaded = repo.load(original.snapshot_id)

    assert loaded.state is SnapshotLifecycleState.DISCARDED
    assert loaded.discarded_at == discarded_at
    assert loaded.discarded_by == "operator"
    assert "malformed" in loaded.discard_reason


def test_anti_tautology_mutating_on_disk_payload_is_detected_on_load(
    isolated_secure_store: None,
) -> None:
    """Anti-tautology proof: if a snapshot's ``superseded_by_snapshot_id``
    is corrupted on disk (set to None while ``state`` remains
    SUPERSEDED), the load path MUST refuse via the model_validator
    instead of silently re-defaulting. If this test ever passes with
    the on-disk mutation in place, every other roundtrip in this
    module is tautological."""

    from pydantic import ValidationError

    from ....adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
    )

    bucket_id = "operator-bucket"
    repo = CensoSnapshotRepository(bucket_id=bucket_id)
    captured_at = datetime(2026, 5, 16, 9, 30, 0, tzinfo=UTC)
    facts = _populated_facts()
    snapshot_id = derive_censo_snapshot_id(
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        censo_facts=facts,
    )
    successor_id = "f" * 64
    original = CensoSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        profile_id="operator",
        captured_at=captured_at,
        source_url="https://example/G313",
        state=SnapshotLifecycleState.SUPERSEDED,
        censo_facts=facts,
        superseded_by_snapshot_id=successor_id,
    )
    repo.save(original)

    # Round-trip through the same Envelope shape that the repository
    # uses, then drop ``superseded_by_snapshot_id`` — re-validating
    # must raise because the SUPERSEDED state requires a successor.
    envelope = Envelope[CensoSnapshot](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.IDENTITY,
        payload=original,
    )
    raw = envelope.model_dump(mode="json")
    raw["payload"]["superseded_by_snapshot_id"] = None

    with pytest.raises(ValidationError, match="superseded"):
        Envelope[CensoSnapshot].model_validate(raw)
