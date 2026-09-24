"""Modelo 193 calculation over a manual row and captured capital disclosure phases, end to end.

A declarant holds one hand-declared ordinary key B row and one key B coupon
captured from its ledger payment: exigible on 15 December 2025 and collected on
20 January 2026, so it is a PENDING row of the 2025 return and a settled
prior-accrual row of the 2026 one. Real encrypted store, real producer, real
source mesh, real formula engine and the published authority, over an ordinary
filer whose Modelo 123 schedule is quarterly.

Expected values are derived by hand from the 2025 record design (Orden
EHA/3377/2011 as updated by Orden HAC/1430/2025):

* the captured coupon is 1000.00 gross with 19% withheld, 190.00; the manual
  row is 500.00 with 19% withheld, 95.00;
* positions 136-144 of the type-1 record count type-2 records, a perceptor on
  several records counting once per record (p. 5): 1 + 1 = 2;
* positions 145-159 sum the type-2 base at 152-164 (pp. 5-6):
  500.00 + 1000.00 = 1500.00;
* positions 160-174 sum the type-2 withholding at 169-181 (p. 6):
  95.00 + 190.00 = 285.00;
* a PENDIENTE record carries "X" at 117, NIF and representative NIF
  999999999, the name "VALORES PENDIENTE DE ABONO" and no accrual year
  (pp. 24-25).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    CAPITAL_GROSS,
    CAPITAL_HOLDER_NAME,
    CAPITAL_HOLDER_NIF,
    CAPITAL_IRPF,
    capital_payment,
    capital_pending_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_modelo_ready_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingCapture,
    LedgerPaymentWithholdingEvidenceError,
    build_ledger_payment_withholding_capture,
)
from cadrumo.application.aggregation.m193_phase_materialization import Modelo193PhaseMaterializationError
from cadrumo.application.aggregation.percepciones_observations_repository import (
    PercepcionObservationPorts,
    persist_percepcion_observations,
)
from cadrumo.application.aggregation.retencion_observations_repository import (
    RetencionObservationPorts,
    persist_retencion_observations,
)
from cadrumo.application.aggregation.retenciones import (
    Modelo193CapitalDetail,
    Modelo193NonpaymentCause,
    RetencionObservation,
)
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
    withholding_work_profile,
)
from cadrumo.application.aggregation.withholding_source import WithholdingSourceResolver
from cadrumo.application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.export import ModeloExportCommand, export_modelo_revision
from cadrumo.application.modelo.m193_settled_row_gate import Modelo193SettledRowAmountAuthorityUnresolvedError
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import BindingSourceKind, CalculationSourceLineageRole, RetencionScheme
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.identifiers import canonical_decimal_string

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "19319319-3193-4193-8193-000000002025"
_T0 = datetime(2026, 1, 25, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 25, 11, 0, tzinfo=UTC)

_TOTAL_PERCEPTORES: CasillaId = validated_casilla_id("decl.total-perceptores")
_BASE_TOTAL: CasillaId = validated_casilla_id("decl.base-total")
_RETENCIONES_TOTAL: CasillaId = validated_casilla_id("decl.retenciones-total")

_NIF_BINDING = "modelo-193-perceptor-row-nif"
_NIF_REPRESENTANTE_BINDING = "modelo-193-perceptor-row-nif-representante"
_NAME_BINDING = "modelo-193-perceptor-row-name"
_PENDIENTE_BINDING = "modelo-193-perceptor-row-pendiente"
_ACCRUAL_YEAR_BINDING = "modelo-193-perceptor-row-ejercicio-devengo"
_BASE_BINDING = "modelo-193-perceptor-row-base"
_RETENCION_BINDING = "modelo-193-perceptor-row-retencion"

_PENDING_NIF = "999999999"
_PENDING_NAME = "VALORES PENDIENTE DE ABONO"
_MANUAL_NIF = "33333333P"
_MANUAL_BASE = Decimal("500.00")
_MANUAL_RETENCION = Decimal("95.00")
_UNRESOLVED_AMOUNTS = "m193_settled_row_amounts_unresolved_authority"
_SETTLED_ROW_REFUSAL = "REFUSED_MODELO_193_SETTLED_ROW_AMOUNT_AUTHORITY_UNRESOLVED"


@dataclass(frozen=True, slots=True)
class _Bucket:
    objects: SecureObjectRepository
    work_unit_id: str


@contextmanager
def _m193_bucket(tmp_path: Path, *, filing_year: int, operation: PinnedAuthorityOperation) -> Iterator[_Bucket]:
    """Open an isolated bucket with a quarterly filer's profile and one Modelo 193 work unit."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects: SecureObjectRepository = profile.repository
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_T0)
        snapshot = operation.snapshot("193", filing_year=filing_year, period="0A")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="193",
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=_T0,
            operation=operation,
        )
        yield _Bucket(objects=objects, work_unit_id=work_unit.work_unit_id)


