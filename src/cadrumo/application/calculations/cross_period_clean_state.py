"""Clean-state proof for filing-grade cross-period modelo dependencies.

:func:`evaluate_cross_period_clean_state` derives dependency requirements from a
:class:`RegistrySnapshot`, then joins filed
:class:`ModeloRecord` rows, calculation revisions, verification reports, and
justificante evidence into a
:class:`~application.calculations.cross_period_models.CrossPeriodCleanStateVerdict`.

The same verdict feeds modelo verification, filing, and export gates. See also
:class:`~application.calculations.cross_period_models.CrossPeriodDependencyEvidence`
for per-dependency blocker/advisory rows
and :class:`ValidatedRegistryAuthority` for
the authority surface that produces the snapshots evaluated here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from functools import cache
from typing import Final, NamedTuple

from ...core.aggregation import BindingSourceKind
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.period import Period, is_filing_period_token
from ...domain.calculations.registry.applicability_modelo202 import Modelo202Modality
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    relation_source_requirements,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import (
    ModeloRecordCatalogue,
)
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import VerificationReportCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from .cross_period_dependency_evaluation import evaluate_requirement
from .cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyInventory,
    CrossPeriodDependencyInventoryItem,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
    CrossPeriodExpectedMemberSet,
    Modelo202InstalmentNotOwedProvenance,
    OperatorAttestedValue,
    period_strictly_before_activity_start,
)
from .cross_period_suppressed_evidence import (
    qualifies_for_first_year_fractional_suppression,
    relax_same_year_local_chain,
    suppressed_first_year_fractional_evidence,
    suppressed_m111_no_retenciones_evidence,
    suppressed_modelo_not_applicable_evidence,
    suppressed_pre_activity_evidence,
    suppressed_zero_value_previous_filing_evidence,
)
from .m111_no_retenciones import is_m111_no_retenciones_period
from .modelo_202_base_source import is_modelo_202
from .modelo_202_instalment_resolution import (
    Modelo202InstalmentResolution,
    Modelo202InstalmentResolutionKind,
    Modelo202InstalmentResolver,
)
from .observations_repository import (
    CalculationObservationRepositoryProtocol,
)
from .per_grupo_member_keys import per_grupo_member_requirement_keys
from .verification_report_gate import require_verification_report_coordinates_current


def cross_period_dependency_requirements(
    snapshot: RegistrySnapshot,
    *,
    support: SupportedFilingYearsCatalogue | None = None,
) -> tuple[CrossPeriodDependencyRequirement, ...]:
    """Return the dependency records for ``snapshot``.

    Each previous-filing record is marked ``source_outside_envelope`` when the
    support envelope refuses its source filing year; the mark never removes a
    record, so the dependency inventory is the same whatever the envelope.
    ``support`` is the pinned operation's catalogue; omitted, the snapshot's own
    pinned catalogue decides, and a snapshot that carries none marks nothing.

    Derives
    :class:`~application.calculations.cross_period_models.CrossPeriodDependencyRequirement`
    records from :class:`RegistrySnapshot` through
    :func:`~domain.calculations.registry.bindings_previous_filing.previous_filing_observation_requirements`
    and
    :func:`~domain.calculations.registry.relations.relation_source_requirements`.
    """
    requirements: dict[
        tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]],
        CrossPeriodDependencyRequirement,
    ] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for item in _requirements_from_previous_filing(
            requirement,
            snapshot=snapshot,
            support=snapshot.supported_filing_years if support is None else support,
        ):
            requirements.setdefault(item.key, item)
    for requirement in relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for item in _requirements_from_relation(requirement):
            requirements.setdefault(item.key, item)
    return tuple(requirements.values())


class _RequirementPartition(NamedTuple):
    """In-scope vs. pre-activity-suppressed split of a registry-derived graph."""

    in_scope: tuple[CrossPeriodDependencyRequirement, ...]
    suppressed: tuple[CrossPeriodDependencyRequirement, ...]


class _CleanStateRepositories(NamedTuple):
    """Loaded repositories needed while evaluating one clean-state verdict."""

    filing_catalogue: ModeloRecordCatalogue
    calculation_catalogue: CalculationRevisionCatalogue
    verification_catalogue: VerificationReportCatalogue
    justificante_repository: JustificanteRepositoryProtocol


class _CleanStateRequirementScope(NamedTuple):
    """Registry requirements grouped by the clean-state disposition they receive."""

    not_applicable: tuple[CrossPeriodDependencyEvidence, ...]
    partition: _RequirementPartition
    first_year_fractional: tuple[CrossPeriodDependencyRequirement, ...]
    zero_value_previous_filing: tuple[CrossPeriodDependencyRequirement, ...]
    m111_no_retenciones: tuple[CrossPeriodDependencyRequirement, ...]
    modelo_202_not_owed: tuple[CrossPeriodDependencyEvidence, ...]


def partition_cross_period_requirements_by_activity_start(
    requirements: Iterable[CrossPeriodDependencyRequirement],
    *,
    activity_start_date: date | None,
    before_activity_unresolved_binding_ids: frozenset[str] = frozenset(),
) -> _RequirementPartition:
    """Split registry-derived requirements into in-scope and pre-activity-suppressed.

    A dependency anchor whose period falls strictly before
    ``activity_start_date`` is no-prior-obligation (absent-by-design) and is
    scoped out of the evaluated graph. The scoping is an application-layer
    filter over the registry-derived requirements - the registry stays pure
    and the declared date is a grounded input (the same field the deadline
    engine consumes), not a per-call ad hoc shrink.

    The suppression is uniform across BOTH ``previous_filing`` bindings and
    ``relation_source_requirements`` origins (the requirement carries its
    ``origin`` field; this predicate is origin-agnostic), so a first filer is
    never unblocked on one origin and
    trapped on the other.

    When ``activity_start_date`` is ``None`` every requirement stays in scope; the
    caller decides whether a missing declared date should fail closed.

    A requirement fed by a binding in ``before_activity_unresolved_binding_ids``
    stays in scope however early its period: the registry declares that the law
    gives such a period a figure of its own, so it is proven or stated, never
    scoped out.
    """
    if activity_start_date is None:
        return _RequirementPartition(tuple(requirements), ())
    in_scope: list[CrossPeriodDependencyRequirement] = []
    suppressed: list[CrossPeriodDependencyRequirement] = []
    for requirement in requirements:
        if period_strictly_before_activity_start(requirement.period, activity_start_date) and not any(
            origin_id in before_activity_unresolved_binding_ids for origin_id in requirement.origin_ids
        ):
            suppressed.append(requirement)
        else:
            in_scope.append(requirement)
    return _RequirementPartition(tuple(in_scope), tuple(suppressed))


def _revision_dependency_inventory_items(
    operation: PinnedAuthorityOperation, *, modelo_id: str, revision_id: str, filing_year: int, periods: Iterable[str]
) -> tuple[CrossPeriodDependencyInventoryItem, ...]:
    """Resolve filing-period snapshots in their declared order and retain dependencies."""
    items: list[CrossPeriodDependencyInventoryItem] = []
    for period in periods:
        # A symbolic or administrative selector covers filings without
        # naming one, so it has no single filing snapshot to inspect.
        if not is_filing_period_token(period):
            continue
        snapshot = operation.snapshot(
            modelo_id,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        )
        dependencies = cross_period_dependency_requirements(snapshot)
        if not dependencies:
            continue
        items.append(
            CrossPeriodDependencyInventoryItem(
                target_modelo=snapshot.modelo.id,
                target_revision_id=snapshot.revision.id,
                target_filing_year=snapshot.filing_year,
                target_period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
                dependencies=dependencies,
            ),
        )
    return tuple(items)


def cross_period_dependency_inventory(
    operation: PinnedAuthorityOperation,
    *,
    filing_year: int,
    modelos: Iterable[str] | None = None,
) -> CrossPeriodDependencyInventory:
    """Return snapshots with cross-period dependencies.

    The
    :class:`~application.calculations.cross_period_models.CrossPeriodDependencyInventory`
    is a backend coverage surface. It lets callers prove which modelos and
    periods are in scope for the clean-state guard before they wire
    model-specific workflow tests or operator diagnostics.

    The :class:`PinnedAuthorityOperation`
    supplies candidate modelos and resolves each target
    :class:`RegistrySnapshot` evaluated for
    dependency coverage.
    """
    selected_modelos = operation.modelo_ids() if modelos is None else tuple(modelos)
    items: list[CrossPeriodDependencyInventoryItem] = []
    for modelo_id in selected_modelos:
        directory = operation.modelo_directory(modelo_id)
        for revision in directory.revisions:
            if not revision.period_selector.includes_year(filing_year):
                continue
            # Dependency inventory is a filing-readiness surface. Applicability-
            # and calculation-grade revisions cannot lawfully produce the filing
            # snapshot consumed below, and therefore cannot own filing blockers.
            revision_payload = operation.revision(modelo_id, revision.id)
            if revision_payload.effective_authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            items.extend(
                _revision_dependency_inventory_items(
                    operation,
                    modelo_id=modelo_id,
                    revision_id=revision.id,
                    filing_year=filing_year,
                    periods=revision.period_selector.periods_for_year(filing_year),
                )
            )
    return CrossPeriodDependencyInventory(
        filing_year=filing_year,
        items=tuple(
            sorted(
                items,
                key=lambda item: (
                    item.target_modelo,
                    item.target_revision_id,
                    item.target_period.registry_token,
                ),
            ),
        ),
    )


def cross_period_clean_state_non_filer_modelos(
    snapshot: RegistrySnapshot,
    *,
    taxpayer_files_economic_activity: bool | None,
    not_applicable_source_modelos: frozenset[str] | None,
) -> frozenset[str]:
    """Return the source modelos the taxpayer is not expected to file.

    ``snapshot`` is a :class:`RegistrySnapshot`.
    """
    return frozenset(
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if (not classification.taxpayer_files_source)
        or (classification.conditional_on_economic_activity and taxpayer_files_economic_activity is False)
        or (
            classification.conditional_on_economic_activity
            and not_applicable_source_modelos is not None
            and classification.source_modelo in not_applicable_source_modelos
        )
    )


def _not_applicable_dependencies(
    all_requirements: tuple[CrossPeriodDependencyRequirement, ...],
    non_filer_modelos: frozenset[str],
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    return tuple(
        suppressed_modelo_not_applicable_evidence(requirement)
        for requirement in all_requirements
        if requirement.source_modelo in non_filer_modelos
    )


def _load_clean_state_repositories(
    *,
    operation: PinnedAuthorityOperation,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepositoryProtocol,
    calculation_catalogue: CalculationRevisionCatalogue | None,
    filing_catalogue: ModeloRecordCatalogue | None,
    verification_catalogue: VerificationReportCatalogue | None,
) -> _CleanStateRepositories:
    """Load all persistence inputs once for a clean-state evaluation."""
    return _CleanStateRepositories(
        filing_catalogue=filing_repository.load() if filing_catalogue is None else filing_catalogue,
        calculation_catalogue=(
            calculation_repository.load(operation=operation) if calculation_catalogue is None else calculation_catalogue
        ),
        verification_catalogue=require_verification_report_coordinates_current(
            verification_repository.load(operation=operation)
            if verification_catalogue is None
            else verification_catalogue,
            operation=operation,
        ),
        justificante_repository=justificante_repository,
    )


def _requirements_outside_non_filer_modelos(
    requirements: tuple[CrossPeriodDependencyRequirement, ...],
    non_filer_modelos: frozenset[str],
) -> tuple[CrossPeriodDependencyRequirement, ...]:
    return tuple(requirement for requirement in requirements if requirement.source_modelo not in non_filer_modelos)


def _first_year_fractional_requirements(
    requirements: Iterable[CrossPeriodDependencyRequirement],
    *,
    modelo_202_modality: Modelo202Modality | None,
    activity_start_date: date | None,
    operation: PinnedAuthorityOperation,
) -> tuple[CrossPeriodDependencyRequirement, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=modelo_202_modality,
            activity_start_date=activity_start_date,
            operation=operation,
        )
    )


def _zero_exemptible_binding_ids(
    snapshot: RegistrySnapshot, zero_value_previous_filing_binding_ids: frozenset[str] | None
) -> frozenset[str] | None:
    """The zero-valued carries a typed zero may exempt: never one whose zero the registry says must be attested.

    Where a zero is the figure that benefits the taxpayer, a typed zero proves
    nothing, so only an attestation or the earlier return makes it clean.
    """
    if zero_value_previous_filing_binding_ids is None:
        return None
    attested_only = {binding.id for binding in snapshot.revision.bindings if binding.zero_needs_attestation}
    return frozenset(item for item in zero_value_previous_filing_binding_ids if item not in attested_only)


def _zero_value_previous_filing_requirements(
    requirements: Iterable[CrossPeriodDependencyRequirement],
    zero_value_previous_filing_binding_ids: frozenset[str] | None,
) -> tuple[CrossPeriodDependencyRequirement, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if _requirement_scoped_by_zero_value_previous_filing(
            requirement,
            zero_value_previous_filing_binding_ids,
        )
    )


def _filing_record_held(requirement: CrossPeriodDependencyRequirement, filing_catalogue: ModeloRecordCatalogue) -> bool:
    """Whether a filing record exists for the requirement's modelo, filing year and period."""
    return any(
        str(record.modelo) == requirement.source_modelo
        and record.filing_year == requirement.filing_year
        and record.period == requirement.period
        for record in filing_catalogue.records.values()
    )


