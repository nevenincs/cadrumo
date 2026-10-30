"""Closed read models of the activity-asset register, computed by the backend for every frontend.

A frontend displays these figures and does no arithmetic.  A null figure is unknown
and comes with its typed reason; a recorded zero is a zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.renta.actividad_asset.election import AmortizationMethod, DirectEstimationRegime
from ...domain.renta.actividad_asset.lifecycle import AssetKind
from ...domain.renta.actividad_asset.register_records import ActivityAssetEventKind
from ..operations.public_scalar import PublicDecimal
from .schedule_walk import PlanFigureAbsence


class ActivityAssetReasonFact(BaseModel):
    """One immutable fact used to render an activity-asset reason."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str
    value: str


def project_reason_facts(facts: Mapping[str, str]) -> tuple[ActivityAssetReasonFact, ...]:
    """Preserve every reason fact in deterministic key order."""
    return tuple(ActivityAssetReasonFact(key=key, value=value) for key, value in sorted(facts.items()))


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


class ActivityAssetClaimStaleReason(StrEnum):
    """Why a claim no longer matches the element's current schedule."""

    REVISION_CHANGED = "revision_changed"
    AUTHORITY_CHANGED = "authority_changed"
    SCHEDULE_UNAVAILABLE = "schedule_unavailable"


class ActivityAssetNonDeductibleIvaState(StrEnum):
    """Whether the ledger settles how much of a row's IVA is not deductible."""

    KNOWN = "known"
    UNKNOWN = "unknown"


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


class ActivityAssetPlanClaim(_ReadModel):
    """One claim of a year, effective or replaced."""

    claim_id: Hex64Str
    amount: PublicDecimal
    covered_from: date
    covered_until: date
    effective: bool
    superseded_by: Hex64Str | None = None
    revision_id: Hex64Str


class ActivityAssetClaimableInterval(_ReadModel):
    """A half-open interval a claim can still cover."""

    covered_from: date
    covered_until: date


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


class ActivityAssetTimelineChange(_ReadModel):
    """One field a record changed, as display text."""

    field: str = Field(min_length=1, max_length=256)
    before: str | None = None
    after: str | None = None


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


class ActivityAssetTableGroup(_ReadModel):
    """One amortization table class with its coefficient corridor."""

    class_key: str = Field(min_length=1, max_length=64)
    maximum_coefficient: PublicDecimal
    minimum_coefficient: PublicDecimal
    maximum_period_years: PublicDecimal


class ActivityAssetFormOptionsView(_ReadModel):
    """What the registry admits for one asset kind and tax year."""

    tax_year: int
    asset_kind: AssetKind
    regime: DirectEstimationRegime
    edition: ActivityAssetEdition
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
    "ActivityAssetAcquisitionCandidate",
    "ActivityAssetClaimStaleReason",
    "ActivityAssetClaimState",
    "ActivityAssetClaimableInterval",
    "ActivityAssetEdition",
    "ActivityAssetFindingCounts",
    "ActivityAssetFormOptionsView",
    "ActivityAssetListRow",
    "ActivityAssetM130Contribution",
    "ActivityAssetM130ProjectionSnapshot",
    "ActivityAssetNonDeductibleIvaState",
    "ActivityAssetPlanClaim",
    "ActivityAssetPlanRow",
    "ActivityAssetReasonFact",
    "ActivityAssetRegisterState",
    "ActivityAssetTableGroup",
    "ActivityAssetTimelineChange",
    "ActivityAssetTimelineClaimUse",
    "ActivityAssetTimelineEvent",
    "project_reason_facts",
]
