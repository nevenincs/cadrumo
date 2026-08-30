"""Typed records for cross-period clean-state evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, OperatorActionAxis
from ...core.period import Period
from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity import BucketId, CalculationRevisionId, FilingRecordId
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.ids import (
    LegalRefId,
    RevisionId,
    SourceRefId,
)
from ...domain.modelos.filing_record import ExternalEvidenceKind
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ...domain.modelos.calculation_revision import CalculationRevisionState
from .observations_repository import ObservationSourceKind


def _require_period_year(period: Period, filing_year: int, *, field_name: str) -> None:
    if period.filing_year != filing_year:
        raise ValueError(f"{field_name}.filing_year must match filing_year")


class _ObservationPayload(Protocol):
    """Structural interface for the observation envelope payload consumed here.

    Matches the public attribute surface of
    :class:`~application.calculations.cross_period_models._ObservationPayload`
    without importing its private name.
    """

    observation: RegistryModeloObservation
    source_kind: ObservationSourceKind
    member_nif: str | None
    stamped_revision_id: RevisionId
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
    UNRESOLVED_TAXPAYER_IDENTITY = "unresolved_taxpayer_identity"
    """No taxpayer identity was resolvable, so the justificante could not be identity-checked.

    Distinct from :attr:`MISMATCHED_EXTERNAL_EVIDENCE_RECORD`, which asserts the
    stored receipt belongs to someone else. Both once reported the same code, so
    an operator whose profile simply carried no NIF was told their filed evidence
    was mismatched -- pointing them at the receipt rather than at the profile
    field they had not filled in. The check is still fail-closed: an
    unidentifiable receipt cannot satisfy the clean-state gate. Only the reason
    given to the operator changes, and it is the reason that tells them what to
    fix.
    """
    MISSING_JUSTIFICANTE_VERIFICATION = "missing_justificante_verification"
    OBSERVATION_REVISION_VALUE_DIVERGENCE = "observation_revision_value_divergence"
    OPERATOR_MANUAL_SOURCE = "operator_manual_source"
    INCOMPLETE_GROUP_MEMBER_COVERAGE = "incomplete_group_member_coverage"
    MISSING_EXPECTED_GROUP_MEMBER_ROSTER = "missing_expected_group_member_roster"
    UNEXPECTED_GROUP_MEMBER_SOURCE = "unexpected_group_member_source"
    REGISTRY_REVISION_DIVERGENCE = "registry_revision_divergence"
    """Stamped revision id does not re-confirm against the law-determined revision for the source.

    A prior observation captured under a revision that is no longer the
    law-determined revision for its source context, or whose source context
    cannot be resolved for re-confirmation, must not silently propagate its
    norms. The carry is refused until the operator re-files and re-stamps
    under the current revision.
    """


OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER: Mapping[
    CrossPeriodCleanStateBlocker,
    OperatorActionAxis,
] = {
    CrossPeriodCleanStateBlocker.MISSING_OBSERVATION: OperatorActionAxis.FILE_PRIOR_PERIOD,
    CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
    CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD: OperatorActionAxis.FILE_PRIOR_PERIOD,
    CrossPeriodCleanStateBlocker.DUPLICATE_CURRENT_FILING_RECORD: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
    CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY: OperatorActionAxis.FILE_PRIOR_PERIOD,
    CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION: OperatorActionAxis.FILE_PRIOR_PERIOD,
    CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION: OperatorActionAxis.FILE_PRIOR_PERIOD,
    CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT: OperatorActionAxis.RE_VERIFY,
    CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE: (OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE),
    CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE: OperatorActionAxis.FILE_PRIOR_PERIOD,
    CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
    CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
    CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
    CrossPeriodCleanStateBlocker.UNRESOLVED_TAXPAYER_IDENTITY: OperatorActionAxis.RESOLVE_IDENTITY,
    CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
    CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
    CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
    CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE: OperatorActionAxis.CONFIRM_GROUP_MEMBERSHIP,
    CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER: OperatorActionAxis.CONFIRM_GROUP_MEMBERSHIP,
    CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE: OperatorActionAxis.CONFIRM_GROUP_MEMBERSHIP,
    CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE: OperatorActionAxis.RESOLVE_REVISION_MISMATCH,
}
"""Total operator-action projection retaining each native clean-state blocker."""

if set(OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER) != set(CrossPeriodCleanStateBlocker):
    _unmapped_cross_period_blockers = sorted(
        blocker.value
        for blocker in set(CrossPeriodCleanStateBlocker) - set(OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER)
    )
    raise RuntimeError(
        "every CrossPeriodCleanStateBlocker must declare an OperatorActionAxis; "
        f"unmapped: {', '.join(_unmapped_cross_period_blockers)}",
    )


class NoPriorObligationProvenanceKind(StrEnum):
    """Provenance family for a no-prior-obligation pre-activity suppression.

    A cross-period dependency anchor whose period falls strictly before the
    taxpayer's recorded activity-start
    date is scoped out of the requirement graph. The scoping is stamped with the
    provenance of the activity-start date that justified it.

    The ``NO_PRIOR_OBLIGATION_PRE_ACTIVITY`` value is the facet-kind discriminator
    carried on the evidence row; it names a *suppression*, not an evidence source,
    and is therefore categorically never an official
    :class:`ObservationSourceKind` (which families a *filing's* AEAT evidence).
    The regression in
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
    #: field. Censal facts are operator-supplied through ``config profile edit``
    #: (the live Modelo 036 censo read was retired: AEAT exposes no read-only
    #: "Mis Datos Censales" projection), so this is the sole provenance kind for
    #: a scoped-out no-prior-obligation dependency. Carries the advisory.
    OPERATOR_DECLARED = "operator_declared"


class NoPriorObligationProvenance(BaseModel):
    """Typed marker that a dependency was scoped out as no-prior-obligation.

    Records the activity-start date that scoped a pre-activity dependency out
    of the requirement graph and the
    provenance kind of that date. The date is operator-declared — censal facts
    are operator-supplied through ``config profile edit`` since the live Modelo
    036 censo read was retired — so ``OPERATOR_DECLARED`` is the sole provenance
    kind. The suppression is an explicit, auditable outcome
    (``no-silent-under-declaration``), never a silent omission.
    """

    model_config = STRICT_FROZEN_CONFIG

    facet_kind: NoPriorObligationProvenanceKind = NoPriorObligationProvenanceKind.NO_PRIOR_OBLIGATION_PRE_ACTIVITY
    activity_start_date: date
    provenance_kind: NoPriorObligationProvenanceKind = NoPriorObligationProvenanceKind.OPERATOR_DECLARED

    @model_validator(mode="after")
    def _provenance_kind_is_a_source_kind(self) -> Self:
        if self.provenance_kind is not NoPriorObligationProvenanceKind.OPERATOR_DECLARED:
            raise ValueError(
                f"provenance_kind must be OPERATOR_DECLARED, got {self.provenance_kind.value!r}",
            )
        return self

    @property
    def is_operator_declared(self) -> bool:
        """True when the activity-start date is operator-declared (carries the advisory)."""
        return self.provenance_kind is NoPriorObligationProvenanceKind.OPERATOR_DECLARED


def _period_strictly_before_activity_start(period: Period, activity_start_date: date) -> bool:
    """Return whether ``period`` falls STRICTLY before the activity-start date.

    The ratified boundary semantics: the
    alta-CONTAINING period IS the first obligation; only STRICTLY-prior periods
    are suppressed. A period is strictly-prior when its entire inclusive span ends
    before the activity-start date - mirroring the deadline engine's pre-start
    gate (``closes_on < activity_start_date``,
    :func:`domain.deadlines.engine._window_outside_activity_period`) against
    the same operator-declared
    field. The comparison is routed through :class:`Period` boundary authority
    (:attr:`Period.end_date`) per ``aeat-registry-authority-flow`` - no
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


ObservationPayload = _ObservationPayload


def period_strictly_before_activity_start(period: Period, activity_start_date: date) -> bool:
    """Report whether ``period`` closes before economic activity began."""
    return _period_strictly_before_activity_start(period, activity_start_date)


class CrossPeriodDependencyRequirement(BaseModel):
    """One upstream filed declaration required by a target registry snapshot."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    required_source_casilla_ids: tuple[CasillaId, ...] | None = None
    source_presence_groups: tuple[tuple[CasillaId, ...], ...] = ()
    origin: CrossPeriodDependencyOrigin
    origin_ids: tuple[str, ...] = Field(min_length=1)
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    requires_member_fan_in: bool = False

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> Self:
        _require_period_year(self.period, self.filing_year, field_name="period")
        if self.required_source_casilla_ids is not None and not set(self.required_source_casilla_ids) <= set(
            self.source_casilla_ids
        ):
            raise ValueError("required_source_casilla_ids must be candidate source_casilla_ids")
        candidate_ids = set(self.source_casilla_ids)
        for group in self.source_presence_groups:
            if not group or not set(group) <= candidate_ids:
                raise ValueError("source_presence_groups must be non-empty subsets of source_casilla_ids")
        return self

    @property
    def enforced_source_casilla_ids(self) -> tuple[CasillaId, ...]:
        """Return mandatory source casillas, defaulting to every candidate."""
        if self.required_source_casilla_ids is None:
            return self.source_casilla_ids
        return self.required_source_casilla_ids

    @property
    def key(self) -> tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]]:
        """Return the identity tuple that distinguishes this dependency."""
        return (self.source_modelo, self.filing_year, self.period.registry_token, self.origin, self.origin_ids)


