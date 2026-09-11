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
from typing import Final, NamedTuple, cast

from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.identity.tax_id import same_tax_identifier
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.applicability_modelo202 import Modelo202Modality
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    relation_source_requirements,
    source_presence_gaps,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.filing_record import (
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
)
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import VerificationCompletenessStatus, VerificationReportCatalogue
from ._per_grupo_member_keys import per_grupo_member_requirement_keys
from .cross_period_external_evidence import filing_external_evidence_blockers as _filing_external_evidence_blockers
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
    ObservationPayload,
    period_strictly_before_activity_start,
)
from .m111_no_retenciones import is_m111_no_retenciones_period
from .observations_repository import (
    CalculationObservationRepository,
    ObservationSourceKind,
    is_official_aeat_observation_source,
)
from .revision_carry_gate import revision_carry_outcome
from .verification_report_gate import require_verification_report_coordinates_current


def cross_period_dependency_requirements(snapshot: RegistrySnapshot) -> tuple[CrossPeriodDependencyRequirement, ...]:
    """Return the dependency records for ``snapshot``.

    Derives
    :class:`~application.calculations.cross_period_models.CrossPeriodDependencyRequirement`
    records from :class:`RegistrySnapshot` through
    :func:`~domain.calculations.registry.previous_filing_observation_requirements`
    and
    :func:`~domain.calculations.registry.relation_source_requirements`.
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
    justificante_repository: JustificanteRepository


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


def cross_period_dependency_inventory(
    authority: ValidatedRegistryAuthority,
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

    The :class:`ValidatedRegistryAuthority`
    supplies candidate modelos and resolves each target
    :class:`RegistrySnapshot` evaluated for
    dependency coverage.
    """
    selected_modelos = authority.modelos if modelos is None else tuple(authority.modelo(modelo) for modelo in modelos)
    items: list[CrossPeriodDependencyInventoryItem] = []
    for modelo in selected_modelos:
        for revision in modelo.revisions.values():
            if not revision.period_selector.includes_year(filing_year):
                continue
            # Dependency inventory is a filing-readiness surface. Applicability-
            # and calculation-grade revisions cannot lawfully produce the filing
            # snapshot consumed below, and therefore cannot own filing blockers.
            if revision.effective_authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            for period in revision.period_selector.periods:
                snapshot = authority.snapshot(
                    str(modelo.id),
                    filing_year=filing_year,
                    period=period,
                    revision_id=str(revision.id),
                )
                dependencies = cross_period_dependency_requirements(snapshot)
                if not dependencies:
                    continue
                items.append(
                    CrossPeriodDependencyInventoryItem(
                        target_modelo=str(snapshot.modelo.id),
                        target_revision_id=str(snapshot.revision.id),
                        target_filing_year=snapshot.filing_year,
                        target_period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
                        dependencies=dependencies,
                    ),
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
    if requirement.source_modelo != Modelo.M202.value:
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
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepository | None,
) -> _CleanStateRepositories:
    """Load all persistence inputs once for a clean-state evaluation."""
    return _CleanStateRepositories(
        filing_catalogue=filing_repository.load(),
        calculation_catalogue=calculation_repository.load(),
        verification_catalogue=require_verification_report_coordinates_current(verification_repository.load()),
        justificante_repository=justificante_repository or JustificanteRepository(),
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
) -> tuple[CrossPeriodDependencyRequirement, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if is_m111_no_retenciones_period(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period_token=requirement.period.registry_token,
            attested_periods=m111_no_retenciones_periods or frozenset(),
        )
    )


def _clean_state_requirement_scope(
    snapshot: RegistrySnapshot,
    *,
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
        ),
    )