def _calculate(bucket: _Bucket) -> BucketAggregationCalculationResult:
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=bucket.objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects),
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects),
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            bucket.work_unit_id,
            ports=ports,
            clock=_T1,
        )


def _coupon_capture(
    *,
    exigible_on: date,
    paid_on: date,
    pending: bool,
) -> LedgerPaymentWithholdingCapture:
    """Build the capture of one synthetic key B coupon, with pending-payment evidence when ``pending``."""
    transaction = capital_payment(provider_id=f"coupon-{exigible_on.isoformat()}", booked_date=paid_on)
    update: dict[str, object] = {
        "payment_event_id": f"coupon-payment-{paid_on.isoformat()}",
        "exigibility_occurred_on": exigible_on,
    }
    if pending:
        update["modelo_193_pending_payment"] = capital_pending_payment(transaction, transaction_date=paid_on)
    return build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="c" * 64,
        request=capital_request(transaction, **update),
        applicable_year=exigible_on.year,
        cadence=quarterly_filer_cadence(exigible_on.year),
    )


def _capture(objects: SecureObjectRepository, capture: LedgerPaymentWithholdingCapture) -> None:
    assert (
        withholding_producer(objects).capture(capture.command, cadence=quarterly_filer_cadence_for(capture.command))
        is not None
    )


def _capture_pending_2025_coupon(objects: SecureObjectRepository) -> None:
    _capture(objects, _coupon_capture(exigible_on=date(2025, 12, 15), paid_on=date(2026, 1, 20), pending=True))


def _persist_manual_2025_row(objects: SecureObjectRepository) -> None:
    """Declare one ordinary key B row by hand: 500.00 base, 19% withheld."""
    template = capital_pending_payment(
        capital_payment(provider_id="manual-coupon"),
        transaction_date=date(2025, 5, 5),
    ).actual_recipient_detail
    persist_percepcion_observations(
        ports=PercepcionObservationPorts(repository=PercepcionObservationRepositoryAdapter(objects=objects)),
        modelo="193",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        observations=[
            template.model_copy(
                update={
                    "source_id": "manual-coupon",
                    "source_allocation_id": "manual-1",
                    "perceptor_tax_id": _MANUAL_NIF,
                    "perceptor_legal_name": "Perceptor Manual Sintetico",
                    "percibido_dinerario": _MANUAL_BASE,
                    "base_retenciones": _MANUAL_BASE,
                    "retencion_practicada": _MANUAL_RETENCION,
                }
            )
        ],
    )


def _persist_pending_2026_accrual_row(objects: SecureObjectRepository) -> None:
    """Write a pending key B coupon accrued in 2026 straight into the Modelo 123 store.

    Capture refuses a 2026 accrual, so this is the path a row persisted outside
    capture takes: the annual materialiser is its only remaining guard.
    """
    exigible_on, paid_on = date(2026, 12, 15), date(2027, 1, 20)
    transaction = capital_payment(provider_id=f"coupon-{exigible_on.isoformat()}", booked_date=paid_on)
    persist_retencion_observations(
        ports=RetencionObservationPorts(repository=RetencionObservationRepositoryAdapter(objects=objects)),
        modelo="123",
        filing_year=exigible_on.year,
        period=Period.from_year_and_code(exigible_on.year, "4T"),
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id=transaction.transaction_id,
                perceptor_nif=CAPITAL_HOLDER_NIF,
                perceptor_name=CAPITAL_HOLDER_NAME,
                scheme=RetencionScheme("intereses"),
                taxable_base=CAPITAL_GROSS,
                retencion_amount=CAPITAL_IRPF,
                accrued_on=exigible_on.isoformat(),
                modelo_193_capital=Modelo193CapitalDetail(
                    pending_payment=capital_pending_payment(transaction, transaction_date=paid_on),
                    recognition_event_id=f"coupon-exigible-{exigible_on.isoformat()}",
                ),
            )
        ],
    )


def _rows_by_nif(row_binding_values: Mapping[str, Mapping[str, str]]) -> dict[str, dict[str, str]]:
    """Return each persisted type-2 row's binding values, keyed by the row's perceptor NIF."""
    rows: dict[str, dict[str, str]] = {}
    for index, nif in row_binding_values[_NIF_BINDING].items():
        rows[nif] = {binding_id: values[index] for binding_id, values in row_binding_values.items() if index in values}
    return rows


def _canonical(value: object) -> str:
    return canonical_decimal_string(value) if isinstance(value, Decimal) else str(value)


