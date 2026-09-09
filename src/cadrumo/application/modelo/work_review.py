"""Canonical immutable projection for one persisted Modelo work target."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from secrets import token_bytes
from threading import RLock
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.estado_casilla_oficial import EstadoCasillaOficial
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
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
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    VerificationCompletenessStatus,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
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


_WORK_REVIEW_CAPTURE_MAX_ATTEMPTS = 8
_work_review_capture_process_pid = os.getpid()
_work_review_capture_process_nonce = token_bytes(32)
_work_review_capture_domains: set[str] = set()
_work_review_capture_lock = RLock()
_work_review_capture_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_work_review_capture_generation = 0


class ModeloWorkReviewCaptureError(ModeloError, RuntimeError):
    """Raised when a work review cannot be assembled over one stable window."""


@dataclass(frozen=True, slots=True)
class ModeloWorkReviewCapture:
    """One complete work review and its currentness coordinate.

    The review is the exact record :func:`build_modelo_work_review` assembled;
    no field is reconstructed here and no parallel assembler exists. The
    physical root, bucket, namespace and key identity that produced it are
    folded into the opaque comparison domain and never exposed.
    """

    review: ModeloWorkReview
    comparison_domain: str
    generation: int

    def require_current(self, current: ModeloWorkReviewCurrentCoordinate) -> ModeloWorkReviewCapture:
        """Refuse a currentness comparison outside this owner process domain."""
        _require_work_review_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class ModeloWorkReviewCurrentCoordinate:
    """Opaque same-process coordinate for one work-review owner scope."""

    comparison_domain: str
    generation: int

    def require_current(self, captured: ModeloWorkReviewCapture) -> ModeloWorkReviewCurrentCoordinate:
        """Require a capture from this exact owner scope and process incarnation."""
        _require_work_review_process_domain(self.comparison_domain)
        _require_work_review_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise ModeloWorkReviewCaptureError(
                translated_message="errors.refused.modelo_work_review_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise ModeloWorkReviewCaptureError(
                translated_message="errors.refused.modelo_work_review_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_work_review_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _work_review_capture_process_pid != os.getpid():
        raise ModeloWorkReviewCaptureError(
            translated_message="errors.refused.modelo_work_review_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _work_review_capture_lock:
        known = domain in _work_review_capture_domains
    if not known:
        raise ModeloWorkReviewCaptureError(
            translated_message="errors.refused.modelo_work_review_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _work_review_comparison_domain(*, bucket_id: str, modelo: ModeloCode, filing_year: int, period: Period) -> str:
    """Mint the non-persisted coordinate domain for one review owner scope."""
    from ...core.config import load_settings

    domain = content_hash_hex(
        {
            "owner": "application.modelo.work_review",
            "storage_root": str(load_settings().cadrumo_local_storage_root),
            "namespace": "modelo.work_review",
            "bucket_id": bucket_id,
            "modelo": str(modelo),
            "filing_year": filing_year,
            "period": period.registry_token,
            "process_incarnation": _work_review_capture_process_nonce.hex(),
        }
    )
    with _work_review_capture_lock:
        _work_review_capture_domains.add(domain)
    return domain


def _work_review_owner_observation(
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
) -> tuple[str, ...]:
    """Read the three joined catalogue limbs into one owner observation."""
    _work_units, work_unit_revision = work_unit_repository.load_revisioned()
    _calculations, calculation_revision = calculation_repository.load_revisioned()
    verification_digest = content_hash_hex(
        require_verification_report_coordinates_current(verification_repository.load()).model_dump(mode="json")
    )
    return (work_unit_revision, calculation_revision, verification_digest)


def _work_review_generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _work_review_capture_generation
    with _work_review_capture_lock:
        recorded = _work_review_capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _work_review_capture_generation += 1
        _work_review_capture_generations[domain] = (observation, _work_review_capture_generation)
        return _work_review_capture_generation


def read_modelo_work_review_current_coordinate(
    bucket_id: BucketId,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
) -> ModeloWorkReviewCurrentCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    observation = _work_review_owner_observation(
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
    )
    domain = _work_review_comparison_domain(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )
    return ModeloWorkReviewCurrentCoordinate(
        comparison_domain=domain,
        generation=_work_review_generation_for(domain, observation),
    )


def capture_modelo_work_review(
    bucket_id: BucketId,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
) -> ModeloWorkReviewCapture:
    """Assemble one review over a window in which its joined limbs did not move.

    The owner observation is read either side of the sole
    :func:`build_modelo_work_review` join. A write landing mid-assembly is
    retried rather than published, so a capture never carries a review stitched
    across two catalogue states. The review itself is returned exactly as the
    assembler produced it.
    """
    for _attempt in range(_WORK_REVIEW_CAPTURE_MAX_ATTEMPTS):
        before = _work_review_owner_observation(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            verification_repository=verification_repository,
        )
        review = build_modelo_work_review(
            bucket_id,
            modelo,
            filing_year,
            period,
            authority=authority,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            verification_repository=verification_repository,
        )
        after = _work_review_owner_observation(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            verification_repository=verification_repository,
        )
        if before != after:
            continue
        domain = _work_review_comparison_domain(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
        )
        return ModeloWorkReviewCapture(
            review=review,
            comparison_domain=domain,
            generation=_work_review_generation_for(domain, after),
        )
    raise ModeloWorkReviewCaptureError(
        translated_message="errors.refused.modelo_work_review_capture_not_current",
        context={"reason": "contended", "attempts": _WORK_REVIEW_CAPTURE_MAX_ATTEMPTS},
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
    "ModeloWorkReviewCapture",
    "ModeloWorkReviewCaptureError",
    "ModeloWorkReviewCasilla",
    "ModeloWorkReviewCurrentCoordinate",
    "build_modelo_work_review",
    "capture_modelo_work_review",
    "read_modelo_work_review_current_coordinate",
]