def upstream_source_absent(
    requirement: CrossPeriodDependencyRequirement,
    *,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_catalogue: ModeloRecordCatalogue,
    work_catalogue: WorkUnitCatalogue,
) -> bool:
    """Whether the application holds no source at all for ``requirement``.

    A source is held when a work unit, a filing record or a captured observation
    exists for its modelo, filing year and period. Edit admission and clean-state
    evaluation both decide through here, so they cannot disagree.
    """
    layers = observation_repository.load_observation_layers(requirement.source_modelo, requirement.period)
    if layers.official is not None or layers.pending_local is not None:
        return False
    if _filing_record_held(requirement, filing_catalogue):
        return False
    return not any(
        str(unit.modelo) == requirement.source_modelo
        and unit.filing_year == requirement.filing_year
        and unit.period == requirement.period
        for unit in work_catalogue.work_units.values()
    )


_ATTESTABLE_ORIGINS: Final[frozenset[CrossPeriodDependencyOrigin]] = frozenset(
    {CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING, CrossPeriodDependencyOrigin.REGISTRY_RELATION}
)
"""The origins whose scalar carries an operator may state a figure for when no source is held."""

_ATTESTABLE_BINDING_SOURCES: Final[frozenset[BindingSourceKind]] = frozenset(
    {BindingSourceKind.PREVIOUS_FILING, BindingSourceKind.RELATION_PREFILL}
)