def test_a_manual_row_and_a_pending_capture_total_the_2025_declarant_from_the_type_2_records(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Both sources become type-2 rows, and the type-1 totals count and sum exactly those rows."""
    with _m193_bucket(tmp_path, filing_year=2025, operation=authority_operation) as bucket:
        _capture_pending_2025_coupon(bucket.objects)
        _persist_manual_2025_row(bucket.objects)
        result = _calculate(bucket)

    revision = result.revision
    assert Decimal(revision.casilla_values[_TOTAL_PERCEPTORES]) == Decimal("2")
    assert Decimal(revision.casilla_values[_BASE_TOTAL]) == Decimal("1500.00")
    assert Decimal(revision.casilla_values[_RETENCIONES_TOTAL]) == Decimal("285.00")

    rows = _rows_by_nif(revision.row_binding_values)
    assert set(rows) == {_MANUAL_NIF, _PENDING_NIF}
    pending, manual = rows[_PENDING_NIF], rows[_MANUAL_NIF]
    assert pending[_PENDIENTE_BINDING] == "X"
    assert pending[_NIF_REPRESENTANTE_BINDING] == _PENDING_NIF
    assert pending[_NAME_BINDING] == _PENDING_NAME
    assert _ACCRUAL_YEAR_BINDING not in pending
    assert Decimal(pending[_BASE_BINDING]) == CAPITAL_GROSS
    assert Decimal(pending[_RETENCION_BINDING]) == CAPITAL_IRPF
    assert _PENDIENTE_BINDING not in manual
    assert _ACCRUAL_YEAR_BINDING not in manual
    assert Decimal(manual[_BASE_BINDING]) == _MANUAL_BASE
    assert Decimal(manual[_RETENCION_BINDING]) == _MANUAL_RETENCION

    withholding_refs = [
        ref for ref in revision.source_provenance if ref.resolver_id == WithholdingSourceResolver.resolver_id
    ]
    roles = sorted(ref.lineage_role.value for ref in withholding_refs)
    assert roles == sorted(
        [
            CalculationSourceLineageRole.PRIMARY.value,
            CalculationSourceLineageRole.PRIMARY.value,
            CalculationSourceLineageRole.CONTRIBUTOR.value,
        ]
    )
    assert not [diagnostic for diagnostic in result.source_diagnostics if diagnostic.reason == _UNRESOLVED_AMOUNTS]


def test_a_same_year_payment_gives_no_phase_row_and_the_zero_stays_loud(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A coupon paid in its own year is an ordinary 123 allocation: no 193 row, a zero count and its advisory."""
    with _m193_bucket(tmp_path, filing_year=2025, operation=authority_operation) as bucket:
        _capture(
            bucket.objects, _coupon_capture(exigible_on=date(2025, 6, 30), paid_on=date(2025, 7, 2), pending=False)
        )
        result = _calculate(bucket)

    revision = result.revision
    assert revision.row_binding_values == {}
    assert Decimal(revision.casilla_values[_TOTAL_PERCEPTORES]) == Decimal("0")
    assert not [ref for ref in revision.source_provenance if ref.resolver_id == WithholdingSourceResolver.resolver_id]
    empty_store = [
        diagnostic
        for diagnostic in result.source_diagnostics
        if diagnostic.binding_source is BindingSourceKind.WITHHOLDING and "materialised as zero" in diagnostic.message
    ]
    assert len(empty_store) == 1


def test_an_empty_withholding_store_keeps_its_advisory_on_the_calculate_result(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """With neither a manual row nor a capture, the zero perceptor count arrives with its advisory."""
    with _m193_bucket(tmp_path, filing_year=2025, operation=authority_operation) as bucket:
        result = _calculate(bucket)

    assert Decimal(result.revision.casilla_values[_TOTAL_PERCEPTORES]) == Decimal("0")
    empty_store = [
        diagnostic
        for diagnostic in result.source_diagnostics
        if diagnostic.binding_source is BindingSourceKind.WITHHOLDING and diagnostic.reason == "source_issue"
    ]
    assert len(empty_store) == 1
    assert "materialised as zero" in empty_store[0].message


@pytest.mark.usefixtures("authority_operation")
def test_a_key_c_coupon_cannot_carry_pending_payment_evidence_into_capture() -> None:
    """Only keys A, B and D admit the pending treatment, so the capture request refuses key C evidence."""
    transaction = capital_payment(booked_date=date(2026, 1, 20))
    detail = capital_pending_payment(transaction, transaction_date=date(2026, 1, 20)).actual_recipient_detail

    with pytest.raises(ValidationError, match="perception_key"):
        capital_request(
            transaction,
            exigibility_occurred_on=date(2025, 12, 15),
            modelo_193_pending_payment={
                "perception_key": "C",
                "nonpayment_cause": Modelo193NonpaymentCause.HOLDER_NOT_PRESENTED_FOR_COLLECTION,
                "actual_recipient_detail": detail,
            },
        )


def test_the_capture_refuses_a_2026_accrual_and_writes_nothing(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Withholding recognition is grounded for 2025 only, so a 2026 accrual never reaches the store."""
    with _m193_bucket(tmp_path, filing_year=2026, operation=authority_operation) as bucket:
        with pytest.raises(LedgerPaymentWithholdingEvidenceError) as refused:
            _coupon_capture(exigible_on=date(2026, 12, 15), paid_on=date(2027, 1, 20), pending=True)
        stored = RetencionObservationRepositoryAdapter(objects=bucket.objects).load_source_observations_through_year(
            "123", 2027
        )

    assert refused.value.refusal_code == "unsupported_applicable_year"
    assert stored == ()


def test_a_2026_accrual_with_pending_evidence_refuses_the_2026_calculation(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Pending disclosure is grounded for 2025 accruals only, so a persisted 2026 accrual stops the 2026 return."""
    with _m193_bucket(tmp_path, filing_year=2026, operation=authority_operation) as bucket:
        _persist_pending_2026_accrual_row(bucket.objects)
        with pytest.raises(Modelo193PhaseMaterializationError) as raised:
            _calculate(bucket)

    assert raised.value.refusal_code == "unsupported_accrual_year"


def test_the_source_resolved_directly_and_the_live_calculation_agree(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Resolving the withholding source and running the formula engine gives what calculate persisted."""
    with _m193_bucket(tmp_path, filing_year=2025, operation=authority_operation) as bucket:
        _capture_pending_2025_coupon(bucket.objects)
        _persist_manual_2025_row(bucket.objects)
        live = _calculate(bucket).revision
        snapshot = authority_operation.snapshot("193", filing_year=2025, period="0A")
        resolution = WithholdingSourceResolver(
            ports=PercepcionObservationPorts(repository=PercepcionObservationRepositoryAdapter(objects=bucket.objects)),
            retencion_ports=RetencionObservationPorts(
                repository=RetencionObservationRepositoryAdapter(objects=bucket.objects)
            ),
        ).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="193",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
                revision=snapshot.revision,
                profile=withholding_work_profile(authority_operation, profile_id=_BUCKET_ID),
            )
        )

    relay_inputs = {
        **{
            casilla.id: Decimal("0") for casilla in snapshot.revision.casillas if casilla.input_kind is InputKind.MANUAL
        },
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, resolution.binding_values),
    }
    relay = calculate_registry_snapshot(
        snapshot,
        inputs=relay_inputs,
        binding_values=resolution.binding_values,
        date_context={"filing_period": date(2025, 12, 31)},
    ).values

    for casilla_id, expected in (
        (_TOTAL_PERCEPTORES, Decimal("2")),
        (_BASE_TOTAL, Decimal("1500.00")),
        (_RETENCIONES_TOTAL, Decimal("285.00")),
    ):
        assert relay[casilla_id] == Decimal(live.casilla_values[casilla_id]) == expected
    relay_rows = {
        (binding_id, str(index)): _canonical(value)
        for (binding_id, index), value in resolution.row_binding_values.items()
    }
    live_rows = {
        (binding_id, index): value
        for binding_id, values in live.row_binding_values.items()
        for index, value in values.items()
    }
    assert relay_rows == live_rows


def test_a_settled_prior_accrual_row_refuses_the_2026_export(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The captured coupon settles in 2026, so exporting that return refuses before any byte is written."""
    export_path = tmp_path / "modelo-193-2026-0A.txt"
    with _m193_bucket(tmp_path, filing_year=2026, operation=authority_operation) as bucket:
        _capture_pending_2025_coupon(bucket.objects)
        result = _calculate(bucket)
        assert [d.reason for d in result.source_diagnostics if d.reason == _UNRESOLVED_AMOUNTS] == [_UNRESOLVED_AMOUNTS]
        with pytest.raises(Modelo193SettledRowAmountAuthorityUnresolvedError) as raised:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=result.revision.calculation_revision_id,
                    output_path=export_path,
                    actor="test",
                ),
                workflow_profile=TaxpayerProfile(
                    tax_id="12345678Z",
                    iva_regime=IVARegime("GENERAL"),
                    activity_start_date=date(2020, 1, 1),
                    has_employees=False,
                    pays_rent_with_retencion=False,
                    does_intracomunitario=False,
                    bienes_extranjero_above_threshold=False,
                ),
                export_ports=modelo_export_ports_for_test(bucket_id=_BUCKET_ID, secure_objects=bucket.objects),
                operation=authority_operation,
            )

    assert get_registered_error_code(raised.value).code == _SETTLED_ROW_REFUSAL
    assert not export_path.exists()
