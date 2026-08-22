"""Application services for read-only registry workflows.

Registry query and corpus validation services consume a
:class:`domain.calculations.registry.ValidatedRegistryAuthority` as
the single entry point for
:class:`domain.calculations.registry.ModeloDefinition` instances,
:class:`domain.calculations.registry.RegistrySnapshot` values, and
deadline windows.

The package exposes three local read surfaces: registry-tree inspection
and verification over the bundled ``registry/aeat`` tree, corpus/manual
projection over :class:`RegistryTopicProjection` and related report
records, and filed-state comparison that loads captured AEAT observations
before recomputing a registry snapshot locally.

The observation-persistence path reads captured filed state through the
active-bucket encrypted observation store.

See Also:
    :class:`domain.calculations.registry.ValidatedRegistryAuthority`
        Domain authority used to load, validate, and snapshot modelo registry
        definitions.
    :class:`RegistryTreeReport`
        Application report returned by registry-tree inspection and verification.
    :class:`RegistryCitationsListReport`
        Citation projection over reviewed registry legal references and topics.
    :class:`RegistryManualVerificationReport`
        Manual/casilla verification report for bundled manual corpus checks.
    :mod:`domain.manuals`
        Strict manual schema and loader surface that owns extracted manual
        records and :class:`domain.manuals.ManualCasillaReference` values.
    :mod:`core.resources`
        Bundled-data boundary used to locate packaged registry and corpus
        material without repository-relative path reads.
    :class:`FiledStateVerificationReport`
        Filed-state comparison report built from encrypted captured AEAT
        observations and local registry recalculation.
    :class:`adapters.outbound.aeat.sede.FiledDeclaracionObservationStore`
        Active-bucket observation store that persists captured filed state for
        local registry comparison.
    :mod:`application.modelo._registry_discovery`
        Modelo work-unit discovery facade for CLI-facing registry queries.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from importlib import import_module as _import_module
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.aeat.sede import (
    FiledDeclaracionObservationStore as _FiledDeclaracionObservationStore,
)
from ...adapters.outbound.aeat.sede import (
    registry_observation_from_filed_declaration as _registry_observation_from_filed_declaration,
)
from ...core import BindingSourceKind as _BindingSourceKind
from ...core import CasillaId as _CasillaId
from ...core import validated_casilla_id as _validated_casilla_id
from ...core.resources import bundled_path as _bundled_path
from ...domain.calculations.registry import BindingId as _BindingId
from ...domain.calculations.registry import CasillaDefinition as _CasillaDefinition
from ...domain.calculations.registry import DataBindingDefinition as _DataBindingDefinition

# Importing the renta package registers the first-slice routing
# cross-domain snapshot check required by Modelo 100 snapshots.
from ...domain.calculations.registry import ExportLayoutId as _ExportLayoutId
from ...domain.calculations.registry import (
    InputKind as _InputKind,
)
from ...domain.calculations.registry import LegalRefId as _LegalRefId
from ...domain.calculations.registry import ModeloDefinition as _ModeloDefinition
from ...domain.calculations.registry import (
    RegistryFiledStateComparison as _RegistryFiledStateComparison,
)
from ...domain.calculations.registry import RegistryModeloObservation as _RegistryModeloObservation
from ...domain.calculations.registry import RegistrySnapshot as _RegistrySnapshot
from ...domain.calculations.registry import RelationId as _RelationId
from ...domain.calculations.registry import SourceRefId as _SourceRefId
from ...domain.calculations.registry import (
    ValidatedRegistryAuthority as _ValidatedRegistryAuthority,
)
from ...domain.calculations.registry import WorkbookParityRefId as _WorkbookParityRefId
from ...domain.calculations.registry import (
    calculate_registry_snapshot as _calculate_registry_snapshot,
)
from ...domain.calculations.registry import (
    compare_calculation_to_filed_observation as _compare_calculation_to_filed_observation,
)
from ...domain.calculations.registry import (
    resolve_previous_filing_binding_values as _resolve_previous_filing_binding_values,
)
from ...domain.calculations.registry import (
    resolve_relation_values_from_observations as _resolve_relation_values_from_observations,
)
from ...domain.calculations.registry import undeclared_casilla_ids as _undeclared_casilla_ids
from ...domain.calculations.registry import verification_tolerance_or_exact as _verification_tolerance_or_exact
from ...domain.calculations.registry import verify_legal_catalogue as _verify_legal_catalogue
from ...domain.period import calculation_filing_date as _calculation_filing_date
from ._conformance import (
    AnnualCasillaPopulationComparison,
    CoverageAuthorityScope,
    LatestRevisionSupportProbe,
    RegistryConformanceProfile,
    RevisionCapabilityFacts,
    RevisionCasillaProducerTrace,
    RevisionConformanceRow,
    RevisionConstructEvidence,
    RevisionGovernanceStamp,
    RevisionModelLawCoverage,
    audit_bundled_registry_conformance,
    build_registry_conformance_profile,
    compare_annual_casilla_population,
    compare_annual_casilla_population_for_revision,
)
from ._corpus import (
    RegistryCitationArticleProjection,
    RegistryCitationReferenceProjection,
    RegistryCitationShowCommand,
    RegistryCitationShowReport,
    RegistryCitationsListCommand,
    RegistryCitationsListReport,
    RegistryCitationsVerificationReport,
    RegistryCorpusIssueProjection,
    RegistryManualId,
    RegistryManualPartProjection,
    RegistryManualRuleProjection,
    RegistryManualRulesCommand,
    RegistryManualRulesReport,
    RegistryManualSectionProjection,
    RegistryManualShowCommand,
    RegistryManualShowReport,
    RegistryManualsListCommand,
    RegistryManualsListReport,
    RegistryManualVerificationReport,
    RegistryManualVerifyCommand,
    RegistryTopicProjection,
    list_registry_citations,
    list_registry_manual_rules,
    list_registry_manuals,
    registry_manual_id,
    show_registry_citation,
    show_registry_manual,
    verify_registry_citations,
    verify_registry_manual,
)
from ._diff import (
    BindingDiff,
    CasillaDiff,
    FormulaDiff,
    ParameterDiff,
    RegistryRevisionDiffReport,
    RenumberedCasilla,
    diff_registry_revisions,
)
from ._errors import RegistryApplicationError, RegistryApplicationInputError
from ._source_connectivity_authority import (
    CalculationRouteManualSourceOwnership,
    CalculationRouteResolverSourceOwnership,
    CalculationRouteSourceOwnershipCatalogue,
    LiveSourceConnectivityProofAuthority,
    RepositoryEvidenceDigestVerifier,
    RepositoryRootEvidenceDigestVerifier,
    build_calculation_route_source_ownership_catalogue,
)

_import_module("cadrumo.domain.renta")


def _verified_required_casilla_ids(
    required_casilla_refs: tuple[object, ...],
    *,
    snapshot: _RegistrySnapshot,
) -> tuple[_CasillaId, ...]:
    """Validate requested filed-state casillas against the resolved revision."""
    requested: list[_CasillaId] = []
    for raw_casilla_id in required_casilla_refs:
        try:
            casilla_id = _validated_casilla_id(
                raw_casilla_id,
                surface="registry.verify_filed_state --casilla",
            )
        except ValueError as exc:
            raise RegistryApplicationInputError(
                f"registry.verify_filed_state --casilla {raw_casilla_id!r} is not a canonical casilla.id",
                context={
                    "modelo": snapshot.modelo.id,
                    "revision_id": snapshot.revision.id,
                    "casilla_id": str(raw_casilla_id),
                },
            ) from exc
        if _undeclared_casilla_ids(snapshot.revision, (casilla_id,)):
            raise RegistryApplicationInputError(
                f"registry.verify_filed_state --casilla {casilla_id!r} is not declared as a canonical "
                f"casilla.id in modelo {snapshot.modelo.id} revision {snapshot.revision.id}",
                context={
                    "modelo": snapshot.modelo.id,
                    "revision_id": snapshot.revision.id,
                    "casilla_id": casilla_id,
                },
            )
        requested.append(casilla_id)
    return tuple(requested)


class RegistryTreeReport(BaseModel):
    """Read-only registry tree load or verification result."""

    model_config = ConfigDict(frozen=True)

    registry_root: str
    source_root: str | None = None
    modelo_count: int
    revision_count: int
    legal_reference_count: int
    source_reference_count: int
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_count: int
    modelos: tuple[str, ...]
    revision_details: tuple[RegistryRevisionDetailReport, ...]
    verified: bool
    verified_invariant_families: tuple[str, ...] = ()
    unverified_invariant_families: tuple[str, ...] = ()


class RegistryWorkbookParityDetailReport(BaseModel):
    """Workbook parity coverage declared by one registry revision."""

    model_config = ConfigDict(frozen=True)

    id: _WorkbookParityRefId
    workbook_source: _SourceRefId
    formula_coverage: str
    runner_required: bool
    output_cell_count: int


class RegistryRevisionDetailReport(BaseModel):
    """Read-only details for one modelo revision from the central registry."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    revision: str
    legal_refs: tuple[_LegalRefId, ...]
    source_refs: tuple[_SourceRefId, ...]
    export_layout_ids: tuple[_ExportLayoutId, ...]
    export_layout_count: int
    export_record_count: int
    export_field_count: int
    deadline_window_count: int
    deadline_periods: tuple[str, ...]
    relation_ids: tuple[_RelationId, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_ids: tuple[str, ...]
    filing_schedule_count: int
    portal_guard_policy_ids: tuple[str, ...]
    workbook_parity: tuple[RegistryWorkbookParityDetailReport, ...]


class FiledStateVerificationReport(BaseModel):
    """Local registry calculation versus filed AEAT state verification report."""

    model_config = ConfigDict(frozen=True)

    observation_path: str
    source_observation_paths: tuple[str, ...]
    comparison: _RegistryFiledStateComparison


class RegistryRevisionInventory(NamedTuple):
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_count: int


def _registry_tree_report(
    *,
    registry_root: Path,
    authority: _ValidatedRegistryAuthority,
    verified: bool,
    source_root: Path | None = None,
) -> RegistryTreeReport:
    """Assemble the read-only inventory :class:`RegistryTreeReport` from a loaded authority.

    The shared report-construction body of :func:`inspect_registry_tree` (which
    passes no ``source_root`` and ``verified=False``) and
    :func:`verify_registry_tree` (which records the ``source_root`` and
    ``verified=True``); each caller owns its own load and validation before
    calling this.
    """
    modelos = authority.modelos
    catalogues = authority.catalogues
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        source_root=None if source_root is None else str(source_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
        casilla_count=inventory.casilla_count,
        formula_count=inventory.formula_count,
        extraction_profile_count=inventory.extraction_profile_count,
        cross_reference_count=inventory.cross_reference_count,
        workbook_parity_ref_count=inventory.workbook_parity_ref_count,
        verification_expectation_count=inventory.verification_expectation_count,
        application_link_count=inventory.application_link_count,
        application_link_surfaces=inventory.application_link_surfaces,
        relation_count=inventory.relation_count,
        relation_dependency_roles=inventory.relation_dependency_roles,
        filing_schedule_count=inventory.filing_schedule_count,
        modelos=tuple(sorted(modelo.id for modelo in modelos)),
        revision_details=_revision_details(modelos),
        verified=verified,
    )


def inspect_registry_tree(registry_root: Path) -> RegistryTreeReport:
    """Load the registry tree and return a :class:`RegistryTreeReport` with stable read-only inventory counts."""
    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=_bundled_path())
    return _registry_tree_report(registry_root=registry_root, authority=authority, verified=False)


