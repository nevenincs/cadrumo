"""Modelo 193's annual withholding source composes its manual window with capital disclosure phases.

Captured movable-capital allocations live in the Modelo 123 retención window.
The annual Modelo 193 source reads that store through every year up to the
filing year, materialises the pending and settled-prior-accrual phases, and
adds their annual detail to the manual 193 window. Real encrypted store, real
producer, real resolver and the published authority's 193 revision.

A capital capture is anchored to the ledger payment, so every captured
allocation carries its settlement event: "unpaid at year end" is a coupon
exigible in 2025 and collected in January 2026, which is PENDING in the 2025
source and SETTLED_PRIOR_ACCRUAL in the 2026 source.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.errors import AggregationValidationError
from cadrumo.application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingCapture,
    build_ledger_payment_withholding_capture,
)
from cadrumo.application.aggregation.m193_phase_materialization import Modelo193PhaseMaterializationError
from cadrumo.application.aggregation.percepciones_observations_repository import (
    PercepcionObservationPorts,
    persist_percepcion_observations,
)
from cadrumo.application.aggregation.retencion_observations_repository import RetencionObservationPorts
from cadrumo.application.aggregation.retenciones import Modelo193NonpaymentCause, Modelo193PendingPaymentEvidence
from cadrumo.application.aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from cadrumo.application.aggregation.tests.ledger_capital_support import (
    CAPITAL_GROSS,
    CAPITAL_HOLDER_NIF,
    CAPITAL_IRPF,
    capital_payment,
    capital_pending_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.application.aggregation.withholding_source import WithholdingSourceResolver
from cadrumo.core.aggregation import AggregationCaptureKind, BindingSourceKind, CalculationSourceLineageRole
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PENDING_NIF = "999999999"
_MANUAL_NIF = "33333333P"
_COUPON_ALLOCATION_ID = "coupon-allocation-2025-06"
_NIF_BINDING = "modelo-193-perceptor-row-nif"
_PENDIENTE_BINDING = "modelo-193-perceptor-row-pendiente"
_ACCRUAL_YEAR_BINDING = "modelo-193-perceptor-row-ejercicio-devengo"
_PERCIBIDO_BINDING = "modelo-193-perceptor-row-percibido"
_RETENCION_BINDING = "modelo-193-perceptor-row-retencion"
_COLLISION_KEY = "aggregation.retenciones.errors.m193_phase_allocation_collision"


def _capture(capture: LedgerPaymentWithholdingCapture, objects: SecureObjectRepository) -> None:
    assert withholding_producer(objects).capture(capture.command) is not None


def _collected_next_year() -> tuple[str, LedgerPaymentWithholdingCapture]:
    """A key B coupon exigible 15 December 2025 that the holder collected on 20 January 2026."""
    paid_on = date(2026, 1, 20)
    transaction = capital_payment(provider_id="coupon-2025-12", booked_date=paid_on)
    request = capital_request(
        transaction,
        payment_event_id="coupon-payment-2026-01",
        exigibility_occurred_on=date(2025, 12, 15),
        modelo_193_pending_payment=capital_pending_payment(transaction, transaction_date=paid_on),
    )
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="c" * 64,
        request=request,
        applicable_year=2025,
    )
    return transaction.transaction_id, capture


def _collected_same_year() -> LedgerPaymentWithholdingCapture:
    """A coupon exigible 30 June 2025 and paid 2 July 2025, with no pending evidence."""
    transaction = capital_payment()
    return build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="c" * 64,
        request=capital_request(transaction),
        applicable_year=2025,
    )


def _manual_row(*, source_id: str, source_allocation_id: str) -> WithholdingObservation:
    """A hand-declared key B 193 row for a second, synthetic holder."""
    template = capital_pending_payment(
        capital_payment(provider_id="manual-coupon"),
        transaction_date=date(2025, 5, 5),
    ).actual_recipient_detail
    return template.model_copy(
        update={
            "source_id": source_id,
            "source_allocation_id": source_allocation_id,
            "perceptor_tax_id": _MANUAL_NIF,
            "perceptor_legal_name": "Perceptor Manual Sintetico",
        }
    )


def _persist_manual(objects: SecureObjectRepository, row: WithholdingObservation) -> None:
    persist_percepcion_observations(
        ports=PercepcionObservationPorts(repository=PercepcionObservationRepositoryAdapter(objects=objects)),
        modelo="193",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        observations=[row],
    )


def _resolve(
    objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation,
    *,
    bucket_id: str,
    filing_year: int,
) -> CalculationSourceResolution:
    resolver = WithholdingSourceResolver(
        ports=PercepcionObservationPorts(repository=PercepcionObservationRepositoryAdapter(objects=objects)),
        retencion_ports=RetencionObservationPorts(repository=RetencionObservationRepositoryAdapter(objects=objects)),
    )
    snapshot = operation.snapshot("193", filing_year=filing_year, period="0A")
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo="193",
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, "0A"),
            revision=snapshot.revision,
        )
    )


def _row_values(resolution: CalculationSourceResolution, binding_id: str) -> list[str]:
    """Return one binding's row values in row order, rendered for comparison."""
    return [
        str(value)
        for (bound_id, _index), value in sorted(resolution.row_binding_values.items(), key=lambda item: item[0][1])
        if bound_id == binding_id
    ]


def _contributors(resolution: CalculationSourceResolution) -> tuple[CalculationSourceProvenance, ...]:
    return tuple(row for row in resolution.provenance if row.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR)