class CrossPeriodExpectedMemberSet(BaseModel):
    """Expected grupo-de-entidades members for one member fan-in dependency."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
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

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: str = Field(min_length=1, max_length=8)
    target_revision_id: RevisionId = Field(min_length=1)
    target_filing_year: FilingYear
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

    model_config = STRICT_FROZEN_CONFIG

    filing_year: FilingYear
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
    """Observed filing-state evidence for one dependency requirement.

    This model IS the clean-state verdict's evidence: a requirement whose
    evidence carries no blockers is reported :attr:`clean`, and a filing
    proceeds on that answer. Declaring the identities and provenance as bare
    strings therefore admitted evidence that could not exist -- an observation
    source outside the closed provenance taxonomy, filing-record and
    calculation-revision references that are not the canonical hex-64
    identities, an external-evidence kind naming no known evidence -- and the
    enclosing verdict still reported ``clean=True``, because nothing had put a
    blocker on it. Malformed evidence is not clean evidence; it is evidence
    that was never observed.

    Every identity and provenance field is now the canonical type its producer
    already holds, so a value the rest of the system could never have minted is
    refused at construction rather than laundered into a filing decision.
    """

    model_config = STRICT_FROZEN_CONFIG

    requirement: CrossPeriodDependencyRequirement
    observation_source_kind: ObservationSourceKind | None = None
    filing_record_id: FilingRecordId | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    member_filing_record_ids: tuple[FilingRecordId, ...] = ()
    member_calculation_revision_ids: tuple[CalculationRevisionId, ...] = ()
    calculation_revision_state: CalculationRevisionState | None = None
    verification_status: VerificationCompletenessStatus | None = None
    aeat_accepted: bool | None = None
    external_evidence_kind: ExternalEvidenceKind | None = None
    observed_member_nifs: tuple[str, ...] = ()
    expected_member_nifs: tuple[str, ...] = ()
    missing_member_nifs: tuple[str, ...] = ()
    unexpected_member_nifs: tuple[str, ...] = ()
    blockers: tuple[CrossPeriodCleanStateBlocker, ...] = ()
    no_prior_obligation: NoPriorObligationProvenance | None = None
    """Typed marker that this dependency was scoped out as no-prior-obligation.

    When the requirement's period
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
    m111_no_retenciones_no_obligation_advisory: bool = False
    """Non-blocking advisory: an M111 source period was explicitly attested as no-obligation.

    Modelo 111 instructions distinguish a negative return (subject payments made
    but no effective withholding) from a period with no subject payments at all.
    The latter must not be filed as an all-blank M111, so a cross-period
    dependency on that period can be scoped out only when the profile carries the
    explicit no-retenciones period token.
    """

    @field_validator("observation_source_kind", mode="before")
    @classmethod
    def _parse_observation_source_kind(cls, value: object) -> object:
        """Lift a raw provenance token to the closed observation-source taxonomy.

        The strict model config does not coerce ``str`` -> ``StrEnum``, and the
        upstream filing-history readers hand the stored token through as text.
        An unknown token raises here rather than reaching a clean verdict as
        free-form provenance.
        """
        if isinstance(value, str) and not isinstance(value, ObservationSourceKind):
            return ObservationSourceKind(value)
        return value

    @field_validator("external_evidence_kind", mode="before")
    @classmethod
    def _parse_external_evidence_kind(cls, value: object) -> object:
        """Lift a raw evidence token to the closed external-evidence catalogue."""
        if isinstance(value, str) and not isinstance(value, ExternalEvidenceKind):
            return ExternalEvidenceKind(value)
        return value

    @property
    def clean(self) -> bool:
        """Report whether this dependency carries no blockers."""
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

        A first-year IS filer
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

        The verification caller raises a NON-BLOCKING advisory for this case
        (operator-declared now, censo-corroborated when the live censo surface
        is fixed). Scoped to the pre-activity facet only: the
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

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    target_modelo: str = Field(min_length=1, max_length=8)
    target_filing_year: FilingYear
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
        """Report whether any dependency must reach a clean state."""
        return bool(self.dependencies)

    @property
    def clean(self) -> bool:
        """Report whether every dependency is clean."""
        return all(item.clean for item in self.dependencies)

    @property
    def blockers(self) -> tuple[CrossPeriodCleanStateBlocker, ...]:
        """Return the deduplicated blockers across every dependency."""
        return tuple(dict.fromkeys(blocker for item in self.dependencies for blocker in item.blockers))

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
    def has_m111_no_retenciones_no_obligation_advisory(self) -> bool:
        """True when any M111 source period was scoped out as no-retenciones/no-obligation."""
        return any(item.m111_no_retenciones_no_obligation_advisory for item in self.dependencies)

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

        Returns:
            The :class:`CrossPeriodDependencyEvidence` entries suppressed as a
            first-year no-fractional-payment obligation (LIS art. 40.2).
        """
        return tuple(item for item in self.dependencies if item.suppressed_first_year_fractional)

    @property
    def has_first_year_fractional_suppression_advisory(self) -> bool:
        """True when any dependency was scoped out as a first-year Modelo 202 modalidad-cuota.

        The verification caller raises a NON-BLOCKING advisory for this case:
        a first-year IS filer
        under modalidad cuota (LIS art. 40.2) has no Modelo 202 obligation, but if
        the entity elected modalidad base (art. 40.3) it IS obligated; the operator
        bears legal responsibility for the modality, so the suppression is surfaced
        non-silently.
        """
        return any(item.suppressed_first_year_fractional for item in self.dependencies)
