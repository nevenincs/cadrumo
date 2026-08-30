"""Live borrador 100 snapshot persistence contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import (
    LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE as BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE,
)
from ....adapters.persistence.storage import (
    Envelope,
    SensitivityClass,
)
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.period import Period
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ..borrador_100 import (
    BORRADOR_100_SNAPSHOT_NAMESPACE,
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    Borrador100SnapshotService,
    borrador_100_snapshot_object_key,
    derive_borrador_100_snapshot_id,
)
from ..errors import LiveApplicationInputError
from ..snapshot_base import SnapshotLifecycleState

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "0acc74be-7842-4530-95f8-8ffca3a6b654"  # was 'bucket-renta'
_SOURCE = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))
_CAPTURED_AT = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)
_WRITTEN_AT = datetime(2026, 4, 3, 10, 5, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "0A")


def test_borrador_100_snapshot_repository_round_trips_active_snapshot(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = Borrador100Snapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={"renta-2025-modelo-111-retenciones-periodicas": Decimal("15.25")},
    )

    repository.save(snapshot)

    assert repository.load(snapshot.snapshot_id) == snapshot


@pytest.mark.parametrize("snapshot_id", ("bad-id", "A" * 64, "a" * 63))
def test_borrador_snapshot_refuses_noncanonical_snapshot_identity(snapshot_id: str) -> None:
    with pytest.raises(ValidationError):
        Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=_PERIOD,
            captured_at=_CAPTURED_AT,
            source_url=_SOURCE,
            state=SnapshotLifecycleState.ACTIVE,
            binding_values={},
        )


def test_borrador_100_snapshot_repository_rejects_payload_id_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    payload = Borrador100Snapshot(
        snapshot_id="b" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={},
    )
    envelope = Envelope[Borrador100Snapshot](
        schema_version=BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=_WRITTEN_AT,
        classification=SensitivityClass.FINANCIAL,
        payload=payload,
    )
    secure_objects.save(
        namespace=BORRADOR_100_SNAPSHOT_NAMESPACE,
        object_key=borrador_100_snapshot_object_key(_BUCKET_ID, "requested-id"),
        classification=SensitivityClass.FINANCIAL,
        schema_version=BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(LiveApplicationInputError, match="does not match requested snapshot"):
        repository.load("requested-id")


def test_borrador_100_snapshot_repository_lists_bucket_scoped_records(
    secure_objects: SecureObjectRepository,
) -> None:
    first = Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    first_snapshot = Borrador100Snapshot(
        snapshot_id="c" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={},
    )
    first.save(first_snapshot)

    # A bucket-scoped repository over its own store returns its own rows.
    assert first.list_snapshots() == (first_snapshot,)

    # In production each bucket owns its encrypted DB. A store polluted with
    # another bucket's row is corruption: the shared SecureSnapshotRepository
    # contract refuses it loudly (rather than silently filtering), and the
    # bucket-scoped facade inherits that guarantee.
    second = Borrador100SnapshotRepository(bucket_id="other-bucket", objects=secure_objects)
    second_snapshot = first_snapshot.model_copy(update={"snapshot_id": "d" * 64, "bucket_id": "other-bucket"})
    second.save(second_snapshot)
    with pytest.raises(LiveApplicationInputError, match="does not match repository bucket"):
        first.list_snapshots()


def test_borrador_100_snapshot_repository_resolves_unambiguous_prefix(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = Borrador100Snapshot(
        snapshot_id="abcdef" + "1" * 58,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={},
    )
    repository.save(snapshot)

    assert repository.resolve("abcdef") == snapshot


def test_borrador_100_snapshot_service_captures_content_addressed_snapshot(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=repository)
    values = {"renta-2025-modelo-111-retenciones-periodicas": Decimal("15.25")}

    snapshot = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        binding_values=values,
    )

    assert snapshot.snapshot_id == derive_borrador_100_snapshot_id(
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        binding_values=values,
    )
    assert repository.load(snapshot.snapshot_id) == snapshot


def test_borrador_100_snapshot_service_rejects_non_binding_id_keys(
    secure_objects: SecureObjectRepository,
) -> None:
    service = Borrador100SnapshotService(
        bucket_id=_BUCKET_ID,
        repository=Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
    )

    with pytest.raises(ValidationError, match="binding_values"):
        service.capture(
            filing_year=2025,
            period=_PERIOD,
            captured_at=_CAPTURED_AT,
            source_url=_SOURCE,
            binding_values={"Casilla 0500": Decimal("15.25")},
        )


def test_borrador_100_snapshot_service_deduplicates_identical_captures(
    secure_objects: SecureObjectRepository,
) -> None:
    service = Borrador100SnapshotService(
        bucket_id=_BUCKET_ID,
        repository=Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
    )
    kwargs = {
        "filing_year": 2025,
        "period": _PERIOD,
        "captured_at": _CAPTURED_AT,
        "source_url": _SOURCE,
        "binding_values": {"renta-2025-modelo-111-retenciones-periodicas": Decimal("15.25")},
    }

    first = service.capture(**kwargs)
    second = service.capture(**kwargs)

    assert first == second
    assert service.list_snapshots() == (first,)


def test_borrador_100_snapshot_service_supersedes_prior_current_snapshot(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=repository)
    older = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-2025-modelo-111-retenciones-periodicas": Decimal("15.25")},
    )
    newer = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-2025-modelo-111-retenciones-periodicas": Decimal("16.25")},
    )

    assert repository.load(older.snapshot_id).state is SnapshotLifecycleState.SUPERSEDED
    assert repository.load(older.snapshot_id).superseded_by_snapshot_id == newer.snapshot_id
    assert service.list_snapshots() == (newer,)
    assert service.list_snapshots(state=None) == (
        older.model_copy(
            update={"state": SnapshotLifecycleState.SUPERSEDED, "superseded_by_snapshot_id": newer.snapshot_id},
        ),
        newer,
    )


def test_borrador_100_snapshot_service_preserves_newer_current_for_out_of_order_capture(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=repository)
    newer = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-2025-modelo-111-retenciones-periodicas": Decimal("16.25")},
    )
    older = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-2025-modelo-111-retenciones-periodicas": Decimal("15.25")},
    )

    assert repository.load(newer.snapshot_id).state is SnapshotLifecycleState.ACTIVE
    assert repository.load(older.snapshot_id).state is SnapshotLifecycleState.SUPERSEDED
    assert repository.load(older.snapshot_id).superseded_by_snapshot_id == newer.snapshot_id
    assert service.list_snapshots() == (newer,)
