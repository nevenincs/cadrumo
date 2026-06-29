"""Clean-state proof for filing-grade cross-period modelo dependencies.

:func:`evaluate_cross_period_clean_state` derives dependency requirements from a
:class:`~aeat.domain.calculations.registry.RegistrySnapshot`, then joins filed
:class:`ModeloRecord` rows, calculation revisions, verification reports, and
justificante evidence into a
:class:`~aeat.application.calculations._cross_period_models.CrossPeriodCleanStateVerdict`.

The same verdict feeds modelo verification, filing, and export gates. See also
:class:`~aeat.application.calculations._cross_period_models.CrossPeriodDependencyEvidence`
for per-dependency blocker/advisory rows
and :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority` for
the authority surface that produces the snapshots evaluated here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Final, NamedTuple

from ...core import Modelo, Period
from ...domain.calculations.registry import (
    CasillaId,
    Modelo202Modality,
    RegistryFoldRequirement,
    RegistrySnapshot,
    ValidatedRegistryAuthority,
    previous_filing_observation_requirements,
    relation_source_requirements,
)
from ...domain.justificante import Justificante, JustificanteRepository
from ...domain.modelos import (
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloRecordStatus,
    VerificationCompletenessStatus,
    VerificationReportCatalogue,
    VerificationReportCatalogueRepositoryProtocol,
)
from ._cross_period_models import (
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
    _ObservationPayload,
    _period_strictly_before_activity_start,
)
from ._observations_repository import CalculationObservationRepository
from ._revision_carry_gate import revision_carry_outcome

_OFFICIAL_SOURCE_KINDS: Final = frozenset(
    {
        "aeat_sede_justificante",
        "aeat_sede_live_capture",
        "aeat_csv_register",
    },
)
_JUSTIFICANTE_VERIFIED_EXTERNAL_EVIDENCE_KINDS: Final = frozenset(
    {
        # A CSV-register import is filing-grade only after the CSV resolves to
        # persisted justificante metadata and the receipt matches the filing.
        "aeat_csv_register",
        "aeat_justificante_pdf",
        # A live-captured justificante is the authentic AEAT-signed receipt
        # pulled read-only from the sede (the same PDF an operator would
        # download and import as aeat_justificante_pdf), so it satisfies the
        # justificante-verification gate. See the live-justificante-reconcile ADR.
        "aeat_live_capture",
    },
)


def cross_period_dependency_requirements(snapshot: RegistrySnapshot) -> tuple[CrossPeriodDependencyRequirement, ...]:
    """Return the dependency records for ``snapshot``.

    Derives
    :class:`~aeat.application.calculations._cross_period_models.CrossPeriodDependencyRequirement`
    records from :class:`RegistrySnapshot`.
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

    ADR 2026-06-13-first-filer-attestation-adr: a dependency anchor whose period
    falls strictly before ``activity_start_date`` is no-prior-obligation
    (absent-by-design) and is scoped out of the evaluated graph. The scoping is an
    application-layer filter over the registry-derived requirements - the registry
    stays pure and the declared date is a grounded input (the same field the
    deadline engine consumes), not a per-call ad hoc shrink
    (``2026-06-05-cross-period-calculation-guards-adr``).

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
        if _period_strictly_before_activity_start(requirement.period, activity_start_date):
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
    :class:`~aeat.application.calculations._cross_period_models.CrossPeriodDependencyInventory`
    is a backend coverage surface. It lets callers prove which modelos and
    periods are in scope for the clean-state guard before they wire
    model-specific workflow tests or operator diagnostics.

    The :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
    supplies candidate modelos and resolves each target
    :class:`~aeat.domain.calculations.registry.RegistrySnapshot` evaluated for
    dependency coverage.
    """
    selected_modelos = authority.modelos if modelos is None else tuple(authority.modelo(modelo) for modelo in modelos)
    items: list[CrossPeriodDependencyInventoryItem] = []
    for modelo in selected_modelos:
        for revision in modelo.revisions.values():
            if not revision.period_selector.includes_year(filing_year):
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

    ADR 2026-06-13-first-filer-attestation-adr: the requirement's period is
    strictly before the recorded activity-start date, so no prior obligation could
    have legally existed. There is no observation to load and nothing to stamp; the
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


def _suppressed_first_year_fractional_evidence(
    requirement: CrossPeriodDependencyRequirement,
    *,
    activity_start_date: date,
) -> CrossPeriodDependencyEvidence:
    """Build the clean, facet-stamped evidence row for a first-year Modelo 202 modalidad-cuota dependency.

    ADR 2026-06-19-m202-first-period-attestation-adr: the taxpayer is a first-year
    Impuesto sobre Sociedades filer under modalidad cuota (LIS art. 40.2), whose
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

    ADR 2026-06-19-m202-first-period-attestation-adr. A requirement qualifies IFF
    ALL hold (fail-closed — any unmet condition keeps the requirement in scope):

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
) -> CrossPeriodCleanStateVerdict:
    """Evaluate cross-period dependencies and return a clean-state verdict.

    Returns a
    :class:`~aeat.application.calculations._cross_period_models.CrossPeriodCleanStateVerdict`.

    The supplied :class:`~aeat.domain.calculations.registry.RegistrySnapshot` is
    the authority for target revision, filing period, and dependency
    requirements.

    ``activity_start_date`` is the operator-declared activity-start date carried on
    the profile (the same field the deadline engine consumes for pre-start
    suppression). When supplied, a dependency whose period falls strictly before it
    is scoped out as no-prior-obligation
    (ADR 2026-06-13-first-filer-attestation-adr): it produces a clean,
    facet-stamped evidence row instead of an evaluated blocker, and is NOT loaded
    from storage. When ``None`` every dependency is evaluated as before - the
    caller decides whether a missing declared date should fail closed.

    ``modelo_202_modality`` is the derived Modelo 202 pago-fraccionado modality
    (:func:`~aeat.domain.calculations.registry.derive_modelo_202_modality`). When it
    is ``ART_40_2_OPTIONAL`` (modalidad cuota) AND the recorded
    ``activity_start_date`` places the taxpayer's first IS year at or after the
    target filing year, the Modelo 202 cross-period dependency is scoped out as a
    first-year no-fractional-payment obligation
    (ADR 2026-06-19-m202-first-period-attestation-adr): a first-year IS filer in
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
    """
    filing_catalogue = filing_repository.load()
    calculation_catalogue = calculation_repository.load()
    verification_catalogue = verification_repository.load()
    resolved_justificante_repository = justificante_repository or JustificanteRepository()
    expected_member_sets_by_key = _expected_member_sets_by_key(expected_member_sets)
    non_filer_modelos = frozenset(
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
    all_requirements = cross_period_dependency_requirements(snapshot)
    not_applicable_dependencies = tuple(
        _suppressed_modelo_not_applicable_evidence(requirement)
        for requirement in all_requirements
        if requirement.source_modelo in non_filer_modelos
    )
    partition = partition_cross_period_requirements_by_activity_start(
        tuple(r for r in all_requirements if r.source_modelo not in non_filer_modelos),
        activity_start_date=activity_start_date,
    )
    # Among the activity-start-in-scope requirements, scope out the first-year
    # Modelo 202 modalidad-cuota obligations (ADR 2026-06-19-m202-first-period-
    # attestation-adr). Everything that does not qualify stays in scope and is
    # evaluated normally (fail-closed).
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
        if requirement.key not in first_year_fractional_keys and requirement.key not in zero_value_previous_filing_keys
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
    grouped_keys = _per_grupo_member_requirement_keys(snapshot)
    source_period = requirement.periods[0]
    yield CrossPeriodDependencyRequirement(
        source_modelo=requirement.source_modelo,
        filing_year=requirement.filing_year,
        period=Period.from_year_and_code(requirement.filing_year, source_period),
        source_casilla_ids=requirement.source_casilla_ids,
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=requirement.binding_ids,
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
        )


def _per_grupo_member_requirement_keys(snapshot: RegistrySnapshot) -> set[tuple[str, int, str]]:
    grouped_binding_ids = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source == "previous_filing" and _selector_grouping(binding.selector) == "per_grupo_member"
    }
    if not grouped_binding_ids:
        return set()
    keys: set[tuple[str, int, str]] = set()
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if any(binding_id in grouped_binding_ids for binding_id in requirement.binding_ids):
            keys.add((requirement.source_modelo, requirement.filing_year, requirement.periods[0]))
    return keys


