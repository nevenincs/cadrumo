"""Public capture command for grounded withholding recognition evidence.

This application boundary turns supported underlying evidence into exactly one
retención projection.  It deliberately has no invoice-date argument and never
accepts an authored recognition coordinate: :mod:`withholding_recognition`
remains the only owner of that derivation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind, RetencionScheme, counterpart_source_kind
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from .retenciones import (
    Modelo180PropertyEvidence,
    Modelo193CapitalDetail,
    Modelo193PendingPaymentEvidence,
    RetencionObservation,
)
from .withholding_observation_service import (
    EconomicAllocation,
    SourceLiabilitySnapshot,
    WithholdingMutationEnvelope,
    WithholdingMutationMode,
    WithholdingMutationResult,
    WithholdingObservationService,
    WithholdingProjectionEntry,
    WithholdingProjectionIdentity,
    WithholdingProjectionRole,
    WithholdingWindowBaseline,
    WithholdingWindowScope,
)
from .withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecognition,
    WithholdingRecognitionEvidence,
    derive_withholding_recognition,
)


class WithholdingProducerError(ValueError):
    """Payload-free refusal for an unsupported producer-to-modelo route."""

    def __init__(self, code: str) -> None:
        """Keep public errors stable without echoing financial evidence."""
        self.code = code
        super().__init__(f"withholding producer refused: {code}")


class WithholdingEvidenceCaptureCommand(BaseModel):
    """One explicit allocation and its underlying recognition evidence.

    ``mode`` deliberately shares the atomic workflow vocabulary.  APPEND is
    the ordinary capture operation; a baseline-guarded REPLACE/CLEAR remains
    explicit rather than being inferred from an empty allocation collection.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    source_object_id: str = Field(min_length=1, max_length=128)
    source_revision_id: str = Field(min_length=1, max_length=128)
    allocation_id: str = Field(min_length=1, max_length=128)
    perceptor_nif: TaxIdIdentityToken = Field(min_length=1, max_length=16)
    perceptor_name: str = Field(default="", max_length=200)
    scheme: RetencionScheme
    taxable_base: Decimal = Field(ge=Decimal("0"))
    retencion_amount: Decimal = Field(ge=Decimal("0"))
    settlement_amount: Decimal = Field(ge=Decimal("0"))
    liability_snapshot: SourceLiabilitySnapshot
    recognition_evidence: WithholdingRecognitionEvidence
    mode: WithholdingMutationMode = WithholdingMutationMode.APPEND
    idempotency_key: str = Field(min_length=1, max_length=128)
    baseline: WithholdingWindowBaseline | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=500)
    supersedes_generation_id: str | None = Field(default=None, min_length=64, max_length=64)
    modelo_180_property: Modelo180PropertyEvidence | None = None
    modelo_190_detail: WithholdingObservation | None = None
    modelo_193_pending_payment: Modelo193PendingPaymentEvidence | None = None

    @model_validator(mode="after")
    def _annual_detail_matches_income_kind(self) -> WithholdingEvidenceCaptureCommand:
        is_rent = self.recognition_evidence.income_kind is WithholdingIncomeKind.URBAN_RENT
        if is_rent != (self.modelo_180_property is not None):
            raise ValueError("urban rent requires Modelo 180 property detail and other income forbids it")
        if self.modelo_180_property is not None and (
            self.modelo_180_property.accrual_year != self.recognition_evidence.applicable_year
        ):
            raise ValueError("Modelo 180 accrual year must match the recognition year")
        requires_modelo_190_detail = self.recognition_evidence.income_kind in {
            WithholdingIncomeKind.WORK,
            WithholdingIncomeKind.PROFESSIONAL,
        }
        if requires_modelo_190_detail != (self.modelo_190_detail is not None):
            raise ValueError(
                "work and professional income require Modelo 190 annual detail and other income forbids it"
            )
        is_capital = self.recognition_evidence.income_kind is WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL
        if not is_capital and self.modelo_193_pending_payment is not None:
            raise ValueError("only ordinary movable capital can carry Modelo 193 pending-payment evidence")
        return self


class WithholdingEvidenceCaptureResult(BaseModel):
    """The safe, derived result of a public evidence-capture command."""

    model_config = STRICT_FROZEN_CONFIG

    scope: WithholdingWindowScope
    recognition: WithholdingRecognition
    mutation: WithholdingMutationResult


