"""The composed AEAT sync status dates the IVA wallet area from what its capture stores."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.aeat_sync.status_operation import load_aeat_sync_status
from ...application.aeat_sync.workspace import AeatSyncAreaState, AeatSyncStatusArea
from ...application.persistence_errors import PersistenceDegradationError
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.config import load_settings
from ...core.hashing import sha256_hex
from ...core.period import Period
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_path
from ...core.time.clock import frozen_clock
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from ..aeat_sync_status_composition import compose_aeat_sync_status_ports, degrade_storage_failure

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CAPTURED_AT = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


def _store_filed(operation: PinnedAuthorityOperation, *, modelo: str) -> None:
    """Persist one filed observation through the store the history capture writes to."""
    store = FiledDeclaracionObservationStore(storage_path(StorageCategory.FILED_DECLARATIONS))
    period = Period.from_year_and_code(2026, "1T")
    expediente = f"{modelo}2026Q1SYNTHETIC0001"
    body = b"synthetic register row"
    artefact = store.persist_artefact(
        (modelo, 2026, period, expediente),
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
    snapshot = operation.snapshot(modelo, filing_year=2026, period="1T", grade=RegistryAuthorityGrade.CALCULATION)
    store.persist_observation(
        FiledDeclaracionObservation(
            modelo=modelo,
            ejercicio=2026,
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
        degrade_storage_failure("aeat_sync_status_synthetic", reader)("B12345674")

    assert raised.value.operation == "aeat_sync_status_synthetic"
    assert raised.value.__cause__ is failure


def test_a_reader_refusal_and_its_value_pass_through_the_storage_translation_unchanged() -> None:
    refusal = RefusalError(RefusalCode.UNAVAILABLE)

    def refusing(nif: str) -> tuple[str, ...]:
        raise refusal

    with pytest.raises(RefusalError) as raised:
        degrade_storage_failure("aeat_sync_status_synthetic", refusing)("B12345674")
    assert raised.value is refusal

    assert degrade_storage_failure("aeat_sync_status_synthetic", lambda nif: (nif,))("B12345674") == ("B12345674",)


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