def _selector_grouping(selector: object) -> object:
    if isinstance(selector, Mapping):
        return next((v for k, v in selector.items() if k == "grouping"), None)
    return getattr(selector, "grouping", None)


class _CrossPeriodSource(NamedTuple):
    value_member_payloads: tuple[_ObservationPayload, ...]
    observed_member_nifs: tuple[str, ...]
    expected_member_nifs: tuple[str, ...]
    missing_member_nifs: tuple[str, ...]
    unexpected_member_nifs: tuple[str, ...]
    payload: _ObservationPayload | None
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]
    unstamped_revision_advisory: bool = False


class _MemberHistory(NamedTuple):
    member_filing_record_ids: tuple[str, ...]
    member_calculation_revision_ids: tuple[str, ...]
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: str | None
    blockers: list[CrossPeriodCleanStateBlocker]


def _revision_carry_check(
    stamped_revision_id: str | None,
    source_modelo: str,
    source_filing_year: int,
    source_period: Period,
) -> tuple[list[CrossPeriodCleanStateBlocker], bool]:
    """Return (blockers, unstamped_advisory) for a carry-read revision check.

    Thin adapter over the single shared
    :func:`~aeat.application.calculations._revision_carry_gate.revision_carry_outcome`
    gate (ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2): it maps
    the shared ``(diverges, advisory)`` decision onto this site's blocker shape —
    a divergent stamp becomes a ``REGISTRY_REVISION_DIVERGENCE`` blocker, an
    absent/unverifiable stamp a non-blocking advisory — so the cross-period
    clean-state, binding-prefill, and relation-prefill carry reads share one
    law-determined re-confirmation.
    """
    diverges, advisory = revision_carry_outcome(
        stamped_revision_id,
        source_modelo=source_modelo,
        source_filing_year=source_filing_year,
        source_period=source_period.registry_token,
    )
    if diverges:
        return [CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE], False
    return [], advisory