def declared_attestable_carry_requirements(
    snapshot: RegistrySnapshot,
    *,
    support: SupportedFilingYearsCatalogue | None = None,
) -> dict[BindingId, tuple[CrossPeriodDependencyRequirement, ...]]:
    """Return, per scalar carry binding the registry declares a stated figure possible for, the returns it reads.

    This is the declaration alone, whatever the profile holds: a binding is
    listed when its value is read from earlier returns through an attestable
    origin, so a figure the filer states can stand in for them. Whether the
    statement is admitted now depends on which of those returns the profile
    holds (:func:`attestable_carry_sources`). ``support`` is as for
    :func:`cross_period_dependency_requirements`.
    """
    return {
        binding_id: tuple(requirements)
        for binding_id, requirements in _attestable_requirements_by_binding(snapshot, support=support).items()
    }


def _attestable_requirements_by_binding(
    snapshot: RegistrySnapshot,
    *,
    support: SupportedFilingYearsCatalogue | None,
) -> dict[BindingId, list[CrossPeriodDependencyRequirement]]:
    """Group the attestable-origin requirements under each scalar carry binding they feed."""
    scalar_binding_ids = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source in _ATTESTABLE_BINDING_SOURCES and binding.value.channel is not BindingValueChannel.ROW_SET
    }
    by_binding: dict[BindingId, list[CrossPeriodDependencyRequirement]] = {}
    if not scalar_binding_ids:
        return by_binding
    for requirement in cross_period_dependency_requirements(snapshot, support=support):
        if requirement.origin not in _ATTESTABLE_ORIGINS:
            continue
        for binding_id in requirement.origin_ids:
            if binding_id in scalar_binding_ids:
                by_binding.setdefault(binding_id, []).append(requirement)
    return by_binding


