"""Deterministic 2025 activity-asset amortization schedule contracts."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from .errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError, ActividadAssetValidationError
from .lifecycle import ActivityAssetRevision, AssetKind, OpeningHistoryStatus


class AmortizationMethod(StrEnum):
    """The authority-backed method used for a single asset charge."""

    LINEAR = "linear"
    LOW_VALUE_FREE = "low_value_free"


class FreeDepreciationElection(BaseModel):
    """Explicit evidence and requested amount for the low-value election.

    The annual ceiling is a taxpayer-period resource.  A caller must therefore
    state the amount it elects to claim; the scheduler never silently grants a
    residual cap amount according to request order.
    """

    model_config = STRICT_FROZEN_CONFIG

    election_reference: str = Field(min_length=1, max_length=256)
    new_material_evidence_reference: str = Field(min_length=1, max_length=512)
    unit_acquisition_value: Decimal
    requested_amount: Decimal

    @field_validator("unit_acquisition_value", "requested_amount")
    @classmethod
    def _require_positive_cents(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= Decimal("0") or value != round_to_cents(value):
            raise ValueError("free-depreciation values must be positive Decimal amounts rounded to euro cents")
        return value


class ScheduleAuthority(BaseModel):
    """The already-selected 2025 authority facts for one asset kind."""

    model_config = STRICT_FROZEN_CONFIG

    tax_year: int = Field(default=2025, ge=2025, le=2025)
    asset_kind: AssetKind
    annual_rate: Decimal | None = None
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=512)
    method: AmortizationMethod = AmortizationMethod.LINEAR
    free_depreciation_unit_threshold: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None
    free_depreciation_election: FreeDepreciationElection | None = None

    @field_validator("annual_rate")
    @classmethod
    def _require_rate_fraction(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or not Decimal("0") < value <= Decimal("1")):
            raise ValueError("annual_rate must be a finite Decimal in (0, 1]")
        return value

    @field_validator("free_depreciation_unit_threshold", "free_depreciation_annual_cap")
    @classmethod
    def _require_positive_cents_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value <= Decimal("0") or value != round_to_cents(value)):
            raise ValueError(
                "free-depreciation authority amounts must be positive Decimal amounts rounded to euro cents",
            )
        return value

    @model_validator(mode="after")
    def _validate_method_shape(self) -> ScheduleAuthority:
        free_fields = (
            self.free_depreciation_unit_threshold,
            self.free_depreciation_annual_cap,
            self.free_depreciation_election,
        )
        if self.method is AmortizationMethod.LOW_VALUE_FREE:
            if self.asset_kind is not AssetKind.MATERIAL:
                raise ValueError("low-value free depreciation is limited to material assets")
            if any(value is None for value in free_fields):
                raise ValueError("low-value free depreciation requires threshold, annual cap, and explicit election")
            if self.annual_rate is not None:
                raise ValueError("low-value free depreciation cannot carry a linear annual_rate")
        else:
            if self.annual_rate is None:
                raise ValueError("linear schedule authority requires annual_rate")
            if any(value is not None for value in free_fields):
                raise ValueError("linear schedule authority cannot carry free-depreciation facts")
        return self

    @property
    def fingerprint(self) -> str:
        """Return a stable digest of the governing authority selection."""
        return content_hash_hex(self.model_dump(mode="json"))


class ScheduledAmortizationCharge(BaseModel):
    """A cents-emitted forecast for one half-open covered service interval."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    tax_year: int = Field(ge=2025, le=2025)
    covered_from: date
    covered_until: date
    service_days: int = Field(ge=0)
    calendar_days: int = Field(ge=365, le=366)
    amount: Decimal
    schedule_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=512)
    method: AmortizationMethod = AmortizationMethod.LINEAR
    free_depreciation_election_reference: str | None = Field(default=None, min_length=1, max_length=256)
    free_depreciation_new_material_evidence_reference: str | None = Field(default=None, min_length=1, max_length=512)
    free_depreciation_unit_acquisition_value: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None

    @field_validator("amount")
    @classmethod
    def _require_cents_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0") or value != round_to_cents(value):
            raise ValueError("amount must be a non-negative Decimal rounded to euro cents")
        return value

    @field_validator("free_depreciation_unit_acquisition_value", "free_depreciation_annual_cap")
    @classmethod
    def _require_optional_positive_cents_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value <= Decimal("0") or value != round_to_cents(value)):
            raise ValueError(
                "free-depreciation schedule amounts must be positive Decimal amounts rounded to euro cents",
            )
        return value

    @model_validator(mode="after")
    def _validate_interval(self) -> ScheduledAmortizationCharge:
        if self.covered_until <= self.covered_from:
            raise ValueError("covered_until must be after covered_from")
        if self.calendar_days != calendar_days_in_tax_year(self.tax_year):
            raise ValueError("calendar_days must match the tax year's actual day count")
        if self.method is AmortizationMethod.LOW_VALUE_FREE:
            if (
                self.free_depreciation_election_reference is None
                or self.free_depreciation_new_material_evidence_reference is None
                or self.free_depreciation_unit_acquisition_value is None
                or self.free_depreciation_annual_cap is None
            ):
                raise ValueError("free-depreciation schedule requires election and annual-cap provenance")
        elif any(
            value is not None
            for value in (
                self.free_depreciation_election_reference,
                self.free_depreciation_new_material_evidence_reference,
                self.free_depreciation_unit_acquisition_value,
                self.free_depreciation_annual_cap,
            )
        ):
            raise ValueError("linear schedule cannot carry free-depreciation claim facts")
        return self


