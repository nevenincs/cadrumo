"""Application services for read-only registry workflows.

Registry query and corpus validation services consume a
:class:`ValidatedRegistryAuthority` as the single entry point for
:class:`ModeloDefinition` instances, revision snapshots, and deadline windows.
The observation-persistence path reads captured filed state through the
active-bucket encrypted observation store.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.aeat.sede import (
    FiledDeclaracionObservationStore as _FiledDeclaracionObservationStore,
)
from ...adapters.outbound.aeat.sede import (
    registry_observation_from_filed_declaration as _registry_observation_from_filed_declaration,
)
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.resources import bundled_path as _bundled_path

# Importing the renta package registers the first-slice routing
# cross-domain snapshot check required by Modelo 100 snapshots.
from ...domain import renta as _renta_snapshot_checks  # noqa: F401 - snapshot-check registration side effect
from ...domain.calculations.registry import AeatNifIvaCheckerOracle as _AeatNifIvaCheckerOracle
from ...domain.calculations.registry import (
    CrossReferenceApplicabilityDeclaracion as _CrossReferenceApplicabilityDeclaracion,
)
from ...domain.calculations.registry import GroiOracle as _GroiOracle
from ...domain.calculations.registry import (
    InputKind as _InputKind,
)
from ...domain.calculations.registry import (
    LiveParityCatalogue as _LiveParityCatalogue,
)
from ...domain.calculations.registry import ModeloDefinition as _ModeloDefinition
from ...domain.calculations.registry import (
    OracleEnvironment as _OracleEnvironment,
)
from ...domain.calculations.registry import (
    RegistryFiledStateComparison as _RegistryFiledStateComparison,
)
from ...domain.calculations.registry import (
    ValidatedRegistryAuthority as _ValidatedRegistryAuthority,
)
from ...domain.calculations.registry import (
    WorkbookBackendVerificationReport as _WorkbookBackendVerificationReport,
)
from ...domain.calculations.registry import (
    audit_registry_oracle_bindings as _audit_registry_oracle_bindings,
)
from ...domain.calculations.registry import (
    calculate_registry_snapshot as _calculate_registry_snapshot,
)
from ...domain.calculations.registry import (
    collect_applicability_declarations as _collect_applicability_declarations,
)
from ...domain.calculations.registry import (
    collect_orphan_oracle_ids as _collect_orphan_oracle_ids,
)
from ...domain.calculations.registry import (
    compare_calculation_to_filed_observation as _compare_calculation_to_filed_observation,
)
from ...domain.calculations.registry import (
    generate_parity_tape_path as _generate_parity_tape_path,
)
from ...domain.calculations.registry import (
    load_parity_scenario as _load_parity_scenario,
)
from ...domain.calculations.registry import (
    load_parity_tape as _load_parity_tape,
)
from ...domain.calculations.registry import (
    replay_parity_tape as _replay_parity_tape,
)
from ...domain.calculations.registry import (
    resolve_previous_filing_binding_values as _resolve_previous_filing_binding_values,
)
from ...domain.calculations.registry import (
    resolve_relation_values_from_observations as _resolve_relation_values_from_observations,
)
from ...domain.calculations.registry import (
    run_parity_scenario as _run_parity_scenario,
)
from ...domain.calculations.registry import (
    save_parity_tape as _save_parity_tape,
)
from ...domain.calculations.registry import verify_legal_catalogue as _verify_legal_catalogue
from ...domain.calculations.registry import (
    verify_workbook_backend as _verify_workbook_backend,
)
from ...domain.period import period_end_date as _period_end_date
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
from ._errors import RegistryApplicationError, RegistryApplicationInputError

_ORACLE_ENVIRONMENT_VALUES: tuple[str, ...] = tuple(sorted(member.value for member in _OracleEnvironment))


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


class RegistryWorkbookParityDetailReport(BaseModel):
    """Workbook parity coverage declared by one registry revision."""

    model_config = ConfigDict(frozen=True)

    id: str
    workbook_source: str
    formula_coverage: str
    runner_required: bool
    output_cell_count: int


class RegistryRevisionDetailReport(BaseModel):
    """Read-only details for one modelo revision from the central registry."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    revision: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    export_layout_ids: tuple[str, ...]
    export_layout_count: int
    export_record_count: int
    export_field_count: int
    deadline_window_count: int
    deadline_periods: tuple[str, ...]
    relation_ids: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_ids: tuple[str, ...]
    filing_schedule_count: int
    portal_guard_policy_ids: tuple[str, ...]
    workbook_parity: tuple[RegistryWorkbookParityDetailReport, ...]
    support_removal_decision_count: int