def attestable_carry_sources(
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_catalogue: ModeloRecordCatalogue,
    work_catalogue: WorkUnitCatalogue,
    set_aside_binding_ids: frozenset[BindingId] = frozenset(),
) -> dict[BindingId, tuple[CrossPeriodDependencyRequirement, ...]]:
    """Return, per scalar carry binding, the source requirements the application holds nothing of.

    A previous-filing binding reads one earlier filing; a relation-prefill
    binding folds several source periods. A binding is offered only when
    *every* one of its sources is absent: where any is held the carry follows
    the sources, and a partial statement is not admitted. Row-set bindings stay
    sourced from records and are never offered. A binding in
    ``set_aside_binding_ids``, whose held return the current return's marks set
    aside, is offered whether or not its sources are held.
    """
    by_binding = _attestable_requirements_by_binding(snapshot, support=operation.supported_filing_years())
    return {
        binding_id: tuple(requirements)
        for binding_id, requirements in by_binding.items()
        if binding_id in set_aside_binding_ids
        or all(
            upstream_source_absent(
                requirement,
                observation_repository=observation_repository,
                filing_catalogue=filing_catalogue,
                work_catalogue=work_catalogue,
            )
            for requirement in requirements
        )
    }


def attestable_carry_binding_ids(
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_catalogue: ModeloRecordCatalogue,
    work_catalogue: WorkUnitCatalogue,
    set_aside_binding_ids: frozenset[BindingId] = frozenset(),
) -> frozenset[BindingId]:
    """Return the bindings an operator may state a figure for."""
    return frozenset(
        attestable_carry_sources(
            snapshot,
            operation=operation,
            observation_repository=observation_repository,
            filing_catalogue=filing_catalogue,
            work_catalogue=work_catalogue,
            set_aside_binding_ids=set_aside_binding_ids,
        )
    )


def _stated_values_for(
    requirement: CrossPeriodDependencyRequirement,
    operator_value_attestations: Mapping[str, OperatorAttestedValue] | None,
) -> tuple[OperatorAttestedValue, ...]:
    """Return the figures the operator stated for every origin binding of ``requirement``, or none.

    An attestation counts only for the source filings it names, so one that
    does not cover this requirement's source period leaves it unsatisfied.
    """
    if (
        operator_value_attestations is None
        or len(operator_value_attestations) == 0
        or requirement.origin not in _ATTESTABLE_ORIGINS
    ):
        return ()
    stated = tuple(operator_value_attestations.get(origin_id) for origin_id in requirement.origin_ids)
    if all(
        item is not None
        and item.covers(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period_token=requirement.period.registry_token,
        )
        for item in stated
    ):
        return tuple(item for item in stated if item is not None)
    return ()


def _attestation_conflicts(
    requirement: CrossPeriodDependencyRequirement,
    stated: tuple[OperatorAttestedValue, ...],
    observation_repository: CalculationObservationRepositoryProtocol,
) -> tuple[OperatorAttestedValue, ...]:
    """Return the stated figures that conflict with the source that now exists.

    A relation folds several sources into one figure, so a single held source
    cannot be compared with the stated total: the relation follows its sources
    and any held source makes the statement conflict. A previous-filing carry
    conflicts only when the observation's value differs.
    """
    if requirement.origin is CrossPeriodDependencyOrigin.REGISTRY_RELATION:
        return stated
    layers = observation_repository.load_observation_layers(requirement.source_modelo, requirement.period)
    effective = layers.effective
    if effective is None or len(stated) != 1:
        return ()
    observed = [
        observation.value
        for observation in effective.observation.observations
        if observation.casilla_id in requirement.source_casilla_ids
    ]
    if not observed:
        return ()
    try:
        differs = Decimal(stated[0].value) != Decimal(str(observed[0]))
    except ArithmeticError:
        return stated
    return stated if differs else ()


def _operator_attested_disposition(
    evidence: CrossPeriodDependencyEvidence,
    stated: tuple[OperatorAttestedValue, ...],
    *,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_catalogue: ModeloRecordCatalogue,
    work_catalogue: WorkUnitCatalogue,
) -> CrossPeriodDependencyEvidence:
    """Clean on the stated figure while no source exists; otherwise the source decides.

    A source that has since appeared with a different value is a conflict, never
    resolved in favour of the attestation.
    """
    requirement = evidence.requirement
    if upstream_source_absent(
        requirement,
        observation_repository=observation_repository,
        filing_catalogue=filing_catalogue,
        work_catalogue=work_catalogue,
    ):
        return CrossPeriodDependencyEvidence(requirement=requirement, operator_attested_absent_upstream=stated)
    conflicts = _attestation_conflicts(requirement, stated, observation_repository)
    if conflicts:
        return evidence.model_copy(update={"operator_attestation_conflict": conflicts})
    return evidence