def _aeat_register_provenance_blockers(
    payload: _ObservationPayload,
    *,
    expected_tax_id: str | None,
) -> list[CrossPeriodCleanStateBlocker]:
    if payload.source_kind not in _OFFICIAL_SOURCE_KINDS:
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

    authenticated_identity = metadata.get("authenticated_identity", "").strip().upper()
    expected_identity = expected_tax_id.strip().upper() if expected_tax_id is not None else ""
    if expected_identity and (not authenticated_identity or authenticated_identity != expected_identity):
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    return blockers


def _resolve_cross_period_source(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepository,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
    taxpayer_tax_id: str | None,
) -> _CrossPeriodSource:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    unstamped_advisory = False
    value_member_payloads: tuple[_ObservationPayload, ...] = ()
    observed_member_nifs: tuple[str, ...] = ()
    expected_member_nifs: tuple[str, ...] = ()
    missing_member_nifs: tuple[str, ...] = ()
    unexpected_member_nifs: tuple[str, ...] = ()
    payload: _ObservationPayload | None = None
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
            value_member_payloads = member_payloads
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
            value_member_payloads = tuple(
                item for item in member_payloads if str(item.member_nif) in expected_member_nif_set
            )
        # R2 carry gate: check revision stamp on each member payload.
        for item in value_member_payloads:
            blockers.extend(_aeat_register_provenance_blockers(item, expected_tax_id=item.member_nif))
            extra_blockers, item_advisory = _revision_carry_check(
                item.stamped_revision_id,
                requirement.source_modelo,
                requirement.filing_year,
                requirement.period,
            )
            blockers.extend(extra_blockers)
            unstamped_advisory = unstamped_advisory or item_advisory
    else:
        payload = observation_repository.load_observation(
            requirement.source_modelo,
            requirement.period,
        )
        # R2 carry gate: re-confirm stamped revision == law-determined revision.
        if payload is not None:
            blockers.extend(_aeat_register_provenance_blockers(payload, expected_tax_id=taxpayer_tax_id))
            extra_blockers, unstamped_advisory = _revision_carry_check(
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
        unstamped_advisory,
    )


