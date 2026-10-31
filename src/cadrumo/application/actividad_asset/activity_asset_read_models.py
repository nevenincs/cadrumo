"""Closed read models of the activity-asset register, computed by the backend for every frontend.

A frontend displays these figures and does no arithmetic.  A null figure is unknown
and comes with its typed reason; a recorded zero is a zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.tipos_actividad import TipoActividad
from ...domain.renta.actividad_asset.disposal import ActivityAssetDisposalFindingKind, ActivityAssetDisposalReason
from ...domain.renta.actividad_asset.election import AcquiredCondition, AmortizationMethod, DirectEstimationRegime
from ...domain.renta.actividad_asset.errors import PercentFact
from ...domain.renta.actividad_asset.fact_leaves import SEQUENCE_STEP, FactKind, indexed_to_step_path
from ...domain.renta.actividad_asset.lifecycle import (
    AcquisitionShape,
    AssetBasisStage,
    AssetKind,
    OpeningHistoryStatus,
)
from ...domain.renta.actividad_asset.register_records import ActivityAssetEventKind
from ...domain.renta.actividad_asset.schedule import last_day_covered
from ..operations.public_scalar import PublicDecimal
from .fact_wording import (
    timeline_field_paths,
    timeline_internal_fields,
    timeline_labelled_fields,
    timeline_token_families,
)
from .schedule_walk import PlanFigureAbsence

ACTIVITY_ASSET_LABEL_NAMESPACE: Final = "ledger.actividad_asset."
"""Where the catalogue holds one word per token, as ``<namespace><family>.<token>``."""

DISPOSAL_FINDING_FAMILY: Final = "disposal_finding"
PLAN_ADVISORY_FAMILY: Final = "plan_advisory"
_REASON_FACT_KEY_LIMIT: Final = 64
_REASON_FACT_VALUE_LIMIT: Final = 2048
NON_DEDUCTIBLE_IVA_STATE_FAMILY: Final = "non_deductible_iva_state"

TIMELINE_TOKEN_FAMILIES: Final[Mapping[str, tuple[str, type[StrEnum]]]] = timeline_token_families()
"""The timeline fields whose values are tokens or flags, with the catalogue family and enum that word them.

Derived from the models a record is made of, with a repeated row's index replaced by ``[]``.
"""

TIMELINE_LABELLED_FIELDS: Final[Mapping[str, FactKind]] = timeline_labelled_fields()
"""The timeline fields whose values are worded by a label: a share, or a table class."""

TIMELINE_INTERNAL_FIELDS: Final[frozenset[str]] = timeline_internal_fields()
"""The record fields no operator states, which the timeline never shows a change of."""

TIMELINE_FIELD_PATHS: Final[tuple[str, ...]] = timeline_field_paths()
"""Every fact the timeline can show a change of; the catalogue words each as ``<namespace>field.<path>``."""

TIMELINE_FIELD_FAMILY: Final = "field"


def activity_asset_label_key(family: str, token: StrEnum) -> str:
    """Name the catalogue key that words one token of a family."""
    return f"{ACTIVITY_ASSET_LABEL_NAMESPACE}{family}.{token.value}"


def timeline_field_word_key(path: str) -> str:
    """Name the catalogue key that words one timeline fact, given its path with ``[]`` for a repeated row."""
    return f"{ACTIVITY_ASSET_LABEL_NAMESPACE}{TIMELINE_FIELD_FAMILY}.{path.replace(SEQUENCE_STEP, '')}"


OPENING_REMEDY_FIELD: Final = "opening_history.accumulated_amount"
"""The field whose entry settles a reason that the amortization already deducted is unknown."""

OPENING_REMEDY_REASON_KEYS: Final[frozenset[str]] = frozenset(
    {
        "ledger.actividad_asset.errors.opening_history_missing",
        "ledger.actividad_asset.errors.opening_history_amount_missing",
    },
)
"""The reasons whose remedy is to enter the opening amount."""


def remedy_field_key(reason_key: str | None) -> str | None:
    """Name the catalogue word of the field that is the remedy of a reason, or ``None`` when entering a field is not."""
    if reason_key is None or reason_key not in OPENING_REMEDY_REASON_KEYS:
        return None
    return timeline_field_word_key(OPENING_REMEDY_FIELD)


def timeline_field_key(field: str) -> str | None:
    """Name the catalogue key of a timeline field, or ``None`` when no fact of the timeline has that path."""
    path = indexed_to_step_path(field)
    return timeline_field_word_key(path) if path in TIMELINE_FIELD_PATHS else None


def timeline_token_key(field: str, value: str | None) -> str | None:
    """Name the catalogue key of a timeline value, or ``None`` when the field carries no token or is unset."""
    family = TIMELINE_TOKEN_FAMILIES.get(indexed_to_step_path(field))
    if family is None or value is None:
        return None
    name, enum = family
    return activity_asset_label_key(name, enum(value))


class ActivityAssetReasonFactKind(StrEnum):
    """What a reason fact's value is, so a screen formats it by type and never by looking at the text."""

    TEXT = "text"
    DATE = "date"
    AMOUNT = "amount"
    PERCENT = "percent"
    COUNT = "count"


