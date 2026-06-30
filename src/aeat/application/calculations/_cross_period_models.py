"""Typed records for cross-period clean-state evaluation."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core import Period
from ...domain.calculations.registry import CasillaId, RegistryModeloObservation
from ...domain.modelos import CalculationRevisionState, VerificationCompletenessStatus

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


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
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
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
        _require_period_year(
            self.target_period,
            self.target_filing_year,
            field_name="target_period",
        )
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
    """Non-blocking advisory: the source revision stamp could not be re-confirmed.

    The carry proceeds but this flag is ``True`` when the source context cannot
    be resolved for stamp re-confirmation. Operators should re-pull the source
    period to obtain a currently verifiable record. A divergent stamp produces
    ``REGISTRY_REVISION_DIVERGENCE`` in :attr:`blockers` instead.
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

    non_official_local_chain_advisory: bool = False
    """Non-blocking advisory: a same-year ``app_filing`` chain admitted, lacking only official AEAT evidence."""
    modelo_not_applicable_advisory: bool = False
    """Non-blocking advisory: a dependency on a modelo the taxpayer suffers but does not file (not-applicable)."""
    zero_value_previous_filing_advisory: bool = False
    """Non-blocking advisory: an explicit zero previous-filing carry needed no source-filing proof.

    This is deliberately narrower than no-prior-obligation suppression: it applies
    only when the verification caller has proven that the target revision carries
    an operator-supplied zero for a whitelisted previous-filing binding whose
    positive value would be a taxpayer benefit. A nonzero carry still requires the
    prior filing evidence.
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
        _require_period_year(
            self.target_period,
            self.target_filing_year,
            field_name="target_period",
        )
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
        """True when any dependency carries a revision re-confirmation advisory."""
        return any(item.unstamped_revision_advisory for item in self.dependencies)

    @property
    def has_non_official_local_chain_advisory(self) -> bool:
        """True when any dependency was admitted as a same-year non-official local chain."""
        return any(item.non_official_local_chain_advisory for item in self.dependencies)

    @property
    def has_modelo_not_applicable_advisory(self) -> bool:
        """True when any dependency was scoped out as not-applicable (taxpayer suffers, does not file)."""
        return any(item.modelo_not_applicable_advisory for item in self.dependencies)

    @property
    def has_zero_value_previous_filing_advisory(self) -> bool:
        """True when an explicit zero previous-filing carry was scoped out."""
        return any(item.zero_value_previous_filing_advisory for item in self.dependencies)

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