def _resolve_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[_ObservationPayload, ...],
    payload: _ObservationPayload | None,
) -> tuple[str | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    observation_source_kind: str | None = None
    observation_values: dict[CasillaId, object] = {}
    if requirement.requires_member_fan_in and value_member_payloads:
        observation_source_kind = _combined_source_kind(item.source_kind for item in value_member_payloads)
        if any(item.source_kind == "operator_manual" for item in value_member_payloads):
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for item in value_member_payloads:
            for casilla_id in requirement.source_casilla_ids:
                if casilla_id not in item.observation.casilla_values:
                    blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    elif payload is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION)
    else:
        observation_source_kind = payload.source_kind
        observation_values = dict(payload.observation.casilla_values)
        if payload.source_kind == "operator_manual":
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for casilla_id in requirement.source_casilla_ids:
            if casilla_id not in observation_values:
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
    observation_source_kind: str | None,
    value_member_payloads: tuple[_ObservationPayload, ...],
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
    external_evidence_kind: str | None = None
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
            unstamped_revision_advisory=source.unstamped_revision_advisory,
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
        unstamped_revision_advisory=source.unstamped_revision_advisory,
    )


def _filing_external_evidence_blockers(
    filing: ModeloRecord,
    observation_source_kind: str | None,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    observation_source_metadata: Mapping[str, str] | None = None,
) -> list[CrossPeriodCleanStateBlocker]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if filing.status is not ModeloRecordStatus.VIGENTE:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
    if not filing.aeat_accepted:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE)
    if filing.external_evidence is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE)
        if observation_source_kind not in _OFFICIAL_SOURCE_KINDS:
            blockers.append(CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE)
    elif filing.external_evidence.kind.value not in _JUSTIFICANTE_VERIFIED_EXTERNAL_EVIDENCE_KINDS:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION)
    else:
        justificante = justificante_repository.load(filing.external_evidence.reference_id)
        if justificante is None:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD)
        elif not _justificante_matches_filing(filing, justificante, taxpayer_tax_id=taxpayer_tax_id):
            blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
        else:
            blockers.extend(_justificante_observation_reference_blockers(justificante, observation_source_metadata))
    return blockers


def _justificante_observation_reference_blockers(
    justificante: Justificante,
    observation_source_metadata: Mapping[str, str] | None,
) -> list[CrossPeriodCleanStateBlocker]:
    """Require comparable filed-history references to agree with the parsed receipt."""
    if not observation_source_metadata:
        return []
    blockers: list[CrossPeriodCleanStateBlocker] = []
    metadata_csv = _clean_metadata_value(
        observation_source_metadata.get("aeat_justificante_csv") or observation_source_metadata.get("justificante_csv"),
    )
    if metadata_csv is not None and metadata_csv.casefold() != justificante.csv.casefold():
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    metadata_csvs = _clean_metadata_csvs(observation_source_metadata.get("aeat_justificante_csvs"))
    if metadata_csvs and justificante.csv.casefold() not in {csv.casefold() for csv in metadata_csvs}:
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)

    metadata_expediente_id = _clean_metadata_value(observation_source_metadata.get("aeat_expediente_id"))
    presentation_id = _clean_metadata_value(justificante.presentation_id)
    if metadata_expediente_id is not None:
        has_csv_reference = metadata_csv is not None or bool(metadata_csvs)
        if (presentation_id is None and not has_csv_reference) or (
            presentation_id is not None and metadata_expediente_id.casefold() != presentation_id.casefold()
        ):
            blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    return blockers


def _clean_metadata_value(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _clean_metadata_csvs(value: str | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in (value or "").split(",") if item.strip()))


def _justificante_matches_filing(
    filing: ModeloRecord,
    justificante: Justificante,
    *,
    taxpayer_tax_id: str | None,
) -> bool:
    expected_tax_id = filing.member_nif or taxpayer_tax_id
    if expected_tax_id is None or not expected_tax_id.strip():
        return False
    tax_id_matches = justificante.tax_id.strip().upper() == expected_tax_id.strip().upper()
    return (
        justificante.modelo.strip() == str(filing.modelo)
        and str(justificante.ejercicio or "").strip() == str(filing.filing_year)
        and justificante.period == filing.period
        and tax_id_matches
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
    calculation_revision_id: str | None
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: str | None
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
    observation_source_kind: str | None,
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
        filing.external_evidence.kind.value if filing.external_evidence is not None else None,
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


def _combined_source_kind(source_kinds: Iterable[str]) -> str:
    unique = tuple(dict.fromkeys(source_kinds))
    if len(unique) == 1:
        return unique[0]
    return "mixed"


filing_external_evidence_blockers = _filing_external_evidence_blockers


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