class WithholdingProducer:
    """Capture a supported allocation through the sole atomic workflow port."""

    def __init__(self, *, service: WithholdingObservationService) -> None:
        """Bind the public command to the existing atomic mutation service."""
        self._service = service

    def capture(
        self,
        command: WithholdingEvidenceCaptureCommand | None,
    ) -> WithholdingEvidenceCaptureResult | None:
        """Capture evidence, or leave all persisted evidence untouched when omitted."""
        if command is None:
            return None
        _require_counterpart_source(command.source_kind)
        modelo = _modelo_for(command.recognition_evidence.income_kind, command.scheme)
        recognition = derive_withholding_recognition(command.recognition_evidence, modelo=modelo)
        if recognition.recognized_on.year != command.recognition_evidence.applicable_year:
            raise WithholdingProducerError("recognition_year_mismatch")
        scope = WithholdingWindowScope(
            modelo=modelo,
            period=_quarter_for(recognition.recognized_on),
        )
        modelo_193_capital = _modelo_193_capital_detail(
            pending_payment=command.modelo_193_pending_payment,
            command=command,
            recognition=recognition,
        )
        retencion_entry = WithholdingProjectionEntry(
            identity=WithholdingProjectionIdentity(
                source_kind=command.source_kind.value,
                source_object_id=command.source_object_id,
                source_revision_id=command.source_revision_id,
                recognition_event_id=recognition.recognition_event_id,
                settlement_event_id=recognition.settlement_event_id,
                allocation_id=command.allocation_id,
                projection_role=WithholdingProjectionRole.RETENCION,
            ),
            allocation=EconomicAllocation(
                liability=command.liability_snapshot,
                recognition_event_id=recognition.recognition_event_id,
                allocation_id=command.allocation_id,
                allocated_base=command.taxable_base,
                allocated_withholding=command.retencion_amount,
                allocated_settlement=command.settlement_amount,
            ),
            retencion=RetencionObservation(
                source_kind=command.source_kind,
                source_object_id=command.source_object_id,
                perceptor_nif=command.perceptor_nif,
                perceptor_name=command.perceptor_name,
                scheme=command.scheme,
                taxable_base=command.taxable_base,
                retencion_amount=command.retencion_amount,
                accrued_on=recognition.recognized_on.isoformat(),
                modelo_180_property=command.modelo_180_property,
                modelo_193_capital=modelo_193_capital,
            ),
        )
        entries: tuple[WithholdingProjectionEntry, ...]
        if command.mode is WithholdingMutationMode.CLEAR:
            entries = ()
        elif command.modelo_190_detail is None:
            entries = (retencion_entry,)
        else:
            entries = (
                retencion_entry,
                WithholdingProjectionEntry(
                    identity=WithholdingProjectionIdentity(
                        source_kind=command.source_kind.value,
                        source_object_id=command.source_object_id,
                        source_revision_id=command.source_revision_id,
                        recognition_event_id=recognition.recognition_event_id,
                        settlement_event_id=recognition.settlement_event_id,
                        allocation_id=command.allocation_id,
                        projection_role=WithholdingProjectionRole.PERCEPCION,
                    ),
                    allocation=retencion_entry.allocation,
                    percepcion=_annual_percepcion(
                        detail=command.modelo_190_detail,
                        command=command,
                        recognition=recognition,
                    ),
                ),
            )
        mutation = self._service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=command.mode,
                idempotency_key=command.idempotency_key,
                entries=entries,
                baseline=command.baseline,
                reason=command.reason,
                supersedes_generation_id=command.supersedes_generation_id,
            )
        )
        if mutation is None:
            raise AssertionError("a non-omitted withholding command must produce a mutation result")
        return WithholdingEvidenceCaptureResult(scope=scope, recognition=recognition, mutation=mutation)


def _require_counterpart_source(source_kind: BindingSourceKind) -> None:
    """Refuse any source provenance the retención aggregation cannot own."""
    try:
        counterpart_source_kind(source_kind)
    except ValueError as exc:
        raise WithholdingProducerError("unsupported_source_kind") from exc


def _modelo_for(income_kind: WithholdingIncomeKind, scheme: RetencionScheme) -> str:
    """Return the one grounded periodic modelo for a supported evidence kind."""
    allowed: tuple[RetencionScheme, ...]
    if income_kind is WithholdingIncomeKind.WORK:
        allowed = (RetencionScheme("rendimientos_trabajo"), RetencionScheme("rendimientos_trabajo_administrador"))
        modelo = "111"
    elif income_kind is WithholdingIncomeKind.PROFESSIONAL:
        allowed = (RetencionScheme("actividades_economicas"), RetencionScheme("actividades_profesionales"))
        modelo = "111"
    elif income_kind is WithholdingIncomeKind.URBAN_RENT:
        allowed = (RetencionScheme("arrendamiento_urbano"),)
        modelo = "115"
    elif income_kind is WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL:
        # The selected 2025 withholding-scheme catalogue is the scope here.
        # It deliberately does not make formalisation, IS, or IRNR branches
        # reachable through this resident-IRPF producer.
        allowed = (
            RetencionScheme("intereses"),
            RetencionScheme("dividendos"),
            RetencionScheme("otros_capital_mobiliario"),
        )
        modelo = "123"
    else:
        raise WithholdingProducerError("unsupported_income_projection")
    if scheme not in allowed:
        raise WithholdingProducerError("scheme_income_kind_mismatch")
    return modelo