def _m111_no_retenciones_requirements(
    requirements: Iterable[CrossPeriodDependencyRequirement],
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[CrossPeriodDependencyRequirement, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if is_m111_no_retenciones_period(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period_token=requirement.period.registry_token,
            attested_periods=m111_no_retenciones_periods or frozenset(),
            operation=operation,
        )
    )


def _modelo_202_not_owed_evidence(
    requirement: CrossPeriodDependencyRequirement,
    resolution: Modelo202InstalmentResolution,
) -> CrossPeriodDependencyEvidence | None:
    """Return the clean row of an instalment its own verdict says was not owed, or ``None``."""
    if resolution.kind is not Modelo202InstalmentResolutionKind.NOT_OWED or resolution.grounds is None:
        return None
    base = resolution.base
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        modelo_202_instalment_not_owed=Modelo202InstalmentNotOwedProvenance(
            grounds=resolution.grounds,
            base_value=None if base is None else base.value,
            base_basis=None if base is None else base.basis,
            base_source_modelo=None if base is None else base.source_modelo,
            base_source_period=None if base is None else base.source_period,
        ),
    )


def _modelo_202_not_owed_dependencies(
    requirements: Iterable[CrossPeriodDependencyRequirement],
    *,
    resolver: Modelo202InstalmentResolver | None,
    filing_catalogue: ModeloRecordCatalogue,
    operation: PinnedAuthorityOperation,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    """Scope out the Modelo 202 instalments that were rightly never filed.

    An instalment whose own verdict says nothing was owed contributes a proven
    0.00 (Orden HFP/227/2017 art. 1.3; LIS art. 40). Any instalment held by a
    filing record or a presented filing follows that filing instead, and an
    instalment whose verdict is unknown, incomplete or owed stays in scope and
    keeps blocking as an absent source.
    """
    if resolver is None:
        return ()
    resolutions: dict[Period, Modelo202InstalmentResolution] = {}
    rows: list[CrossPeriodDependencyEvidence] = []
    for requirement in requirements:
        if not is_modelo_202(requirement.source_modelo, operation=operation) or _filing_record_held(
            requirement, filing_catalogue
        ):
            continue
        if requirement.period not in resolutions:
            resolutions[requirement.period] = resolver(requirement.period)
        row = _modelo_202_not_owed_evidence(requirement, resolutions[requirement.period])
        if row is not None:
            rows.append(row)
    return tuple(rows)


def _clean_state_requirement_scope(
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
    activity_start_date: date | None,
    modelo_202_modality: Modelo202Modality | None,
    taxpayer_files_economic_activity: bool | None,
    not_applicable_source_modelos: frozenset[str] | None,
    zero_value_previous_filing_binding_ids: frozenset[str] | None,
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None,
    operator_value_attestations: Mapping[str, OperatorAttestedValue] | None,
    modelo_202_instalment_resolver: Modelo202InstalmentResolver | None,
    filing_catalogue: ModeloRecordCatalogue,
) -> _CleanStateRequirementScope:
    """Derive and disposition registry requirements before evaluating their sources."""
    all_requirements = cross_period_dependency_requirements(snapshot, support=operation.supported_filing_years())
    non_filer_modelos = cross_period_clean_state_non_filer_modelos(
        snapshot,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
    )
    partition = partition_cross_period_requirements_by_activity_start(
        _requirements_outside_non_filer_modelos(all_requirements, non_filer_modelos),
        activity_start_date=activity_start_date,
        before_activity_unresolved_binding_ids=frozenset(
            binding.id for binding in snapshot.revision.bindings if binding.before_activity_unresolved
        ),
    )
    attested_keys = {
        requirement.key
        for requirement in partition.in_scope
        if _stated_values_for(requirement, operator_value_attestations)
    }
    first_year_fractional = _first_year_fractional_requirements(
        partition.in_scope,
        modelo_202_modality=modelo_202_modality,
        activity_start_date=activity_start_date,
        operation=operation,
    )
    first_year_keys = {requirement.key for requirement in first_year_fractional}
    return _CleanStateRequirementScope(
        not_applicable=_not_applicable_dependencies(all_requirements, non_filer_modelos),
        partition=partition,
        first_year_fractional=first_year_fractional,
        zero_value_previous_filing=tuple(
            requirement
            for requirement in _zero_value_previous_filing_requirements(
                partition.in_scope,
                _zero_exemptible_binding_ids(snapshot, zero_value_previous_filing_binding_ids),
            )
            if requirement.key not in attested_keys
        ),
        m111_no_retenciones=_m111_no_retenciones_requirements(
            partition.in_scope,
            m111_no_retenciones_periods,
            operation=operation,
        ),
        modelo_202_not_owed=_modelo_202_not_owed_dependencies(
            (requirement for requirement in partition.in_scope if requirement.key not in first_year_keys),
            resolver=modelo_202_instalment_resolver,
            filing_catalogue=filing_catalogue,
            operation=operation,
        ),
    )


def _scoped_out_keys(
    scope: _CleanStateRequirementScope,
) -> frozenset[tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]]]:
    """The keys of the requirements a scope settles without evaluating them."""
    return frozenset(
        requirement.key
        for requirement in (
            *scope.first_year_fractional,
            *scope.zero_value_previous_filing,
            *scope.m111_no_retenciones,
            *(evidence.requirement for evidence in scope.modelo_202_not_owed),
        )
    )