def _evaluate_in_scope_dependencies(
    scope: _CleanStateRequirementScope,
    *,
    bucket_id: str,
    observation_repository: CalculationObservationRepository,
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
        evidence = _evaluate_requirement(
            requirement,
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
    bucket_id: str,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepository | None = None,
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

    ``activity_start_date`` is the operator-declared activity-start date carried on
    the profile (the same field the deadline engine consumes for pre-start
    suppression). When supplied, a dependency whose period falls strictly before it
    is scoped out as no-prior-obligation: it produces a clean,
    facet-stamped evidence row instead of an evaluated blocker, and is NOT loaded
    from storage. When ``None`` every dependency is evaluated as before - the
    caller decides whether a missing declared date should fail closed.

    ``modelo_202_modality`` is the derived Modelo 202 pago-fraccionado modality
    (:func:`~domain.calculations.registry.derive_modelo_202_modality`). When it
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
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        justificante_repository=justificante_repository,
    )
    expected_member_sets_by_key = _expected_member_sets_by_key(expected_member_sets)
    scope = _clean_state_requirement_scope(
        snapshot,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids,
        m111_no_retenciones_periods=m111_no_retenciones_periods,
    )
    return CrossPeriodCleanStateVerdict(
        bucket_id=bucket_id,
        target_modelo=str(snapshot.modelo.id),
        target_filing_year=snapshot.filing_year,
        target_period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        dependencies=_clean_state_dependencies(
            scope,
            in_scope=_evaluate_in_scope_dependencies(
                scope,
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
    if not zero_value_previous_filing_binding_ids:
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
            origin_ids=requirement.relation_ids,
            legal_refs=requirement.legal_refs,
            source_refs=requirement.source_refs,
        )


class _CrossPeriodSource(NamedTuple):
    value_member_payloads: tuple[ObservationPayload, ...]
    observed_member_nifs: tuple[str, ...]
    expected_member_nifs: tuple[str, ...]
    missing_member_nifs: tuple[str, ...]
    unexpected_member_nifs: tuple[str, ...]
    payload: ObservationPayload | None
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]


class _MemberSourceSelection(NamedTuple):
    value_member_payloads: tuple[ObservationPayload, ...]
    observed_member_nifs: tuple[str, ...]
    expected_member_nifs: tuple[str, ...]
    missing_member_nifs: tuple[str, ...]
    unexpected_member_nifs: tuple[str, ...]
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]


class _MemberHistory(NamedTuple):
    member_filing_record_ids: tuple[str, ...]
    member_calculation_revision_ids: tuple[str, ...]
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: ExternalEvidenceKind | None
    blockers: list[CrossPeriodCleanStateBlocker]


def _revision_carry_check(
    stamped_revision_id: RevisionId,
    source_modelo: str,
    source_filing_year: int,
    source_period: Period,
) -> list[CrossPeriodCleanStateBlocker]:
    """Return blockers for a carry-read revision check.

    Thin adapter over the single shared
    :func:`~application.calculations.revision_carry_gate.revision_carry_outcome`
    gate: it maps the shared refusal decision onto this site's
    blocker shape. A divergent or unreconfirmable stamp becomes a
    ``REGISTRY_REVISION_DIVERGENCE`` blocker so the cross-period clean-state,
    binding-prefill, and relation-prefill carry reads share one fail-closed
    law-determined re-confirmation.
    """
    refused = revision_carry_outcome(
        RegistrySnapshotRef(
            modelo=source_modelo,
            revision_id=stamped_revision_id,
            modelo_year=source_filing_year,
            period=source_period.registry_token,
        )
    ).refused
    if refused:
        return [CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE]
    return []


def _aeat_register_provenance_blockers(
    payload: ObservationPayload,
    *,
    expected_tax_id: str | None,
) -> list[CrossPeriodCleanStateBlocker]:
    if not is_official_aeat_observation_source(payload.source_kind):
        return []
    metadata = payload.source_metadata
    if not metadata:
        return [CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD]

    blockers: list[CrossPeriodCleanStateBlocker] = []
    register_status = metadata.get("aeat_register_status", "").strip().upper()
    if not register_status or register_status != "ALTA":
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)

    expediente_id = metadata.get("aeat_expediente_id", "").strip()
    if not expediente_id:
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)

    authenticated_identity = metadata.get("authenticated_identity", "")
    if expected_tax_id and not same_tax_identifier(authenticated_identity, expected_tax_id):
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    return blockers


def _member_payloads_for_requirement(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepository,
) -> tuple[ObservationPayload, ...]:
    # CAST-RATIONALE-CROSS-PERIOD-MEMBER-PAYLOAD: iter_modelo records are typed envelopes at runtime.
    return tuple(
        # CAST-RATIONALE-CROSS-PERIOD-MEMBER-ITEM: iter_modelo records are typed envelopes at runtime.
        cast(  # nosemgrep: no-cast-in-domain-application reason: repository rows satisfy _ObservationPayload.
            ObservationPayload,
            item,
        )
        for item in observation_repository.iter_modelo(requirement.source_modelo)
        if item.observation.filing_year == requirement.filing_year
        and item.observation.period == requirement.period.registry_token
        and item.member_nif is not None
    )