def schedule_charge(
    revision: ActivityAssetRevision,
    authority: ScheduleAuthority,
    *,
    covered_from: date,
    covered_until: date,
    accumulated_effective_claims: Decimal = Decimal("0"),
    accumulated_effective_free_depreciation_claims: Decimal = Decimal("0"),
) -> ScheduledAmortizationCharge:
    """Forecast a filing-grade cents charge for a half-open service interval.

    Intermediate rate and day-ratio arithmetic deliberately remains exact
    ``Decimal``.  Rounding occurs at the emitted charge boundary only; then the
    result is capped to the available lawful basis, which is also emitted in
    canonical cents.
    """
    if authority.asset_kind is not revision.asset_kind:
        raise ActividadAssetValidationError("schedule authority asset kind does not match asset revision")
    if revision.opening_history.status is OpeningHistoryStatus.MISSING:
        raise ActividadAssetIncompleteError("opening amortization history is missing")
    if not accumulated_effective_claims.is_finite() or accumulated_effective_claims < Decimal("0"):
        raise ActividadAssetValidationError("accumulated_effective_claims must be finite and non-negative")
    if (
        not accumulated_effective_free_depreciation_claims.is_finite()
        or accumulated_effective_free_depreciation_claims < Decimal("0")
    ):
        raise ActividadAssetValidationError("accumulated free-depreciation claims must be finite and non-negative")
    if covered_until <= covered_from:
        raise ActividadAssetValidationError("covered interval must be half-open and non-empty")

    year_start = date(authority.tax_year, 1, 1)
    year_end = date(authority.tax_year + 1, 1, 1)
    service_start = max(revision.in_service_date, year_start)
    service_end = min(revision.out_of_service_date or year_end, year_end)
    interval_start = max(covered_from, service_start)
    interval_end = min(covered_until, service_end)
    if interval_end <= interval_start:
        raise ActividadAssetUnsupportedError("covered interval has no in-service days in the selected tax year")

    opening_amount = revision.opening_history.accumulated_amount
    if opening_amount is None:  # defensive: status validation proves unreachable
        raise ActividadAssetIncompleteError("known opening amortization history lacks an amount")
    allocated_basis = revision.basis.deductible_basis()
    remaining_base = allocated_basis - revision.residual_value - opening_amount - accumulated_effective_claims
    if remaining_base < Decimal("0"):
        raise ActividadAssetValidationError("opening and effective claims exceed the lawful allocated basis")
    calendar_days = calendar_days_in_tax_year(authority.tax_year)
    service_days = (interval_end - interval_start).days
    if authority.method is AmortizationMethod.LOW_VALUE_FREE:
        amount = _schedule_free_depreciation_charge(
            revision,
            authority,
            remaining_base=remaining_base,
            accumulated_effective_free_depreciation_claims=accumulated_effective_free_depreciation_claims,
        )
    else:
        if authority.annual_rate is None:  # defensive: authority validation proves unreachable
            raise ActividadAssetValidationError("linear schedule authority lacks annual rate")
        unrounded_amount = allocated_basis * authority.annual_rate * Decimal(service_days) / Decimal(calendar_days)
        amount = min(round_to_cents(unrounded_amount), round_to_cents(remaining_base))
    schedule_fingerprint = content_hash_hex(
        {
            "asset_id": revision.asset_id,
            "asset_revision_id": revision.revision_id,
            "authority_fingerprint": authority.fingerprint,
            "tax_year": authority.tax_year,
            "allocated_basis": str(allocated_basis),
            "residual_value": str(revision.residual_value),
            "opening_amount": str(opening_amount),
            "method": authority.method.value,
        },
    )
    return ScheduledAmortizationCharge(
        asset_id=revision.asset_id,
        asset_revision_id=revision.revision_id,
        tax_year=authority.tax_year,
        covered_from=interval_start,
        covered_until=interval_end,
        service_days=service_days,
        calendar_days=calendar_days,
        amount=amount,
        schedule_fingerprint=schedule_fingerprint,
        authority_generation=authority.authority_generation,
        source_reference=authority.source_reference,
        method=authority.method,
        free_depreciation_election_reference=(
            authority.free_depreciation_election.election_reference
            if authority.free_depreciation_election is not None
            else None
        ),
        free_depreciation_new_material_evidence_reference=(
            authority.free_depreciation_election.new_material_evidence_reference
            if authority.free_depreciation_election is not None
            else None
        ),
        free_depreciation_unit_acquisition_value=(
            authority.free_depreciation_election.unit_acquisition_value
            if authority.free_depreciation_election is not None
            else None
        ),
        free_depreciation_annual_cap=authority.free_depreciation_annual_cap,
    )