def _evaluate_in_scope_requirement(
    requirement: CrossPeriodDependencyRequirement,
    *,
    operation: PinnedAuthorityOperation,
    bucket_id: str,
    observation_repository: CalculationObservationRepositoryProtocol,
    repositories: _CleanStateRepositories,
    taxpayer_tax_id: str | None,
    expected_member_sets_by_key: Mapping[
        tuple[str, int, str],
        CrossPeriodExpectedMemberSet,
    ],
    target_filing_year: int,
    operator_value_attestations: Mapping[str, OperatorAttestedValue] | None,
    work_catalogue: WorkUnitCatalogue,
    attestable_binding_ids: Callable[[], frozenset[BindingId]],
    set_aside_binding_ids: frozenset[BindingId],
) -> CrossPeriodDependencyEvidence:
    """Evaluate one requirement against its sources, then apply the filer's statement and the chain relaxation."""
    stated = _stated_values_for(requirement, operator_value_attestations)
    if requirement.origin_ids and all(origin_id in set_aside_binding_ids for origin_id in requirement.origin_ids):
        return _set_aside_evidence(requirement, stated)
    evidence = evaluate_requirement(
        requirement,
        operation=operation,
        bucket_id=bucket_id,
        observation_repository=observation_repository,
        filing_catalogue=repositories.filing_catalogue,
        calculation_catalogue=repositories.calculation_catalogue,
        verification_catalogue=repositories.verification_catalogue,
        justificante_repository=repositories.justificante_repository,
        taxpayer_tax_id=taxpayer_tax_id,
        expected_member_set=expected_member_sets_by_key.get(
            (requirement.source_modelo, requirement.filing_year, requirement.period.registry_token),
        ),
    )
    if stated:
        evidence = _operator_attested_disposition(
            evidence,
            stated,
            observation_repository=observation_repository,
            filing_catalogue=repositories.filing_catalogue,
            work_catalogue=work_catalogue,
        )
    evidence = relax_same_year_local_chain(evidence, target_filing_year=target_filing_year)
    if (
        evidence.blockers
        and not evidence.requirement.requires_member_fan_in
        and all(origin_id in attestable_binding_ids() for origin_id in requirement.origin_ids)
    ):
        evidence = evidence.model_copy(update={"attestation_admitted": True})
    return evidence


def _evaluate_in_scope_dependencies(
    scope: _CleanStateRequirementScope,
    *,
    operation: PinnedAuthorityOperation,
    bucket_id: str,
    observation_repository: CalculationObservationRepositoryProtocol,
    repositories: _CleanStateRepositories,
    taxpayer_tax_id: str | None,
    expected_member_sets_by_key: Mapping[
        tuple[str, int, str],
        CrossPeriodExpectedMemberSet,
    ],
    target_filing_year: int,
    operator_value_attestations: Mapping[str, OperatorAttestedValue] | None,
    work_catalogue: WorkUnitCatalogue,
    snapshot: RegistrySnapshot,
    set_aside_binding_ids: frozenset[BindingId] = frozenset(),
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    """Evaluate only requirements that were not explicitly scoped out."""
    suppressed_keys = _scoped_out_keys(scope)

    @cache
    def attestable_binding_ids() -> frozenset[BindingId]:
        return attestable_carry_binding_ids(
            snapshot,
            operation=operation,
            observation_repository=observation_repository,
            filing_catalogue=repositories.filing_catalogue,
            work_catalogue=work_catalogue,
            set_aside_binding_ids=set_aside_binding_ids,
        )

    return tuple(
        _evaluate_in_scope_requirement(
            requirement,
            operation=operation,
            bucket_id=bucket_id,
            observation_repository=observation_repository,
            repositories=repositories,
            taxpayer_tax_id=taxpayer_tax_id,
            expected_member_sets_by_key=expected_member_sets_by_key,
            target_filing_year=target_filing_year,
            operator_value_attestations=operator_value_attestations,
            work_catalogue=work_catalogue,
            attestable_binding_ids=attestable_binding_ids,
            set_aside_binding_ids=set_aside_binding_ids,
        )
        for requirement in scope.partition.in_scope
        if requirement.key not in suppressed_keys
    )


def _set_aside_evidence(
    requirement: CrossPeriodDependencyRequirement,
    stated: tuple[OperatorAttestedValue, ...],
) -> CrossPeriodDependencyEvidence:
    """A carry whose held return the current return's marks set aside: only the filer's statement settles it."""
    if stated:
        return CrossPeriodDependencyEvidence(requirement=requirement, operator_attested_absent_upstream=stated)
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        blockers=(CrossPeriodCleanStateBlocker.HELD_SOURCE_SET_ASIDE,),
        attestation_admitted=True,
    )


