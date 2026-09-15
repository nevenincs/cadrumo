"""Application-owned Modelo 100 borrador snapshot contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistrySnapshotError
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ..borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotService,
    BorradorSnapshotNotFoundError,
    derive_borrador_100_snapshot_id,
)
from ..snapshot_base import SnapshotLifecycleState

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "0acc74be-7842-4530-95f8-8ffca3a6b654"  # was 'bucket-renta'
_SOURCE = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))
_CAPTURED_AT = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "0A")
_REGISTRY_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="100",
    revision_id="2025",
    modelo_year=2025,
    period="0A",
)


class _InMemoryBorradorRepository:
    """Inward fake for lifecycle tests that do not exercise secure storage."""

    def __init__(self, *, bucket_id: str) -> None:
        self.bucket_id = bucket_id
        self._snapshots: dict[str, Borrador100Snapshot] = {}

    def exists(self, snapshot_id: str) -> bool:
        return snapshot_id in self._snapshots

    def load(self, snapshot_id: str) -> Borrador100Snapshot:
        try:
            return self._snapshots[snapshot_id]
        except KeyError as exc:
            raise BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            ) from exc

    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        return tuple(
            sorted(
                self._snapshots.values(),
                key=lambda snapshot: (snapshot.captured_at, snapshot.snapshot_id),
            )
        )

    def resolve(self, snapshot_id: str) -> Borrador100Snapshot:
        trimmed = snapshot_id.strip()
        matches = tuple(
            snapshot
            for snapshot in self.list_snapshots()
            if snapshot.snapshot_id == trimmed or snapshot.snapshot_id.startswith(trimmed)
        )
        if not matches:
            raise BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            )
        if len(matches) > 1:
            raise BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(matches)},
            )
        return matches[0]

    def save(self, snapshot: Borrador100Snapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot


@pytest.mark.parametrize("snapshot_id", ("bad-id", "A" * 64, "a" * 63))
def test_borrador_snapshot_refuses_noncanonical_snapshot_identity(snapshot_id: str) -> None:
    with pytest.raises(ValidationError):
        Borrador100Snapshot(
            snapshot_id=snapshot_id,
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


def test_borrador_snapshot_requires_canonical_registry_coordinate() -> None:
    with pytest.raises(ValidationError, match="registry_snapshot_ref"):
        Borrador100Snapshot.model_validate(
            {
                "snapshot_id": "a" * 64,
                "bucket_id": _BUCKET_ID,
                "modelo": "100",
                "filing_year": 2025,
                "period": _PERIOD,
                "captured_at": _CAPTURED_AT,
                "source_url": _SOURCE,
                "state": SnapshotLifecycleState.ACTIVE,
                "binding_values": {},
            }
        )


def test_borrador_100_snapshot_service_captures_content_addressed_snapshot() -> None:
    repository = _InMemoryBorradorRepository(bucket_id=_BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=repository)
    values = {"renta-modelo-111-retenciones-periodicas": Decimal("15.25")}

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
        registry_snapshot_ref=snapshot.registry_snapshot_ref,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        binding_values=values,
    )
    assert repository.load(snapshot.snapshot_id) == snapshot


def test_borrador_show_refuses_persisted_registry_revision_divergence() -> None:
    """The operator-facing show boundary never exposes stale binding values."""
    repository = _InMemoryBorradorRepository(bucket_id=_BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=repository)
    snapshot = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        binding_values={"renta-modelo-111-retenciones-periodicas": Decimal("15.25")},
    )
    repository.save(
        snapshot.model_copy(
            update={
                "registry_snapshot_ref": snapshot.registry_snapshot_ref.model_copy(
                    update={"revision_id": "persisted-stale-revision"}
                )
            }
        )
    )

    with bundled_indexed_authority().operation() as operation:
        with pytest.raises(RegistrySnapshotError, match="cannot be re-confirmed"):
            service.show(snapshot.snapshot_id, operation=operation)


def test_borrador_100_snapshot_service_rejects_non_binding_id_keys() -> None:
    service = Borrador100SnapshotService(
        bucket_id=_BUCKET_ID,
        repository=_InMemoryBorradorRepository(bucket_id=_BUCKET_ID),
    )

    with pytest.raises(ValidationError, match="binding_values"):
        service.capture(
            filing_year=2025,
            period=_PERIOD,
            captured_at=_CAPTURED_AT,
            source_url=_SOURCE,
            binding_values={"Casilla 0500": Decimal("15.25")},
        )


def test_borrador_100_snapshot_service_deduplicates_identical_captures() -> None:
    service = Borrador100SnapshotService(
        bucket_id=_BUCKET_ID,
        repository=_InMemoryBorradorRepository(bucket_id=_BUCKET_ID),
    )
    kwargs = {
        "filing_year": 2025,
        "period": _PERIOD,
        "captured_at": _CAPTURED_AT,
        "source_url": _SOURCE,
        "binding_values": {"renta-modelo-111-retenciones-periodicas": Decimal("15.25")},
    }

    first = service.capture(**kwargs)
    second = service.capture(**kwargs)

    assert first == second
    assert service.list_snapshots() == (first,)


def test_borrador_100_snapshot_service_supersedes_prior_current_snapshot() -> None:
    repository = _InMemoryBorradorRepository(bucket_id=_BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=repository)
    older = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-modelo-111-retenciones-periodicas": Decimal("15.25")},
    )
    newer = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-modelo-111-retenciones-periodicas": Decimal("16.25")},
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


def test_borrador_100_snapshot_service_preserves_newer_current_for_out_of_order_capture() -> None:
    repository = _InMemoryBorradorRepository(bucket_id=_BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=repository)
    newer = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-modelo-111-retenciones-periodicas": Decimal("16.25")},
    )
    older = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-modelo-111-retenciones-periodicas": Decimal("15.25")},
    )

    assert repository.load(newer.snapshot_id).state is SnapshotLifecycleState.ACTIVE
    assert repository.load(older.snapshot_id).state is SnapshotLifecycleState.SUPERSEDED
    assert repository.load(older.snapshot_id).superseded_by_snapshot_id == newer.snapshot_id
    assert service.list_snapshots() == (newer,)