def _schedule_free_depreciation_charge(
    revision: ActivityAssetRevision,
    authority: ScheduleAuthority,
    *,
    remaining_base: Decimal,
    accumulated_effective_free_depreciation_claims: Decimal,
) -> Decimal:
    """Validate the elected low-value branch without consuming its annual cap."""
    election = authority.free_depreciation_election
    threshold = authority.free_depreciation_unit_threshold
    annual_cap = authority.free_depreciation_annual_cap
    if election is None or threshold is None or annual_cap is None:  # defensive: authority validation proves this
        raise ActividadAssetValidationError("free-depreciation authority is incomplete")
    if revision.asset_kind is not AssetKind.MATERIAL:
        raise ActividadAssetUnsupportedError("low-value free depreciation supports only material assets")
    if revision.in_service_date.year != authority.tax_year:
        raise ActividadAssetUnsupportedError(
            "low-value free depreciation requires a new asset placed in service in tax year",
        )
    if election.unit_acquisition_value > threshold:
        raise ActividadAssetUnsupportedError("asset unit acquisition value exceeds the enrolled low-value threshold")
    if election.unit_acquisition_value < revision.basis.deductible_basis():
        raise ActividadAssetValidationError("free-depreciation unit value cannot be below the allocated asset basis")
    if election.requested_amount > remaining_base:
        raise ActividadAssetValidationError("free-depreciation election exceeds the asset's remaining lawful basis")
    if accumulated_effective_free_depreciation_claims + election.requested_amount > annual_cap:
        raise ActividadAssetUnsupportedError(
            "free-depreciation election exceeds the annual cap; submit an explicit compliant election amount",
        )
    return election.requested_amount


def calendar_days_in_tax_year(tax_year: int) -> int:
    """Return the actual calendar-day denominator for a filing year."""
    return 366 if calendar.isleap(tax_year) else 365


__all__ = [
    "AmortizationMethod",
    "FreeDepreciationElection",
    "ScheduleAuthority",
    "ScheduledAmortizationCharge",
    "calendar_days_in_tax_year",
    "schedule_charge",
]