def test_2025_accrual_collected_in_2026_is_pending_in_the_2025_source(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The coupon appears once, under the prescribed pending recipient, with its amounts."""
    _source_id, capture = _collected_next_year()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _capture(capture, profile.repository)
        resolution = _resolve(profile.repository, authority_operation, bucket_id=profile.bucket_id, filing_year=2025)

    assert _row_values(resolution, _NIF_BINDING) == [_PENDING_NIF]
    assert _row_values(resolution, _PENDIENTE_BINDING) == ["X"]
    assert _row_values(resolution, _PERCIBIDO_BINDING) == [str(CAPITAL_GROSS)]
    assert _row_values(resolution, _RETENCION_BINDING) == [str(CAPITAL_IRPF)]
    assert resolution.diagnostics == ()
    primaries = {
        row.source_ref for row in resolution.provenance if row.lineage_role is CalculationSourceLineageRole.PRIMARY
    }
    (contributor,) = _contributors(resolution)
    assert contributor.parent_source_ref in primaries
    assert contributor.contributor_binding_source is BindingSourceKind.LEDGER_TRANSACTION
    assert (contributor.source_modelo, contributor.source_filing_year) == ("123", 2025)
    assert contributor.source_ref.startswith("retencion:")


def test_the_same_allocation_is_settled_prior_accrual_in_the_2026_source(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The 2025-window allocation reaches the payment year under the actual holder and its accrual year."""
    _source_id, capture = _collected_next_year()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _capture(capture, profile.repository)
        resolution = _resolve(profile.repository, authority_operation, bucket_id=profile.bucket_id, filing_year=2026)

    assert _row_values(resolution, _NIF_BINDING) == [CAPITAL_HOLDER_NIF]
    assert _row_values(resolution, _ACCRUAL_YEAR_BINDING) == ["2025"]
    assert _row_values(resolution, _PENDIENTE_BINDING) == []
    assert resolution.diagnostics == ()
    (contributor,) = _contributors(resolution)
    assert (contributor.source_modelo, contributor.source_filing_year) == ("123", 2025)


def test_a_same_year_payment_gives_no_phase_row_and_keeps_the_empty_store_advisory(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A coupon collected in its own year is an ordinary 123 allocation, not a disclosure phase."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _capture(_collected_same_year(), profile.repository)
        accrual_year = _resolve(profile.repository, authority_operation, bucket_id=profile.bucket_id, filing_year=2025)
        next_year = _resolve(profile.repository, authority_operation, bucket_id=profile.bucket_id, filing_year=2026)

    for resolution in (accrual_year, next_year):
        assert resolution.row_binding_values == {}
        assert _contributors(resolution) == ()
        assert [diagnostic.source_kind for diagnostic in resolution.diagnostics] == ["withholding"]
        assert "materialised as zero" in resolution.diagnostics[0].message


@pytest.mark.usefixtures("authority_operation")
def test_key_c_cannot_carry_pending_payment_evidence() -> None:
    """Only keys A, B and D admit the pending treatment, so no key C phase row can be captured."""
    detail = capital_pending_payment(capital_payment(), transaction_date=date(2026, 1, 20)).actual_recipient_detail

    with pytest.raises(ValidationError, match="perception_key"):
        Modelo193PendingPaymentEvidence.model_validate(
            {
                "perception_key": "C",
                "nonpayment_cause": Modelo193NonpaymentCause.HOLDER_NOT_PRESENTED_FOR_COLLECTION,
                "actual_recipient_detail": detail,
            }
        )


def test_a_manual_row_and_a_phase_row_compose_one_source(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The manual window and the materialised phase both reach the annual rows, each with its provenance."""
    _source_id, capture = _collected_next_year()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _capture(capture, profile.repository)
        _persist_manual(profile.repository, _manual_row(source_id="manual-coupon", source_allocation_id="manual-1"))
        resolution = _resolve(profile.repository, authority_operation, bucket_id=profile.bucket_id, filing_year=2025)

    assert sorted(_row_values(resolution, _NIF_BINDING)) == sorted([_MANUAL_NIF, _PENDING_NIF])
    assert _row_values(resolution, _PENDIENTE_BINDING) == ["X"]
    assert resolution.diagnostics == ()
    primaries = [row for row in resolution.provenance if row.lineage_role is CalculationSourceLineageRole.PRIMARY]
    assert len(primaries) == 2
    assert len(_contributors(resolution)) == 1


def test_a_manual_row_declaring_a_captured_allocation_refuses(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The same allocation declared by hand and materialised from capture has two writers, so it refuses."""
    source_id, capture = _collected_next_year()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _capture(capture, profile.repository)
        _persist_manual(
            profile.repository, _manual_row(source_id=source_id, source_allocation_id=_COUPON_ALLOCATION_ID)
        )
        with pytest.raises(AggregationValidationError) as exc_info:
            _resolve(profile.repository, authority_operation, bucket_id=profile.bucket_id, filing_year=2025)

    assert exc_info.value.translated_message == _COLLISION_KEY
    assert exc_info.value.context == {
        "modelo": "193",
        "filing_year": "2025",
        "source_allocations": f"{source_id}/{_COUPON_ALLOCATION_ID}",
    }


def test_a_later_accrual_carrying_pending_evidence_is_refused(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Pending disclosure is grounded for 2025 accruals only; a 2026 accrual stops the 2026 source."""
    _source_id, capture = _collected_next_year()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _capture(capture, profile.repository)
        retenciones = RetencionObservationRepositoryAdapter(objects=profile.repository)
        (captured,) = retenciones.load_observations("123", Period.from_year_and_code(2025, "4T"))
        retenciones.replace_observations(
            modelo="123",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            observations=[
                captured.model_copy(update={"source_object_id": "coupon-2026-01", "accrued_on": "2026-01-10"})
            ],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        with pytest.raises(Modelo193PhaseMaterializationError) as exc_info:
            _resolve(profile.repository, authority_operation, bucket_id=profile.bucket_id, filing_year=2026)

    assert exc_info.value.refusal_code == "unsupported_accrual_year"