def _select_member_source_payloads(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepository,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
) -> _MemberSourceSelection:
    member_payloads = _member_payloads_for_requirement(requirement, observation_repository)
    observed_member_nifs = tuple(sorted({str(item.member_nif) for item in member_payloads}))
    if expected_member_set is None:
        value_member_payloads = member_payloads
        roster_blockers: tuple[CrossPeriodCleanStateBlocker, ...] = (
            CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER,
            CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE,
        )
        return _MemberSourceSelection(
            value_member_payloads,
            observed_member_nifs,
            (),
            (),
            (),
            roster_blockers,
        )

    expected_member_nifs = tuple(sorted(set(expected_member_set.member_nifs)))
    expected_member_nif_set = set(expected_member_nifs)
    observed_member_nif_set = set(observed_member_nifs)
    missing_member_nifs = tuple(sorted(expected_member_nif_set - observed_member_nif_set))
    unexpected_member_nifs = tuple(sorted(observed_member_nif_set - expected_member_nif_set))
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if missing_member_nifs:
        blockers.append(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE)
    if unexpected_member_nifs:
        blockers.append(CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE)
    value_member_payloads = tuple(item for item in member_payloads if str(item.member_nif) in expected_member_nif_set)
    return _MemberSourceSelection(
        value_member_payloads,
        observed_member_nifs,
        expected_member_nifs,
        missing_member_nifs,
        unexpected_member_nifs,
        tuple(blockers),
    )


