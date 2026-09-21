"""Deterministic 2025 activity-asset amortization schedule contracts."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from .errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError, ActividadAssetValidationError
from .lifecycle import ActivityAssetRevision, AssetKind, OpeningHistoryStatus


class ScheduleAuthority(BaseModel):
    """The already-selected 2025 authority facts for one asset kind."""

    model_config = STRICT_FROZEN_CONFIG

    tax_year: int = Field(default=2025, ge=2025, le=2025)
    asset_kind: AssetKind
    annual_rate: Decimal
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=512)

    @field_validator("annual_rate")
    @classmethod
    def _require_rate_fraction(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or not Decimal("0") < value <= Decimal("1"):
            raise ValueError("annual_rate must be a finite Decimal in (0, 1]")
        return value

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

    @field_validator("amount")
    @classmethod
    def _require_cents_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0") or value != round_to_cents(value):
            raise ValueError("amount must be a non-negative Decimal rounded to euro cents")
        return value

    @model_validator(mode="after")
    def _validate_interval(self) -> ScheduledAmortizationCharge:
        if self.covered_until <= self.covered_from:
            raise ValueError("covered_until must be after covered_from")
        if self.calendar_days != calendar_days_in_tax_year(self.tax_year):
            raise ValueError("calendar_days must match the tax year's actual day count")
        return self


def schedule_charge(
    revision: ActivityAssetRevision,
    authority: ScheduleAuthority,
    *,
    covered_from: date,
    covered_until: date,
    accumulated_effective_claims: Decimal = Decimal("0"),
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
    )


def calendar_days_in_tax_year(tax_year: int) -> int:
    """Return the actual calendar-day denominator for a filing year."""
    return 366 if calendar.isleap(tax_year) else 365


__all__ = [
    "ScheduleAuthority",
    "ScheduledAmortizationCharge",
    "calendar_days_in_tax_year",
    "schedule_charge",
]
