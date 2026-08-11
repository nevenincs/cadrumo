"""Canonical read projection for one persisted modelo work target."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind, CasillaId, OfficialBoxStatus, OperatorActionAxis, Period
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
from ...domain.calculations.registry import (
    BindingId,
    CasillaConstraints,
    FormulaId,
    InputKind,
    LegalRefId,
    RegistrySnapshot,
    RelationId,
    RevisionId,
    SourceRefId,
    ValidatedRegistryAuthority,
    bundled_authority,
    casillas_by_binding,
    classify_official_boxes,
    derive_export_layouts_from_bindings,
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_casilla_refs,
    expression_relation_refs,
    relation_consumption_channels,
    relation_consumption_index,
    relations_by_target_binding,
    revision_date_binding_ids,
    xml_dictionary_entries,
)
from ...domain.filing import ModeloScalar, ModeloValueKind
from ...domain.modelos import (
    OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND,
    CalculationRevision,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFinding,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnit,
    WorkUnitCatalogueRepositoryProtocol,
)
from ._action_errors import (
    CalculationRevisionNotFoundError,
    StoredCalculationDriftError,
    WorkUnitNotFoundError,
    WorkUnitRevisionDivergenceError,
)


class ModeloWorkOriginAnomaly(StrEnum):
    """Closed disagreements between declared and realised value origin."""

    BROKEN_CALCULATION_CHAIN = "broken_calculation_chain"
    OPERATOR_OVERRIDE = "operator_override"


class ModeloWorkRelationConsumption(BaseModel):
    """One relation channel that can feed a reviewed casilla."""

    model_config = STRICT_FROZEN_CONFIG
    relation_id: RelationId
    channels: tuple[str, ...]


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
    official_box_status: OfficialBoxStatus
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    formula_id: FormulaId | None
    blocked_by: tuple[BlockerRef, ...] = ()


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
    casillas: tuple[ModeloWorkReviewCasilla, ...]
    findings: tuple[ModeloVerificationFinding, ...]
    blockers: tuple[BlockerRef, ...]


def _work_unit_for_target(
    *,
    bucket_id: BucketId,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId,
    repository: WorkUnitCatalogueRepositoryProtocol,
) -> WorkUnit:
    candidates = tuple(
        unit
        for unit in repository.load().values()
        if str(unit.bucket_id) == bucket_id
        and str(unit.modelo) == modelo
        and unit.filing_year == filing_year
        and unit.period == period
    )
    if not candidates:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={
                "bucket_id": bucket_id,
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
            },
        )
    matching = tuple(unit for unit in candidates if unit.revision_id == registry_revision_id)
    if len(matching) != 1:
        stored = sorted(str(unit.revision_id) for unit in candidates)
        raise WorkUnitRevisionDivergenceError(
            f"persisted modelo work target for {modelo} {filing_year} {period.registry_token!r} "
            f"was created against registry revision(s) {stored!r}, but law-determined resolution "
            f"selected {registry_revision_id!r}. Re-create the work unit against the current registry revision.",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "stored_revision_ids": stored,
                "resolved_revision_id": registry_revision_id,
            },
        )
    return matching[0]


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
        return {}
    enum_ids = enum_consumed_binding_ids(snapshot.revision)
    date_ids = revision_date_binding_ids(snapshot.revision)
    decimal_bindings: dict[BindingId, Decimal] = {}
    for binding_id, raw_value in revision.binding_overrides.items():
        if binding_id in enum_ids or binding_id in date_ids:
            continue
        try:
            decimal_bindings[binding_id] = Decimal(raw_value)
        except InvalidOperation as exc:
            raise StoredCalculationDriftError(
                f"stored revision {revision.calculation_revision_id!r} has non-decimal value "
                f"{raw_value!r} for decimal binding {binding_id!r}",
                context={
                    "calculation_revision_id": revision.calculation_revision_id,
                    "binding_id": binding_id,
                },
            ) from exc
    return decimal_bindings


def _official_references(
    snapshot: RegistrySnapshot,
    authority: ValidatedRegistryAuthority,
    statuses: Mapping[CasillaId, OfficialBoxStatus],
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
        if statuses[casilla.id] is OfficialBoxStatus.ADDRESSED
        else None
        for casilla in snapshot.revision.casillas
    }


def _blocker_ref(finding: ModeloVerificationFinding) -> BlockerRef:
    return BlockerRef(
        axis=OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[finding.kind],
        native_code=finding.kind.value,
        facts=finding.message_facts,
    )


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
    observation = (
        None
        if revision is None
        else next(
            (item for item in revision.observations if item.casilla_id == casilla_id),
            None,
        )
    )
    if observation is None:
        anomaly = ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN if input_kind is InputKind.COMPUTED else None
        return ModeloValueKind.EMPTY, None, anomaly
    if formula_id is not None:
        return ModeloValueKind.COMPUTED, observation.value, None
    if input_kind is InputKind.BOUND and observation.absent_by_design:
        return ModeloValueKind.INHERITED, observation.value, None
    binding_values = tuple(resolved_bindings[item] for item in binding_ids if item in resolved_bindings)
    if input_kind is InputKind.BOUND and binding_values and observation.value not in binding_values:
        return ModeloValueKind.LITERAL, observation.value, ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE
    if input_kind is InputKind.BOUND:
        return ModeloValueKind.INHERITED, observation.value, None
    return ModeloValueKind.LITERAL, observation.value, None


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
    snapshot = resolved_authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    work_repo = work_unit_repository
    calculation_repo = calculation_repository
    verification_repo = verification_repository
    work_unit = _work_unit_for_target(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        repository=work_repo,
    )
    revision = _current_revision(work_unit, calculation_repo)
    verification = _latest_verification(revision, verification_repo)
    findings = () if verification is None else verification.findings
    blocking_findings = tuple(
        finding for finding in findings if finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    )
    blockers = tuple(_blocker_ref(finding) for finding in blocking_findings)
    statuses = classify_official_boxes(
        snapshot.revision,
        source_root=resolved_authority.source_root,
        sources=snapshot.sources,
    )
    official_references = _official_references(snapshot, resolved_authority, statuses)
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    formulas_by_id = {formula.id: formula for formula in snapshot.revision.formulas}
    binding_to_casillas = casillas_by_binding(snapshot.revision)
    relations_by_binding = relations_by_target_binding(snapshot.revision)
    consumption_index = relation_consumption_index(snapshot.revision)
    persisted_decimal_bindings = _persisted_decimal_bindings(snapshot=snapshot, revision=revision)
    persisted_binding_ids = frozenset(() if revision is None else revision.binding_overrides)

    rows: list[ModeloWorkReviewCasilla] = []
    for casilla in snapshot.revision.casillas:
        binding_ids = tuple(
            binding_id for binding_id, casilla_ids in binding_to_casillas.items() if casilla.id in casilla_ids
        )
        formula = formulas_by_id.get(casilla.formula) if casilla.formula is not None else None
        formula_relation_ids: set[RelationId] = (
            set() if formula is None else set(expression_relation_refs(formula.expression))
        )
        formula_binding_ids: set[BindingId] = (
            set() if formula is None else set(expression_binding_refs(formula.expression))
        )
        relation_candidates = {
            relation.id: relation
            for binding_id in (*binding_ids, *formula_binding_ids)
            for relation in relations_by_binding.get(binding_id, ())
        }
        relation_candidates.update(
            {relation.id: relation for relation in snapshot.revision.relations if relation.id in formula_relation_ids}
        )
        consumptions: list[ModeloWorkRelationConsumption] = []
        for relation in snapshot.revision.relations:
            if relation.id not in relation_candidates:
                continue
            consumptions.append(
                ModeloWorkRelationConsumption(
                    relation_id=relation.id,
                    channels=relation_consumption_channels(relation, consumption_index),
                ),
            )
        realised_kind, value, anomaly = _realised_value(
            casilla_id=casilla.id,
            input_kind=casilla.input_kind,
            formula_id=casilla.formula,
            binding_ids=binding_ids,
            revision=revision,
            resolved_bindings=persisted_decimal_bindings,
        )
        rows.append(
            ModeloWorkReviewCasilla(
                casilla_id=casilla.id,
                number=casilla.number,
                segmento=casilla.segmento,
                official_reference=official_references[casilla.id],
                section_path=casilla.section,
                label=casilla.label,
                data_type=casilla.data_type,
                constraints=casilla.constraints,
                declared_input_kind=casilla.input_kind,
                concrete_bindings=tuple(
                    ModeloWorkBindingOrigin(
                        binding_id=binding_id,
                        source=bindings_by_id[binding_id].source,
                        resolved=binding_id in persisted_binding_ids,
                    )
                    for binding_id in binding_ids
                ),
                concrete_formula=None
                if formula is None
                else ModeloWorkFormulaOrigin(
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
                ),
                relation_consumption=tuple(consumptions),
                realised_kind=realised_kind,
                value=value,
                origin_anomaly=anomaly,
                official_box_status=statuses[casilla.id],
                legal_refs=tuple(casilla.legal_refs),
                source_refs=tuple(casilla.source_refs),
                formula_id=casilla.formula,
                blocked_by=tuple(
                    _blocker_ref(finding) for finding in blocking_findings if finding.casilla_id == casilla.id
                ),
            ),
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
        casillas=tuple(rows),
        findings=findings,
        blockers=blockers,
    )


__all__ = [
    "BlockerRef",
    "ModeloWorkBindingOrigin",
    "ModeloWorkFormulaOrigin",
    "ModeloWorkOriginAnomaly",
    "ModeloWorkRelationConsumption",
    "ModeloWorkReview",
    "ModeloWorkReviewCasilla",
    "build_modelo_work_review",
]