def _quarter_for(recognized_on: date) -> Period:
    """Derive the exact ordinary quarterly filing coordinate from a date."""
    # ``recognized_on`` is a ``date`` by the typed recognition result.  Keeping
    # this operation here prevents invoice or caller-selected periods entering
    # the public producer boundary.
    year = recognized_on.year
    quarter = ((recognized_on.month - 1) // 3) + 1
    return Period.from_year_and_code(year, f"{quarter}T")


def _annual_percepcion(
    *,
    detail: WithholdingObservation,
    command: WithholdingEvidenceCaptureCommand,
    recognition: WithholdingRecognition,
) -> WithholdingObservation:
    """Validate annual detail against its source evidence without inventing it.

    The annual row is deliberately supplied through the existing typed Modelo
    190 contract.  Its identity, recognition date, recipient and quarterly
    economic amounts are the shared producer's derived facts; any conflicting
    caller declaration is refused rather than becoming a second authority.
    All other annual fields remain explicitly supplied by the caller's typed
    annual-detail record and retain that record's own absence semantics.
    """
    expected = {
        "source_id": command.source_object_id,
        "perceptor_tax_id": command.perceptor_nif,
        "perceptor_legal_name": command.perceptor_name,
        "transaction_date": recognition.recognized_on,
        "percibido_dinerario": command.taxable_base,
        "retencion_practicada": command.retencion_amount,
    }
    for field, value in expected.items():
        if getattr(detail, field) != value:
            raise WithholdingProducerError(f"modelo_190_detail_{field}_mismatch")
    if detail.source_allocation_id and detail.source_allocation_id != command.allocation_id:
        raise WithholdingProducerError("modelo_190_detail_source_allocation_id_mismatch")
    return detail.model_copy(update={"source_allocation_id": command.allocation_id})


def _modelo_193_capital_detail(
    *,
    pending_payment: Modelo193PendingPaymentEvidence | None,
    command: WithholdingEvidenceCaptureCommand,
    recognition: WithholdingRecognition,
) -> Modelo193CapitalDetail | None:
    """Couple the narrow 2025 pending-payment facts to their capital allocation.

    The only accepted cause is retained through a later correction so the
    payment-year phase can prove why it carries an earlier accrual year.  A
    same-year payment conflicts with that cause: it must use a separately
    grounded ordinary Modelo 193 path, rather than an invented pending row.
    """
    if pending_payment is None:
        return None
    detail = pending_payment.actual_recipient_detail
    expected = {
        "source_id": command.source_object_id,
        "perceptor_tax_id": command.perceptor_nif,
        "perceptor_legal_name": command.perceptor_name,
        "percibido_dinerario": command.taxable_base,
        "retencion_practicada": command.retencion_amount,
        "base_retenciones": command.taxable_base,
    }
    for field, value in expected.items():
        if getattr(detail, field) != value:
            raise WithholdingProducerError(f"modelo_193_detail_{field}_mismatch")
    if detail.source_allocation_id and detail.source_allocation_id != command.allocation_id:
        raise WithholdingProducerError("modelo_193_detail_source_allocation_id_mismatch")

    settlement = command.recognition_evidence.payment_or_satisfaction
    if settlement is None:
        expected_detail_date = recognition.recognized_on
    else:
        if settlement.event_id != recognition.settlement_event_id:
            raise AssertionError("ordinary-capital recognition must preserve its settlement event")
        if settlement.occurred_on.year <= recognition.recognized_on.year:
            raise WithholdingProducerError("modelo_193_nonpayment_cause_conflicts_with_same_year_settlement")
        expected_detail_date = settlement.occurred_on
    if detail.transaction_date != expected_detail_date:
        raise WithholdingProducerError("modelo_193_detail_transaction_date_mismatch")

    return Modelo193CapitalDetail(
        pending_payment=pending_payment.model_copy(
            update={
                "actual_recipient_detail": detail.model_copy(update={"source_allocation_id": command.allocation_id})
            }
        ),
        recognition_event_id=recognition.recognition_event_id,
        settlement_event=settlement,
    )


__all__ = [
    "WithholdingEvidenceCaptureCommand",
    "WithholdingEvidenceCaptureResult",
    "WithholdingProducer",
    "WithholdingProducerError",
]
