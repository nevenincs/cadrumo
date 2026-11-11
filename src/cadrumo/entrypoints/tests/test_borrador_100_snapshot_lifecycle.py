"""The Modelo 100 borrador snapshot service over the composed encrypted repository.

A stored snapshot the pinned authority refuses is reported with its reason
beside the readable ones, a capture with an inadmissible key writes nothing,
and importing a document again says which stored snapshot it resolved to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.live.borrador_100 import (
    Borrador100CaptureOutcome,
    Borrador100Snapshot,
    Borrador100SnapshotRefusalReason,
    Borrador100SnapshotService,
    derive_borrador_100_snapshot_id,
)
from ...application.live.errors import LiveApplicationInputError
from ...application.live.snapshot_base import SnapshotLifecycleState
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.calculations.registry.temporal import select_authored_revision_metadata
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ..adapter_composition_ports import build_borrador_100_snapshot_repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_FILING_YEAR = newest_authored_edition("100")
_LEGACY_YEAR = filing_year_envelope().floor

_CERTIFICATE = "renta-retencion-soportada-trabajo"
_CAPTURED_AT = datetime(_YEAR, 4, 3, 10, 0, tzinfo=UTC)


def _source(index: int) -> str:
    return f"file-import:sha256:{index:064x}"


def _store_legacy_snapshot(
    operation: PinnedAuthorityOperation,
    bucket_id: str,
    *,
    filing_year: int,
    key: str,
    captured_at: datetime = _CAPTURED_AT,
    revision_id: str | None = None,
) -> Borrador100Snapshot:
    """Store an active snapshot the way an earlier key contract wrote it, bypassing the capture check."""
    period = Period.from_year_and_code(filing_year, "0A")
    ref = operation.snapshot("100", filing_year=filing_year, period="0A").snapshot_ref
    if revision_id is not None:
        ref = ref.model_copy(update={"revision_id": revision_id})
    values = {key: Decimal("15.25")}
    source = _source(filing_year)
    snapshot = Borrador100Snapshot(
        snapshot_id=derive_borrador_100_snapshot_id(
            filing_year=filing_year,
            period=period,
            registry_snapshot_ref=ref,
            source_url=source,
            binding_values=values,
        ),
        bucket_id=bucket_id,
        modelo="100",
        filing_year=filing_year,
        period=period,
        registry_snapshot_ref=ref,
        captured_at=captured_at,
        source_url=source,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=values,
    )
    build_borrador_100_snapshot_repository(bucket_id=bucket_id).save(snapshot)
    return snapshot


def _store_snapshot_below_support_floor(operation: PinnedAuthorityOperation, bucket_id: str) -> Borrador100Snapshot:
    """Store an active snapshot whose year the registry authors but its support envelope refuses."""
    filing_year = operation.supported_filing_years().floor - 1
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = select_authored_revision_metadata(
        operation.modelo_directory("100"), filing_year=filing_year, period="0A"
    ).id
    ref = RegistrySnapshotRef(modelo="100", revision_id=revision_id, modelo_year=filing_year, period="0A")
    values = {_CERTIFICATE: Decimal("15.25")}
    source = _source(filing_year)
    snapshot = Borrador100Snapshot(
        snapshot_id=derive_borrador_100_snapshot_id(
            filing_year=filing_year,
            period=period,
            registry_snapshot_ref=ref,
            source_url=source,
            binding_values=values,
        ),
        bucket_id=bucket_id,
        modelo="100",
        filing_year=filing_year,
        period=period,
        registry_snapshot_ref=ref,
        captured_at=_CAPTURED_AT,
        source_url=source,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=values,
    )
    build_borrador_100_snapshot_repository(bucket_id=bucket_id).save(snapshot)
    return snapshot


def _service(bucket_id: str) -> Borrador100SnapshotService:
    return Borrador100SnapshotService(
        bucket_id=bucket_id, repository=build_borrador_100_snapshot_repository(bucket_id=bucket_id)
    )


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("casilla.0596", id="free-casilla-key"),
        pytest.param("renta-retencion-trabajo-retirada", id="binding-the-revision-does-not-declare"),
    ],
)
def test_a_legacy_snapshot_is_refused_by_name_while_the_others_still_read(
    tmp_path: Path, operation: PinnedAuthorityOperation, key: str
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        bucket_id = runtime.bucket_id
        legacy = _store_legacy_snapshot(operation, bucket_id, filing_year=_LEGACY_YEAR, key=key)
        service = _service(bucket_id)
        valid = service.capture(
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, "0A"),
            captured_at=_CAPTURED_AT,
            source_url=_source(1),
            binding_values={_CERTIFICATE: Decimal("100.00")},
            operation=operation,
        )

        reading = service.read_snapshots(operation=operation)
        legacy_year = service.read_latest_for_year(filing_year=_LEGACY_YEAR, operation=operation)
        valid_year = service.read_latest_for_year(filing_year=_FILING_YEAR, operation=operation)
        with pytest.raises(LiveApplicationInputError) as viewed:
            service.show(legacy.snapshot_id, operation=operation)
        stored = build_borrador_100_snapshot_repository(bucket_id=bucket_id).load(legacy.snapshot_id)

    assert reading.readable == (valid,)
    assert [(item.snapshot.snapshot_id, item.reason) for item in reading.refused] == [
        (legacy.snapshot_id, Borrador100SnapshotRefusalReason.BINDING_KEYS_NOT_ADMITTED)
    ]
    assert legacy_year.readable == ()
    assert [item.snapshot.snapshot_id for item in legacy_year.refused] == [legacy.snapshot_id]
    assert (valid_year.readable, valid_year.refused) == ((valid,), ())
    assert viewed.value.context == {"bindings": key}
    assert stored == legacy


def test_a_snapshot_whose_revision_no_longer_reconfirms_is_refused_with_that_reason(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        stale = _store_legacy_snapshot(
            operation,
            runtime.bucket_id,
            filing_year=_FILING_YEAR,
            key=_CERTIFICATE,
            revision_id="persisted-stale-revision",
        )
        service = _service(runtime.bucket_id)
        reading = service.read_snapshots(operation=operation)
        with pytest.raises(RegistrySnapshotError, match="cannot be re-confirmed"):
            service.show(stale.snapshot_id, operation=operation)

    assert reading.readable == ()
    assert [(item.snapshot.snapshot_id, item.reason) for item in reading.refused] == [
        (stale.snapshot_id, Borrador100SnapshotRefusalReason.REGISTRY_COORDINATE_UNCONFIRMED)
    ]


def test_a_snapshot_outside_the_support_envelope_is_refused_while_the_others_still_read(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        outside = _store_snapshot_below_support_floor(operation, runtime.bucket_id)
        valid = _store_legacy_snapshot(operation, runtime.bucket_id, filing_year=_FILING_YEAR, key=_CERTIFICATE)
        service = _service(runtime.bucket_id)
        reading = service.read_snapshots(operation=operation)
        latest = service.read_latest_for_year(filing_year=outside.filing_year, operation=operation)

    assert reading.readable == (valid,)
    assert [(item.snapshot.snapshot_id, item.reason) for item in reading.refused] == [
        (outside.snapshot_id, Borrador100SnapshotRefusalReason.COORDINATE_OUTSIDE_SUPPORT)
    ]
    assert latest.readable == ()
    assert [item.reason for item in latest.refused] == [Borrador100SnapshotRefusalReason.COORDINATE_OUTSIDE_SUPPORT]


def test_a_capture_with_an_inadmissible_key_writes_nothing(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        service = _service(runtime.bucket_id)
        with pytest.raises(LiveApplicationInputError) as refused:
            service.capture(
                filing_year=_FILING_YEAR,
                period=Period.from_year_and_code(_FILING_YEAR, "0A"),
                captured_at=_CAPTURED_AT,
                source_url=_source(1),
                binding_values={_CERTIFICATE: Decimal("100.00"), "casilla.0596": Decimal("15.25")},
                operation=operation,
            )
        stored = build_borrador_100_snapshot_repository(bucket_id=runtime.bucket_id).list_snapshots()

    assert refused.value.translated_message == "application.live.borrador.errors.binding_keys_not_admitted"
    assert stored == ()


def test_each_capture_says_whether_it_stored_or_resolved_to_a_stored_snapshot(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        service = _service(runtime.bucket_id)

        def capture(document: int, *, hours: int):
            return service.capture_with_outcome(
                filing_year=_FILING_YEAR,
                period=period,
                captured_at=_CAPTURED_AT + timedelta(hours=hours),
                source_url=_source(document),
                binding_values={_CERTIFICATE: Decimal(document)},
                operation=operation,
            )

        first = capture(1, hours=0)
        second = capture(2, hours=1)
        first_again = capture(1, hours=2)
        second_again = capture(2, hours=3)
        late = capture(3, hours=-1)
        active = service.read_snapshots(operation=operation).readable

    assert first.outcome is Borrador100CaptureOutcome.CAPTURED
    assert second.outcome is Borrador100CaptureOutcome.CAPTURED
    assert first_again.outcome is Borrador100CaptureOutcome.RESOLVED_SUPERSEDED
    assert first_again.snapshot.snapshot_id == first.snapshot.snapshot_id
    assert first_again.snapshot.superseded_by_snapshot_id == second.snapshot.snapshot_id
    assert first_again.snapshot.captured_at == _CAPTURED_AT
    assert second_again.outcome is Borrador100CaptureOutcome.ALREADY_ACTIVE
    assert late.outcome is Borrador100CaptureOutcome.CAPTURED_SUPERSEDED
    assert [snapshot.snapshot_id for snapshot in active] == [second.snapshot.snapshot_id]