def _member_source_revision_blockers(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[ObservationPayload, ...],
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    for item in value_member_payloads:
        blockers.extend(_aeat_register_provenance_blockers(item, expected_tax_id=item.member_nif))
        blockers.extend(
            _revision_carry_check(
                item.stamped_revision_id,
                requirement.source_modelo,
                requirement.filing_year,
                requirement.period,
            ),
        )
    return tuple(blockers)


def _single_source_payload(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepository,
) -> ObservationPayload | None:
    # CAST-RATIONALE-CROSS-PERIOD-SINGLE-PAYLOAD: load_observation returns the same envelope contract as iteration.
    # CAST-RATIONALE-CROSS-PERIOD-SINGLE-RESULT: load_observation returns the same envelope contract as iteration.
    return cast(  # nosemgrep: no-cast-in-domain-application reason: lookup returns this Protocol or None.
        ObservationPayload | None,
        observation_repository.load_observation(
            requirement.source_modelo,
            requirement.period,
        ),
    )


def _single_source_revision_blockers(
    requirement: CrossPeriodDependencyRequirement,
    payload: ObservationPayload | None,
    taxpayer_tax_id: str | None,
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    if payload is None:
        return ()
    blockers = _aeat_register_provenance_blockers(payload, expected_tax_id=taxpayer_tax_id)
    blockers.extend(
        _revision_carry_check(
            payload.stamped_revision_id,
            requirement.source_modelo,
            requirement.filing_year,
            requirement.period,
        ),
    )
    return tuple(blockers)


def _resolve_cross_period_source(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepository,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
    taxpayer_tax_id: str | None,
) -> _CrossPeriodSource:
    if requirement.requires_member_fan_in:
        selection = _select_member_source_payloads(
            requirement,
            observation_repository,
            expected_member_set,
        )
        blockers = [
            *selection.blockers,
            *_member_source_revision_blockers(
                requirement,
                selection.value_member_payloads,
            ),
        ]
        return _CrossPeriodSource(
            selection.value_member_payloads,
            selection.observed_member_nifs,
            selection.expected_member_nifs,
            selection.missing_member_nifs,
            selection.unexpected_member_nifs,
            None,
            tuple(blockers),
        )
    payload = _single_source_payload(requirement, observation_repository)
    blockers = _single_source_revision_blockers(requirement, payload, taxpayer_tax_id)
    return _CrossPeriodSource(
        (),
        (),
        (),
        (),
        (),
        payload,
        tuple(blockers),
    )


def _resolve_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[ObservationPayload, ...],
    payload: ObservationPayload | None,
) -> tuple[ObservationSourceKind | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    if requirement.requires_member_fan_in and value_member_payloads:
        return _member_observation_values(requirement, value_member_payloads)
    if payload is None:
        return None, {}, [CrossPeriodCleanStateBlocker.MISSING_OBSERVATION]
    return _single_observation_values(requirement, payload)


def _is_missing_declared_source(
    requirement: CrossPeriodDependencyRequirement,
    values: Mapping[CasillaId, object],
) -> bool:
    missing_required, missing_groups = source_presence_gaps(
        required_source_casilla_ids=requirement.enforced_source_casilla_ids,
        source_presence_groups=requirement.source_presence_groups,
        observed_source_casilla_ids=values,
    )
    return bool(missing_required or missing_groups)


def _member_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[ObservationPayload, ...],
) -> tuple[ObservationSourceKind | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    observation_source_kind = _combined_source_kind(item.source_kind for item in value_member_payloads)
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if any(item.source_kind is ObservationSourceKind.OPERATOR_MANUAL for item in value_member_payloads):
        blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
    for item in value_member_payloads:
        if _is_missing_declared_source(requirement, item.observation.casilla_values):
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    return observation_source_kind, {}, blockers


def _single_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    payload: ObservationPayload,
) -> tuple[ObservationSourceKind | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    observation_source_kind = payload.source_kind
    observation_values: dict[CasillaId, object] = dict(payload.observation.casilla_values)
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if payload.source_kind is ObservationSourceKind.OPERATOR_MANUAL:
        blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
    if _is_missing_declared_source(requirement, observation_values):
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    return observation_source_kind, observation_values, blockers


def _aggregate_member_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    observation_source_kind: ObservationSourceKind | None,
    value_member_payloads: tuple[ObservationPayload, ...],
    expected_member_nifs: tuple[str, ...],
    observed_member_nifs: tuple[str, ...],
) -> _MemberHistory:
    member_payload_by_nif = {str(item.member_nif): item for item in value_member_payloads}
    members_to_check = expected_member_nifs or observed_member_nifs
    results = tuple(
        _evaluate_member_history(
            requirement,
            member_nif=member_nif,
            member_payload=member_payload_by_nif.get(member_nif),
            bucket_id=bucket_id,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=justificante_repository,
            taxpayer_tax_id=taxpayer_tax_id,
            observation_source_kind=observation_source_kind,
        )
        for member_nif in members_to_check
    )
    return _member_history_from_results(results)


def _evaluate_requirement(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    observation_repository: CalculationObservationRepository,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
) -> CrossPeriodDependencyEvidence:
    source = _resolve_cross_period_source(
        requirement,
        observation_repository,
        expected_member_set,
        taxpayer_tax_id,
    )
    observation_source_kind, observation_values, value_blockers = _resolve_observation_values(
        requirement,
        source.value_member_payloads,
        source.payload,
    )
    blockers: list[CrossPeriodCleanStateBlocker] = [*source.blockers, *value_blockers]

    if requirement.requires_member_fan_in:
        history = _aggregate_member_history(
            requirement,
            bucket_id=bucket_id,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=justificante_repository,
            taxpayer_tax_id=taxpayer_tax_id,
            observation_source_kind=observation_source_kind,
            value_member_payloads=source.value_member_payloads,
            expected_member_nifs=source.expected_member_nifs,
            observed_member_nifs=source.observed_member_nifs,
        )
        blockers.extend(history.blockers)
        return CrossPeriodDependencyEvidence(
            requirement=requirement,
            observation_source_kind=observation_source_kind,
            observed_member_nifs=source.observed_member_nifs,
            expected_member_nifs=source.expected_member_nifs,
            missing_member_nifs=source.missing_member_nifs,
            unexpected_member_nifs=source.unexpected_member_nifs,
            member_filing_record_ids=history.member_filing_record_ids,
            member_calculation_revision_ids=history.member_calculation_revision_ids,
            calculation_revision_state=history.calculation_revision_state,
            verification_status=history.verification_status,
            aeat_accepted=history.aeat_accepted,
            external_evidence_kind=history.external_evidence_kind,
            blockers=_unique_blockers(blockers),
        )

    filing_result = _evaluate_filing_history(
        requirement,
        bucket_id=bucket_id,
        filing_catalogue=filing_catalogue,
        calculation_catalogue=calculation_catalogue,
        verification_catalogue=verification_catalogue,
        justificante_repository=justificante_repository,
        taxpayer_tax_id=taxpayer_tax_id,
        observation_source_kind=observation_source_kind,
        observation_source_metadata=source.payload.source_metadata if source.payload is not None else None,
        observation_values=observation_values,
        member_nif=None,
    )
    blockers.extend(filing_result.blockers)

    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        observation_source_kind=observation_source_kind,
        filing_record_id=filing_result.filing_record_id,
        calculation_revision_id=filing_result.calculation_revision_id,
        calculation_revision_state=filing_result.calculation_revision_state,
        verification_status=filing_result.verification_status,
        aeat_accepted=filing_result.aeat_accepted,
        external_evidence_kind=filing_result.external_evidence_kind,
        observed_member_nifs=source.observed_member_nifs,
        expected_member_nifs=source.expected_member_nifs,
        missing_member_nifs=source.missing_member_nifs,
        unexpected_member_nifs=source.unexpected_member_nifs,
        blockers=_unique_blockers(blockers),
    )