class FiledStateVerificationReport(BaseModel):
    """Local registry calculation versus filed AEAT state verification report."""

    model_config = ConfigDict(frozen=True)

    observation_path: str
    source_observation_paths: tuple[str, ...]
    comparison: _RegistryFiledStateComparison


class RegistryOracleAuditReport(BaseModel):
    """Live-parity oracle binding audit report."""

    model_config = ConfigDict(frozen=True)

    environment: str
    registered_oracle_ids: tuple[str, ...]
    failure_count: int
    failures: tuple[str, ...]
    applicability_declarations: tuple[_CrossReferenceApplicabilityDeclaracion, ...]
    orphan_oracle_ids: tuple[str, ...]


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


def inspect_registry_tree(registry_root: Path) -> RegistryTreeReport:
    """Load the registry tree and return a :class:`RegistryTreeReport` with stable read-only inventory counts."""
    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=_bundled_path())
    modelos = authority.modelos
    catalogues = authority.catalogues
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
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
        verified=False,
    )


def verify_registry_tree(registry_root: Path, *, source_root: Path) -> RegistryTreeReport:
    """Load and fail-fast validate every registry modelo against shared catalogues.

    Returns a :class:`RegistryTreeReport`.

    Runs a full strict audit including ``required_text`` corpus checks on
    every legal reference — the checks that the production authority skips
    so that pending corpus annotations never abort user-facing workflows.
    """
    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
    authority.validate_registry()
    # Run the strict corpus-text check that the production authority omits.
    _verify_legal_catalogue(authority.catalogues.legal, source_root=source_root, corpus_strict=True)
    modelos = authority.modelos
    catalogues = authority.catalogues
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        source_root=str(source_root),
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
        verified=True,
    )


def _typed_oracle_environment(environment: str) -> _OracleEnvironment:
    """Validate ``environment`` against :data:`_OracleEnvironment` literally.

    Replaces the previous ``cast(_OracleEnvironment, environment)``
    pattern after an untyped string check. The match statement
    returns each Literal arm verbatim so pyrefly narrows the return
    type exactly — no cast, no type-ignore escape. A future
    expansion of the Literal forces an explicit case here, surfacing
    the contract change at the validator rather than letting the
    cast silently widen.
    """
    match environment:
        case "production":
            return _OracleEnvironment.PRODUCTION
        case "test_environment":
            return _OracleEnvironment.TEST_ENVIRONMENT
        case "both":
            return _OracleEnvironment.BOTH
        case _:
            raise RegistryApplicationInputError(
                translated_message="application.registry.errors.invalid_oracle_environment",
                context={
                    "allowed_values": _ORACLE_ENVIRONMENT_VALUES,
                    "value": environment,
                },
            )


def audit_registry_oracles(registry_root: Path, *, environment: str) -> RegistryOracleAuditReport:
    """Audit registered live-parity oracles against every registry cross-reference.

    Returns a :class:`RegistryOracleAuditReport`.
    """
    typed_environment = _typed_oracle_environment(environment)
    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=_bundled_path())
    oracle_catalogue = _LiveParityCatalogue()
    oracle_catalogue.register(_AeatNifIvaCheckerOracle(), environment=_OracleEnvironment.PRODUCTION)
    oracle_catalogue.register(_GroiOracle(), environment=_OracleEnvironment.PRODUCTION)
    failures = _audit_registry_oracle_bindings(
        authority.modelos,
        oracle_catalogue,
        environment=typed_environment,
    )
    applicability_declarations = _collect_applicability_declarations(authority.modelos)
    orphan_oracle_ids = _collect_orphan_oracle_ids(authority.modelos, oracle_catalogue)
    return RegistryOracleAuditReport(
        environment=environment,
        registered_oracle_ids=tuple(sorted(oracle_catalogue.ids())),
        failure_count=len(failures),
        failures=tuple(failures),
        applicability_declarations=applicability_declarations,
        orphan_oracle_ids=tuple(orphan_oracle_ids),
    )


