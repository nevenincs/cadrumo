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

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Final, NamedTuple

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.modelo import Modelo
from ...core.period import Period, is_filing_period_token
from ...domain.calculations.registry.applicability_modelo202 import Modelo202Modality
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    relation_source_requirements,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
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
from ._per_grupo_member_keys import per_grupo_member_requirement_keys
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
    NoPriorObligationProvenance,
    NoPriorObligationProvenanceKind,
    period_strictly_before_activity_start,
)
from .m111_no_retenciones import is_m111_no_retenciones_period
from .observations_repository import (
    CalculationObservationRepositoryProtocol,
)
from .verification_report_gate import require_verification_report_coordinates_current


def cross_period_dependency_requirements(snapshot: RegistrySnapshot) -> tuple[CrossPeriodDependencyRequirement, ...]:
    """Return the dependency records for ``snapshot``.

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
        for item in _requirements_from_previous_filing(requirement, snapshot=snapshot):
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


def partition_cross_period_requirements_by_activity_start(
    requirements: Iterable[CrossPeriodDependencyRequirement],
    *,
    activity_start_date: date | None,
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
    """
    if activity_start_date is None:
        return _RequirementPartition(tuple(requirements), ())
    in_scope: list[CrossPeriodDependencyRequirement] = []
    suppressed: list[CrossPeriodDependencyRequirement] = []
    for requirement in requirements:
        if period_strictly_before_activity_start(requirement.period, activity_start_date):
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


def _suppressed_pre_activity_evidence(
    requirement: CrossPeriodDependencyRequirement,
    *,
    activity_start_date: date,
) -> CrossPeriodDependencyEvidence:
    """Build the clean, facet-stamped evidence row for a pre-activity dependency.

    The requirement's period is strictly before the recorded activity-start
    date, so no prior obligation could have legally existed. There is no
    observation to load and nothing to stamp; the
    binding value resolves to a provenance-marked ``Decimal`` zero through the
    existing absent-by-design path, recorded here as an explicit, auditable
    no-prior-obligation outcome with NO blockers (the row is :attr:`clean`).
    """
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        no_prior_obligation=NoPriorObligationProvenance(
            activity_start_date=activity_start_date,
            provenance_kind=NoPriorObligationProvenanceKind.OPERATOR_DECLARED,
        ),
    )


_OFFICIAL_EVIDENCE_DELTA_BLOCKERS: Final = frozenset(
    {
        CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE,
        CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE,
        CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE,
    },
)
"""The blocker set that distinguishes a locally-evidenced chain from an AEAT-evidenced one."""


def _relax_same_year_local_chain(
    evidence: CrossPeriodDependencyEvidence,
    *,
    target_filing_year: int,
) -> CrossPeriodDependencyEvidence:
    """Admit a same-year ``app_filing`` chain (only official-evidence-delta blockers) to verify/export with an advisory.

    Cross-year deps, operator_manual sources, value/revision divergence, and missing
    observation/filing keep their blockers (stay blocking); the source stays non-official.
    """
    if evidence.requirement.filing_year != target_filing_year:
        return evidence
    if evidence.observation_source_kind != "app_filing":
        return evidence
    if not evidence.blockers:
        return evidence
    if not set(evidence.blockers) <= _OFFICIAL_EVIDENCE_DELTA_BLOCKERS:
        return evidence
    return evidence.model_copy(
        update={"blockers": (), "non_official_local_chain_advisory": True},
    )


def _suppressed_modelo_not_applicable_evidence(
    requirement: CrossPeriodDependencyRequirement,
) -> CrossPeriodDependencyEvidence:
    """Clean, advisory-stamped row for a not-applicable dependency (taxpayer suffers, does not file)."""
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        modelo_not_applicable_advisory=True,
    )


def _suppressed_zero_value_previous_filing_evidence(
    requirement: CrossPeriodDependencyRequirement,
) -> CrossPeriodDependencyEvidence:
    """Clean, advisory-stamped row for an explicit zero previous-filing carry."""
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        zero_value_previous_filing_advisory=True,
    )