def _filing_revision_blockers(
    filing: ModeloRecord,
    requirement: CrossPeriodDependencyRequirement,
    calculation_catalogue: CalculationRevisionCatalogue,
    observation_values: Mapping[CasillaId, object],
) -> tuple[CalculationRevisionState | None, list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    revision = calculation_catalogue.get(filing.calculation_revision_id)
    revision_state: CalculationRevisionState | None = None
    if revision is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION)
    else:
        if revision_carry_outcome(revision.registry_snapshot_ref).refused:
            blockers.append(CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE)
            return None, blockers
        revision_state = revision.state
        if revision.state is not CalculationRevisionState.PRESENTADO:
            blockers.append(CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION)
        for casilla_id in requirement.source_casilla_ids:
            observed = observation_values.get(casilla_id)
            if observed is None:
                continue
            if revision.casilla_values.get(casilla_id) != observed:
                blockers.append(CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE)
    return revision_state, blockers


def _filing_verification_blockers(
    filing: ModeloRecord,
    verification_catalogue: VerificationReportCatalogue,
) -> tuple[VerificationCompletenessStatus | None, list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    verification_status: VerificationCompletenessStatus | None = None
    if filing.external_evidence is None:
        complete_reports = tuple(
            report
            for report in verification_catalogue.for_calculation_revision(filing.calculation_revision_id)
            if report.granted_verificado_completo
            and report.completeness_status is VerificationCompletenessStatus.COMPLETE
        )
        if complete_reports:
            verification_status = complete_reports[-1].completeness_status
        else:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT)
    return verification_status, blockers


class _FilingHistory(NamedTuple):
    filing_record_id: str | None
    calculation_revision_id: CalculationRevisionId | None
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: ExternalEvidenceKind | None
    blockers: list[CrossPeriodCleanStateBlocker]


def _evaluate_member_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    member_nif: str,
    member_payload: ObservationPayload | None,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    observation_source_kind: ObservationSourceKind | None,
) -> _FilingHistory:
    member_values = dict(member_payload.observation.casilla_values) if member_payload is not None else {}
    member_source_kind = member_payload.source_kind if member_payload is not None else observation_source_kind
    member_source_metadata = member_payload.source_metadata if member_payload is not None else None
    return _evaluate_filing_history(
        requirement,
        bucket_id=bucket_id,
        filing_catalogue=filing_catalogue,
        calculation_catalogue=calculation_catalogue,
        verification_catalogue=verification_catalogue,
        justificante_repository=justificante_repository,
        taxpayer_tax_id=taxpayer_tax_id,
        observation_source_kind=member_source_kind,
        observation_source_metadata=member_source_metadata,
        observation_values=member_values,
        member_nif=member_nif,
    )


def _member_history_from_results(results: tuple[_FilingHistory, ...]) -> _MemberHistory:
    return _MemberHistory(
        _member_filing_record_ids(results),
        _member_calculation_revision_ids(results),
        _last_member_revision_state(results),
        _last_member_verification_status(results),
        _last_member_aeat_acceptance(results),
        _last_member_external_evidence_kind(results),
        _member_history_blockers(results),
    )