def verify_filed_state(
    *,
    observation_path: Path,
    source_observation_paths: tuple[Path, ...] = (),
    registry_root: Path | None = None,
    source_root: Path | None = None,
    required_casillas: tuple[str, ...] = (),
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
    binding_values = _resolve_previous_filing_binding_values(
        snapshot.revision,
        registry_source_observations,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    input_casillas = set()
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind == _InputKind.COMPUTED:
            continue
        if (
            casilla.input_kind == _InputKind.BOUND
            and casilla.binding is not None
            and (binding_def := bindings_by_id.get(casilla.binding)) is not None
            and binding_def.source == "previous_filing"
            and binding_def.id not in binding_values
        ):
            continue
        input_casillas.add(casilla.id)
    inputs: dict[str, Decimal] = {
        casilla_id: value
        for casilla_id, value in registry_observation.casilla_values.items()
        if casilla_id in input_casillas
    }
    relation_values = _resolve_relation_values_from_observations(
        snapshot.revision,
        registry_source_observations,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    calculation = _calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={
            "filing_period": _period_end_date(
                filing_year=filed_observation.ejercicio,
                registry_period=filing_period_token,
            ),
        },
        binding_values=binding_values,
        relation_values=relation_values,
    )
    casillas = required_casillas or tuple(
        casilla.id for casilla in snapshot.revision.casillas if casilla.input_kind == _InputKind.COMPUTED
    )
    comparison = _compare_calculation_to_filed_observation(
        calculation,
        registry_observation,
        required_casillas=casillas,
    )
    return FiledStateVerificationReport(
        observation_path=str(observation_path),
        source_observation_paths=tuple(str(path) for path in source_observation_paths),
        comparison=comparison,
    )


def verify_registry_workbooks(
    *,
    root: Path,
    limit: int | None = None,
    per_file_timeout_seconds: float = 10.0,
    resume_from: Path | None = None,
    output: Path | None = None,
) -> _WorkbookBackendVerificationReport:
    """Run workbook backend verification and optionally persist the JSON report."""
    previous_report = None
    if resume_from is not None:
        previous_report = _WorkbookBackendVerificationReport.model_validate_json(
            resume_from.read_text(encoding=_UTF_8_ENCODING),
        )
    report = _verify_workbook_backend(
        root,
        scan_limit=limit,
        per_file_timeout_seconds=per_file_timeout_seconds,
        previous_report=previous_report,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.model_dump_json(indent=2), encoding=_UTF_8_ENCODING)
    return report


def run_registry_parity(
    *,
    scenario_path: Path,
    registry_root: Path,
    source_root: Path,
    store_root: Path,
    output: Path | None = None,
):
    """Run one stored parity scenario and archive the resulting tape."""
    scenario = _load_parity_scenario(scenario_path)
    tape = _run_parity_scenario(
        scenario,
        registry_root=registry_root,
        source_root=source_root,
        scenario_path=scenario_path,
    )
    target = output or _generate_parity_tape_path(store_root, scenario.id, tape.created_at)
    _save_parity_tape(tape, target)
    return tape, target


def replay_registry_parity(
    *,
    tape_path: Path,
    registry_root: Path,
    source_root: Path,
):
    """Replay one archived parity tape against the current registry runtime."""
    tape = _load_parity_tape(tape_path)
    return _replay_parity_tape(
        tape,
        registry_root=registry_root,
        source_root=source_root,
        tape_path=tape_path,
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
                    id=str(reference.id),
                    workbook_source=str(reference.workbook_source),
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
                    legal_refs=tuple(str(ref) for ref in revision.legal_refs),
                    source_refs=tuple(str(ref) for ref in revision.source_refs),
                    export_layout_ids=tuple(str(layout.id) for layout in revision.export_layouts),
                    export_layout_count=len(revision.export_layouts),
                    export_record_count=len(export_records),
                    export_field_count=len(export_fields),
                    deadline_window_count=len(revision.deadline_windows),
                    deadline_periods=tuple(
                        sorted(window.period.registry_token for window in revision.deadline_windows),
                    ),
                    relation_ids=tuple(str(relation.id) for relation in revision.relations),
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
                    support_removal_decision_count=len(revision.support_removal_decisions),
                ),
            )
    return tuple(reports)


def _load_filed_observation(path: Path):
    return _FiledDeclaracionObservationStore(path.parent).load_observation(path)


__all__ = [
    "FiledStateVerificationReport",
    "RegistryApplicationError",
    "RegistryApplicationInputError",
    "RegistryCitationArticleProjection",
    "RegistryCitationReferenceProjection",
    "RegistryCitationShowCommand",
    "RegistryCitationShowReport",
    "RegistryCitationsListCommand",
    "RegistryCitationsListReport",
    "RegistryCitationsVerificationReport",
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
    "RegistryOracleAuditReport",
    "RegistryTopicProjection",
    "RegistryTreeReport",
    "audit_registry_oracles",
    "inspect_registry_tree",
    "list_registry_citations",
    "list_registry_manual_rules",
    "list_registry_manuals",
    "registry_manual_id",
    "replay_registry_parity",
    "run_registry_parity",
    "show_registry_citation",
    "show_registry_manual",
    "verify_filed_state",
    "verify_registry_citations",
    "verify_registry_manual",
    "verify_registry_tree",
    "verify_registry_workbooks",
]