class ActivityAssetReasonFact(BaseModel):
    """One immutable fact used to render an activity-asset reason."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str = Field(min_length=1, max_length=_REASON_FACT_KEY_LIMIT)
    value: str = Field(max_length=_REASON_FACT_VALUE_LIMIT)
    kind: ActivityAssetReasonFactKind = ActivityAssetReasonFactKind.TEXT
    """Date values are ISO dates, amounts and percents plain decimals (a percent as a fraction), counts integers."""


def reason_fact_kind(value: object) -> ActivityAssetReasonFactKind:
    """Name the kind of a fact from the type it was raised with."""
    if isinstance(value, bool):
        return ActivityAssetReasonFactKind.TEXT
    if isinstance(value, PercentFact):
        return ActivityAssetReasonFactKind.PERCENT
    if isinstance(value, Decimal):
        return ActivityAssetReasonFactKind.AMOUNT
    if isinstance(value, int):
        return ActivityAssetReasonFactKind.COUNT
    if isinstance(value, date):
        return ActivityAssetReasonFactKind.DATE
    return ActivityAssetReasonFactKind.TEXT


def reason_fact_text(value: object) -> str:
    """Write a fact's value the way a reader receives it."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def project_reason_facts(
    facts: Mapping[str, object],
    kinds: Mapping[str, ActivityAssetReasonFactKind] | None = None,
) -> tuple[ActivityAssetReasonFact, ...]:
    """Preserve every reason fact in deterministic key order, each with the kind it was raised with."""
    return tuple(
        ActivityAssetReasonFact(
            key=key[:_REASON_FACT_KEY_LIMIT],
            value=reason_fact_text(value)[:_REASON_FACT_VALUE_LIMIT],
            kind=reason_fact_kind(value) if kinds is None else kinds.get(key, reason_fact_kind(value)),
        )
        for key, value in sorted(facts.items())
    )


class ActivityAssetRegisterState(StrEnum):
    """Where an element stands in the register today."""

    IN_SERVICE = "in_service"
    FULLY_AMORTIZED = "fully_amortized"
    OUT_OF_SERVICE = "out_of_service"


class ActivityAssetClaimState(StrEnum):
    """How a year's claims stand against what can be claimed in it."""

    CLAIMED = "claimed"
    MISSING = "missing"
    SUPERSEDED = "superseded"
    PARTIAL = "partial"
    NOT_DUE = "not_due"
    EDITION_UNAVAILABLE = "edition_unavailable"


class ActivityAssetPlanAdvisoryKind(StrEnum):
    """What the plan tells the operator about an election, changing no figure and refusing nothing."""

    USED_ELEMENT_GROUP_LIMIT = "used_element_group_limit"


