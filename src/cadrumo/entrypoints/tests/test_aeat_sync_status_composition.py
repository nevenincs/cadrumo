"""The composed AEAT sync status dates each area from what its stored captures hold."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ...adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ...adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from ...adapters.persistence.storage.errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    PathContainmentError,
    RepositoryError,
    SecureObjectRowIdentityError,
    SessionExpiredError,
)
from ...adapters.persistence.storage.secure_object_namespaces import LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE
from ...adapters.persistence.storage.tests.secure_sql import (
    isolated_runtime_profile,
    restamp_secure_object_schema_version,
)
from ...application.aeat_sync.status_operation import load_aeat_sync_status
from ...application.aeat_sync.workspace import (
    AeatSyncAreaState,
    AeatSyncRefusedSnapshotV1,
    AeatSyncStatusArea,
)
from ...application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRefusalReason,
    Borrador100SnapshotService,
    derive_borrador_100_snapshot_id,
)
from ...application.live.snapshot_base import SnapshotLifecycleState
from ...application.persistence_errors import PersistenceDegradationError
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.config import load_settings
from ...core.hashing import sha256_hex
from ...core.period import Period
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_path
from ...core.time.clock import frozen_clock
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.calculations.registry.temporal import select_authored_revision_metadata
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ...tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from ..adapter_composition_ports import build_borrador_100_snapshot_repository
from ..aeat_sync_status_composition import compose_aeat_sync_status_ports, degrade_storage_failure

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_BORRADOR_YEAR = newest_authored_edition("100")
_LEGACY_YEAR = filing_year_envelope().floor

_CAPTURED_AT = datetime(_YEAR, 10, 20, 9, 0, tzinfo=UTC)


def _store_filed(operation: PinnedAuthorityOperation, *, modelo: str) -> None:
    """Persist one filed observation through the store the history capture writes to."""
    store = FiledDeclaracionObservationStore(storage_path(StorageCategory.FILED_DECLARATIONS))
    period = Period.from_year_and_code(_YEAR, "1T")
    expediente = f"{modelo}{_YEAR}Q1SYNTHETIC0001"
    body = b"synthetic register row"
    artefact = store.persist_artefact(
        (modelo, _YEAR, period, expediente),
        FiledDeclaracionArtefact(
            kind="register_row",
            source_url=TypeAdapter(AnyHttpUrl).validate_python(SEDE_ROOT_URL_FIXTURE),
            content_type="text/html",
            byte_count=len(body),
            sha256=sha256_hex(body),
            captured_at=_CAPTURED_AT,
        ),
        body,
    )
    snapshot = operation.snapshot(modelo, filing_year=_YEAR, period="1T", grade=RegistryAuthorityGrade.CALCULATION)
    store.persist_observation(
        FiledDeclaracionObservation(
            modelo=modelo,
            ejercicio=_YEAR,
            period=period,
            expediente_id=expediente,
            status="ALTA",
            presented_at=_CAPTURED_AT - timedelta(days=5),
            authenticated_identity="12345678Z",
            artefacts=(artefact,),
            registry_snapshot_ref=snapshot.snapshot_ref,
        ),
        operation=operation,
    )


def _store_legacy_borrador(operation: PinnedAuthorityOperation, bucket_id: str) -> Borrador100Snapshot:
    """Store an active earlier-year borrador keyed by a free casilla id, as the earlier key contract did."""
    period = Period.from_year_and_code(_LEGACY_YEAR, "0A")
    ref = operation.snapshot("100", filing_year=_LEGACY_YEAR, period="0A").snapshot_ref
    values = {"casilla.0596": Decimal("15.25")}
    source = "file-import:sha256:" + "1" * 64
    snapshot = Borrador100Snapshot(
        snapshot_id=derive_borrador_100_snapshot_id(
            filing_year=_LEGACY_YEAR, period=period, registry_snapshot_ref=ref, source_url=source, binding_values=values
        ),
        bucket_id=bucket_id,
        modelo="100",
        filing_year=_LEGACY_YEAR,
        period=period,
        registry_snapshot_ref=ref,
        captured_at=_CAPTURED_AT,
        source_url=source,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=values,
    )
    build_borrador_100_snapshot_repository(bucket_id=bucket_id).save(snapshot)
    return snapshot


def _store_borrador_below_support_floor(operation: PinnedAuthorityOperation, bucket_id: str) -> Borrador100Snapshot:
    """Store an active borrador whose year the registry authors but its support envelope refuses."""
    filing_year = operation.supported_filing_years().floor - 1
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = select_authored_revision_metadata(
        operation.modelo_directory("100"), filing_year=filing_year, period="0A"
    ).id
    ref = RegistrySnapshotRef(modelo="100", revision_id=revision_id, modelo_year=filing_year, period="0A")
    values = {"renta-retencion-soportada-trabajo": Decimal("15.25")}
    source = "file-import:sha256:" + "3" * 64
    snapshot = Borrador100Snapshot(
        snapshot_id=derive_borrador_100_snapshot_id(
            filing_year=filing_year, period=period, registry_snapshot_ref=ref, source_url=source, binding_values=values
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


def _capture_borrador(operation: PinnedAuthorityOperation, bucket_id: str, *, captured_at: datetime) -> str:
    """Capture an admitted borrador through the canonical service."""
    service = Borrador100SnapshotService(
        bucket_id=bucket_id, repository=build_borrador_100_snapshot_repository(bucket_id=bucket_id)
    )
    return service.capture(
        filing_year=_BORRADOR_YEAR,
        period=Period.from_year_and_code(_BORRADOR_YEAR, "0A"),
        captured_at=captured_at,
        source_url="file-import:sha256:" + "2" * 64,
        binding_values={"renta-retencion-soportada-trabajo": Decimal("100.00")},
        operation=operation,
    ).snapshot_id


def _status(operation: PinnedAuthorityOperation, bucket_id: str, *, days_later: int):
    return load_aeat_sync_status(
        compose_aeat_sync_status_ports(load_settings(), bucket_id, operation),
        bucket_id=bucket_id,
        observed_at=_CAPTURED_AT + timedelta(days=days_later),
        operation=operation,
    )


def _area(result, area: AeatSyncStatusArea):
    return next(item for item in result.status.areas if item.area is area)


def test_a_legacy_borrador_is_named_as_refused_while_the_valid_one_and_other_areas_still_read(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    valid_at = _CAPTURED_AT + timedelta(days=2)
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        legacy = _store_legacy_borrador(operation, runtime.bucket_id)
        _capture_borrador(operation, runtime.bucket_id, captured_at=valid_at)
        _store_filed(operation, modelo="303")
        result = _status(operation, runtime.bucket_id, days_later=3)

    borrador = _area(result, AeatSyncStatusArea.BORRADOR_100)
    assert (borrador.state, borrador.last_brought_at, borrador.refusal) == (AeatSyncAreaState.CURRENT, valid_at, None)
    assert borrador.refused_snapshots == (
        AeatSyncRefusedSnapshotV1(
            snapshot_id=legacy.snapshot_id, reason=Borrador100SnapshotRefusalReason.BINDING_KEYS_NOT_ADMITTED
        ),
    )
    wallet = _area(result, AeatSyncStatusArea.IVA_WALLET)
    assert (wallet.state, wallet.last_brought_at) == (AeatSyncAreaState.CURRENT, _CAPTURED_AT)


def test_a_profile_holding_only_a_legacy_borrador_reads_it_as_unavailable_not_never_brought(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        legacy = _store_legacy_borrador(operation, runtime.bucket_id)
        result = _status(operation, runtime.bucket_id, days_later=1)

    borrador = _area(result, AeatSyncStatusArea.BORRADOR_100)
    assert (borrador.state, borrador.last_brought_at, borrador.refusal) == (
        AeatSyncAreaState.UNAVAILABLE,
        None,
        "aeat_sync.status.capture_refused",
    )
    assert [item.snapshot_id for item in borrador.refused_snapshots] == [legacy.snapshot_id]
    assert _area(result, AeatSyncStatusArea.NOTIFICATIONS).state is AeatSyncAreaState.NEVER_BROUGHT


def _restamp_stored_borrador_as_earlier_schema(runtime, snapshot_id: str) -> None:
    """Turn one stored borrador row into an earlier-schema row, whose values were plain strings."""
    from sqlalchemy import select

    from ...adapters.persistence.storage.sql.tables import secure_objects_table
    from ...application.live.borrador_100 import borrador_100_snapshot_object_key

    def to_earlier_shape(document) -> None:
        document["schema_version"] = 1
        payload = document["payload"]
        payload["binding_values"] = {key: value["value"] for key, value in payload["binding_values"].items()}

    restamp_secure_object_schema_version(
        runtime.repository._engine,
        row_statement=select(secure_objects_table).where(
            secure_objects_table.c.namespace == LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.namespace,
            secure_objects_table.c.object_key == borrador_100_snapshot_object_key(runtime.bucket_id, snapshot_id),
        ),
        schema_version=1,
        mutate=to_earlier_shape,
    )


def test_a_profile_holding_only_an_earlier_schema_borrador_reads_it_as_unavailable_and_counted(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        stored = _capture_borrador(operation, runtime.bucket_id, captured_at=_CAPTURED_AT)
        _restamp_stored_borrador_as_earlier_schema(runtime, stored)
        _store_filed(operation, modelo="303")
        result = _status(operation, runtime.bucket_id, days_later=1)

    borrador = _area(result, AeatSyncStatusArea.BORRADOR_100)
    assert (borrador.state, borrador.last_brought_at, borrador.refusal, borrador.outdated_stored_snapshots) == (
        AeatSyncAreaState.UNAVAILABLE,
        None,
        "aeat_sync.status.snapshot_schema_outdated",
        1,
    )
    assert borrador.refused_snapshots == ()
    assert _area(result, AeatSyncStatusArea.IVA_WALLET).state is AeatSyncAreaState.CURRENT


def test_an_earlier_schema_borrador_beside_a_current_one_is_counted_and_the_area_stays_current(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    valid_at = _CAPTURED_AT + timedelta(days=2)
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        stored = _capture_borrador(operation, runtime.bucket_id, captured_at=_CAPTURED_AT)
        _restamp_stored_borrador_as_earlier_schema(runtime, stored)
        service = Borrador100SnapshotService(
            bucket_id=runtime.bucket_id, repository=build_borrador_100_snapshot_repository(bucket_id=runtime.bucket_id)
        )
        service.capture(
            filing_year=_BORRADOR_YEAR,
            period=Period.from_year_and_code(_BORRADOR_YEAR, "0A"),
            captured_at=valid_at,
            source_url="file-import:sha256:" + "8" * 64,
            binding_values={"renta-retencion-soportada-trabajo": Decimal("100.00")},
            operation=operation,
        )
        result = _status(operation, runtime.bucket_id, days_later=3)

    borrador = _area(result, AeatSyncStatusArea.BORRADOR_100)
    assert (borrador.state, borrador.last_brought_at, borrador.refusal, borrador.outdated_stored_snapshots) == (
        AeatSyncAreaState.CURRENT,
        valid_at,
        None,
        1,
    )


def test_a_borrador_outside_the_support_envelope_is_named_as_refused_without_failing_the_status(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    valid_at = _CAPTURED_AT + timedelta(days=2)
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        outside = _store_borrador_below_support_floor(operation, runtime.bucket_id)
        _capture_borrador(operation, runtime.bucket_id, captured_at=valid_at)
        _store_filed(operation, modelo="303")
        result = _status(operation, runtime.bucket_id, days_later=3)

    borrador = _area(result, AeatSyncStatusArea.BORRADOR_100)
    assert (borrador.state, borrador.last_brought_at) == (AeatSyncAreaState.CURRENT, valid_at)
    assert borrador.refused_snapshots == (
        AeatSyncRefusedSnapshotV1(
            snapshot_id=outside.snapshot_id, reason=Borrador100SnapshotRefusalReason.COORDINATE_OUTSIDE_SUPPORT
        ),
    )
    assert _area(result, AeatSyncStatusArea.IVA_WALLET).state is AeatSyncAreaState.CURRENT


def _iva_wallet(operation: PinnedAuthorityOperation, bucket_id: str, *, days_later: int):
    ports = compose_aeat_sync_status_ports(load_settings(), bucket_id, operation)
    result = load_aeat_sync_status(
        ports,
        bucket_id=bucket_id,
        observed_at=_CAPTURED_AT + timedelta(days=days_later),
        operation=operation,
    )
    return next(area for area in result.status.areas if area.area is AeatSyncStatusArea.IVA_WALLET)


def test_a_stored_303_history_capture_brings_the_iva_wallet_area(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        assert _iva_wallet(operation, runtime.bucket_id, days_later=1).state is AeatSyncAreaState.NEVER_BROUGHT
        _store_filed(operation, modelo="303")
        current = _iva_wallet(operation, runtime.bucket_id, days_later=30)
        stale = _iva_wallet(operation, runtime.bucket_id, days_later=31)

    assert current.state is AeatSyncAreaState.CURRENT
    assert current.last_brought_at == _CAPTURED_AT
    assert stale.state is AeatSyncAreaState.POSSIBLY_STALE


def test_a_filed_declaration_of_another_form_does_not_date_the_iva_wallet(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        _store_filed(operation, modelo="130")
        area = _iva_wallet(operation, runtime.bucket_id, days_later=1)

    assert area.state is AeatSyncAreaState.NEVER_BROUGHT
    assert area.last_brought_at is None


def test_a_reader_adapter_storage_failure_surfaces_as_a_persistence_degradation() -> None:
    failure = RepositoryError("synthetic adapter failure")

    def reader(nif: str) -> tuple[str, ...]:
        raise failure

    with pytest.raises(PersistenceDegradationError) as raised:
        degrade_storage_failure("aeat_sync_status_synthetic", reader)("B00015016")

    assert raised.value.operation == "aeat_sync_status_synthetic"
    assert raised.value.__cause__ is failure


def test_a_reader_refusal_and_its_value_pass_through_the_storage_translation_unchanged() -> None:
    refusal = RefusalError(RefusalCode.UNAVAILABLE)

    def refusing(nif: str) -> tuple[str, ...]:
        raise refusal

    with pytest.raises(RefusalError) as raised:
        degrade_storage_failure("aeat_sync_status_synthetic", refusing)("B00015016")
    assert raised.value is refusal

    assert degrade_storage_failure("aeat_sync_status_synthetic", lambda nif: (nif,))("B00015016") == ("B00015016",)


@pytest.mark.parametrize(
    "failure",
    [
        SessionExpiredError("synthetic sealed session"),
        PathContainmentError("synthetic path escape"),
        SecureObjectRowIdentityError("synthetic.namespace", expected_identifier="synthetic-key"),
        BlobIntegrityError("synthetic blob digest mismatch"),
    ],
    ids=lambda failure: type(failure).__name__,
)
def test_a_sealed_session_or_integrity_failure_keeps_its_own_meaning(failure: Exception) -> None:
    def reader() -> tuple[str, ...]:
        raise failure

    with pytest.raises(type(failure)) as raised:
        degrade_storage_failure("aeat_sync_status_synthetic", reader)()
    assert raised.value is failure


def test_a_missing_blob_is_a_data_unavailable_failure() -> None:
    def reader() -> tuple[str, ...]:
        raise BlobNotFoundError("synthetic missing blob")

    with pytest.raises(PersistenceDegradationError):
        degrade_storage_failure("aeat_sync_status_synthetic", reader)()


def test_a_sealed_profile_session_refuses_the_composed_status_read(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        ports = compose_aeat_sync_status_ports(load_settings(), runtime.bucket_id, operation)
        assert ports.filed_attempt() is None
        with frozen_clock(datetime.now(UTC) + timedelta(days=30)), pytest.raises(SessionExpiredError):
            ports.filed_attempt()
