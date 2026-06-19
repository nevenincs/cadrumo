"""Clean-state proof for filing-grade cross-period modelo dependencies.

Used by: :mod:`~aeat.application.calculations._calculate` to verify cross-period requirements before filing.

Use of :class:`~aeat.domain.calculations.registry.RegistrySnapshot` and
:class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority` for
compliance. Reads filed :class:`ModeloRecord` rows from the record catalogue
to prove a dependent period's upstream filings carry official evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from enum import StrEnum
from typing import Final, NamedTuple, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core import Period
from ...domain.calculations.registry import (
    Modelo202Modality,
    RegistryModeloObservation,
    RegistryModeloObservationRequirement,
    RegistryRelationSourceRequirement,
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
from ._observations_repository import CalculationObservationRepository
from ._revision_carry_gate import revision_carry_outcome

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")
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


def _require_period_year(period: Period, filing_year: int, *, field_name: str) -> None:
    if period.filing_year != filing_year:
        raise ValueError(f"{field_name}.filing_year must match filing_year")


class _ObservationPayload(Protocol):
    """Structural interface for the observation envelope payload consumed here.

    Matches the public attribute surface of
    :class:`~aeat.application.calculations._observations_repository._ObservationPayload`
    without importing its private name.
    """

    observation: RegistryModeloObservation
    source_kind: str
    member_nif: str | None
    stamped_revision_id: str | None
    source_metadata: dict[str, str]


class CrossPeriodDependencyOrigin(StrEnum):
    """Registry source family that created a cross-period dependency."""

    PREVIOUS_FILING_BINDING = "previous_filing_binding"
    REGISTRY_RELATION = "registry_relation"


class CrossPeriodCleanStateBlocker(StrEnum):
    """Blocking reason codes for a cross-period clean-state verdict."""

    MISSING_OBSERVATION = "missing_observation"
    MISSING_OBSERVED_CASILLA = "missing_observed_casilla"
    MISSING_CURRENT_FILING_RECORD = "missing_current_filing_record"
    DUPLICATE_CURRENT_FILING_RECORD = "duplicate_current_filing_record"
    SUPERSEDED_DEPENDENCY = "superseded_dependency"
    MISSING_CALCULATION_REVISION = "missing_calculation_revision"
    UNFILED_CALCULATION_REVISION = "unfiled_calculation_revision"
    MISSING_COMPLETE_VERIFICATION_REPORT = "missing_complete_verification_report"
    LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE = "local_filing_missing_external_evidence"
    MISSING_AEAT_ACCEPTANCE = "missing_aeat_acceptance"
    MISSING_EXTERNAL_EVIDENCE = "missing_external_evidence"
    MISSING_EXTERNAL_EVIDENCE_RECORD = "missing_external_evidence_record"
    MISMATCHED_EXTERNAL_EVIDENCE_RECORD = "mismatched_external_evidence_record"
    MISSING_JUSTIFICANTE_VERIFICATION = "missing_justificante_verification"
    OBSERVATION_REVISION_VALUE_DIVERGENCE = "observation_revision_value_divergence"
    OPERATOR_MANUAL_SOURCE = "operator_manual_source"
    INCOMPLETE_GROUP_MEMBER_COVERAGE = "incomplete_group_member_coverage"
    MISSING_EXPECTED_GROUP_MEMBER_ROSTER = "missing_expected_group_member_roster"
    UNEXPECTED_GROUP_MEMBER_SOURCE = "unexpected_group_member_source"
    REGISTRY_REVISION_DIVERGENCE = "registry_revision_divergence"
    """Stamped revision id does not match the law-determined revision for the source (modelo, filing_year, period).

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2: a prior
    observation captured under a revision that is no longer the law-determined
    revision for its source context must not silently propagate its norms. The
    carry is refused until the operator re-files and re-stamps under the correct
    revision.
    """


class NoPriorObligationProvenanceKind(StrEnum):
    """Provenance family for a no-prior-obligation pre-activity suppression.

    ADR 2026-06-13-first-filer-attestation-adr: a cross-period dependency anchor
    whose period falls strictly before the taxpayer's recorded activity-start
    date is scoped out of the requirement graph. The scoping is stamped with the
    provenance of the activity-start date that justified it.

    The ``NO_PRIOR_OBLIGATION_PRE_ACTIVITY`` value is the facet-kind discriminator
    carried on the evidence row; it names a *suppression*, not an evidence source,
    and is therefore categorically never a member of :data:`_OFFICIAL_SOURCE_KINDS`
    (which families a *filing's* AEAT evidence). The regression in
    ``test_cross_period_clean_state_enforcement.py`` pins that exclusion.
    """

    #: The facet-kind discriminator: this requirement was suppressed because its
    #: period is pre-activity (no prior obligation could have existed).
    NO_PRIOR_OBLIGATION_PRE_ACTIVITY = "no_prior_obligation_pre_activity"

    #: The facet-kind discriminator: this Modelo 202 pago-fraccionado requirement
    #: was suppressed because the taxpayer is a first-year Impuesto sobre
    #: Sociedades filer under modalidad cuota (LIS art. 40.2). The pago fraccionado
    #: in modalidad cuota is computed as a percentage of the cuota íntegra of the
    #: LAST IS return whose filing deadline has elapsed (LIS art. 40.2); a company
    #: whose first IS year is the target year has no such prior IS return, so the
    #: art. 40.2 modality produces no pago-fraccionado obligation and the
    #: cross-period dependency demanding evidence of a prior Modelo 200/202 that
    #: never existed is scoped out. This applies ONLY to art. 40.2 (cuota) — under
    #: art. 40.3 (base imponible, INCN > 6.000.000 €) the pago fraccionado is
    #: computed on the current year's running base and IS owed in the first year,
    #: so that modality is never suppressed.
    NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR = "no_fractional_payment_obligation_first_year"

    #: The activity-start date is the operator-declared ``activity_start_date``
    #: field (not corroborated by an AEAT censo snapshot). Carries the advisory.
    OPERATOR_DECLARED = "operator_declared"

    #: The activity-start date was corroborated against an AEAT censo snapshot.
    #: Deferred per the accepted ADR until the live censo read is functional;
    #: declared above for the upgrade path so the facet vocabulary is stable.
    CENSO_CORROBORATED = "censo_corroborated"


class NoPriorObligationProvenance(BaseModel):
    """Typed marker that a dependency was scoped out as no-prior-obligation.

    ADR 2026-06-13-first-filer-attestation-adr (operator-declared now,
    censo-corroborated when the live censo surface is fixed): records the
    activity-start date that scoped a pre-activity dependency out of the
    requirement graph, the provenance kind of that date, and - when present - the
    AEAT censo snapshot id that corroborated it. The suppression is an explicit,
    auditable outcome (``no-silent-under-declaration``), never a silent omission.
    """

    model_config = _STRICT_FROZEN

    facet_kind: NoPriorObligationProvenanceKind = NoPriorObligationProvenanceKind.NO_PRIOR_OBLIGATION_PRE_ACTIVITY
    activity_start_date: date
    provenance_kind: NoPriorObligationProvenanceKind = NoPriorObligationProvenanceKind.OPERATOR_DECLARED
    censo_snapshot_id: str | None = None

    @model_validator(mode="after")
    def _provenance_kind_is_a_source_kind(self) -> Self:
        if self.provenance_kind not in (
            NoPriorObligationProvenanceKind.OPERATOR_DECLARED,
            NoPriorObligationProvenanceKind.CENSO_CORROBORATED,
        ):
            raise ValueError(
                f"provenance_kind must be OPERATOR_DECLARED or CENSO_CORROBORATED, got {self.provenance_kind.value!r}",
            )
        if (
            self.provenance_kind is NoPriorObligationProvenanceKind.CENSO_CORROBORATED
            and self.censo_snapshot_id is None
        ):
            raise ValueError("censo_corroborated provenance requires a censo_snapshot_id")
        return self

    @property
    def is_operator_declared(self) -> bool:
        """True when the activity-start date is operator-declared (carries the advisory)."""
        return self.provenance_kind is NoPriorObligationProvenanceKind.OPERATOR_DECLARED


def _period_strictly_before_activity_start(period: Period, activity_start_date: date) -> bool:
    """Return whether ``period`` falls STRICTLY before the activity-start date.

    ADR 2026-06-13-first-filer-attestation-adr, ratified boundary semantics: the
    alta-CONTAINING period IS the first obligation; only STRICTLY-prior periods
    are suppressed. A period is strictly-prior when its entire inclusive span ends
    before the activity-start date - mirroring the deadline engine's pre-start
    gate (``closes_on < activity_start_date``,
    :func:`aeat.domain.deadlines._engine`) against the same operator-declared
    field. The comparison is routed through :class:`Period` boundary authority
    (:attr:`Period.end_date`) per ``period-filter-single-boundary-authority`` - no
    parallel inclusion math.

    A period whose span contains the activity-start date returns ``False`` (it is
    the first obligation, in scope). A period with no calendar span
    (instalment/extended claves) cannot be positioned against a date and returns
    ``False`` (never suppressed), so the scoping never silently drops a
    non-calendar anchor.
    """
    if not period.has_date_span():
        return False
    return period.end_date < activity_start_date


class CrossPeriodDependencyRequirement(BaseModel):
    """One upstream filed declaration required by a target registry snapshot."""

    model_config = _STRICT_FROZEN

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    source_casillas: tuple[str, ...] = Field(min_length=1)
    origin: CrossPeriodDependencyOrigin
    origin_ids: tuple[str, ...] = Field(min_length=1)
    requires_member_fan_in: bool = False

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> Self:
        _require_period_year(self.period, self.filing_year, field_name="period")
        return self

    @property
    def key(self) -> tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]]:
        return (self.source_modelo, self.filing_year, self.period.registry_token, self.origin, self.origin_ids)


class CrossPeriodExpectedMemberSet(BaseModel):
    """Expected grupo-de-entidades members for one member fan-in dependency."""

    model_config = _STRICT_FROZEN

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    member_nifs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> Self:
        _require_period_year(self.period, self.filing_year, field_name="period")
        return self

    @property
    def requirement_key(self) -> tuple[str, int, str]:
        """Return the dependency key this expected member roster proves."""
        return (self.source_modelo, self.filing_year, self.period.registry_token)


class CrossPeriodDependencyInventoryItem(BaseModel):
    """Registry-derived cross-period dependency coverage for one target snapshot."""

    model_config = _STRICT_FROZEN

    target_modelo: str = Field(min_length=1, max_length=8)
    target_revision_id: str = Field(min_length=1)
    target_filing_year: int = Field(ge=2000, le=2099)
    target_period: Period
    dependencies: tuple[CrossPeriodDependencyRequirement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> Self:
        _require_period_year(self.target_period, self.target_filing_year, field_name="target_period")
        return self

    @property
    def source_modelos(self) -> tuple[str, ...]:
        """Return the upstream modelos required by this target snapshot."""
        return tuple(sorted({requirement.source_modelo for requirement in self.dependencies}))


class CrossPeriodDependencyInventory(BaseModel):
    """Registry-derived inventory of all cross-period target snapshots for a filing year."""

    model_config = _STRICT_FROZEN

    filing_year: int = Field(ge=2000, le=2099)
    items: tuple[CrossPeriodDependencyInventoryItem, ...] = ()

    @property
    def target_modelos(self) -> tuple[str, ...]:
        """Return target modelos that declare filing-history dependencies."""
        return tuple(sorted({item.target_modelo for item in self.items}))

    @property
    def source_modelos(self) -> tuple[str, ...]:
        """Return upstream modelos required by the inventory."""
        return tuple(sorted({source_modelo for item in self.items for source_modelo in item.source_modelos}))


class CrossPeriodDependencyEvidence(BaseModel):
    """Observed filing-state evidence for one dependency requirement."""

    model_config = _STRICT_FROZEN

    requirement: CrossPeriodDependencyRequirement
    observation_source_kind: str | None = None
    filing_record_id: str | None = None
    calculation_revision_id: str | None = None
    member_filing_record_ids: tuple[str, ...] = ()
    member_calculation_revision_ids: tuple[str, ...] = ()
    calculation_revision_state: CalculationRevisionState | None = None
    verification_status: VerificationCompletenessStatus | None = None
    aeat_accepted: bool | None = None
    external_evidence_kind: str | None = None
    observed_member_nifs: tuple[str, ...] = ()
    expected_member_nifs: tuple[str, ...] = ()
    missing_member_nifs: tuple[str, ...] = ()
    unexpected_member_nifs: tuple[str, ...] = ()
    blockers: tuple[CrossPeriodCleanStateBlocker, ...] = ()
    unstamped_revision_advisory: bool = False
    """Non-blocking advisory: the source observation has no revision stamp (legacy record).

    The carry proceeds but this flag is ``True`` when the persisted observation
    predates the revision-provenance field (ADR 2026-06-10-period-revision-resolution-adr,
    Ruling 3 / R2). Operators should re-file the source period to obtain a stamped
    record. A divergent stamp produces ``REGISTRY_REVISION_DIVERGENCE`` in
    :attr:`blockers` instead.
    """
    no_prior_obligation: NoPriorObligationProvenance | None = None
    """Typed marker that this dependency was scoped out as no-prior-obligation.

    ADR 2026-06-13-first-filer-attestation-adr: when the requirement's period
    falls strictly before the taxpayer's recorded activity-start date, the
    dependency is suppressed (no prior obligation could have legally existed) and
    this facet records the activity-start date and provenance that justified it.
    A suppressed requirement carries no blockers and is :attr:`clean`, but the
    suppression is explicit and auditable here rather than a silent omission
    (``no-silent-under-declaration``). ``None`` for an in-scope dependency.
    """

    @property
    def clean(self) -> bool:
        return not self.blockers

    @property
    def suppressed_pre_activity(self) -> bool:
        """True when this dependency was scoped out as no-prior-obligation pre-activity.

        Scoped to the ``NO_PRIOR_OBLIGATION_PRE_ACTIVITY`` facet specifically: a
        dependency suppressed under the first-year Modelo 202 modalidad-cuota facet
        is NOT a pre-activity suppression and must not read as one (the two
        suppressions raise different advisories — see
        :attr:`suppressed_first_year_fractional`).
        """
        return (
            self.no_prior_obligation is not None
            and self.no_prior_obligation.facet_kind == NoPriorObligationProvenanceKind.NO_PRIOR_OBLIGATION_PRE_ACTIVITY
        )

    @property
    def suppressed_first_year_fractional(self) -> bool:
        """True when this dependency was scoped out as a first-year Modelo 202 modalidad-cuota.

        ADR 2026-06-19-m202-first-period-attestation-adr: a first-year IS filer
        under modalidad cuota (LIS art. 40.2) has no Modelo 202 pago-fraccionado
        obligation, so the cross-period dependency demanding evidence of a prior
        Modelo 200/202 that never existed is scoped out under the
        ``NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR`` facet.
        """
        return (
            self.no_prior_obligation is not None
            and self.no_prior_obligation.facet_kind
            == NoPriorObligationProvenanceKind.NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR
        )

    @property
    def operator_declared_suppression_advisory(self) -> bool:
        """True when the PRE-ACTIVITY suppression rests on an operator-declared (uncorroborated) date.

        The verification caller raises a NON-BLOCKING advisory for this case per
        the accepted ADR (operator-declared now, censo-corroborated when the live
        censo surface is fixed). Scoped to the pre-activity facet only: the
        first-year Modelo 202 modalidad-cuota suppression carries its own distinct
        advisory (:attr:`suppressed_first_year_fractional`) and must not cross-fire
        this one.
        """
        return (
            self.suppressed_pre_activity
            and self.no_prior_obligation is not None
            and (self.no_prior_obligation.is_operator_declared)
        )


class CrossPeriodCleanStateVerdict(BaseModel):
    """Clean-state result for every cross-period dependency in a target snapshot."""

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    target_modelo: str = Field(min_length=1, max_length=8)
    target_filing_year: int = Field(ge=2000, le=2099)
    target_period: Period
    dependencies: tuple[CrossPeriodDependencyEvidence, ...] = ()

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> Self:
        _require_period_year(self.target_period, self.target_filing_year, field_name="target_period")
        return self

    @property
    def requires_clean_state(self) -> bool:
        return bool(self.dependencies)

    @property
    def clean(self) -> bool:
        return all(item.clean for item in self.dependencies)

    @property
    def blockers(self) -> tuple[CrossPeriodCleanStateBlocker, ...]:
        return tuple(dict.fromkeys(blocker for item in self.dependencies for blocker in item.blockers))

    @property
    def has_unstamped_revision_advisory(self) -> bool:
        """True when any dependency carries a legacy unstamped-revision advisory."""
        return any(item.unstamped_revision_advisory for item in self.dependencies)

    @property
    def suppressed_pre_activity_dependencies(self) -> tuple[CrossPeriodDependencyEvidence, ...]:
        """Return dependencies scoped out as no-prior-obligation pre-activity.

        Returns:
            The :class:`CrossPeriodDependencyEvidence` entries suppressed as
            pre-activity.
        """
        return tuple(item for item in self.dependencies if item.suppressed_pre_activity)

    @property
    def has_operator_declared_suppression_advisory(self) -> bool:
        """True when any pre-activity suppression rests on an operator-declared (uncorroborated) date."""
        return any(item.operator_declared_suppression_advisory for item in self.dependencies)

    @property
    def suppressed_first_year_fractional_dependencies(self) -> tuple[CrossPeriodDependencyEvidence, ...]:
        """Return dependencies scoped out as first-year Modelo 202 modalidad-cuota.

        ADR 2026-06-19-m202-first-period-attestation-adr.

        Returns:
            The :class:`CrossPeriodDependencyEvidence` entries suppressed as a
            first-year no-fractional-payment obligation (LIS art. 40.2).
        """
        return tuple(item for item in self.dependencies if item.suppressed_first_year_fractional)

    @property
    def has_first_year_fractional_suppression_advisory(self) -> bool:
        """True when any dependency was scoped out as a first-year Modelo 202 modalidad-cuota.

        The verification caller raises a NON-BLOCKING advisory for this case
        (ADR 2026-06-19-m202-first-period-attestation-adr): a first-year IS filer
        under modalidad cuota (LIS art. 40.2) has no Modelo 202 obligation, but if
        the entity elected modalidad base (art. 40.3) it IS obligated; the operator
        bears legal responsibility for the modality, so the suppression is surfaced
        non-silently.
        """
        return any(item.suppressed_first_year_fractional for item in self.dependencies)


def cross_period_dependency_requirements(snapshot: RegistrySnapshot) -> tuple[CrossPeriodDependencyRequirement, ...]:
    """Return the :class:`CrossPeriodDependencyRequirement` records for ``snapshot``.

    Derives filed-history requirements from :class:`RegistrySnapshot`.
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
    :attr:`CrossPeriodDependencyRequirement.origin`; this predicate is
    origin-agnostic), so a first filer is never unblocked on one origin and
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
    """Return a :class:`CrossPeriodDependencyInventory` of snapshots with cross-period dependencies.

    The inventory is a backend coverage surface. It lets callers prove which
    modelos and periods are in scope for the clean-state guard before they wire
    model-specific workflow tests or operator diagnostics.

    Uses :class:`ValidatedRegistryAuthority` for snapshot resolution.
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
    outcome with NO blockers (the row is :attr:`CrossPeriodDependencyEvidence.clean`).

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
    if requirement.source_modelo != "202":
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
) -> CrossPeriodCleanStateVerdict:
    """Evaluate cross-period dependencies and return a :class:`CrossPeriodCleanStateVerdict`.

    Uses :class:`RegistrySnapshot` to derive the dependency requirements.

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
    """
    filing_catalogue = filing_repository.load()
    calculation_catalogue = calculation_repository.load()
    verification_catalogue = verification_repository.load()
    resolved_justificante_repository = justificante_repository or JustificanteRepository()
    expected_member_sets_by_key = _expected_member_sets_by_key(expected_member_sets)
    partition = partition_cross_period_requirements_by_activity_start(
        cross_period_dependency_requirements(snapshot),
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
    return CrossPeriodCleanStateVerdict(
        bucket_id=bucket_id,
        target_modelo=str(snapshot.modelo.id),
        target_filing_year=snapshot.filing_year,
        target_period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        dependencies=(*in_scope_dependencies, *suppressed_dependencies, *first_year_fractional_dependencies),
    )


def _requirements_from_previous_filing(
    requirement: RegistryModeloObservationRequirement,
    *,
    snapshot: RegistrySnapshot,
) -> Iterable[CrossPeriodDependencyRequirement]:
    grouped_keys = _per_grupo_member_requirement_keys(snapshot)
    yield CrossPeriodDependencyRequirement(
        source_modelo=requirement.modelo,
        filing_year=requirement.filing_year,
        period=Period.from_year_and_code(requirement.filing_year, requirement.period),
        source_casillas=requirement.source_casillas,
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=requirement.binding_ids,
        requires_member_fan_in=(requirement.modelo, requirement.filing_year, requirement.period) in grouped_keys,
    )


def _requirements_from_relation(
    requirement: RegistryRelationSourceRequirement,
) -> Iterable[CrossPeriodDependencyRequirement]:
    for period in requirement.periods:
        yield CrossPeriodDependencyRequirement(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=Period.from_year_and_code(requirement.filing_year, period),
            source_casillas=(requirement.source_output,),
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
            keys.add((requirement.modelo, requirement.filing_year, requirement.period))
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
) -> tuple[str | None, dict[str, object], list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    observation_source_kind: str | None = None
    observation_values: dict[str, object] = {}
    if requirement.requires_member_fan_in and value_member_payloads:
        observation_source_kind = _combined_source_kind(item.source_kind for item in value_member_payloads)
        if any(item.source_kind == "operator_manual" for item in value_member_payloads):
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for item in value_member_payloads:
            for casilla_id in requirement.source_casillas:
                if casilla_id not in item.observation.casilla_values:
                    blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    elif payload is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION)
    else:
        observation_source_kind = payload.source_kind
        observation_values = dict(payload.observation.casilla_values)
        if payload.source_kind == "operator_manual":
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for casilla_id in requirement.source_casillas:
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
    observation_values: Mapping[str, object],
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
        for casilla_id in requirement.source_casillas:
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
    observation_values: Mapping[str, object],
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
    "partition_cross_period_requirements_by_activity_start",
]