def verify_registry_tree(registry_root: Path, *, source_root: Path) -> RegistryTreeReport:
    """Load and fail-fast validate every registry modelo against shared catalogues.

    Returns a :class:`RegistryTreeReport`.

    Runs a full audit including ``required_text`` corpus checks on every
    legal reference.
    """
    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
    authority.validate_registry()
    _verify_legal_catalogue(authority.catalogues.legal, source_root=source_root)
    return _registry_tree_report(
        registry_root=registry_root,
        authority=authority,
        verified=True,
        source_root=source_root,
    ).model_copy(
        update={
            "verified_invariant_families": (
                "catalogue_and_corpus_integrity",
                "revision_section_contracts",
                "relation_source_coordinate_coverage",
            ),
            "unverified_invariant_families": (
                "export_layout_population",
                "published_design_span_attribution",
            ),
        },
    )


def verify_filed_state(
    *,
    observation_path: Path,
    source_observation_paths: tuple[Path, ...] = (),
    registry_root: Path | None = None,
    source_root: Path | None = None,
    required_casilla_ids: tuple[_CasillaId, ...] = (),
) -> FiledStateVerificationReport:
    """Compare a local registry calculation to a captured filed observation.

    Returns a :class:`FiledStateVerificationReport` with the per-casilla
    comparison results between the registry calculation and the filed values.
    """
    filed_observation = _load_filed_observation(observation_path)
    registry_observation = _registry_observation_from_filed_declaration(filed_observation)
    source_observations = tuple(_load_filed_observation(path) for path in source_observation_paths)
    registry_source_observations = tuple(
        _registry_observation_from_filed_declaration(observation) for observation in source_observations
    )
    authority = _ValidatedRegistryAuthority.load(
        registry_root or _bundled_path("registry", "aeat"),
        source_root=source_root or _bundled_path(),
    )
    filing_period_token = filed_observation.period.registry_token
    snapshot = authority.snapshot(
        filed_observation.modelo,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    requested_required_casilla_ids = _verified_required_casilla_ids(required_casilla_ids, snapshot=snapshot)
    binding_values = _resolve_previous_filing_binding_values(
        snapshot.revision,
        registry_source_observations,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    inputs = _filed_state_inputs(
        snapshot,
        registry_observation,
        binding_values=binding_values,
    )
    relation_values = _resolve_relation_values_from_observations(
        snapshot.revision,
        registry_source_observations,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    calculation = _calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": _calculation_filing_date(filed_observation.period)},
        binding_values=binding_values,
        relation_values=relation_values,
        # Recomputation reconciles a filed observation's own values, carrying no
    )
    casilla_ids = requested_required_casilla_ids or tuple(
        casilla.id for casilla in snapshot.revision.casillas if casilla.input_kind == _InputKind.COMPUTED
    )
    comparison = _compare_calculation_to_filed_observation(
        calculation,
        registry_observation,
        required_casilla_ids=casilla_ids,
        tolerance=_verification_tolerance_or_exact(snapshot),
    )
    return FiledStateVerificationReport(
        observation_path=str(observation_path),
        source_observation_paths=tuple(str(path) for path in source_observation_paths),
        comparison=comparison,
    )


def _filed_state_inputs(
    snapshot: _RegistrySnapshot,
    registry_observation: _RegistryModeloObservation,
    *,
    binding_values: Mapping[_BindingId, Decimal],
) -> dict[_CasillaId, Decimal]:
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    input_casilla_ids = {
        casilla.id
        for casilla in snapshot.revision.casillas
        if _filed_state_casilla_is_input(casilla, bindings_by_id=bindings_by_id, binding_values=binding_values)
    }
    return {
        casilla_id: value
        for casilla_id, value in registry_observation.casilla_values.items()
        if casilla_id in input_casilla_ids
    }


def _filed_state_casilla_is_input(
    casilla: _CasillaDefinition,
    *,
    bindings_by_id: Mapping[_BindingId, _DataBindingDefinition],
    binding_values: Mapping[_BindingId, Decimal],
) -> bool:
    if casilla.input_kind == _InputKind.COMPUTED:
        return False
    if casilla.input_kind != _InputKind.BOUND or casilla.binding is None:
        return True
    binding_def = bindings_by_id.get(casilla.binding)
    return not (
        binding_def is not None
        and binding_def.source == _BindingSourceKind.PREVIOUS_FILING
        and binding_def.id not in binding_values
    )


def _revision_inventory(modelos: tuple[_ModeloDefinition, ...]) -> RegistryRevisionInventory:
    revisions = tuple(revision for modelo in modelos for revision in modelo.revisions.values())
    application_surfaces = {link.surface for revision in revisions for link in revision.application_links}
    relation_roles = {relation.dependency_role for revision in revisions for relation in revision.relations}
    return RegistryRevisionInventory(
        casilla_count=sum(len(revision.casillas) for revision in revisions),
        formula_count=sum(len(revision.formulas) for revision in revisions),
        extraction_profile_count=sum(len(revision.extraction_profiles) for revision in revisions),
        cross_reference_count=sum(len(revision.live_cross_references) for revision in revisions),
        workbook_parity_ref_count=sum(len(revision.workbook_parity_refs) for revision in revisions),
        verification_expectation_count=sum(len(revision.verification_expectations) for revision in revisions),
        application_link_count=sum(len(revision.application_links) for revision in revisions),
        application_link_surfaces=tuple(sorted(application_surfaces)),
        relation_count=sum(len(revision.relations) for revision in revisions),
        relation_dependency_roles=tuple(sorted(relation_roles)),
        filing_schedule_count=sum(len(revision.filing_schedules) for revision in revisions),
    )


def _revision_details(modelos: tuple[_ModeloDefinition, ...]) -> tuple[RegistryRevisionDetailReport, ...]:
    reports: list[RegistryRevisionDetailReport] = []
    for modelo in sorted(modelos, key=lambda item: item.id):
        for revision_id, revision in sorted(modelo.revisions.items()):
            export_records = tuple(record for layout in revision.export_layouts for record in layout.records)
            export_fields = tuple(field for record in export_records for field in record.fields)
            workbook_parity = tuple(
                RegistryWorkbookParityDetailReport(
                    id=reference.id,
                    workbook_source=reference.workbook_source,
                    formula_coverage=reference.formula_coverage,
                    runner_required=reference.runner_required,
                    output_cell_count=len(reference.output_cells),
                )
                for reference in sorted(revision.workbook_parity_refs, key=lambda item: item.id)
            )
            reports.append(
                RegistryRevisionDetailReport(
                    modelo=str(modelo.id),
                    revision=str(revision_id),
                    legal_refs=tuple(revision.legal_refs),
                    source_refs=tuple(revision.source_refs),
                    export_layout_ids=tuple(layout.id for layout in revision.export_layouts),
                    export_layout_count=len(revision.export_layouts),
                    export_record_count=len(export_records),
                    export_field_count=len(export_fields),
                    deadline_window_count=len(revision.deadline_windows),
                    deadline_periods=tuple(
                        sorted(window.period.registry_token for window in revision.deadline_windows),
                    ),
                    relation_ids=tuple(relation.id for relation in revision.relations),
                    relation_count=len(revision.relations),
                    relation_dependency_roles=tuple(
                        sorted({relation.dependency_role for relation in revision.relations}),
                    ),
                    filing_schedule_ids=tuple(str(schedule.id) for schedule in revision.filing_schedules),
                    filing_schedule_count=len(revision.filing_schedules),
                    portal_guard_policy_ids=tuple(
                        sorted({decision.guard_policy_id for decision in revision.live_cross_references}),
                    ),
                    workbook_parity=workbook_parity,
                ),
            )
    return tuple(reports)


def _load_filed_observation(path: Path):
    return _FiledDeclaracionObservationStore(path.parent).load_observation(path)


__all__ = [
    "AnnualCasillaPopulationComparison",
    "BindingDiff",
    "CalculationRouteManualSourceOwnership",
    "CalculationRouteResolverSourceOwnership",
    "CalculationRouteSourceOwnershipCatalogue",
    "CasillaDiff",
    "CoverageAuthorityScope",
    "FiledStateVerificationReport",
    "FormulaDiff",
    "LatestRevisionSupportProbe",
    "LiveSourceConnectivityProofAuthority",
    "ParameterDiff",
    "RegistryApplicationError",
    "RegistryApplicationInputError",
    "RegistryCitationArticleProjection",
    "RegistryCitationReferenceProjection",
    "RegistryCitationShowCommand",
    "RegistryCitationShowReport",
    "RegistryCitationsListCommand",
    "RegistryCitationsListReport",
    "RegistryCitationsVerificationReport",
    "RegistryConformanceProfile",
    "RegistryCorpusIssueProjection",
    "RegistryManualId",
    "RegistryManualPartProjection",
    "RegistryManualRuleProjection",
    "RegistryManualRulesCommand",
    "RegistryManualRulesReport",
    "RegistryManualSectionProjection",
    "RegistryManualShowCommand",
    "RegistryManualShowReport",
    "RegistryManualVerificationReport",
    "RegistryManualVerifyCommand",
    "RegistryManualsListCommand",
    "RegistryManualsListReport",
    "RegistryRevisionDiffReport",
    "RegistryTopicProjection",
    "RegistryTreeReport",
    "RenumberedCasilla",
    "RepositoryEvidenceDigestVerifier",
    "RepositoryRootEvidenceDigestVerifier",
    "RevisionCapabilityFacts",
    "RevisionCasillaProducerTrace",
    "RevisionConformanceRow",
    "RevisionConstructEvidence",
    "RevisionGovernanceStamp",
    "RevisionModelLawCoverage",
    "audit_bundled_registry_conformance",
    "build_calculation_route_source_ownership_catalogue",
    "build_registry_conformance_profile",
    "compare_annual_casilla_population",
    "compare_annual_casilla_population_for_revision",
    "diff_registry_revisions",
    "inspect_registry_tree",
    "list_registry_citations",
    "list_registry_manual_rules",
    "list_registry_manuals",
    "registry_manual_id",
    "show_registry_citation",
    "show_registry_manual",
    "verify_filed_state",
    "verify_registry_citations",
    "verify_registry_manual",
    "verify_registry_tree",
]