def _member_filing_record_ids(results: tuple[_FilingHistory, ...]) -> tuple[str, ...]:
    return tuple(result.filing_record_id for result in results if result.filing_record_id is not None)


def _member_calculation_revision_ids(results: tuple[_FilingHistory, ...]) -> tuple[CalculationRevisionId, ...]:
    return tuple(result.calculation_revision_id for result in results if result.calculation_revision_id is not None)


def _last_member_revision_state(
    results: tuple[_FilingHistory, ...],
) -> CalculationRevisionState | None:
    return next(
        (result.calculation_revision_state for result in reversed(results) if result.calculation_revision_state),
        None,
    )


def _last_member_verification_status(
    results: tuple[_FilingHistory, ...],
) -> VerificationCompletenessStatus | None:
    return next((result.verification_status for result in reversed(results) if result.verification_status), None)


def _last_member_aeat_acceptance(results: tuple[_FilingHistory, ...]) -> bool | None:
    return next((result.aeat_accepted for result in reversed(results) if result.aeat_accepted is not None), None)


def _last_member_external_evidence_kind(
    results: tuple[_FilingHistory, ...],
) -> ExternalEvidenceKind | None:
    return next(
        (result.external_evidence_kind for result in reversed(results) if result.external_evidence_kind),
        None,
    )


def _member_history_blockers(results: tuple[_FilingHistory, ...]) -> list[CrossPeriodCleanStateBlocker]:
    return [blocker for result in results for blocker in result.blockers]


def _evaluate_filing_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    observation_source_kind: ObservationSourceKind | None,
    observation_source_metadata: Mapping[str, str] | None,
    observation_values: Mapping[CasillaId, object],
    member_nif: str | None,
) -> _FilingHistory:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    filing_history = filing_catalogue.history_for(
        bucket_id=bucket_id,
        modelo=requirement.source_modelo,
        filing_year=requirement.filing_year,
        period=requirement.period,
        member_nif=member_nif,
    )
    current_filings = tuple(record for record in filing_history if record.status is ModeloRecordStatus.VIGENTE)
    superseded_filings = tuple(record for record in filing_history if record.status is ModeloRecordStatus.SUPERSEDIDO)
    if len(current_filings) > 1:
        blockers.append(CrossPeriodCleanStateBlocker.DUPLICATE_CURRENT_FILING_RECORD)
    filing = current_filings[-1] if current_filings else None
    if filing is None:
        if superseded_filings:
            blockers.append(CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY)
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
        return _FilingHistory(None, None, None, None, None, None, blockers)

    blockers.extend(
        _filing_external_evidence_blockers(
            filing,
            observation_source_kind,
            justificante_repository,
            taxpayer_tax_id,
            observation_source_metadata,
        ),
    )
    revision_state, revision_blockers = _filing_revision_blockers(
        filing,
        requirement,
        calculation_catalogue,
        observation_values,
    )
    blockers.extend(revision_blockers)
    verification_status, verification_blockers = _filing_verification_blockers(filing, verification_catalogue)
    blockers.extend(verification_blockers)

    return _FilingHistory(
        filing.filing_record_id,
        filing.calculation_revision_id,
        revision_state,
        verification_status,
        filing.aeat_accepted,
        filing.external_evidence.kind if filing.external_evidence is not None else None,
        blockers,
    )


def _expected_member_sets_by_key(
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> Mapping[tuple[str, int, str], CrossPeriodExpectedMemberSet]:
    return {item.requirement_key: item for item in expected_member_sets}


def _unique_blockers(
    blockers: Iterable[CrossPeriodCleanStateBlocker],
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    return tuple(dict.fromkeys(blockers))


def _combined_source_kind(source_kinds: Iterable[ObservationSourceKind]) -> ObservationSourceKind | None:
    unique = tuple(dict.fromkeys(source_kinds))
    if len(unique) == 1:
        return unique[0]
    return None


__all__ = [
    "cross_period_dependency_inventory",
    "cross_period_dependency_requirements",
    "evaluate_cross_period_clean_state",
    "partition_cross_period_requirements_by_activity_start",
]