def _suppressed_m111_no_retenciones_evidence(
    requirement: CrossPeriodDependencyRequirement,
) -> CrossPeriodDependencyEvidence:
    """Clean advisory row for an explicit M111 no-retenciones/no-obligation period."""
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        m111_no_retenciones_no_obligation_advisory=True,
    )


def _suppressed_first_year_fractional_evidence(
    requirement: CrossPeriodDependencyRequirement,
    *,
    activity_start_date: date,
) -> CrossPeriodDependencyEvidence:
    """Build the clean, facet-stamped evidence row for a first-year Modelo 202 modalidad-cuota dependency.

    The taxpayer is a first-year Impuesto sobre Sociedades filer under
    modalidad cuota (LIS art. 40.2), whose
    pago fraccionado is a percentage of the cuota íntegra of the LAST IS return
    whose deadline has elapsed. A first-year IS company has no such prior return,
    so the art. 40.2 modality produces no Modelo 202 obligation. There is no
    observation to load and nothing to stamp; the requirement is scoped out and
    recorded here as an explicit, auditable no-fractional-payment-obligation
    outcome with NO blockers (the row's ``clean`` property is true).

    The provenance kind stays ``OPERATOR_DECLARED`` — the determination rests on the
    operator-declared INCN (driving the derived modality) and the operator-declared
    ``activity_start_date`` (proving the first IS year), neither corroborated against
    an AEAT censo snapshot — so the suppression carries the operator-declared
    advisory, never silently. The ``facet_kind`` records that this is the
    modalidad-cuota first-year facet, distinct from the pre-activity facet.
    """
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        no_prior_obligation=NoPriorObligationProvenance(
            facet_kind=NoPriorObligationProvenanceKind.NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR,
            activity_start_date=activity_start_date,
            provenance_kind=NoPriorObligationProvenanceKind.OPERATOR_DECLARED,
        ),
    )


def _qualifies_for_first_year_fractional_suppression(
    requirement: CrossPeriodDependencyRequirement,
    *,
    modelo_202_modality: Modelo202Modality | None,
    activity_start_date: date | None,
    target_filing_year: int,
) -> bool:
    """Return whether ``requirement`` is a first-year Modelo 202 modalidad-cuota obligation to scope out.

    A requirement qualifies IFF ALL hold (fail-closed — any unmet condition
    keeps the requirement in scope):

    * the cross-period source is Modelo 202 (``source_modelo == "202"``);
    * the derived Modelo 202 modality is ``ART_40_2_OPTIONAL`` (modalidad cuota,
      INCN ≤ 6.000.000 €) — under ``ART_40_3_MANDATORY`` (base imponible) the pago
      fraccionado IS owed in the first year, and ``INCOMPLETE`` / ``None`` means the
      modality could not be derived, so neither is suppressed;
    * an ``activity_start_date`` is recorded AND its year is on or after the target
      filing year (``activity_start_date.year >= target_filing_year``) — the target
      year is the taxpayer's first IS year, so no prior IS return provides the
      art. 40.2 cuota basis.
    """
    if requirement.source_modelo != Modelo("202").value:
        return False
    if modelo_202_modality is not Modelo202Modality.ART_40_2_OPTIONAL:
        return False
    if activity_start_date is None:
        return False
    return activity_start_date.year >= target_filing_year


