"""Public capture command for grounded withholding recognition evidence.

This application boundary turns supported underlying evidence into exactly one
retención projection.  It deliberately has no invoice-date argument and never
accepts an authored recognition coordinate: :mod:`withholding_recognition`
remains the only owner of that derivation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.aggregation import BindingSourceKind, RetencionScheme, counterpart_source_kind
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from .retenciones import RetencionObservation
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
        entry = WithholdingProjectionEntry(
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
            ),
        )
        entries = () if command.mode is WithholdingMutationMode.CLEAR else (entry,)
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


__all__ = [
    "WithholdingEvidenceCaptureCommand",
    "WithholdingEvidenceCaptureResult",
    "WithholdingProducer",
    "WithholdingProducerError",
]
