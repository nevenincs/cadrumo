"""Canonical immutable projection for one persisted Modelo work target."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.estado_casilla_oficial import EstadoCasillaOficial
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.modelo_work_progress_state import ModeloWorkProgressState
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import OperatorActionAxis
from ...core.period import Period
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.handoffs import RelationConsumptionChannel
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaConstraints
from ...domain.filing.schema import ModeloScalar, ModeloValueKind
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    VerificationCompletenessStatus,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
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


def build_modelo_work_review(
    bucket_id: BucketId,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
) -> ModeloWorkReview:
    """Assemble the sole read record for a persisted modelo work target."""
    from ._work_review_assembly import assemble_modelo_work_review

    return assemble_modelo_work_review(
        bucket_id,
        modelo,
        filing_year=filing_year,
        period=period,
        authority=authority,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
    )


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
    "build_modelo_work_review",
]
