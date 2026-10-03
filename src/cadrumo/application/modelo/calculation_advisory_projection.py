"""Strict, locale-neutral calculation advisories captured with the writer's authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import BindingId, LegalRefId, RelationId, SourceRefId
from ...domain.calculations.registry.modelo_rendering import modelo_rendering_value
from ..aggregation.source_mesh import (
    DIAGNOSTIC_MESSAGE_MAX_LENGTH,
    DIAGNOSTIC_REMEDY_MAX_LENGTH,
    CalculationSourceDiagnostic,
    CalculationSourceDiagnosticReason,
)
from .calculate_input import Modelo202ModalitySummary, ModeloWorkCalculationServiceResult
from .lifecycle_advisories import ModeloM210PlazoAdvisoryV1
from .work_plazo import (
    M210PlazoResolution,
    ModeloWorkConditionalRecargoPreview,
    ModeloWorkDeadlinePosture,
    modelo_work_deadline_posture,
)


class CalculationSourceDiagnosticSnapshot(BaseModel):
    """Every current canonical diagnostic field, with no open-ended wire payload."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    reason: CalculationSourceDiagnosticReason
    source_kind: str = Field(min_length=1, max_length=64)
    binding_source: BindingSourceKind | None = None
    message: str = Field(max_length=DIAGNOSTIC_MESSAGE_MAX_LENGTH)
    remedy: str | None = Field(default=None, min_length=1, max_length=DIAGNOSTIC_REMEDY_MAX_LENGTH)
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref: str | None = Field(default=None, min_length=1, max_length=256)
    binding_id: BindingId | None = None
    relation_id: RelationId | None = None
    relation_ids: tuple[RelationId, ...] = ()
    casilla_id: CasillaId | None = None
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    asserted_legal_refs: tuple[LegalRefId, ...] = ()
    out_of_window_count: int | None = Field(default=None, ge=1)
    out_of_window_min_filing_date: date | None = None
    out_of_window_max_filing_date: date | None = None

    @classmethod
    def from_diagnostic(cls, diagnostic: CalculationSourceDiagnostic) -> Self:
        """Capture the already validated diagnostic without changing its message."""
        return cls.model_validate(diagnostic.model_dump(mode="python"))

    def to_diagnostic(self) -> CalculationSourceDiagnostic:
        """Revalidate the transported facts with the canonical domain owner."""
        return CalculationSourceDiagnostic.model_validate(self.model_dump(mode="python"))

    @model_validator(mode="after")
    def _canonical_diagnostic(self) -> Self:
        self.to_diagnostic()
        return self


class Modelo202ModalitySnapshot(BaseModel):
    """The registry-selected Modelo 202 modality and its existing explanation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modality: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=1024)

    @classmethod
    def from_modality(cls, modality: Modelo202ModalitySummary) -> Self:
        """Freeze the existing calculated modality and explanation."""
        return cls(modality=modality.modality, reason=modality.reason)

    def to_modality(self) -> Modelo202ModalitySummary:
        """Restore the existing CLI renderer's application value."""
        return Modelo202ModalitySummary(modality=self.modality, reason=self.reason)


class ModeloWorkRecargoPreviewSnapshot(BaseModel):
    """Rate-only Article 27 preview; never a liability or filing assessment."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    band_id: str = Field(min_length=1, max_length=128)
    surcharge_pct: str = Field(min_length=1, max_length=128)
    interest_applies: bool
    legal_ref: str = Field(min_length=1, max_length=256)
    rate_reference_on: date
    assessment_status: Literal["unassessed"] = "unassessed"

    @field_validator("surcharge_pct")
    @classmethod
    def _finite_decimal(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("recargo rate must be decimal text") from exc
        if not amount.is_finite():
            raise ValueError("recargo rate must be finite")
        return value

    @classmethod
    def from_preview(cls, preview: ModeloWorkConditionalRecargoPreview) -> Self:
        """Carry rate-only preview facts without assessing liability."""
        return cls(
            band_id=preview.band_id,
            surcharge_pct=str(preview.surcharge_pct),
            interest_applies=preview.interest_applies,
            legal_ref=preview.legal_ref,
            rate_reference_on=preview.rate_reference_on,
            assessment_status=preview.assessment_status,
        )

    def to_preview(self) -> ModeloWorkConditionalRecargoPreview:
        """Revalidate the preview with its canonical application model."""
        return ModeloWorkConditionalRecargoPreview(
            band_id=self.band_id,
            surcharge_pct=Decimal(self.surcharge_pct),
            interest_applies=self.interest_applies,
            legal_ref=self.legal_ref,
            rate_reference_on=self.rate_reference_on,
            assessment_status=self.assessment_status,
        )


class ModeloWorkDeadlinePostureSnapshot(BaseModel):
    """The canonical deadline posture and all unassessed recargo preview facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    closes_on: date
    days_remaining: int | None = Field(default=None, ge=0)
    days_overdue: int | None = Field(default=None, ge=0)
    conditional_recargo_preview: ModeloWorkRecargoPreviewSnapshot | None = None

    @classmethod
    def from_posture(cls, posture: ModeloWorkDeadlinePosture) -> Self:
        """Freeze the already resolved filing deadline posture."""
        return cls(
            closes_on=posture.closes_on,
            days_remaining=posture.days_remaining,
            days_overdue=posture.days_overdue,
            conditional_recargo_preview=(
                ModeloWorkRecargoPreviewSnapshot.from_preview(posture.conditional_recargo_preview)
                if posture.conditional_recargo_preview is not None
                else None
            ),
        )

    def to_posture(self) -> ModeloWorkDeadlinePosture:
        """Restore the canonical one-sided deadline posture."""
        return ModeloWorkDeadlinePosture(
            closes_on=self.closes_on,
            days_remaining=self.days_remaining,
            days_overdue=self.days_overdue,
            conditional_recargo_preview=(
                self.conditional_recargo_preview.to_preview() if self.conditional_recargo_preview is not None else None
            ),
        )

    @model_validator(mode="after")
    def _canonical_posture(self) -> Self:
        self.to_posture()
        if self.conditional_recargo_preview is not None and self.days_overdue is None:
            raise ValueError("recargo preview requires an overdue deadline")
        return self


