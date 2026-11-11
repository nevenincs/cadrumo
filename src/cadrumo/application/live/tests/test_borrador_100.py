"""Application-owned Modelo 100 borrador snapshot contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistrySnapshotError
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ..borrador_100 import (
    Borrador100RefusedSnapshot,
    Borrador100Snapshot,
    Borrador100SnapshotReading,
    Borrador100SnapshotRefusalReason,
    Borrador100SnapshotService,
    BorradorSnapshotNotFoundError,
    derive_borrador_100_snapshot_id,
)
from ..errors import LiveApplicationInputError
from ..snapshot_base import SnapshotLifecycleState

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

BUCKET_ID = "0acc74be-7842-4530-95f8-8ffca3a6b654"  # was 'bucket-renta'
_SOURCE = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))
_CAPTURED_AT = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "0A")
_REGISTRY_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="100",
    revision_id="2025",
    modelo_year=2025,
    period="0A",
)


class InMemoryBorradorRepository:
    """Inward fake for lifecycle tests that do not exercise secure storage."""

    def __init__(self, *, bucket_id: str) -> None:
        self.bucket_id = bucket_id
        self._snapshots: dict[str, Borrador100Snapshot] = {}
        self.outdated = 0
        self.store_reads = 0

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

    def list_snapshots_with_outdated_count(self) -> tuple[tuple[Borrador100Snapshot, ...], int]:
        self.store_reads += 1
        return self.list_snapshots(), self.outdated

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
            bucket_id=BUCKET_ID,
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
                "bucket_id": BUCKET_ID,
                "modelo": "100",
                "filing_year": 2025,
                "period": _PERIOD,
                "captured_at": _CAPTURED_AT,
                "source_url": _SOURCE,
                "state": SnapshotLifecycleState.ACTIVE,
                "binding_values": {},
            }
        )


@pytest.mark.parametrize(
    ("binding_values", "message"),
    [
        (["renta-retencion-soportada-trabajo"], "borrador binding values must be a mapping"),
        ({"renta-retencion-soportada-trabajo": 15}, "borrador binding value must be a tagged decimal or text"),
        (
            {"renta-retencion-soportada-trabajo": {"kind": "decimal", "value": "1", "extra": "x"}},
            "borrador binding value must be a tagged decimal or text",
        ),
        (
            {"renta-retencion-soportada-trabajo": {"kind": "decimal", "value": 1}},
            "borrador binding value must be a tagged decimal or text",
        ),
        (
            {"renta-retencion-soportada-trabajo": {"kind": "number", "value": "1"}},
            "borrador binding value kind must be decimal or text",
        ),
    ],
)
def test_borrador_snapshot_refuses_stored_binding_values_of_the_wrong_type(
    binding_values: object, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Borrador100Snapshot.model_validate(
            {
                "snapshot_id": "a" * 64,
                "bucket_id": BUCKET_ID,
                "modelo": "100",
                "filing_year": 2025,
                "period": _PERIOD,
                "registry_snapshot_ref": _REGISTRY_SNAPSHOT_REF,
                "captured_at": _CAPTURED_AT,
                "source_url": _SOURCE,
                "state": SnapshotLifecycleState.ACTIVE,
                "binding_values": binding_values,
            }
        )


def test_borrador_100_snapshot_service_captures_content_addressed_snapshot() -> None:
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)
    values = {"renta-retencion-soportada-trabajo": Decimal("15.25")}

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
        source_url=_SOURCE,
        binding_values=values,
    )
    assert repository.load(snapshot.snapshot_id) == snapshot


def test_borrador_100_snapshot_identity_ignores_the_capture_instant_and_follows_the_values() -> None:
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)

    def capture(*, hours: int, amount: str) -> Borrador100Snapshot:
        return service.capture(
            filing_year=2025,
            period=_PERIOD,
            captured_at=_CAPTURED_AT + timedelta(hours=hours),
            source_url=_SOURCE,
            binding_values={"renta-retencion-soportada-trabajo": Decimal(amount)},
        )

    first = capture(hours=0, amount="15.25")
    again = capture(hours=30, amount="15.25")
    changed = capture(hours=31, amount="15.26")

    assert again.snapshot_id == first.snapshot_id
    assert again.captured_at == first.captured_at == _CAPTURED_AT
    assert changed.snapshot_id != first.snapshot_id
    assert repository.load(first.snapshot_id).superseded_by_snapshot_id == changed.snapshot_id


@pytest.mark.parametrize(
    "stored_key",
    [
        pytest.param("casilla.0596", id="free-casilla-key"),
        pytest.param("renta-retencion-trabajo-retirada", id="binding-the-revision-does-not-declare"),
        pytest.param("renta-profile-minimo-descendientes-estatal", id="binding-not-admitted-to-the-borrador"),
    ],
)
def test_borrador_reads_refuse_a_stored_key_the_pinned_revision_does_not_admit(stored_key: str) -> None:
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)
    values = {stored_key: Decimal("15.25")}
    with bundled_indexed_authority().operation() as pinned:
        ref = pinned.snapshot("100", filing_year=2025, period="0A").snapshot_ref
    stored = Borrador100Snapshot(
        snapshot_id=derive_borrador_100_snapshot_id(
            filing_year=2025,
            period=_PERIOD,
            registry_snapshot_ref=ref,
            source_url=_SOURCE,
            binding_values=values,
        ),
        bucket_id=BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=_PERIOD,
        registry_snapshot_ref=ref,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=values,
    )
    repository.save(stored)

    with bundled_indexed_authority().operation() as operation:
        for read in (
            lambda: service.show(stored.snapshot_id, operation=operation),
            lambda: service.list_snapshots(operation=operation),
        ):
            with pytest.raises(LiveApplicationInputError) as refused:
                read()
            assert refused.value.translated_message == "application.live.borrador.errors.binding_keys_not_admitted"
            assert refused.value.context == {"bindings": stored_key}
        expected = Borrador100SnapshotReading(
            readable=(),
            refused=(
                Borrador100RefusedSnapshot(
                    snapshot=stored, reason=Borrador100SnapshotRefusalReason.BINDING_KEYS_NOT_ADMITTED
                ),
            ),
        )
        assert service.read_snapshots(operation=operation) == expected
        assert service.read_latest_for_year(filing_year=2025, operation=operation) == expected
    assert repository.load(stored.snapshot_id).binding_values == values


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("casilla.0596", id="free-casilla-key"),
        pytest.param("renta-retencion-trabajo-retirada", id="binding-the-revision-does-not-declare"),
        pytest.param("renta-profile-minimo-descendientes-estatal", id="binding-not-admitted-to-the-borrador"),
    ],
)
def test_borrador_capture_refuses_a_key_the_pinned_revision_does_not_admit_before_any_write(key: str) -> None:
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)

    with pytest.raises(LiveApplicationInputError) as refused:
        service.capture(
            filing_year=2025,
            period=_PERIOD,
            captured_at=_CAPTURED_AT,
            source_url=_SOURCE,
            binding_values={"renta-retencion-soportada-trabajo": Decimal("1.00"), key: Decimal("15.25")},
        )

    assert refused.value.translated_message == "application.live.borrador.errors.binding_keys_not_admitted"
    assert refused.value.context == {"bindings": key}
    assert repository.list_snapshots() == ()


def test_borrador_show_refuses_persisted_registry_revision_divergence() -> None:
    """The operator-facing show boundary never exposes stale binding values."""
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)
    snapshot = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE,
        binding_values={"renta-retencion-soportada-trabajo": Decimal("15.25")},
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

    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(RegistrySnapshotError, match="cannot be re-confirmed"),
    ):
        service.show(snapshot.snapshot_id, operation=operation)


def test_borrador_100_snapshot_service_rejects_non_binding_id_keys() -> None:
    service = Borrador100SnapshotService(
        bucket_id=BUCKET_ID,
        repository=InMemoryBorradorRepository(bucket_id=BUCKET_ID),
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
        bucket_id=BUCKET_ID,
        repository=InMemoryBorradorRepository(bucket_id=BUCKET_ID),
    )

    def capture() -> Borrador100Snapshot:
        return service.capture(
            filing_year=2025,
            period=_PERIOD,
            captured_at=_CAPTURED_AT,
            source_url=_SOURCE,
            binding_values={"renta-retencion-soportada-trabajo": Decimal("15.25")},
        )

    first = capture()
    second = capture()

    assert first == second
    assert service.list_snapshots() == (first,)


def test_borrador_100_snapshot_service_supersedes_prior_current_snapshot() -> None:
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)
    older = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-retencion-soportada-trabajo": Decimal("15.25")},
    )
    newer = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-retencion-soportada-trabajo": Decimal("16.25")},
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
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)
    newer = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-retencion-soportada-trabajo": Decimal("16.25")},
    )
    older = service.capture(
        filing_year=2025,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_SOURCE,
        binding_values={"renta-retencion-soportada-trabajo": Decimal("15.25")},
    )

    assert repository.load(newer.snapshot_id).state is SnapshotLifecycleState.ACTIVE
    assert repository.load(older.snapshot_id).state is SnapshotLifecycleState.SUPERSEDED
    assert repository.load(older.snapshot_id).superseded_by_snapshot_id == newer.snapshot_id
    assert service.list_snapshots() == (newer,)


def test_borrador_reading_reads_the_store_once_and_reports_the_older_rows_store_wide() -> None:
    repository = InMemoryBorradorRepository(bucket_id=BUCKET_ID)
    repository.outdated = 3
    service = Borrador100SnapshotService(bucket_id=BUCKET_ID, repository=repository)

    with bundled_indexed_authority().operation() as operation:
        year = service.read_snapshots(operation=operation, filing_year=2025)
        assert repository.store_reads == 1
        latest = service.read_latest_for_year(filing_year=1999, operation=operation)

    assert repository.store_reads == 2
    assert year.outdated_stored_snapshots == 3
    assert latest.readable == () and latest.outdated_stored_snapshots == 3
