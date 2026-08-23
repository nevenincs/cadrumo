"""Canonical read projection for one persisted modelo work target."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    BindingSourceKind,
    CasillaId,
    EstadoCasillaOficial,
    ModeloWorkProgressState,
    OperatorActionAxis,
    Period,
)
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
from ...domain.calculations.registry import (
    BindingId,
    CasillaConstraints,
    FormulaId,
    InputKind,
    LegalRefId,
    RelationConsumptionChannel,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.filing import ModeloScalar, ModeloValueKind
from ...domain.modelos import (
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFinding,
    VerificationCompletenessStatus,
)
from ._row_source_identity_replay import ModeloRowSourceFingerprint


class ModeloWorkOriginAnomaly(StrEnum):
    """Closed disagreements between declared and realised value origin."""

    BROKEN_CALCULATION_CHAIN = "broken_calculation_chain"
    OPERATOR_OVERRIDE = "operator_override"


class ModeloWorkRelationConsumption(BaseModel):
    """One relation channel that can feed a reviewed casilla."""

    model_config = STRICT_FROZEN_CONFIG
    relation_id: RelationId
    channels: tuple[RelationConsumptionChannel, ...]


class ModeloWorkBindingOrigin(BaseModel):
    """One declared binding path and whether replay resolution materialised it."""

    model_config = STRICT_FROZEN_CONFIG
    binding_id: BindingId
    source: BindingSourceKind
    resolved: bool


class ModeloWorkFormulaOrigin(BaseModel):
    """Declared formula reference and its registry operand lineage."""

    model_config = STRICT_FROZEN_CONFIG
    formula_id: FormulaId
    operand_refs: tuple[str, ...]


_BlockerFact = str | int | bool | Decimal | None


class BlockerRef(BaseModel):
    """One native blocker projected onto the shared operator-action axis."""

    model_config = STRICT_FROZEN_CONFIG
    axis: OperatorActionAxis
    native_code: str = Field(min_length=1)
    facts: Mapping[str, _BlockerFact] = Field(default_factory=dict)

    @field_validator("facts")
    @classmethod
    def _freeze_facts(cls, value: Mapping[str, _BlockerFact]) -> Mapping[str, _BlockerFact]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("facts")
    def _serialize_facts(self, value: Mapping[str, _BlockerFact]) -> dict[str, _BlockerFact]:
        return dict(value)


class ModeloWorkReviewCasilla(BaseModel):
    """Schema, origin, value, grounding, and blockers for one casilla."""

    model_config = STRICT_FROZEN_CONFIG
    casilla_id: CasillaId
    number: str
    segmento: str | None
    official_reference: str | None
    section_path: tuple[str, ...]
    label: str
    data_type: str
    constraints: CasillaConstraints | None
    declared_input_kind: InputKind
    concrete_bindings: tuple[ModeloWorkBindingOrigin, ...]
    concrete_formula: ModeloWorkFormulaOrigin | None
    relation_consumption: tuple[ModeloWorkRelationConsumption, ...]
    realised_kind: ModeloValueKind
    value: ModeloScalar
    origin_anomaly: ModeloWorkOriginAnomaly | None
    estado_casilla_oficial: EstadoCasillaOficial
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    formula_id: FormulaId | None
    blocked_by: tuple[BlockerRef, ...] = ()


class ModeloWorkProgressDenominator(BaseModel):
    """Identity of the revision manifest against which counts are measured."""

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["calculation_completeness_manifest"] = "calculation_completeness_manifest"
    registry_revision_id: RevisionId
    source_ref: SourceRefId


def _validate_undefined_progress(
    values: tuple[int | None, int | None, ModeloWorkProgressDenominator | None],
) -> None:
    """Reject counts attached to the explicit undefined progress state."""
    if any(value is not None for value in values):
        raise ValueError("undefined modelo work progress cannot carry counts or a denominator")


def _validate_defined_progress(
    *,
    state: ModeloWorkProgressState,
    materialised_count: int | None,
    target_count: int | None,
    denominator: ModeloWorkProgressDenominator | None,
) -> None:
    """Validate count and manifest invariants for a measured progress state."""
    if materialised_count is None or target_count is None or denominator is None:
        raise ValueError("defined modelo work progress requires both counts and its manifest denominator")
    if materialised_count > target_count:
        raise ValueError("materialised_count cannot exceed target_count")
    if state is ModeloWorkProgressState.COMPLETE and materialised_count != target_count:
        raise ValueError("complete modelo work progress requires every manifest casilla to materialise")


class ModeloWorkProgress(BaseModel):
    """N-of-M progress with an explicit, registry-authored denominator."""

    model_config = STRICT_FROZEN_CONFIG
    state: ModeloWorkProgressState
    materialised_count: int | None = Field(default=None, ge=0)
    target_count: int | None = Field(default=None, gt=0)
    denominator: ModeloWorkProgressDenominator | None = None

    @model_validator(mode="after")
    def _counts_match_state(self) -> ModeloWorkProgress:
        values = (self.materialised_count, self.target_count, self.denominator)
        if self.state is ModeloWorkProgressState.UNDEFINED:
            _validate_undefined_progress(values)
            return self
        _validate_defined_progress(
            state=self.state,
            materialised_count=self.materialised_count,
            target_count=self.target_count,
            denominator=self.denominator,
        )
        return self


class ModeloWorkReview(BaseModel):
    """Frozen application-owned review record for one modelo work target."""

    model_config = STRICT_FROZEN_CONFIG
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None
    lifecycle_state: CalculationRevisionState | None
    verification_outcome: VerificationCompletenessStatus | None
    progress: ModeloWorkProgress
    casillas: tuple[ModeloWorkReviewCasilla, ...]
    findings: tuple[ModeloVerificationFinding, ...]
    blockers: tuple[BlockerRef, ...]
    row_source_fingerprints: tuple[ModeloRowSourceFingerprint, ...] = ()


__all__ = [
    "BlockerRef",
    "ModeloWorkBindingOrigin",
    "ModeloWorkFormulaOrigin",
    "ModeloWorkOriginAnomaly",
    "ModeloWorkProgress",
    "ModeloWorkProgressDenominator",
    "ModeloWorkRelationConsumption",
    "ModeloWorkReview",
    "ModeloWorkReviewCasilla",
]