class ModeloCalculationAdvisories(BaseModel):
    """All calculation-only presentation facts frozen at the admitted writer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    version: Literal[1] = 1
    source_diagnostics: tuple[CalculationSourceDiagnosticSnapshot, ...]
    modality: Modelo202ModalitySnapshot | None
    m210_plazo: tuple[ModeloM210PlazoAdvisoryV1, ...]
    deadline: ModeloWorkDeadlinePostureSnapshot | None
    fallback_recargo_legal_ref: str | None = Field(default=None, min_length=1, max_length=256)

    @classmethod
    def from_result(
        cls,
        result: ModeloWorkCalculationServiceResult,
        *,
        operation: PinnedAuthorityOperation,
    ) -> Self:
        """Capture all advisories under the calculation's pinned registry lease."""
        posture = modelo_work_deadline_posture(result.work_unit, operation=operation)
        fallback_ref = (
            modelo_rendering_value("extemporaneous_recargo.legal_ref", authority=operation)
            if posture is not None and posture.days_overdue is not None and posture.conditional_recargo_preview is None
            else None
        )
        return cls(
            source_diagnostics=tuple(
                CalculationSourceDiagnosticSnapshot.from_diagnostic(row) for row in result.source_diagnostics
            ),
            modality=(Modelo202ModalitySnapshot.from_modality(result.modality) if result.modality else None),
            m210_plazo=tuple(ModeloM210PlazoAdvisoryV1.from_resolution(row) for row in result.plazo_resolutions),
            deadline=ModeloWorkDeadlinePostureSnapshot.from_posture(posture) if posture is not None else None,
            fallback_recargo_legal_ref=fallback_ref,
        )

    def to_diagnostics(self) -> tuple[CalculationSourceDiagnostic, ...]:
        """Restore every diagnostic in its original order."""
        return tuple(row.to_diagnostic() for row in self.source_diagnostics)

    def to_modality(self) -> Modelo202ModalitySummary | None:
        """Restore the optional Modelo 202 modality summary."""
        return self.modality.to_modality() if self.modality is not None else None

    def to_plazo_resolutions(self) -> tuple[M210PlazoResolution, ...]:
        """Restore the existing M210 notice inputs in order."""
        return tuple(row.to_resolution() for row in self.m210_plazo)

    def to_deadline_posture(self) -> ModeloWorkDeadlinePosture | None:
        """Restore the deadline and unassessed rate preview."""
        return self.deadline.to_posture() if self.deadline is not None else None

    @model_validator(mode="after")
    def _fallback_only_for_unpreviewed_overdue(self) -> Self:
        needs_ref = (
            self.deadline is not None
            and self.deadline.days_overdue is not None
            and self.deadline.conditional_recargo_preview is None
        )
        if (self.fallback_recargo_legal_ref is not None) != needs_ref:
            raise ValueError("deadline fallback legal reference does not match posture")
        return self


__all__ = [
    "CalculationSourceDiagnosticSnapshot",
    "Modelo202ModalitySnapshot",
    "ModeloCalculationAdvisories",
    "ModeloWorkDeadlinePostureSnapshot",
    "ModeloWorkRecargoPreviewSnapshot",
]
