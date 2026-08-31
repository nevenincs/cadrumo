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
from ...core.identity import CalculationRevisionId, same_tax_identifier
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
from ._cross_period_external_evidence import filing_external_evidence_blockers
from ._per_grupo_member_keys import per_grupo_member_requirement_keys
from ._revision_carry_gate import revision_carry_outcome
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
    filing_catalogue = filing_repository.load()
    calculation_catalogue = calculation_repository.load()
    verification_catalogue = verification_repository.load()
    resolved_justificante_repository = justificante_repository or JustificanteRepository()
    expected_member_sets_by_key = _expected_member_sets_by_key(expected_member_sets)
    non_filer_modelos = _non_filer_modelos(
        snapshot,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
    )
    all_requirements = cross_period_dependency_requirements(snapshot)
    not_applicable_dependencies = _not_applicable_dependencies(all_requirements, non_filer_modelos)
    partition = partition_cross_period_requirements_by_activity_start(
        tuple(r for r in all_requirements if r.source_modelo not in non_filer_modelos),
        activity_start_date=activity_start_date,
    )
    # Among the activity-start-in-scope requirements, scope out the first-year
    # Modelo 202 modalidad-cuota obligations. Everything that does not qualify
    # stays in scope and is evaluated normally (fail-closed).
    first_year_fractional_requirements = tuple(
        requirement
        for requirement in partition.in_scope
        if _qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=modelo_202_modality,
            activity_start_date=activity_start_date,
            target_filing_year=snapshot.filing_year,
        )
    )
    first_year_fractional_keys = {requirement.key for requirement in first_year_fractional_requirements}
    zero_value_previous_filing_requirements = tuple(
        requirement
        for requirement in partition.in_scope
        if _requirement_scoped_by_zero_value_previous_filing(
            requirement,
            zero_value_previous_filing_binding_ids,
        )
    )
    zero_value_previous_filing_keys = {requirement.key for requirement in zero_value_previous_filing_requirements}
    m111_no_retenciones_requirements = tuple(
        requirement
        for requirement in partition.in_scope
        if is_m111_no_retenciones_period(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period_token=requirement.period.registry_token,
            attested_periods=m111_no_retenciones_periods or frozenset(),
        )
    )
    m111_no_retenciones_keys = {requirement.key for requirement in m111_no_retenciones_requirements}
    in_scope_dependencies = tuple(
        _evaluate_requirement(
            requirement,
            bucket_id=bucket_id,
            observation_repository=observation_repository,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=resolved_justificante_repository,
            taxpayer_tax_id=taxpayer_tax_id,
            expected_member_set=expected_member_sets_by_key.get(
                (requirement.source_modelo, requirement.filing_year, requirement.period.registry_token),
            ),
        )
        for requirement in partition.in_scope
        if requirement.key not in first_year_fractional_keys
        and requirement.key not in zero_value_previous_filing_keys
        and requirement.key not in m111_no_retenciones_keys
    )
    in_scope_dependencies = tuple(
        _relax_same_year_local_chain(evidence, target_filing_year=snapshot.filing_year)
        for evidence in in_scope_dependencies
    )
    # ``activity_start_date`` is non-None whenever ``suppressed`` is non-empty.
    suppressed_dependencies = tuple(
        _suppressed_pre_activity_evidence(requirement, activity_start_date=activity_start_date)
        for requirement in partition.suppressed
        if activity_start_date is not None
    )
    # ``activity_start_date`` is non-None for every first-year fractional requirement
    # (the qualification predicate requires a recorded date).
    first_year_fractional_dependencies = tuple(
        _suppressed_first_year_fractional_evidence(requirement, activity_start_date=activity_start_date)
        for requirement in first_year_fractional_requirements
        if activity_start_date is not None
    )
    zero_value_previous_filing_dependencies = tuple(
        _suppressed_zero_value_previous_filing_evidence(requirement)
        for requirement in zero_value_previous_filing_requirements
    )
    m111_no_retenciones_dependencies = tuple(
        _suppressed_m111_no_retenciones_evidence(requirement) for requirement in m111_no_retenciones_requirements
    )
    return CrossPeriodCleanStateVerdict(
        bucket_id=bucket_id,
        target_modelo=str(snapshot.modelo.id),
        target_filing_year=snapshot.filing_year,
        target_period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        dependencies=(
            *in_scope_dependencies,
            *suppressed_dependencies,
            *not_applicable_dependencies,
            *first_year_fractional_dependencies,
            *zero_value_previous_filing_dependencies,
            *m111_no_retenciones_dependencies,
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
    :func:`~application.calculations._revision_carry_gate.revision_carry_outcome`
    gate: it maps the shared refusal decision onto this site's
    blocker shape. A divergent or unreconfirmable stamp becomes a
    ``REGISTRY_REVISION_DIVERGENCE`` blocker so the cross-period clean-state,
    binding-prefill, and relation-prefill carry reads share one fail-closed
    law-determined re-confirmation.
    """
    refused = revision_carry_outcome(
        stamped_revision_id,
        source_modelo=source_modelo,
        source_filing_year=source_filing_year,
        source_period=source_period.registry_token,
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


def _resolve_cross_period_source(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepository,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
    taxpayer_tax_id: str | None,
) -> _CrossPeriodSource:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    value_member_payloads: tuple[ObservationPayload, ...] = ()
    observed_member_nifs: tuple[str, ...] = ()
    expected_member_nifs: tuple[str, ...] = ()
    missing_member_nifs: tuple[str, ...] = ()
    unexpected_member_nifs: tuple[str, ...] = ()
    payload: ObservationPayload | None = None
    if requirement.requires_member_fan_in:
        member_payloads = tuple(
            item
            for item in observation_repository.iter_modelo(requirement.source_modelo)
            if item.observation.filing_year == requirement.filing_year
            and item.observation.period == requirement.period.registry_token
            and item.member_nif is not None
        )
        observed_member_nifs = tuple(sorted({str(item.member_nif) for item in member_payloads}))
        if expected_member_set is None:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER)
            blockers.append(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE)
            # CAST-RATIONALE-CROSS-PERIOD-MEMBER-PAYLOAD: iter_modelo records are typed envelopes at runtime.
            value_member_payloads = tuple(
                # CAST-RATIONALE-CROSS-PERIOD-MEMBER-ITEM: iter_modelo records are typed envelopes at runtime.
                cast(  # nosemgrep: no-cast-in-domain-application reason: repository rows satisfy _ObservationPayload.
                    ObservationPayload,
                    item,
                )
                for item in member_payloads
            )
        else:
            expected_member_nifs = tuple(sorted(set(expected_member_set.member_nifs)))
            expected_member_nif_set = set(expected_member_nifs)
            observed_member_nif_set = set(observed_member_nifs)
            missing_member_nifs = tuple(sorted(expected_member_nif_set - observed_member_nif_set))
            unexpected_member_nifs = tuple(sorted(observed_member_nif_set - expected_member_nif_set))
            if missing_member_nifs:
                blockers.append(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE)
            if unexpected_member_nifs:
                blockers.append(CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE)
            # CAST-RATIONALE-CROSS-PERIOD-FILTERED-PAYLOAD: roster filtering retains the typed repository envelope.
            value_member_payloads = tuple(
                # CAST-RATIONALE-CROSS-PERIOD-FILTERED-ITEM: roster filtering retains the typed repository envelope.
                cast(  # nosemgrep: no-cast-in-domain-application reason: roster rows satisfy _ObservationPayload.
                    ObservationPayload,
                    item,
                )
                for item in member_payloads
                if str(item.member_nif) in expected_member_nif_set
            )
        # R2 carry gate: check revision stamp on each member payload.
        for item in value_member_payloads:
            blockers.extend(_aeat_register_provenance_blockers(item, expected_tax_id=item.member_nif))
            extra_blockers = _revision_carry_check(
                item.stamped_revision_id,
                requirement.source_modelo,
                requirement.filing_year,
                requirement.period,
            )
            blockers.extend(extra_blockers)
    else:
        # CAST-RATIONALE-CROSS-PERIOD-SINGLE-PAYLOAD: load_observation returns the same envelope contract as iteration.
        # CAST-RATIONALE-CROSS-PERIOD-SINGLE-RESULT: load_observation returns the same envelope contract as iteration.
        payload = cast(  # nosemgrep: no-cast-in-domain-application reason: lookup returns this Protocol or None.
            ObservationPayload | None,
            observation_repository.load_observation(
                requirement.source_modelo,
                requirement.period,
            ),
        )
        # R2 carry gate: re-confirm stamped revision == law-determined revision.
        if payload is not None:
            blockers.extend(_aeat_register_provenance_blockers(payload, expected_tax_id=taxpayer_tax_id))
            extra_blockers = _revision_carry_check(
                payload.stamped_revision_id,
                requirement.source_modelo,
                requirement.filing_year,
                requirement.period,
            )
            blockers.extend(extra_blockers)
    return _CrossPeriodSource(
        value_member_payloads,
        observed_member_nifs,
        expected_member_nifs,
        missing_member_nifs,
        unexpected_member_nifs,
        payload,
        tuple(blockers),
    )


def _resolve_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[ObservationPayload, ...],
    payload: ObservationPayload | None,
) -> tuple[ObservationSourceKind | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    observation_source_kind: ObservationSourceKind | None = None
    observation_values: dict[CasillaId, object] = {}

    def _is_missing_declared_source(values: Mapping[CasillaId, object]) -> bool:
        missing_required, missing_groups = source_presence_gaps(
            required_source_casilla_ids=requirement.enforced_source_casilla_ids,
            source_presence_groups=requirement.source_presence_groups,
            observed_source_casilla_ids=values,
        )
        return bool(missing_required or missing_groups)

    if requirement.requires_member_fan_in and value_member_payloads:
        observation_source_kind = _combined_source_kind(item.source_kind for item in value_member_payloads)
        if any(item.source_kind is ObservationSourceKind.OPERATOR_MANUAL for item in value_member_payloads):
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for item in value_member_payloads:
            if _is_missing_declared_source(item.observation.casilla_values):
                blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    elif payload is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION)
    else:
        observation_source_kind = payload.source_kind
        observation_values = dict(payload.observation.casilla_values)
        if payload.source_kind is ObservationSourceKind.OPERATOR_MANUAL:
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        if _is_missing_declared_source(observation_values):
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
    blockers: list[CrossPeriodCleanStateBlocker] = []
    member_filing_record_ids: list[str] = []
    member_calculation_revision_ids: list[str] = []
    revision_state: CalculationRevisionState | None = None
    verification_status: VerificationCompletenessStatus | None = None
    aeat_accepted: bool | None = None
    external_evidence_kind: ExternalEvidenceKind | None = None
    for member_nif in members_to_check:
        member_payload = member_payload_by_nif.get(member_nif)
        member_values = dict(member_payload.observation.casilla_values) if member_payload is not None else {}
        member_source_kind = member_payload.source_kind if member_payload is not None else observation_source_kind
        member_source_metadata = member_payload.source_metadata if member_payload is not None else None
        member_result = _evaluate_filing_history(
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
        blockers.extend(member_result.blockers)
        if member_result.filing_record_id is not None:
            member_filing_record_ids.append(member_result.filing_record_id)
        if member_result.calculation_revision_id is not None:
            member_calculation_revision_ids.append(member_result.calculation_revision_id)
        revision_state = member_result.calculation_revision_state or revision_state
        verification_status = member_result.verification_status or verification_status
        aeat_accepted = member_result.aeat_accepted if member_result.aeat_accepted is not None else aeat_accepted
        external_evidence_kind = member_result.external_evidence_kind or external_evidence_kind
    return _MemberHistory(
        tuple(member_filing_record_ids),
        tuple(member_calculation_revision_ids),
        revision_state,
        verification_status,
        aeat_accepted,
        external_evidence_kind,
        blockers,
    )


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
        filing_external_evidence_blockers(
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
    "CrossPeriodCleanStateBlocker",
    "CrossPeriodCleanStateVerdict",
    "CrossPeriodDependencyEvidence",
    "CrossPeriodDependencyInventory",
    "CrossPeriodDependencyInventoryItem",
    "CrossPeriodDependencyOrigin",
    "CrossPeriodDependencyRequirement",
    "CrossPeriodExpectedMemberSet",
    "NoPriorObligationProvenance",
    "NoPriorObligationProvenanceKind",
    "cross_period_dependency_inventory",
    "cross_period_dependency_requirements",
    "evaluate_cross_period_clean_state",
    "filing_external_evidence_blockers",
    "partition_cross_period_requirements_by_activity_start",
]
