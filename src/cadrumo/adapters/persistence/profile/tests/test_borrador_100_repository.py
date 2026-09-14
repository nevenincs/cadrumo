"""Persistence-adapter coverage for the Modelo 100 borrador snapshot port."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.snapshots import SecureSnapshotRepository
from cadrumo.adapters.persistence.storage.envelope.contract import Envelope
from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.live.borrador_100 import (
    Borrador100Snapshot,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
)
from cadrumo.application.live.errors import LiveApplicationInputError
from cadrumo.application.live.snapshot_base import SnapshotLifecycleState
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.tests.aeat_literal_fixtures import aeat_url, configured_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "0acc74be-7842-4530-95f8-8ffca3a6b654"
_SOURCE = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))
_CAPTURED_AT = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)
_WRITTEN_AT = datetime(2026, 4, 3, 10, 5, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "0A")
_REGISTRY_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="100",
    revision_id="2025",
    modelo_year=2025,
    period="0A",
)


@pytest.fixture
def borrador_runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Bind this adapter suite to one isolated encrypted profile store."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


def _repository(
    objects: SecureObjectRepository,
    *,
    bucket_id: str = _BUCKET_ID,
) -> SecureSnapshotRepository[Borrador100Snapshot]:
    """Build the concrete secure adapter for the application borrador port."""
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=Borrador100Snapshot,
        namespace_definition=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        object_key=borrador_100_snapshot_object_key,
        not_found_factory=lambda snapshot_id: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="borrador",
        input_error_cls=LiveApplicationInputError,
        objects=objects,
    )


def test_borrador_100_snapshot_repository_round_trips_active_snapshot(
    borrador_runtime: TestRuntimeProfile,
) -> None:
    repository = _repository(borrador_runtime.repository)
    snapshot = Borrador100Snapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={"renta-modelo-111-retenciones-periodicas": Decimal("15.25")},
    )

    repository.save(snapshot)

    assert repository.load(snapshot.snapshot_id) == snapshot


def test_borrador_100_snapshot_repository_rejects_payload_id_mismatch(
    borrador_runtime: TestRuntimeProfile,
) -> None:
    repository = _repository(borrador_runtime.repository)
    payload = Borrador100Snapshot(
        snapshot_id="b" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={},
    )
    envelope = Envelope[Borrador100Snapshot](
        schema_version=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.schema_version,
        written_at=_WRITTEN_AT,
        classification=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.sensitivity,
        payload=payload,
    )
    borrador_runtime.repository.save(
        namespace=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.namespace,
        object_key=borrador_100_snapshot_object_key(_BUCKET_ID, "requested-id"),
        classification=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.sensitivity,
        schema_version=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(LiveApplicationInputError, match="does not match requested snapshot"):
        repository.load("requested-id")


def test_borrador_100_snapshot_repository_lists_bucket_scoped_records(
    borrador_runtime: TestRuntimeProfile,
) -> None:
    first = _repository(borrador_runtime.repository)
    first_snapshot = Borrador100Snapshot(
        snapshot_id="c" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={},
    )
    first.save(first_snapshot)

    assert first.list_snapshots() == (first_snapshot,)

    # A bucket-scoped repository over its own store returns its own rows.
    second = _repository(borrador_runtime.repository, bucket_id="other-bucket")
    second_snapshot = first_snapshot.model_copy(update={"snapshot_id": "d" * 64, "bucket_id": "other-bucket"})
    second.save(second_snapshot)
    with pytest.raises(LiveApplicationInputError, match="does not match repository bucket"):
        first.list_snapshots()


def test_borrador_100_snapshot_repository_resolves_unambiguous_prefix(
    borrador_runtime: TestRuntimeProfile,
) -> None:
    repository = _repository(borrador_runtime.repository)
    snapshot = Borrador100Snapshot(
        snapshot_id="abcdef" + "1" * 58,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={},
    )
    repository.save(snapshot)

    assert repository.resolve("abcdef") == snapshot
