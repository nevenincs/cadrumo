"""Closed read models of the activity-asset register, computed by the backend for every frontend.

A frontend displays these figures and does no arithmetic.  A null figure is unknown
and comes with its typed reason; a recorded zero is a zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import StrEnum
from typing import Final, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.renta.actividad_asset.claims import last_day_covered
from ...domain.renta.actividad_asset.disposal import ActivityAssetDisposalFindingKind, ActivityAssetDisposalReason
from ...domain.renta.actividad_asset.election import AmortizationMethod, DirectEstimationRegime
from ...domain.renta.actividad_asset.fact_leaves import FactKind, indexed_to_step_path
from ...domain.renta.actividad_asset.lifecycle import AcquisitionShape, AssetKind
from ...domain.renta.actividad_asset.register_records import ActivityAssetEventKind
from ..operations.public_scalar import PublicDecimal
from .fact_wording import timeline_labelled_fields, timeline_token_families
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


def activity_asset_label_key(family: str, token: StrEnum) -> str:
    """Name the catalogue key that words one token of a family."""
    return f"{ACTIVITY_ASSET_LABEL_NAMESPACE}{family}.{token.value}"


def timeline_token_key(field: str, value: str | None) -> str | None:
    """Name the catalogue key of a timeline value, or ``None`` when the field carries no token or is unset."""
    family = TIMELINE_TOKEN_FAMILIES.get(indexed_to_step_path(field))
    if family is None or value is None:
        return None
    name, enum = family
    return activity_asset_label_key(name, enum(value))


class ActivityAssetReasonFact(BaseModel):
    """One immutable fact used to render an activity-asset reason."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str = Field(min_length=1, max_length=_REASON_FACT_KEY_LIMIT)
    value: str = Field(max_length=_REASON_FACT_VALUE_LIMIT)


def project_reason_facts(facts: Mapping[str, str]) -> tuple[ActivityAssetReasonFact, ...]:
    """Preserve every reason fact in deterministic key order."""
    return tuple(
        ActivityAssetReasonFact(key=key[:_REASON_FACT_KEY_LIMIT], value=value[:_REASON_FACT_VALUE_LIMIT])
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
    stale: int = Field(ge=0)


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
    findings: ActivityAssetFindingCounts
    years: tuple[int, ...] = ()
    """The tax years the element can be read in with an edition: its service window through the registry's last."""
    projected_years: tuple[int, ...] = ()
    """The later service years, whose figures are a projection until the registry publishes their edition."""


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
    claimed: PublicDecimal
    claim_state: ActivityAssetClaimState
    claimable_intervals: tuple[ActivityAssetClaimableInterval, ...] = ()
    claimable_refusal_key: str | None = None
    edition: ActivityAssetEdition | None = None
    service_days: int | None = None
    calendar_days: int | None = None
    claims: tuple[ActivityAssetPlanClaim, ...] = ()
    minimum_through: PublicDecimal | None = None
    """Minimum amortization from entry to this year's end, which reduces cost at a baja and not the value pending."""
    minimum_complete: bool = True
    """False when a year up to this one has no minimum authority, so ``minimum_through`` leaves it out."""


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
    legal_citations: tuple[ActivityAssetLegalCitation, ...] = ()
    legal_citations_complete: bool = True
    """False when a cited parameter or provision did not resolve, so ``legal_citations`` leaves it out."""
    not_table_bound: ActivityAssetNotTableBoundReason | None = None
    unavailable_reason_key: str | None = None


class ActivityAssetTimelineChange(_ReadModel):
    """One field a record changed, as display text."""

    field: str = Field(min_length=1, max_length=256)
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


class ActivityAssetTimelineEvent(_ReadModel):
    """One record of an element's history, in history order."""

    sequence: int = Field(ge=1)
    recorded_at: datetime | None = None
    kind: ActivityAssetEventKind
    asset_id: str = Field(min_length=1, max_length=128)
    record_id: str = Field(min_length=1, max_length=128)
    effect_date: date | None = None
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


class ActivityAssetFormOptionsView(_ReadModel):
    """What the registry admits for one asset kind and tax year."""

    tax_year: int
    asset_kind: AssetKind
    regime: DirectEstimationRegime
    edition: ActivityAssetEdition
    acquisition_shapes: tuple[AcquisitionShape, ...]
    methods: tuple[AmortizationMethod, ...]
    table_groups: tuple[ActivityAssetTableGroup, ...]


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
    """The accrual of one asset kind for Modelo 130 casilla 02."""

    target_casilla_id: Literal["02"] = "02"
    tax_year: int
    amount: PublicDecimal
    contributions: tuple[ActivityAssetM130Contribution, ...] = ()
    unavailable_asset_ids: tuple[str, ...] = ()


__all__ = [
    "ACTIVITY_ASSET_LABEL_NAMESPACE",
    "DISPOSAL_FINDING_FAMILY",
    "NON_DEDUCTIBLE_IVA_STATE_FAMILY",
    "PLAN_ADVISORY_FAMILY",
    "TIMELINE_LABELLED_FIELDS",
    "TIMELINE_TOKEN_FAMILIES",
    "ActivityAssetAcquisitionCandidate",
    "ActivityAssetClaimStaleReason",
    "ActivityAssetClaimState",
    "ActivityAssetClaimableInterval",
    "ActivityAssetCoveredInterval",
    "ActivityAssetDisposalCalculationView",
    "ActivityAssetDisposalFindingView",
    "ActivityAssetDisposalYearView",
    "ActivityAssetEdition",
    "ActivityAssetElectionLimits",
    "ActivityAssetFindingCounts",
    "ActivityAssetFormOptionsView",
    "ActivityAssetListRow",
    "ActivityAssetM130Contribution",
    "ActivityAssetM130ProjectionSnapshot",
    "ActivityAssetNonDeductibleIvaState",
    "ActivityAssetNotTableBoundReason",
    "ActivityAssetPlanAdvisory",
    "ActivityAssetPlanAdvisoryKind",
    "ActivityAssetPlanClaim",
    "ActivityAssetPlanRow",
    "ActivityAssetReasonFact",
    "ActivityAssetRegisterState",
    "ActivityAssetTableGroup",
    "ActivityAssetTimelineChange",
    "ActivityAssetTimelineClaimUse",
    "ActivityAssetTimelineEvent",
    "activity_asset_label_key",
    "project_reason_facts",
    "timeline_token_key",
]
