"""Canonical immutable projection for one persisted Modelo work target."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from secrets import token_bytes
from threading import RLock
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, FormulaDefinition, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaConstraints,
    CasillaDefinition,
    RelationDefinition,
)

from ...core import (
    STRICT_FROZEN_CONFIG,
    BindingSourceKind,
    CasillaId,
    EstadoCasillaOficial,
    ModeloWorkProgressState,
    OperatorActionAxis,
    Period,
)
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
from ...domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)
from ...domain.calculations.registry.bindings import (
    CasillaObservation,
    casillas_by_binding,
)
from ...domain.calculations.registry.export import (
    clasificar_casillas_oficiales,
    derive_export_layouts_from_bindings,
)
from ...domain.calculations.registry.export_parse import xml_dictionary_entries
from ...domain.calculations.registry.handoffs import (
    RelationConsumptionChannel,
    relation_consumption_channels,
    relation_consumption_index,
)
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.queries import relations_by_target_binding
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_casilla_refs,
    expression_relation_refs,
    revision_date_binding_ids,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.temporal import select_revision
from ...domain.filing import ModeloScalar, ModeloValueKind
from ...domain.modelos import (
    OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND,
    CalculationRevision,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ModeloCode,
    ModeloError,
    ModeloVerificationFinding,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnit,
    WorkUnitCatalogue,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ._action_errors import (
    CalculationRevisionNotFoundError,
    StoredCalculationDriftError,
    WorkUnitNotFoundError,
)
from ._row_source_identity_replay import ModeloRowSourceFingerprint, revision_row_source_fingerprints_for_review
from .work_addressing import (
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    select_modelo_work_resolution,
)


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


@dataclass(frozen=True, slots=True)
class _ReviewRowContext:
    """Precomputed registry and persistence facts shared by every review row."""

    revision: CalculationRevision | None
    bindings_by_id: Mapping[BindingId, DataBindingDefinition]
    formulas_by_id: Mapping[FormulaId, FormulaDefinition]
    binding_to_casillas: Mapping[BindingId, tuple[CasillaId, ...]]
    relations_by_binding: Mapping[BindingId, tuple[RelationDefinition, ...]]
    relations: tuple[RelationDefinition, ...]
    relation_channels: Mapping[RelationId, tuple[RelationConsumptionChannel, ...]]
    persisted_decimal_bindings: Mapping[BindingId, Decimal]
    persisted_binding_ids: frozenset[BindingId]
    estados_casillas_oficiales: Mapping[CasillaId, EstadoCasillaOficial]
    official_references: Mapping[CasillaId, str | None]
    blocking_findings: tuple[ModeloVerificationFinding, ...]


def _work_unit_for_target(
    *,
    bucket_id: BucketId,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId,
    catalogue: WorkUnitCatalogue,
) -> WorkUnit:
    resolution = select_modelo_work_resolution(
        ModeloWorkSelectorRequest(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=registry_revision_id,
        ),
        catalogue=catalogue,
        bucket_id=bucket_id,
    )
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={
                "bucket_id": bucket_id,
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
            },
        )
    return resolution.work_unit


def _current_revision(
    work_unit: WorkUnit,
    repository: CalculationRevisionCatalogueRepositoryProtocol,
) -> CalculationRevision | None:
    revision_id = work_unit.current_calculation_revision_id
    if revision_id is None:
        return None
    revision = repository.load().get(revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": revision_id, "work_unit_id": work_unit.work_unit_id},
        )
    if revision.work_unit_id != work_unit.work_unit_id:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={
                "calculation_revision_id": revision.calculation_revision_id,
                "work_unit_id": work_unit.work_unit_id,
                "stored_work_unit_id": revision.work_unit_id,
            },
        )
    return revision


def _latest_verification(
    revision: CalculationRevision | None,
    repository: VerificationReportCatalogueRepositoryProtocol,
) -> VerificationReport | None:
    if revision is None:
        return None
    reports = repository.load().for_calculation_revision(revision.calculation_revision_id)
    return reports[-1] if reports else None


def _persisted_decimal_bindings(
    *, snapshot: RegistrySnapshot, revision: CalculationRevision | None
) -> Mapping[BindingId, Decimal]:
    """Read only historical decimal replay facts, never live profile state."""
    if revision is None:
        empty_bindings: dict[BindingId, Decimal] = {}
        return empty_bindings
    enum_ids = enum_consumed_binding_ids(snapshot.revision)
    date_ids = revision_date_binding_ids(snapshot.revision)
    decimal_bindings: dict[BindingId, Decimal] = {}
    for binding_id, raw_value in revision.binding_overrides.items():
        if binding_id in enum_ids or binding_id in date_ids:
            continue
        try:
            parsed_value: Decimal = Decimal(str(raw_value))
            decimal_bindings[binding_id] = parsed_value
        except InvalidOperation as exc:
            raise StoredCalculationDriftError(
                translated_message="errors.storage.stored_data_validation_boundary",
                context={
                    "calculation_revision_id": revision.calculation_revision_id,
                    "binding_id": binding_id,
                },
            ) from exc
    return decimal_bindings


def _official_references(
    snapshot: RegistrySnapshot,
    authority: ValidatedRegistryAuthority,
    estados_casillas_oficiales: Mapping[CasillaId, EstadoCasillaOficial],
) -> Mapping[CasillaId, str | None]:
    xml_paths: dict[CasillaId, str] = {}
    for layout in derive_export_layouts_from_bindings(snapshot.revision):
        if layout.dictionary_source_ref is None:
            continue
        for entry in xml_dictionary_entries(layout, source_root=authority.source_root, sources=snapshot.sources):
            if entry.casilla_id is not None:
                xml_paths.setdefault(entry.casilla_id, entry.path)
    return {
        casilla.id: xml_paths.get(casilla.id, casilla.number)
        if estados_casillas_oficiales[casilla.id] is EstadoCasillaOficial.ADDRESSED
        else None
        for casilla in snapshot.revision.casillas
    }


def _blocker_ref(finding: ModeloVerificationFinding) -> BlockerRef:
    return BlockerRef(
        axis=OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[finding.kind],
        native_code=finding.kind.value,
        facts=finding.message_facts,
    )


def _casilla_observation(
    revision: CalculationRevision | None,
    casilla_id: CasillaId,
) -> CasillaObservation | None:
    if revision is None:
        return None
    return next(
        (item for item in revision.observations if item.casilla_id == casilla_id),
        None,
    )


def _persisted_binding_values(
    binding_ids: tuple[BindingId, ...],
    resolved_bindings: Mapping[BindingId, Decimal],
) -> tuple[Decimal, ...]:
    return tuple(resolved_bindings[item] for item in binding_ids if item in resolved_bindings)


def _classify_observed_value(
    *,
    observation: CasillaObservation,
    input_kind: InputKind,
    formula_id: FormulaId | None,
    binding_ids: tuple[BindingId, ...],
    resolved_bindings: Mapping[BindingId, Decimal],
) -> tuple[ModeloValueKind, ModeloScalar, ModeloWorkOriginAnomaly | None]:
    if formula_id is not None:
        return ModeloValueKind.COMPUTED, observation.value, None
    if input_kind is not InputKind.BOUND:
        return ModeloValueKind.LITERAL, observation.value, None
    if observation.absent_by_design:
        return ModeloValueKind.INHERITED, observation.value, None
    binding_values = _persisted_binding_values(binding_ids, resolved_bindings)
    if binding_values and observation.value not in binding_values:
        return ModeloValueKind.LITERAL, observation.value, ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE
    return ModeloValueKind.INHERITED, observation.value, None


def _realised_value(
    *,
    casilla_id: CasillaId,
    input_kind: InputKind,
    formula_id: FormulaId | None,
    binding_ids: tuple[BindingId, ...],
    revision: CalculationRevision | None,
    resolved_bindings: Mapping[BindingId, Decimal],
) -> tuple[ModeloValueKind, ModeloScalar, ModeloWorkOriginAnomaly | None]:
    """Classify the realised value from persisted observations and replay facts.

    ``OPERATOR_OVERRIDE`` is emitted only for an observable disagreement between
    a persisted bound value and the persisted casilla observation. Caller
    casilla inputs have final precedence during calculation, so that mismatch is
    durable evidence of an override. An equal-value explicit input is not
    distinguishable after persistence and therefore does not claim an anomaly.
    """
    observation = _casilla_observation(revision, casilla_id)
    if observation is None:
        anomaly = ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN if input_kind is InputKind.COMPUTED else None
        return ModeloValueKind.EMPTY, None, anomaly
    return _classify_observed_value(
        observation=observation,
        input_kind=input_kind,
        formula_id=formula_id,
        binding_ids=binding_ids,
        resolved_bindings=resolved_bindings,
    )


def _casilla_binding_ids(
    casilla_id: CasillaId,
    binding_to_casillas: Mapping[BindingId, tuple[CasillaId, ...]],
) -> tuple[BindingId, ...]:
    return tuple(binding_id for binding_id, casilla_ids in binding_to_casillas.items() if casilla_id in casilla_ids)


def _formula_origin(formula: FormulaDefinition | None) -> ModeloWorkFormulaOrigin | None:
    if formula is None:
        return None
    return ModeloWorkFormulaOrigin(
        formula_id=formula.id,
        operand_refs=tuple(
            dict.fromkeys(
                (
                    *expression_casilla_refs(formula.expression),
                    *expression_binding_refs(formula.expression),
                    *expression_relation_refs(formula.expression),
                ),
            ),
        ),
    )


def _relation_consumptions(
    *,
    binding_ids: tuple[BindingId, ...],
    formula: FormulaDefinition | None,
    context: _ReviewRowContext,
) -> tuple[ModeloWorkRelationConsumption, ...]:
    formula_relation_ids: set[RelationId] = (
        set() if formula is None else set(expression_relation_refs(formula.expression))
    )
    formula_binding_ids: set[BindingId] = set() if formula is None else set(expression_binding_refs(formula.expression))
    candidate_ids = {
        relation.id
        for binding_id in (*binding_ids, *formula_binding_ids)
        for relation in context.relations_by_binding.get(binding_id, ())
    }
    candidate_ids.update(relation.id for relation in context.relations if relation.id in formula_relation_ids)
    return tuple(
        ModeloWorkRelationConsumption(
            relation_id=relation.id,
            channels=context.relation_channels[relation.id],
        )
        for relation in context.relations
        if relation.id in candidate_ids
    )


def _binding_origins(
    binding_ids: tuple[BindingId, ...],
    context: _ReviewRowContext,
) -> tuple[ModeloWorkBindingOrigin, ...]:
    return tuple(
        ModeloWorkBindingOrigin(
            binding_id=binding_id,
            source=context.bindings_by_id[binding_id].source,
            resolved=binding_id in context.persisted_binding_ids,
        )
        for binding_id in binding_ids
    )


def _review_casilla(
    casilla: CasillaDefinition,
    context: _ReviewRowContext,
) -> ModeloWorkReviewCasilla:
    binding_ids = _casilla_binding_ids(casilla.id, context.binding_to_casillas)
    formula = context.formulas_by_id.get(casilla.formula) if casilla.formula is not None else None
    realised_kind, value, anomaly = _realised_value(
        casilla_id=casilla.id,
        input_kind=casilla.input_kind,
        formula_id=casilla.formula,
        binding_ids=binding_ids,
        revision=context.revision,
        resolved_bindings=context.persisted_decimal_bindings,
    )
    return ModeloWorkReviewCasilla(
        casilla_id=casilla.id,
        number=casilla.number,
        segmento=casilla.segmento,
        official_reference=context.official_references[casilla.id],
        section_path=casilla.section,
        label=casilla.label,
        data_type=casilla.data_type,
        constraints=casilla.constraints,
        declared_input_kind=casilla.input_kind,
        concrete_bindings=_binding_origins(binding_ids, context),
        concrete_formula=_formula_origin(formula),
        relation_consumption=_relation_consumptions(
            binding_ids=binding_ids,
            formula=formula,
            context=context,
        ),
        realised_kind=realised_kind,
        value=value,
        origin_anomaly=anomaly,
        estado_casilla_oficial=context.estados_casillas_oficiales[casilla.id],
        legal_refs=tuple(casilla.legal_refs),
        source_refs=tuple(casilla.source_refs),
        formula_id=casilla.formula,
        blocked_by=tuple(
            _blocker_ref(finding) for finding in context.blocking_findings if finding.casilla_id == casilla.id
        ),
    )


def _review_row_context(
    *,
    snapshot: RegistrySnapshot,
    authority: ValidatedRegistryAuthority,
    revision: CalculationRevision | None,
    blocking_findings: tuple[ModeloVerificationFinding, ...],
) -> _ReviewRowContext:
    estados_casillas_oficiales = clasificar_casillas_oficiales(
        snapshot.revision,
        source_root=authority.source_root,
        sources=snapshot.sources,
    )
    consumption_index = relation_consumption_index(snapshot.revision)
    return _ReviewRowContext(
        revision=revision,
        bindings_by_id={binding.id: binding for binding in snapshot.revision.bindings},
        formulas_by_id={formula.id: formula for formula in snapshot.revision.formulas},
        binding_to_casillas=casillas_by_binding(snapshot.revision),
        relations_by_binding=relations_by_target_binding(snapshot.revision),
        relations=snapshot.revision.relations,
        relation_channels={
            relation.id: relation_consumption_channels(relation, consumption_index)
            for relation in snapshot.revision.relations
        },
        persisted_decimal_bindings=_persisted_decimal_bindings(snapshot=snapshot, revision=revision),
        persisted_binding_ids=frozenset(() if revision is None else revision.binding_overrides),
        estados_casillas_oficiales=estados_casillas_oficiales,
        official_references=_official_references(snapshot, authority, estados_casillas_oficiales),
        blocking_findings=blocking_findings,
    )


def _review_casillas(
    *,
    snapshot: RegistrySnapshot,
    authority: ValidatedRegistryAuthority,
    revision: CalculationRevision | None,
    blocking_findings: tuple[ModeloVerificationFinding, ...],
) -> tuple[ModeloWorkReviewCasilla, ...]:
    context = _review_row_context(
        snapshot=snapshot,
        authority=authority,
        revision=revision,
        blocking_findings=blocking_findings,
    )
    return tuple(_review_casilla(casilla, context) for casilla in snapshot.revision.casillas)


def _work_progress(
    *,
    snapshot: RegistrySnapshot,
    rows: tuple[ModeloWorkReviewCasilla, ...],
    verification: VerificationReport | None,
) -> ModeloWorkProgress:
    manifest = snapshot.revision.completeness_manifest
    if manifest is None:
        return ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED)

    target_ids = frozenset(item.casilla_id for item in manifest.casillas)
    materialised_count = sum(
        row.casilla_id in target_ids and row.realised_kind is not ModeloValueKind.EMPTY for row in rows
    )
    if verification is not None and verification.completeness_status is VerificationCompletenessStatus.BLOCKED:
        state = ModeloWorkProgressState.BLOCKED
    elif (
        verification is not None
        and verification.completeness_status is VerificationCompletenessStatus.COMPLETE
        and materialised_count == len(target_ids)
    ):
        state = ModeloWorkProgressState.COMPLETE
    else:
        state = ModeloWorkProgressState.IN_PROGRESS
    return ModeloWorkProgress(
        state=state,
        materialised_count=materialised_count,
        target_count=len(target_ids),
        denominator=ModeloWorkProgressDenominator(
            registry_revision_id=snapshot.revision.id,
            source_ref=manifest.source_ref,
        ),
    )


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
    resolved_authority = authority or bundled_authority()
    selected_revision = select_revision(
        resolved_authority.validate_modelo(modelo),
        filing_year=filing_year,
        period=period.registry_token,
    )
    snapshot = resolved_authority.snapshot(
        modelo,
        filing_year=filing_year,
        period=period.registry_token,
        grade=selected_revision.effective_authority_grade,
    )
    work_units = work_unit_repository.load()
    calculation_repo = calculation_repository
    verification_repo = verification_repository
    work_unit = _work_unit_for_target(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        catalogue=work_units,
    )
    revision = _current_revision(work_unit, calculation_repo)
    verification = _latest_verification(revision, verification_repo)
    findings = () if verification is None else verification.findings
    blocking_findings = tuple(
        finding for finding in findings if finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    )
    blockers = tuple(_blocker_ref(finding) for finding in blocking_findings)
    rows = _review_casillas(
        snapshot=snapshot,
        authority=resolved_authority,
        revision=revision,
        blocking_findings=blocking_findings,
    )
    return ModeloWorkReview(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=None if revision is None else revision.calculation_revision_id,
        lifecycle_state=None if revision is None else revision.state,
        verification_outcome=None if verification is None else verification.completeness_status,
        progress=_work_progress(snapshot=snapshot, rows=rows, verification=verification),
        casillas=rows,
        findings=findings,
        blockers=blockers,
        row_source_fingerprints=revision_row_source_fingerprints_for_review(revision),
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
    verification_digest = content_hash_hex(verification_repository.load().model_dump(mode="json"))
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