def _pre_activity_dependencies(
    partition: _RequirementPartition,
    activity_start_date: date | None,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    if activity_start_date is None:
        return ()
    return tuple(
        suppressed_pre_activity_evidence(requirement, activity_start_date=activity_start_date)
        for requirement in partition.suppressed
    )


def _first_year_fractional_dependencies(
    requirements: tuple[CrossPeriodDependencyRequirement, ...],
    activity_start_date: date | None,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    if activity_start_date is None:
        return ()
    return tuple(
        suppressed_first_year_fractional_evidence(requirement, activity_start_date=activity_start_date)
        for requirement in requirements
    )


def _scoped_advisory_dependencies(
    scope: _CleanStateRequirementScope,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    return (
        *tuple(
            suppressed_zero_value_previous_filing_evidence(requirement)
            for requirement in scope.zero_value_previous_filing
        ),
        *tuple(suppressed_m111_no_retenciones_evidence(requirement) for requirement in scope.m111_no_retenciones),
    )


def _clean_state_dependencies(
    scope: _CleanStateRequirementScope,
    *,
    in_scope: tuple[CrossPeriodDependencyEvidence, ...],
    activity_start_date: date | None,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    return (
        *in_scope,
        *_pre_activity_dependencies(scope.partition, activity_start_date),
        *scope.not_applicable,
        *_first_year_fractional_dependencies(scope.first_year_fractional, activity_start_date),
        *_scoped_advisory_dependencies(scope),
        *scope.modelo_202_not_owed,
    )


def evaluate_cross_period_clean_state(
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
    bucket_id: str,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepositoryProtocol,
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
    filing_catalogue: ModeloRecordCatalogue | None = None,
    verification_catalogue: VerificationReportCatalogue | None = None,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    taxpayer_tax_id: str | None = None,
    activity_start_date: date | None = None,
    modelo_202_modality: Modelo202Modality | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    not_applicable_source_modelos: frozenset[str] | None = None,
    zero_value_previous_filing_binding_ids: frozenset[str] | None = None,
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None = None,
    operator_value_attestations: Mapping[str, OperatorAttestedValue] | None = None,
    work_catalogue: WorkUnitCatalogue | None = None,
    modelo_202_instalment_resolver: Modelo202InstalmentResolver | None = None,
    set_aside_binding_ids: frozenset[BindingId] = frozenset(),
) -> CrossPeriodCleanStateVerdict:
    """Evaluate cross-period dependencies and return a clean-state verdict.

    The supplied :class:`RegistrySnapshot` is
    the authority for target revision, filing period, and dependency
    requirements.

    The optional catalogues may reuse the caller's freshly validated catalogues
    within the same synchronous invocation and pinned operation. Omission loads
    it here. This does not replace an independent persistence/currentness read.

    ``activity_start_date`` is the operator-declared activity-start date carried on
    the profile (the same field the deadline engine consumes for pre-start
    suppression). When supplied, a dependency whose period falls strictly before it
    is scoped out as no-prior-obligation: it produces a clean,
    facet-stamped evidence row instead of an evaluated blocker, and is NOT loaded
    from storage. When ``None`` every dependency is evaluated as before - the
    caller decides whether a missing declared date should fail closed.

    ``modelo_202_modality`` is the derived Modelo 202 pago-fraccionado modality
    (:func:`~domain.calculations.registry.applicability_modelo202.derive_modelo_202_modality`). When it
    is ``ART_40_2_OPTIONAL`` (modalidad cuota) AND the recorded
    ``activity_start_date`` places the taxpayer's first IS year at or after the
    target filing year, the Modelo 202 cross-period dependency is scoped out as a
    first-year no-fractional-payment obligation: a first-year IS filer in
    modalidad cuota has no prior IS return to provide the art. 40.2 cuota basis, so
    no pago fraccionado is owed. It is fail-closed everywhere else: under
    ``ART_40_3_MANDATORY`` / ``INCOMPLETE`` / ``None`` modality, when no
    activity-start date is recorded, or when the year is not the first IS year, the
    Modelo 202 dependency stays in scope and keeps blocking. The default ``None``
    preserves the prior behaviour (no Modelo 202 suppression).

    ``not_applicable_source_modelos`` carries source modelos that the caller has
    positively resolved as not applicable for the taxpayer. It is only applied to
    dependency classifications already marked conditional on economic activity,
    so the payee/payer classification remains the primary retenciones boundary
    while the mutually-exclusive M130/M131 regime split can still be enforced
    without blocking on the modelo the taxpayer does not file. ``None`` means the
    caller could not decide, so no suppression occurs.

    ``zero_value_previous_filing_binding_ids`` carries whitelisted previous-filing
    binding ids whose target revision value is explicitly zero. Those requirements
    are retained as clean advisory rows rather than demanding evidence of a prior
    filing for a carry the taxpayer is not claiming. Nonzero carries and every
    binding not named here stay fully in scope.

    ``m111_no_retenciones_periods`` carries explicit profile attestations that no
    Modelo 111 filing obligation existed for a source period because no rentas
    subject to withholding/ingreso a cuenta were paid. It scopes out only those
    exact M111 periods; nonzero and unknown periods remain fully evaluated.

    ``operator_value_attestations`` carries, per binding id, the figure the
    operator stated for earlier filings. It satisfies a scalar previous-filing or
    relation-prefill dependency only while the application holds no source for
    it (no work unit in ``work_catalogue``, no filing record, no observation),
    whether the source year is inside the support envelope or not, and only when
    every origin binding of the requirement is attested for that very source
    period. The requirement then yields a clean row of kind
    ``operator_attested_absent_upstream``. Where a source exists the dependency
    follows it as before; a previous-filing source whose value differs from the
    recorded figure, or any held source of a relation, is a conflict that
    blocks. A plain override or a blank binding never satisfies it.

    ``modelo_202_instalment_resolver`` resolves a Modelo 202 instalment the
    target reads. An instalment no filing record holds and whose resolution is
    not owed, because its own verdict says no ingreso resulted (Orden
    HFP/227/2017 art. 1.3 below the LIS art. 40.3 threshold), yields a clean
    row of kind ``modelo_202_instalment_not_owed``: it was rightly never filed
    and contributes 0.00. A filed instalment, and one whose verdict is unknown,
    incomplete or owed, is evaluated as before. ``None`` resolves nothing, so
    every unfiled instalment keeps blocking.

    ``set_aside_binding_ids`` names the carries whose held earlier return the
    target's marked boxes set aside (see
    :func:`~domain.calculations.registry.binding_prior_value_rules.set_aside_binding_ids`).
    Their requirements are not read from any source: the filer's statement makes
    them clean, and without one they block with the statement admitted.
    """
    repositories = _load_clean_state_repositories(
        operation=operation,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        justificante_repository=justificante_repository,
        calculation_catalogue=calculation_catalogue,
        filing_catalogue=filing_catalogue,
        verification_catalogue=verification_catalogue,
    )
    scope = _clean_state_requirement_scope(
        snapshot,
        operation=operation,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids,
        m111_no_retenciones_periods=m111_no_retenciones_periods,
        operator_value_attestations=operator_value_attestations,
        modelo_202_instalment_resolver=modelo_202_instalment_resolver,
        filing_catalogue=repositories.filing_catalogue,
    )
    return CrossPeriodCleanStateVerdict(
        bucket_id=bucket_id,
        target_modelo=snapshot.modelo.id,
        target_filing_year=snapshot.filing_year,
        target_period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        dependencies=_clean_state_dependencies(
            scope,
            in_scope=_evaluate_in_scope_dependencies(
                scope,
                operation=operation,
                bucket_id=bucket_id,
                observation_repository=observation_repository,
                repositories=repositories,
                taxpayer_tax_id=taxpayer_tax_id,
                expected_member_sets_by_key=_expected_member_sets_by_key(expected_member_sets),
                target_filing_year=snapshot.filing_year,
                operator_value_attestations=operator_value_attestations,
                work_catalogue=WorkUnitCatalogue() if work_catalogue is None else work_catalogue,
                snapshot=snapshot,
                set_aside_binding_ids=set_aside_binding_ids,
            ),
            activity_start_date=activity_start_date,
        ),
    )


def _requirement_scoped_by_zero_value_previous_filing(
    requirement: CrossPeriodDependencyRequirement,
    zero_value_previous_filing_binding_ids: frozenset[str] | None,
) -> bool:
    if not (zero_value_previous_filing_binding_ids is not None and zero_value_previous_filing_binding_ids):
        return False
    return requirement.origin is CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING and all(
        origin_id in zero_value_previous_filing_binding_ids for origin_id in requirement.origin_ids
    )


def _requirements_from_previous_filing(
    requirement: RegistryFoldRequirement,
    *,
    snapshot: RegistrySnapshot,
    support: SupportedFilingYearsCatalogue | None,
) -> Iterable[CrossPeriodDependencyRequirement]:
    grouped_keys = per_grupo_member_requirement_keys(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    source_period = requirement.periods[0]
    yield CrossPeriodDependencyRequirement(
        source_modelo=requirement.source_modelo,
        filing_year=requirement.filing_year,
        period=Period.from_year_and_code(requirement.filing_year, source_period),
        source_casilla_ids=requirement.source_casilla_ids,
        required_source_casilla_ids=requirement.required_source_casilla_ids,
        source_presence_groups=requirement.source_presence_groups,
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=requirement.binding_ids,
        legal_refs=requirement.legal_refs,
        source_refs=requirement.source_refs,
        requires_member_fan_in=(requirement.source_modelo, requirement.filing_year, source_period) in grouped_keys,
        source_outside_envelope=support is not None and not support.admits_filing_year(requirement.filing_year),
    )


def _requirements_from_relation(
    requirement: RegistryFoldRequirement,
) -> Iterable[CrossPeriodDependencyRequirement]:
    for period in requirement.periods:
        yield CrossPeriodDependencyRequirement(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=Period.from_year_and_code(requirement.filing_year, period),
            source_casilla_ids=requirement.source_casilla_ids,
            origin=CrossPeriodDependencyOrigin.REGISTRY_RELATION,
            origin_ids=requirement.target_bindings,
            legal_refs=requirement.legal_refs,
            source_refs=requirement.source_refs,
        )


def _expected_member_sets_by_key(
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> Mapping[tuple[str, int, str], CrossPeriodExpectedMemberSet]:
    return {item.requirement_key: item for item in expected_member_sets}


__all__ = [
    "attestable_carry_binding_ids",
    "attestable_carry_sources",
    "cross_period_dependency_inventory",
    "cross_period_dependency_requirements",
    "declared_attestable_carry_requirements",
    "evaluate_cross_period_clean_state",
    "partition_cross_period_requirements_by_activity_start",
    "upstream_source_absent",
]