class ActivityAssetClaimStaleReason(StrEnum):
    """Why a claim no longer matches the element's current schedule."""

    REVISION_CHANGED = "revision_changed"
    AUTHORITY_CHANGED = "authority_changed"
    SCHEDULE_UNAVAILABLE = "schedule_unavailable"


class ActivityAssetNonDeductibleIvaState(StrEnum):
    """Whether the ledger settles how much of a row's IVA is not deductible."""

    KNOWN = "known"
    UNKNOWN = "unknown"


class ActivityAssetNotTableBoundReason(StrEnum):
    """Why an election's limits do not come from the amortization table."""

    TWENTIETH_LIMIT = "twentieth_limit"
    USEFUL_LIFE_EVIDENCE = "useful_life_evidence"
    APPROVED_PLAN = "approved_plan"
    RESEARCH_DEVELOPMENT_PERIOD = "research_development_period"
    FREE_ELECTION = "free_election"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"


class _ReadModel(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class ActivityAssetFindingCounts(_ReadModel):
    """How many years or claims of an element need attention, by kind."""

    missing: int = Field(ge=0)
    incomplete: int = Field(ge=0)
    conflict: int = Field(ge=0)
    unsupported: int = Field(default=0, ge=0)
    without_tables: int = Field(default=0, ge=0)
    """Years no Modelo 100 edition covers, which have no table to charge under."""
    stale: int = Field(ge=0)
    """Claims in effect that no longer match the current schedule; a claim, not a year."""


class ActivityAssetListDisposal(_ReadModel):
    """The baja an element's current revision records."""

    disposal_date: date
    reason: ActivityAssetDisposalReason
    reason_key: str
    """The catalogue key that words ``reason``."""


class ActivityAssetListRow(_ReadModel):
    """One element of the register."""

    asset_id: str = Field(min_length=1, max_length=128)
    name: str | None = None
    serial_number: str | None = None
    asset_kind: AssetKind
    state: ActivityAssetRegisterState
    in_service_date: date
    method: AmortizationMethod
    revision_number: int = Field(ge=1)
    basis: PublicDecimal
    accumulated: PublicDecimal | None = None
    pending: PublicDecimal | None = None
    pending_applies: bool = True
    """False once a baja is recorded: ``pending`` stays the basis less the deductions, but none is left to amortize."""
    findings: ActivityAssetFindingCounts
    default_claim_year: int | None = None
    """The year a claim form opens on: the latest year up to the backend's current one that still has something to
    claim, else the earliest year that has; null when no year has a remainder."""
    years: tuple[int, ...] = ()
    """The tax years the element can be read in with an edition: its service window through the registry's last."""
    projected_years: tuple[int, ...] = ()
    """The later service years, whose figures are a projection until the registry publishes their edition."""
    disposal: ActivityAssetListDisposal | None = None
    """The recorded baja, or null while the element has none."""


class ActivityAssetCoveredInterval(_ReadModel):
    """A half-open interval of days, stated with the last day it covers for display.

    ``covered_until`` is the exclusive boundary the operations compute with, and
    ``covered_through`` is the day before it: the inclusive end a reader sees.
    """

    covered_from: date
    covered_until: date
    covered_through: date

    @model_validator(mode="after")
    def _through_is_the_day_before_the_boundary(self) -> Self:
        if self.covered_through != last_day_covered(self.covered_until):
            raise ValueError("covered_through is the day before covered_until")
        return self


class ActivityAssetPlanClaim(ActivityAssetCoveredInterval):
    """One claim of a year, effective or replaced."""

    claim_id: Hex64Str
    amount: PublicDecimal
    effective: bool
    superseded_by: Hex64Str | None = None
    revision_id: Hex64Str
    matches_current_schedule: bool
    """Whether the current revision and authority would stamp this claim's schedule fingerprint again."""
    stale_reason: ActivityAssetClaimStaleReason | None = None
    """Why it no longer does; null exactly when ``matches_current_schedule``."""

    @model_validator(mode="after")
    def _stale_exactly_when_it_no_longer_matches(self) -> Self:
        if self.matches_current_schedule != (self.stale_reason is None):
            raise ValueError("a claim names why it is stale exactly when it no longer matches its schedule")
        return self


class ActivityAssetClaimableInterval(ActivityAssetCoveredInterval):
    """A half-open interval a claim can still cover."""


class ActivityAssetEdition(_ReadModel):
    """The Modelo 100 edition a figure stands on.

    ``projected`` says the tax year has no edition of its own, so the rates come
    from the nearest authored one: they serve a forecast and not a filed Modelo 100.
    """

    revision_id: str = Field(min_length=1, max_length=256)
    authored_filing_year: int
    projected: bool


class ActivityAssetPlanRow(_ReadModel):
    """One tax year of an element's amortization plan."""

    tax_year: int
    method: AmortizationMethod
    coefficient: PublicDecimal | None = None
    planned: PublicDecimal | None = None
    absence: PlanFigureAbsence | None = None
    absence_reason_key: str | None = None
    absence_reason_facts: tuple[ActivityAssetReasonFact, ...] = ()
    absence_remedy_field_key: str | None = None
    """The catalogue word of the register field that supplies what the absence lacks, when entering it is the remedy."""
    applies: bool = True
    """Whether the year has something to work out: false for a known state of nothing to work out with no span open."""
    claimed: PublicDecimal
    claim_state: ActivityAssetClaimState
    claimable_intervals: tuple[ActivityAssetClaimableInterval, ...] = ()
    claimable_refusal_key: str | None = None
    claimable_refusal_facts: tuple[ActivityAssetReasonFact, ...] = ()
    claimable_refusal_remedy_field_key: str | None = None
    edition: ActivityAssetEdition | None = None
    service_days: int | None = None
    calendar_days: int | None = None
    claims: tuple[ActivityAssetPlanClaim, ...] = ()
    minimum_through: PublicDecimal | None = None
    """Minimum amortization from entry to this year's end, which reduces cost at a baja and not the value pending.

    Null while a year up to this one has no minimum authority: a partial sum would read as a figure.
    """
    minimum_reason_key: str | None = None
    """Why ``minimum_through`` is null."""
    minimum_complete: bool = True
    """False when a year up to this one has no minimum authority."""


class ActivityAssetPlanAdvisory(_ReadModel):
    """One non-blocking advisory on an element's plan, worded by its catalogue key."""

    kind: ActivityAssetPlanAdvisoryKind
    label_key: str


class ActivityAssetLegalCitation(_ReadModel):
    """One legal provision, cited from its own identifier, with its official link."""

    text: str
    permalink: str


class ActivityAssetElectionLimits(_ReadModel):
    """What the registry allows one element's election.

    A table method carries its class and corridor.  Any other names the limit it
    has instead, and says why through ``not_table_bound``.  ``legal_citations``
    are the provisions behind the registry parameters the figures rest on.
    """

    class_key: str | None = None
    class_label: str | None = None
    maximum_coefficient: PublicDecimal | None = None
    minimum_coefficient: PublicDecimal | None = None
    maximum_period_years: PublicDecimal | None = None
    maximum_period_ends_on: date | None = None
    """The first day after the maximum period, the boundary the schedule computes with."""
    maximum_period_last_day: date | None = None
    """The last day of the maximum period, the day a reader sees it end on."""
    legal_citations: tuple[ActivityAssetLegalCitation, ...] = ()
    legal_citations_complete: bool = True
    """False when a cited parameter or provision did not resolve, so ``legal_citations`` leaves it out."""
    not_table_bound: ActivityAssetNotTableBoundReason | None = None
    unavailable_reason_key: str | None = None
    unavailable_reason_facts: tuple[ActivityAssetReasonFact, ...] = ()


class ActivityAssetTimelineChange(_ReadModel):
    """One field a record changed, as display text."""

    field: str = Field(min_length=1, max_length=256)
    field_key: str | None = None
    """The catalogue key that words ``field``; null for a path no fact of the timeline has."""
    before: str | None = None
    after: str | None = None
    before_key: str | None = None
    after_key: str | None = None
    """The catalogue keys that word ``before`` and ``after`` when the field carries a token or a flag."""
    before_label: str | None = None
    after_label: str | None = None
    """The text that words ``before`` and ``after`` when the field carries a share or a table class.

    A share reads as a percentage and a class as the official name of its table class.  A class
    the pinned authority does not name has no label, and its key shows.
    """


class ActivityAssetTimelineClaimUse(_ReadModel):
    """What the rest of the profile makes of one claim."""

    used_by: tuple[str, ...]
    matches_current_schedule: bool
    stale_reason: ActivityAssetClaimStaleReason | None = None
    in_effect: bool = True
    """False for a claim a later one replaced; only a claim in effect can mismatch the schedule."""
    tax_year: int | None = None
    covered_from: date | None = None
    covered_through: date | None = None
    """The last day the claim covers."""


class ActivityAssetTimelineEventKind(StrEnum):
    """What a record did to the element, worded apart from the storage kind of the record."""

    CREATED = "created"
    CORRECTED = "corrected"
    BAJA_RECORDED = "baja_recorded"
    BAJA_CHANGED = "baja_changed"
    BAJA_REMOVED = "baja_removed"
    CLAIM_RECORDED = "claim_recorded"
    CLAIM_REPLACED = "claim_replaced"
    DESCRIBED = "described"


class ActivityAssetTimelineEvent(_ReadModel):
    """One record of an element's history, in history order."""

    sequence: int = Field(ge=1)
    recorded_at: datetime | None = None
    kind: ActivityAssetEventKind
    event_kind: ActivityAssetTimelineEventKind | None = None
    asset_id: str = Field(min_length=1, max_length=128)
    record_id: str = Field(min_length=1, max_length=128)
    effect_date: date | None = None
    """The day the record takes effect: entry into service for a creation or correction, the baja's date for a baja
    recorded, changed or removed, and the first day a claim covers."""
    origin: str | None = None
    changes: tuple[ActivityAssetTimelineChange, ...] = ()
    affects_calculation: bool
    claim: ActivityAssetTimelineClaimUse | None = None


class ActivityAssetDisposalFindingView(_ReadModel):
    """One non-blocking finding of a baja's calculation."""

    kind: ActivityAssetDisposalFindingKind
    label_key: str
    tax_year: int | None = None
    effect_on_cost: PublicDecimal | None = None


class ActivityAssetDisposalYearView(_ReadModel):
    """One service year's cumulative figures."""

    tax_year: int
    claims: PublicDecimal
    deducted_through: PublicDecimal
    minimum_through: PublicDecimal | None = None
    reduction_through: PublicDecimal


class ActivityAssetDisposalCalculationView(_ReadModel):
    """The figures of one baja; a withdrawal has no transmission value, costs or result."""

    disposal_date: date
    reason: ActivityAssetDisposalReason
    acquisition_value: PublicDecimal
    deducted: PublicDecimal
    minimum: PublicDecimal | None = None
    reduction: PublicDecimal
    excess: PublicDecimal
    net_value: PublicDecimal
    transmission_value: PublicDecimal | None = None
    transmission_costs: PublicDecimal | None = None
    result: PublicDecimal | None = None
    route_changed_by_later_affectation: bool
    years: tuple[ActivityAssetDisposalYearView, ...]
    findings: tuple[ActivityAssetDisposalFindingView, ...]


class ActivityAssetTableGroup(_ReadModel):
    """One amortization table class with its coefficient corridor."""

    class_key: str = Field(min_length=1, max_length=64)
    class_label: str = Field(min_length=1, max_length=256)
    maximum_coefficient: PublicDecimal
    minimum_coefficient: PublicDecimal
    maximum_period_years: PublicDecimal
    can_hold_vehicle: bool
    """Whether a material asset of this class can be a restricted vehicle, so the election is asked
    for a vehicle affectation declaration; the registry classifies each table class."""


class ActivityAssetMethodFact(_ReadModel):
    """One fact an election of a method states, typed by the election model itself.

    ``path`` runs from the election down to the fact.  ``kind`` says how it is stated.  A
    ``choice`` names the catalogue family of its words and lists its tokens; a ``class`` is
    chosen among the form options' table groups.  ``required`` means the election is refused
    without the fact, and ``required_with_group`` that it is refused when the fact's optional
    group is stated without it.
    """

    path: tuple[str, ...]
    kind: FactKind
    required: bool
    required_with_group: bool
    token_family: str | None = None
    tokens: tuple[str, ...] = ()


class ActivityAssetMethodFacts(_ReadModel):
    """The facts one offered method takes beyond its method and modality."""

    method: AmortizationMethod
    facts: tuple[ActivityAssetMethodFact, ...]


class ActivityAssetDisposalReasonOption(_ReadModel):
    """One reason a baja is accepted with, and the catalogue key that words it."""

    reason: ActivityAssetDisposalReason
    label_key: str


class ActivityAssetBasisStageOption(_ReadModel):
    """One stage a basis can be stated at, with the facts only that stage carries."""

    stage: AssetBasisStage
    facts: tuple[str, ...]
    """Names of the basis facts this stage states; the form carries these and no others of the stages."""
    is_property: bool
    """Whether the basis is the whole-property one, which flags the element as property."""


class ActivityAssetOpeningStatusOption(_ReadModel):
    """One status an opening history can have, with the facts it can state."""

    status: OpeningHistoryStatus
    facts: tuple[str, ...]


class ActivityAssetConditionOption(_ReadModel):
    """One condition an element can be acquired in, with the facts only that condition carries."""

    condition: AcquiredCondition
    facts: tuple[str, ...]
    """Names of the facts an element states only when acquired in this condition."""


class ActivityAssetFormOptionsView(_ReadModel):
    """What the registry admits for one asset kind and tax year."""

    tax_year: int
    asset_kind: AssetKind
    regime: DirectEstimationRegime
    edition: ActivityAssetEdition
    acquisition_shapes: tuple[AcquisitionShape, ...]
    declared_activities: tuple[TipoActividad, ...]
    methods: tuple[AmortizationMethod, ...]
    """Only the methods the registry admits and a form can state in full."""
    method_facts: tuple[ActivityAssetMethodFacts, ...]
    """The facts of each offered method, in the order of ``methods``."""
    table_groups: tuple[ActivityAssetTableGroup, ...]
    disposal_reasons: tuple[ActivityAssetDisposalReasonOption, ...]
    """The reasons a baja is accepted with, in the order the record's own check admits them."""
    basis_stages: tuple[ActivityAssetBasisStageOption, ...] = ()
    opening_statuses: tuple[ActivityAssetOpeningStatusOption, ...] = ()
    acquired_conditions: tuple[ActivityAssetConditionOption, ...] = ()
    further_acquisition_shapes: tuple[AcquisitionShape, ...] = ()
    """The shapes a later payment or cost of an element's acquisition takes, which no element is registered under."""
    m130_periods: tuple[str, ...] = ()
    """The Modelo 130 periods the registry serves for the tax year, as the handoff names them."""


class ActivityAssetAcquisitionCandidate(_ReadModel):
    """A ledger payment an element could name as its acquisition."""

    transaction_id: TransactionId
    booked_date: date
    description: str
    amount: PublicDecimal
    currency: str = Field(min_length=3, max_length=3)
    paid_in_euro: PublicDecimal | None = None
    taxable_base: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    non_deductible_iva_state: ActivityAssetNonDeductibleIvaState
    non_deductible_iva_state_key: str
    non_deductible_iva: PublicDecimal | None = None
    invoice_evidence_id: str | None = None
    evidence_fingerprint: Hex64Str | None = None


class ActivityAssetM130Contribution(_ReadModel):
    """One amount behind Modelo 130 casilla 02; exactly one of its two sources is set."""

    asset_id: str = Field(min_length=1, max_length=128)
    amount: PublicDecimal
    claim_id: Hex64Str | None = None
    schedule_fingerprint: Hex64Str | None = None


class ActivityAssetM130ProjectionSnapshot(_ReadModel):
    """The accrual of one asset kind for the Modelo 130 box its edition binds."""

    asset_kind: AssetKind
    """Which kind's accrual this row states; both kinds share the one box."""
    target_casilla_id: CasillaId
    box_name: str | None = None
    """The box in the filer's words with the asset kind, which tells the two kinds' rows apart."""
    tax_year: int
    amount: PublicDecimal
    contributions: tuple[ActivityAssetM130Contribution, ...] = ()
    unavailable_asset_ids: tuple[str, ...] = ()
    free_gap_asset_ids: tuple[str, ...] = ()
    agrarian_excluded_asset_ids: tuple[str, ...] = ()


__all__ = [
    "ACTIVITY_ASSET_LABEL_NAMESPACE",
    "DISPOSAL_FINDING_FAMILY",
    "NON_DEDUCTIBLE_IVA_STATE_FAMILY",
    "OPENING_REMEDY_FIELD",
    "OPENING_REMEDY_REASON_KEYS",
    "PLAN_ADVISORY_FAMILY",
    "TIMELINE_FIELD_FAMILY",
    "TIMELINE_FIELD_PATHS",
    "TIMELINE_INTERNAL_FIELDS",
    "TIMELINE_LABELLED_FIELDS",
    "TIMELINE_TOKEN_FAMILIES",
    "ActivityAssetAcquisitionCandidate",
    "ActivityAssetBasisStageOption",
    "ActivityAssetClaimStaleReason",
    "ActivityAssetClaimState",
    "ActivityAssetClaimableInterval",
    "ActivityAssetConditionOption",
    "ActivityAssetCoveredInterval",
    "ActivityAssetDisposalCalculationView",
    "ActivityAssetDisposalFindingView",
    "ActivityAssetDisposalReasonOption",
    "ActivityAssetDisposalYearView",
    "ActivityAssetEdition",
    "ActivityAssetElectionLimits",
    "ActivityAssetFindingCounts",
    "ActivityAssetFormOptionsView",
    "ActivityAssetListDisposal",
    "ActivityAssetListRow",
    "ActivityAssetM130Contribution",
    "ActivityAssetM130ProjectionSnapshot",
    "ActivityAssetMethodFact",
    "ActivityAssetMethodFacts",
    "ActivityAssetNonDeductibleIvaState",
    "ActivityAssetNotTableBoundReason",
    "ActivityAssetOpeningStatusOption",
    "ActivityAssetPlanAdvisory",
    "ActivityAssetPlanAdvisoryKind",
    "ActivityAssetPlanClaim",
    "ActivityAssetPlanRow",
    "ActivityAssetReasonFact",
    "ActivityAssetReasonFactKind",
    "ActivityAssetRegisterState",
    "ActivityAssetTableGroup",
    "ActivityAssetTimelineChange",
    "ActivityAssetTimelineClaimUse",
    "ActivityAssetTimelineEvent",
    "ActivityAssetTimelineEventKind",
    "activity_asset_label_key",
    "project_reason_facts",
    "reason_fact_kind",
    "reason_fact_text",
    "remedy_field_key",
    "timeline_field_key",
    "timeline_field_word_key",
    "timeline_token_key",
]