def _non_filer_modelos(
    snapshot: RegistrySnapshot,
    *,
    taxpayer_files_economic_activity: bool | None,
    not_applicable_source_modelos: frozenset[str] | None,
) -> frozenset[str]:
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
        _suppressed_modelo_not_applicable_evidence(requirement)
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
    target_filing_year: int,
) -> tuple[CrossPeriodDependencyRequirement, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if _qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=modelo_202_modality,
            activity_start_date=activity_start_date,
            target_filing_year=target_filing_year,
        )
    )


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
) -> _CleanStateRequirementScope:
    """Derive and disposition registry requirements before loading observations."""
    all_requirements = cross_period_dependency_requirements(snapshot)
    non_filer_modelos = _non_filer_modelos(
        snapshot,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
    )
    partition = partition_cross_period_requirements_by_activity_start(
        _requirements_outside_non_filer_modelos(all_requirements, non_filer_modelos),
        activity_start_date=activity_start_date,
    )
    return _CleanStateRequirementScope(
        not_applicable=_not_applicable_dependencies(all_requirements, non_filer_modelos),
        partition=partition,
        first_year_fractional=_first_year_fractional_requirements(
            partition.in_scope,
            modelo_202_modality=modelo_202_modality,
            activity_start_date=activity_start_date,
            target_filing_year=snapshot.filing_year,
        ),
        zero_value_previous_filing=_zero_value_previous_filing_requirements(
            partition.in_scope,
            zero_value_previous_filing_binding_ids,
        ),
        m111_no_retenciones=_m111_no_retenciones_requirements(
            partition.in_scope,
            m111_no_retenciones_periods,
            operation=operation,
        ),
    )


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
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    """Evaluate only requirements that were not explicitly scoped out."""
    suppressed_keys = {
        requirement.key
        for requirement in (
            *scope.first_year_fractional,
            *scope.zero_value_previous_filing,
            *scope.m111_no_retenciones,
        )
    }
    dependencies: list[CrossPeriodDependencyEvidence] = []
    for requirement in scope.partition.in_scope:
        if requirement.key in suppressed_keys:
            continue
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
        dependencies.append(_relax_same_year_local_chain(evidence, target_filing_year=target_filing_year))
    return tuple(dependencies)


def _pre_activity_dependencies(
    partition: _RequirementPartition,
    activity_start_date: date | None,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    if activity_start_date is None:
        return ()
    return tuple(
        _suppressed_pre_activity_evidence(requirement, activity_start_date=activity_start_date)
        for requirement in partition.suppressed
    )


def _first_year_fractional_dependencies(
    requirements: tuple[CrossPeriodDependencyRequirement, ...],
    activity_start_date: date | None,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    if activity_start_date is None:
        return ()
    return tuple(
        _suppressed_first_year_fractional_evidence(requirement, activity_start_date=activity_start_date)
        for requirement in requirements
    )


def _scoped_advisory_dependencies(
    scope: _CleanStateRequirementScope,
) -> tuple[CrossPeriodDependencyEvidence, ...]:
    return (
        *tuple(
            _suppressed_zero_value_previous_filing_evidence(requirement)
            for requirement in scope.zero_value_previous_filing
        ),
        *tuple(_suppressed_m111_no_retenciones_evidence(requirement) for requirement in scope.m111_no_retenciones),
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
) -> CrossPeriodCleanStateVerdict:
    """Evaluate cross-period dependencies and return a clean-state verdict.

    Returns a
    :class:`~application.calculations.cross_period_models.CrossPeriodCleanStateVerdict`.

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
    expected_member_sets_by_key = _expected_member_sets_by_key(expected_member_sets)
    scope = _clean_state_requirement_scope(
        snapshot,
        operation=operation,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids,
        m111_no_retenciones_periods=m111_no_retenciones_periods,
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
                expected_member_sets_by_key=expected_member_sets_by_key,
                target_filing_year=snapshot.filing_year,
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
    )


def _requirements_from_relation(
    requirement: RegistryFoldRequirement,
) -> Iterable[CrossPeriodDependencyRequirement]:
    source_casilla_id = requirement.source_casilla_ids[0]
    for period in requirement.periods:
        yield CrossPeriodDependencyRequirement(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=Period.from_year_and_code(requirement.filing_year, period),
            source_casilla_ids=(source_casilla_id,),
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
    "cross_period_dependency_inventory",
    "cross_period_dependency_requirements",
    "evaluate_cross_period_clean_state",
    "partition_cross_period_requirements_by_activity_start",
]
