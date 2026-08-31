"""Typed inventory of canonical cross-model relation handoffs.

A handoff is a coordinate in the registry: the source and target
:class:`ModeloRevision` a value crosses between, resolved against the
:class:`RegistrySnapshot` the authority compiled. The inventory is what makes
"which model feeds which" a declared fact rather than one re-derived per caller.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal, NamedTuple

from pydantic import BaseModel, Field, model_validator

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import FilingPeriodCode, RegistrySelectorPeriodCode
from ....core.casilla_id import CasillaId
from ....core.aggregation import BindingSourceKind, RelationAggregationOp
from ._relation_aggregation import relation_aggregation_op
from ._validate import RegistryValidator
from .authority import ValidatedRegistryAuthority
from .bindings import bound_casilla_binding_ids
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, RelationId, RevisionId, SourceRefId
from .iva_wallet_relation_targets import is_iva_wallet_owned_relation_target
from .relations import RegistryFoldRequirement, relation_source_requirements
from .runtime_graph import expression_binding_refs, expression_relation_refs
from .schema import (
    DependencyClassificationDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
)
from .schema_references import PeriodSelector
from .schema_surfaces import RelationDefinition, RelationPeriodAlignment, RelationRevisionSelector

__all__ = [
    "HandoffPathClassification",
    "RegistryHandoffPathAudit",
    "RegistryRelationHandoffApplicabilityAudit",
    "RegistryRelationHandoffAudit",
    "RelationConsumptionChannel",
    "RelationHandoffApplicabilityRecord",
    "RelationHandoffPathRecord",
    "RelationHandoffRecord",
    "audit_registry_handoff_paths",
    "audit_registry_relation_handoff_applicability",
    "audit_registry_relation_handoffs",
    "relation_consumption_channels",
    "relation_consumption_index",
    "relation_is_consumed",
]

RelationConsumptionChannel = Literal["primary_binding", "alternate_binding", "formula_relation", "formula_binding"]
"""Canonical closed channels through which a relation feeds a casilla."""


class _RelationConsumptionIndex(NamedTuple):
    primary_bindings: frozenset[BindingId]
    alternate_bindings: frozenset[BindingId]
    formula_relations: frozenset[RelationId]
    formula_bindings: frozenset[BindingId]


def relation_consumption_index(revision: ModeloRevision) -> _RelationConsumptionIndex:
    """Return the binding and formula channels that consume relation values."""
    primary_bindings: set[BindingId] = set()
    alternate_bindings: set[BindingId] = set()
    for casilla in revision.casillas:
        if casilla.binding is not None:
            primary_bindings.add(casilla.binding)
        alternate_bindings.update(casilla.alternate_bindings)

    formula_relations: set[RelationId] = set()
    formula_bindings: set[BindingId] = set()
    for formula in revision.formulas:
        formula_relations.update(expression_relation_refs(formula.expression))
        formula_bindings.update(expression_binding_refs(formula.expression))
    return _RelationConsumptionIndex(
        primary_bindings=frozenset(primary_bindings),
        alternate_bindings=frozenset(alternate_bindings),
        formula_relations=frozenset(formula_relations),
        formula_bindings=frozenset(formula_bindings),
    )


def relation_consumption_channels(
    relation: RelationDefinition,
    index: _RelationConsumptionIndex,
) -> tuple[RelationConsumptionChannel, ...]:
    """Return every declared channel that consumes ``relation`` in stable order."""
    channels: list[RelationConsumptionChannel] = []
    if relation.target_binding in index.primary_bindings:
        channels.append("primary_binding")
    if relation.target_binding in index.alternate_bindings:
        channels.append("alternate_binding")
    if relation.id in index.formula_relations:
        channels.append("formula_relation")
    if relation.target_binding in index.formula_bindings:
        channels.append("formula_binding")
    return tuple(channels)


def relation_is_consumed(relation: RelationDefinition, index: _RelationConsumptionIndex) -> bool:
    """Return whether a formula or bound casilla consumes ``relation``."""
    return bool(relation_consumption_channels(relation, index))


class RelationHandoffRecord(BaseModel):
    """One validated relation handoff with source, target, period, and provenance axes."""

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: ModeloId
    target_revision: RevisionId
    relation_id: RelationId
    relation_kind: Literal["previous_period", "annual_summary", "cross_model_output"]
    dependency_role: Literal[
        "periodic_to_annual_summary",
        "instalment_to_final_settlement",
        "direct_calculation",
        "factual_evidence",
    ]
    source_modelo: ModeloId
    source_revision_selector: RelationRevisionSelector
    source_casilla_id: CasillaId
    target_binding: BindingId
    target_binding_source: BindingSourceKind | None
    target_casilla_ids: tuple[CasillaId, ...]
    consumption_channels: tuple[RelationConsumptionChannel, ...]
    period_alignment: RelationPeriodAlignment
    source_periods: tuple[str, ...]
    target_periods: tuple[str, ...]
    source_period_offset_from_target: int | None
    aggregation_op: RelationAggregationOp
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    target_binding_legal_refs: tuple[LegalRefId, ...] = ()
    target_binding_source_refs: tuple[SourceRefId, ...] = ()

    @model_validator(mode="after")
    def _target_casilla_ids_are_unique(self) -> RelationHandoffRecord:
        if len(self.target_casilla_ids) != len(set(self.target_casilla_ids)):
            raise RegistryValidationError(
                f"relation handoff {self.relation_id!r} repeats a target casilla identity",
            )
        return self


class RegistryRelationHandoffAudit(BaseModel):
    """Finite validated inventory of every declared relation handoff."""

    model_config = STRICT_FROZEN_CONFIG

    records: tuple[RelationHandoffRecord, ...]

    @property
    def relation_count(self) -> int:
        """Return the number of relation declarations measured."""
        return len(self.records)

    @property
    def by_revision(self) -> dict[tuple[ModeloId, RevisionId], tuple[RelationHandoffRecord, ...]]:
        """Group records by their target modelo revision without losing identity."""
        grouped: dict[tuple[ModeloId, RevisionId], list[RelationHandoffRecord]] = {}
        for record in self.records:
            grouped.setdefault((record.target_modelo, record.target_revision), []).append(record)
        return {key: tuple(value) for key, value in grouped.items()}


class RelationHandoffApplicabilityRecord(BaseModel):
    """One relation-period applicability and clean-state contract row."""

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: ModeloId
    target_revision: RevisionId
    relation_id: RelationId
    filing_year: int
    target_period: RegistrySelectorPeriodCode
    relation_target_periods: tuple[RegistrySelectorPeriodCode, ...]
    applicability: Literal["active", "not_applicable", "unresolved"]
    source_modelo: ModeloId
    source_filing_year: int | None = None
    source_periods: tuple[RegistrySelectorPeriodCode, ...] = ()
    source_filing_periods: tuple[FilingPeriodCode, ...] = ()
    source_casilla_id: CasillaId
    target_binding: BindingId
    requirement_relation_ids: tuple[RelationId, ...] = ()
    dependency_treatment: Literal["direct_annual_settlement", "factual_evidence", "non_dependency"]
    taxpayer_files_source: bool
    conditional_on_economic_activity: bool
    clean_state_mode: Literal["required", "conditional", "advisory"]
    runtime_clean_state: Literal["unmeasured"] = "unmeasured"
    aggregation_op: RelationAggregationOp
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class RegistryRelationHandoffApplicabilityAudit(BaseModel):
    """Finite authority-selected relation-period applicability inventory."""

    model_config = STRICT_FROZEN_CONFIG

    records: tuple[RelationHandoffApplicabilityRecord, ...]

    @property
    def row_count(self) -> int:
        """Return the number of relation-period rows measured."""
        return len(self.records)

    @property
    def active_count(self) -> int:
        """Return relation-period rows that produce a source requirement."""
        return sum(record.applicability == "active" for record in self.records)

    @property
    def not_applicable_count(self) -> int:
        """Return relation-period rows excluded by the relation period selector."""
        return sum(record.applicability == "not_applicable" for record in self.records)

    @property
    def unresolved_count(self) -> int:
        """Return rows whose declared applicability produced no requirement."""
        return sum(record.applicability == "unresolved" for record in self.records)

    @property
    def by_revision(
        self,
    ) -> dict[tuple[ModeloId, RevisionId], tuple[RelationHandoffApplicabilityRecord, ...]]:
        """Group rows by target revision without collapsing periods."""
        grouped: dict[tuple[ModeloId, RevisionId], list[RelationHandoffApplicabilityRecord]] = {}
        for record in self.records:
            grouped.setdefault((record.target_modelo, record.target_revision), []).append(record)
        return {key: tuple(value) for key, value in grouped.items()}


def audit_registry_relation_handoffs(
    modelos: Iterable[ModeloDefinition],
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
) -> RegistryRelationHandoffAudit:
    """Validate and enumerate canonical relation declarations.

    The function is deliberately an inventory, not a semantic adjudicator. It
    walks the relations each :class:`ModeloDefinition` in ``modelos`` declares
    and records the relation declaration and the binding slot it targets. Parallel
    paths and accepted exceptions are classified by the later handoff validator,
    so this fold cannot turn a source/binding shape into a new legal conclusion.
    """
    modelo_tuple = tuple(sorted(modelos, key=lambda item: item.id))
    RegistryValidator(catalogues, source_root=source_root).validate_registry(modelo_tuple)

    records: list[RelationHandoffRecord] = []
    for modelo in modelo_tuple:
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            bindings_by_id = {binding.id: binding for binding in revision.bindings}
            consumption_index = relation_consumption_index(revision)
            for relation in revision.relations:
                target_binding = bindings_by_id.get(relation.target_binding)
                if target_binding is None:
                    raise RegistryValidationError(
                        f"modelo {modelo.id} revision {revision.id}: relation {relation.id!r} "
                        f"has no target binding {relation.target_binding!r}",
                    )
                target_casilla_ids = tuple(
                    sorted(
                        casilla.id
                        for casilla in revision.casillas
                        if relation.target_binding in bound_casilla_binding_ids(casilla)
                    ),
                )
                records.append(
                    RelationHandoffRecord(
                        target_modelo=modelo.id,
                        target_revision=revision.id,
                        relation_id=relation.id,
                        relation_kind=relation.kind,
                        dependency_role=relation.dependency_role,
                        source_modelo=relation.source_modelo,
                        source_revision_selector=relation.source_revision_selector,
                        source_casilla_id=relation.source_casilla_id,
                        target_binding=relation.target_binding,
                        target_binding_source=target_binding.source,
                        target_casilla_ids=target_casilla_ids,
                        consumption_channels=relation_consumption_channels(relation, consumption_index),
                        period_alignment=relation.period_alignment,
                        source_periods=relation.source_periods,
                        target_periods=relation.target_periods,
                        source_period_offset_from_target=relation.source_period_offset_from_target,
                        aggregation_op=relation_aggregation_op(relation),
                        legal_refs=relation.legal_refs,
                        source_refs=relation.source_refs,
                        target_binding_legal_refs=target_binding.legal_refs,
                        target_binding_source_refs=target_binding.source_refs,
                    ),
                )
    return RegistryRelationHandoffAudit(records=tuple(records))


def _representative_filing_year(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    selector: PeriodSelector,
) -> int:
    """Return the filing year this revision's own period selector nominates.

    Raises:
        RegistryValidationError: When the selector nominates neither an
            explicit year nor a ``year_from`` floor, leaving the expansion
            below no year to resolve against.
    """
    filing_year = selector.years[0] if selector.years else selector.year_from
    if filing_year is None:
        raise RegistryValidationError(
            f"modelo {modelo.id} revision {revision.id} has no representative filing year",
        )
    return filing_year


def _clean_state_mode(
    classification: DependencyClassificationDefinition,
) -> Literal["required", "conditional", "advisory"]:
    """Map a dependency classification onto its clean-state contract.

    A source the taxpayer does not file (a suffered retencion) can only ever
    be advisory; one conditional on economic activity is conditional; the
    remainder are required.
    """
    if not classification.taxpayer_files_source:
        return "advisory"
    if classification.conditional_on_economic_activity:
        return "conditional"
    return "required"


def _relation_applicability(
    *,
    relation: RelationDefinition,
    period: str,
    matching: tuple[RegistryFoldRequirement, ...],
) -> Literal["active", "not_applicable", "unresolved"]:
    """Classify one relation against the period being expanded.

    A relation naming target periods that exclude this one is not applicable
    here at all; otherwise it is active when the requirement graph produced a
    row for it, and unresolved when it did not.
    """
    if relation.target_periods and period not in relation.target_periods:
        return "not_applicable"
    return "active" if matching else "unresolved"


def _sole_matching_requirement(
    relation: RelationDefinition,
    requirements: tuple[RegistryFoldRequirement, ...],
    *,
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    period: str,
) -> tuple[RegistryFoldRequirement, ...]:
    """Return the requirement rows this relation produced, refusing ambiguity.

    Raises:
        RegistryValidationError: When one relation produces more than one
            source requirement for a single period, which would leave the
            record below choosing arbitrarily between two source contracts.
    """
    matching = tuple(requirement for requirement in requirements if relation.id in requirement.relation_ids)
    if len(matching) > 1:
        raise RegistryValidationError(
            f"relation {relation.id!r} produces multiple source requirements for {modelo.id}/{revision.id}/{period}",
        )
    return matching


def _self_consistent_snapshot(
    authority: ValidatedRegistryAuthority,
    *,
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    filing_year: int,
    period: str,
) -> RegistrySnapshot:
    """Resolve the snapshot law-determined, then assert it names this revision.

    Resolution is law-determined and then asserted equal against the revision
    the caller is already walking -- never injected as the selector, per the
    registry authority-flow rule. Injecting it would silently mask a revision
    whose own period_selector does not self-consistently resolve back to
    itself; asserting turns that into a loud registry-validation failure. A
    live probe against the bundled registry confirms the two are equivalent
    for every relation-bearing revision today (0 mismatches across 42
    modelo/revision/period triples).

    Raises:
        RegistryValidationError: When the law-determined resolution selects a
            different revision than the one declaring this period.
    """
    # This audit reads relation requirements, bindings, and formula consumption;
    # it neither renders nor validates a filing artefact.  Request the minimum
    # calculation-grade authority through the canonical facade, so a legitimate
    # calculation-only revision remains part of the inventory rather than being
    # silently omitted or incorrectly required to have filing layouts.
    snapshot = authority.snapshot(
        str(modelo.id),
        filing_year=filing_year,
        period=period,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    if snapshot.revision.id != revision.id:
        raise RegistryValidationError(
            f"modelo {modelo.id} revision {revision.id}: law-determined "
            f"resolution for filing_year={filing_year} period={period!r} "
            f"selected revision {snapshot.revision.id!r} instead -- this "
            "revision's own declared period_selector does not "
            "self-consistently resolve to itself",
        )
    return snapshot


def _applicability_records_for_period(
    snapshot: RegistrySnapshot,
    *,
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    classifications_by_source: dict[ModeloId, DependencyClassificationDefinition],
) -> list[RelationHandoffApplicabilityRecord]:
    """Project every relation this snapshot declares onto one applicability row.

    Raises:
        RegistryValidationError: When a relation names a source modelo the
            revision declares no dependency classification for. Without that
            classification the clean-state contract for this relation has no
            declared enforcement rule, so the missing classification is
            refused here rather than let flow onward unenforced.
    """
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    records: list[RelationHandoffApplicabilityRecord] = []
    for relation in snapshot.revision.relations:
        classification = classifications_by_source.get(relation.source_modelo)
        if classification is None:
            raise RegistryValidationError(
                f"modelo {modelo.id} revision {revision.id}: relation {relation.id!r} "
                f"has no dependency classification for source {relation.source_modelo!r}",
            )
        matching = _sole_matching_requirement(
            relation,
            requirements,
            modelo=modelo,
            revision=revision,
            period=snapshot.period,
        )
        requirement = matching[0] if matching else None
        records.append(
            RelationHandoffApplicabilityRecord(
                target_modelo=modelo.id,
                target_revision=revision.id,
                relation_id=relation.id,
                filing_year=snapshot.filing_year,
                target_period=snapshot.period,
                relation_target_periods=relation.target_periods,
                applicability=_relation_applicability(
                    relation=relation,
                    period=snapshot.period,
                    matching=matching,
                ),
                source_modelo=relation.source_modelo,
                source_filing_year=None if requirement is None else requirement.filing_year,
                source_periods=() if requirement is None else requirement.periods,
                source_filing_periods=()
                if requirement is None
                else tuple(filing_period.registry_token for filing_period in requirement.filing_periods),
                source_casilla_id=relation.source_casilla_id,
                target_binding=relation.target_binding,
                requirement_relation_ids=() if requirement is None else requirement.relation_ids,
                dependency_treatment=classification.treatment,
                taxpayer_files_source=classification.taxpayer_files_source,
                conditional_on_economic_activity=classification.conditional_on_economic_activity,
                clean_state_mode=_clean_state_mode(classification),
                aggregation_op=relation_aggregation_op(relation),
                legal_refs=relation.legal_refs,
                source_refs=relation.source_refs,
            ),
        )
    return records


def audit_registry_relation_handoff_applicability(
    authority: ValidatedRegistryAuthority,
) -> RegistryRelationHandoffApplicabilityAudit:
    """Measure authority-selected relation periods and clean-state contracts.

    Every relation declared in the registry that the
    :class:`ValidatedRegistryAuthority` ``authority`` validates is expanded over
    its target revision's declared periods at the revision's representative
    filing year. Active rows are
    projected from :func:`relation_source_requirements`, the same requirement
    graph consumed by the runtime clean-state gate. This function records the
    clean-state contract (required, conditional, or advisory) but deliberately
    does not manufacture a taxpayer-specific runtime verdict.
    """
    authority.validate_registry()
    records: list[RelationHandoffApplicabilityRecord] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            if not revision.relations:
                continue
            selector = revision.period_selector
            filing_year = _representative_filing_year(modelo, revision, selector)
            classifications_by_source = {
                classification.source_modelo: classification for classification in revision.dependency_classifications
            }
            for period in selector.periods:
                snapshot = _self_consistent_snapshot(
                    authority,
                    modelo=modelo,
                    revision=revision,
                    filing_year=filing_year,
                    period=period,
                )
                records.extend(
                    _applicability_records_for_period(
                        snapshot,
                        modelo=modelo,
                        revision=revision,
                        classifications_by_source=classifications_by_source,
                    ),
                )
    return RegistryRelationHandoffApplicabilityAudit(records=tuple(records))


class RelationHandoffPathRecord(BaseModel):
    """One validated relation target classified by its runtime owner."""

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: ModeloId
    target_revision: RevisionId
    relation_id: RelationId
    target_binding: BindingId
    target_binding_source: BindingSourceKind
    target_casilla_ids: tuple[CasillaId, ...]
    classification: Literal["canonical_relation_prefill", "iva_wallet_exception", "non_canonical"]
    resolver_owner: Literal["relation_mesh", "iva_wallet", "unresolved"]
    parallel_path: bool
    parallel_binding_ids: tuple[BindingId, ...] = ()
    parallel_casilla_ids: tuple[CasillaId, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    target_binding_legal_refs: tuple[LegalRefId, ...] = ()
    target_binding_source_refs: tuple[SourceRefId, ...] = ()


class HandoffPathClassification(BaseModel):
    """Finite counts for canonical, exceptional, and parallel handoff paths."""

    model_config = STRICT_FROZEN_CONFIG

    total: int = Field(ge=0)
    canonical_relation_prefill: int = Field(ge=0)
    iva_wallet_exception: int = Field(ge=0)
    non_canonical: int = Field(ge=0)
    parallel: int = Field(ge=0)


class RegistryHandoffPathAudit(BaseModel):
    """Authority-validated handoff-path inventory with preserved provenance."""

    model_config = STRICT_FROZEN_CONFIG

    records: tuple[RelationHandoffPathRecord, ...]

    @property
    def relation_count(self) -> int:
        """Return the number of relation targets classified."""
        return len(self.records)

    @property
    def classification(self) -> HandoffPathClassification:
        """Return finite counts without changing individual provenance rows."""
        return HandoffPathClassification(
            total=self.relation_count,
            canonical_relation_prefill=sum(
                record.classification == "canonical_relation_prefill" for record in self.records
            ),
            iva_wallet_exception=sum(record.classification == "iva_wallet_exception" for record in self.records),
            non_canonical=sum(record.classification == "non_canonical" for record in self.records),
            parallel=sum(record.parallel_path for record in self.records),
        )

    @property
    def by_revision(self) -> dict[tuple[ModeloId, RevisionId], tuple[RelationHandoffPathRecord, ...]]:
        """Group path rows by target revision."""
        grouped: dict[tuple[ModeloId, RevisionId], list[RelationHandoffPathRecord]] = {}
        for record in self.records:
            grouped.setdefault((record.target_modelo, record.target_revision), []).append(record)
        return {key: tuple(value) for key, value in grouped.items()}


def audit_registry_handoff_paths(authority: ValidatedRegistryAuthority) -> RegistryHandoffPathAudit:
    """Classify validated relation paths without inventing semantic repairs.

    The :class:`ValidatedRegistryAuthority` passed as ``authority`` validates the
    registry before any path is read, and remains the authority for rejecting a
    non-canonical relation/previous-filing collision. This audit only projects the validated
    topology and records the one accepted M303 IVA-wallet exception. A parallel
    path is also reported when a target casilla carries a second direct
    ``previous_filing`` binding.
    """
    authority.validate_registry()
    relation_inventory: RegistryRelationHandoffAudit = audit_registry_relation_handoffs(
        authority.modelos,
        authority.catalogues,
        source_root=authority.source_root,
    )
    records: list[RelationHandoffPathRecord] = []
    for inventory_record in relation_inventory.records:
        modelo = authority.modelo(str(inventory_record.target_modelo))
        revision = modelo.revisions[inventory_record.target_revision]
        bindings_by_id = {binding.id: binding for binding in revision.bindings}
        target_binding = bindings_by_id[inventory_record.target_binding]
        previous_filing_binding_ids = {
            binding.id for binding in revision.bindings if binding.source is BindingSourceKind.PREVIOUS_FILING
        }
        parallel_binding_ids: set[BindingId] = set()
        parallel_casilla_ids: set[CasillaId] = set()
        for casilla in revision.casillas:
            if casilla.id not in inventory_record.target_casilla_ids:
                continue
            competing = set(bound_casilla_binding_ids(casilla)).intersection(previous_filing_binding_ids)
            competing.discard(inventory_record.target_binding)
            if competing:
                parallel_casilla_ids.add(casilla.id)
                parallel_binding_ids.update(competing)
        wallet_owned = is_iva_wallet_owned_relation_target(
            modelo_id=str(inventory_record.target_modelo),
            revision_id=str(inventory_record.target_revision),
            relation_id=str(inventory_record.relation_id),
            target_binding=str(inventory_record.target_binding),
        )
        if wallet_owned:
            classification: Literal["canonical_relation_prefill", "iva_wallet_exception", "non_canonical"] = (
                "iva_wallet_exception"
            )
            resolver_owner: Literal["relation_mesh", "iva_wallet", "unresolved"] = "iva_wallet"
        elif inventory_record.target_binding_source is BindingSourceKind.RELATION_PREFILL:
            classification = "canonical_relation_prefill"
            resolver_owner = "relation_mesh"
        else:
            classification = "non_canonical"
            resolver_owner = "unresolved"
        records.append(
            RelationHandoffPathRecord(
                target_modelo=inventory_record.target_modelo,
                target_revision=inventory_record.target_revision,
                relation_id=inventory_record.relation_id,
                target_binding=inventory_record.target_binding,
                target_binding_source=target_binding.source,
                target_casilla_ids=inventory_record.target_casilla_ids,
                classification=classification,
                resolver_owner=resolver_owner,
                parallel_path=bool(parallel_binding_ids)
                or (target_binding.source is BindingSourceKind.PREVIOUS_FILING and not wallet_owned),
                parallel_binding_ids=tuple(sorted(parallel_binding_ids)),
                parallel_casilla_ids=tuple(sorted(parallel_casilla_ids)),
                legal_refs=inventory_record.legal_refs,
                source_refs=inventory_record.source_refs,
                target_binding_legal_refs=inventory_record.target_binding_legal_refs,
                target_binding_source_refs=inventory_record.target_binding_source_refs,
            ),
        )
    return RegistryHandoffPathAudit(records=tuple(records))
