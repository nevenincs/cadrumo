"""Read-only Modelo 193 pending-payment disclosure materialization.

This module is deliberately narrower than an exporter.  It derives the two
accepted domain views from active 123 allocation evidence, but does not claim
that a later filing-year record layout is available or write a second annual
authority.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from .retenciones import Modelo193CapitalDetail, RetencionObservation

_PENDING_PERCEPTOR_NIF = "999999999"
_PENDING_PERCEPTOR_NAME = "VALORES PENDIENTE DE ABONO"


class Modelo193DisclosurePhase(StrEnum):
    """The authority-selected disclosure phase, not a second economic event."""

    PENDING = "pending"
    SETTLED_PRIOR_ACCRUAL = "settled_prior_accrual"


class Modelo193PhaseMaterializationError(ValueError):
    """Payload-free refusal when active capital evidence cannot support a phase."""

    def __init__(self, code: str) -> None:
        """Keep corrupted or incomplete evidence out of a filing-facing view."""
        self.code = code
        super().__init__(f"Modelo 193 phase materialization refused: {code}")


class Modelo193PhaseRow(BaseModel):
    """One derived annual disclosure row retaining source/allocation provenance."""

    model_config = STRICT_FROZEN_CONFIG

    phase: Modelo193DisclosurePhase
    filing_year: int = Field(ge=2000, le=9999)
    original_accrual_year: int = Field(ge=2000, le=9999)
    recognized_on: date
    source_kind: BindingSourceKind
    source_object_id: str = Field(min_length=1, max_length=128)
    allocation_id: str = Field(min_length=1, max_length=128)
    recognition_event_id: str = Field(min_length=1, max_length=128)
    settlement_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    taxable_base: Decimal = Field(ge=Decimal("0"))
    retencion_amount: Decimal = Field(ge=Decimal("0"))
    annual_detail: WithholdingObservation
    filing_export_supported: Literal[False] = False
    """Always false: this is domain evidence, not a filing-grade later-year export."""

    @model_validator(mode="after")
    def _matches_derived_phase_contract(self) -> Modelo193PhaseRow:
        detail = self.annual_detail
        if detail.source_id != self.source_object_id or detail.source_allocation_id != self.allocation_id:
            raise ValueError("Modelo 193 phase annual detail must retain source/allocation provenance")
        if detail.percibido_dinerario != self.taxable_base or detail.retencion_practicada != self.retencion_amount:
            raise ValueError("Modelo 193 phase annual detail amounts must match the economic allocation")
        if detail.base_retenciones != self.taxable_base:
            raise ValueError("Modelo 193 phase retention base must match the economic allocation")
        if self.phase is Modelo193DisclosurePhase.PENDING:
            if self.filing_year != self.original_accrual_year:
                raise ValueError("Modelo 193 pending disclosure belongs to the accrual year")
            if (
                detail.perceptor_tax_id != _PENDING_PERCEPTOR_NIF
                or detail.representative_tax_id != _PENDING_PERCEPTOR_NIF
                or detail.perceptor_legal_name != _PENDING_PERCEPTOR_NAME
                or detail.pendiente_flag != "X"
                or detail.accrual_year is not None
            ):
                raise ValueError("Modelo 193 pending disclosure must use the prescribed recipient values")
            if self.settlement_event_id is not None:
                raise ValueError("Modelo 193 pending disclosure cannot carry a settlement event")
        else:
            if self.filing_year <= self.original_accrual_year:
                raise ValueError("Modelo 193 prior-accrual settlement must be in a later payment year")
            if self.settlement_event_id is None:
                raise ValueError("Modelo 193 prior-accrual settlement requires its settlement event")
            if detail.pendiente_flag is not None or detail.accrual_year != self.original_accrual_year:
                raise ValueError("Modelo 193 prior-accrual settlement must carry only the original accrual year")
        return self


def materialize_modelo_193_disclosure_phases(
    observations: Iterable[RetencionObservation],
    *,
    filing_year: int,
) -> tuple[Modelo193PhaseRow, ...]:
    """Derive active 2025 pending and later-settlement disclosure rows.

    Callers provide active rows read from the existing encrypted 123
    projection.  This function neither creates an annual cache nor contributes
    a second row to Modelo 123; a later settlement is a disclosure phase of the
    same allocation.
    """
    rows: list[Modelo193PhaseRow] = []
    seen_allocations: set[tuple[str, str, str]] = set()
    for observation in observations:
        capital = observation.modelo_193_capital
        if capital is None:
            continue
        recognized_on = date.fromisoformat(str(observation.accrued_on))
        if recognized_on.year != 2025:
            raise Modelo193PhaseMaterializationError("unsupported_accrual_year")
        allocation_key = (
            observation.source_kind.value,
            observation.source_object_id,
            capital.pending_payment.actual_recipient_detail.source_allocation_id,
        )
        if not allocation_key[-1]:
            raise Modelo193PhaseMaterializationError("missing_allocation_provenance")
        if allocation_key in seen_allocations:
            raise Modelo193PhaseMaterializationError("duplicate_active_allocation")
        seen_allocations.add(allocation_key)
        _validate_active_evidence(observation, capital, recognized_on)

        settlement = capital.settlement_event
        if filing_year == recognized_on.year:
            if settlement is None or settlement.occurred_on.year > recognized_on.year:
                rows.append(_pending_row(observation, capital, recognized_on))
        elif settlement is not None and filing_year == settlement.occurred_on.year:
            rows.append(_settled_prior_accrual_row(observation, capital, recognized_on))
    return tuple(sorted(rows, key=_phase_sort_key))


def _validate_active_evidence(
    observation: RetencionObservation,
    capital: Modelo193CapitalDetail,
    recognized_on: date,
) -> None:
    """Fail closed if a persisted row no longer describes the accepted contract."""
    annual = capital.pending_payment.actual_recipient_detail
    if annual.source_id != observation.source_object_id:
        raise Modelo193PhaseMaterializationError("source_provenance_mismatch")
    if annual.percibido_dinerario != observation.taxable_base:
        raise Modelo193PhaseMaterializationError("taxable_base_mismatch")
    if annual.retencion_practicada != observation.retencion_amount:
        raise Modelo193PhaseMaterializationError("withholding_amount_mismatch")
    if annual.base_retenciones != observation.taxable_base:
        raise Modelo193PhaseMaterializationError("retention_base_mismatch")
    settlement = capital.settlement_event
    if settlement is not None and settlement.occurred_on.year <= recognized_on.year:
        raise Modelo193PhaseMaterializationError("nonpayment_cause_conflicts_with_same_year_settlement")


def _pending_row(
    observation: RetencionObservation,
    capital: Modelo193CapitalDetail,
    recognized_on: date,
) -> Modelo193PhaseRow:
    """Build the prescribed 2025 PENDING representation without exposing the holder."""
    actual = capital.pending_payment.actual_recipient_detail
    detail = actual.model_copy(
        update={
            "perceptor_tax_id": _PENDING_PERCEPTOR_NIF,
            "representative_tax_id": _PENDING_PERCEPTOR_NIF,
            "perceptor_legal_name": _PENDING_PERCEPTOR_NAME,
            "country_code": None,
            "province_code": None,
            "perceptor_mediador_flag": None,
            "pendiente_flag": "X",
            "accrual_year": None,
            "transaction_date": recognized_on,
        }
    )
    return Modelo193PhaseRow(
        phase=Modelo193DisclosurePhase.PENDING,
        filing_year=recognized_on.year,
        original_accrual_year=recognized_on.year,
        recognized_on=recognized_on,
        source_kind=observation.source_kind,
        source_object_id=observation.source_object_id,
        allocation_id=detail.source_allocation_id,
        recognition_event_id=capital.recognition_event_id,
        taxable_base=observation.taxable_base,
        retencion_amount=observation.retencion_amount,
        annual_detail=detail,
    )


def _settled_prior_accrual_row(
    observation: RetencionObservation,
    capital: Modelo193CapitalDetail,
    recognized_on: date,
) -> Modelo193PhaseRow:
    """Build the actual-recipient payment-year phase from the same allocation."""
    settlement = capital.settlement_event
    if settlement is None:  # pragma: no cover - guarded by caller branch
        raise Modelo193PhaseMaterializationError("missing_settlement_event")
    detail = capital.pending_payment.actual_recipient_detail.model_copy(
        update={
            "pendiente_flag": None,
            "accrual_year": recognized_on.year,
            "transaction_date": settlement.occurred_on,
        }
    )
    return Modelo193PhaseRow(
        phase=Modelo193DisclosurePhase.SETTLED_PRIOR_ACCRUAL,
        filing_year=settlement.occurred_on.year,
        original_accrual_year=recognized_on.year,
        recognized_on=recognized_on,
        source_kind=observation.source_kind,
        source_object_id=observation.source_object_id,
        allocation_id=detail.source_allocation_id,
        recognition_event_id=capital.recognition_event_id,
        settlement_event_id=settlement.event_id,
        taxable_base=observation.taxable_base,
        retencion_amount=observation.retencion_amount,
        annual_detail=detail,
    )


def _phase_sort_key(row: Modelo193PhaseRow) -> tuple[str, str, str, str]:
    """Keep read-only materialization deterministic regardless of store order."""
    return (
        row.phase.value,
        row.source_kind.value,
        row.source_object_id,
        row.allocation_id,
    )


__all__ = [
    "Modelo193DisclosurePhase",
    "Modelo193PhaseMaterializationError",
    "Modelo193PhaseRow",
    "materialize_modelo_193_disclosure_phases",
]
