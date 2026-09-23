"""Deterministic activity-asset amortization schedule contracts.

A :class:`ScheduleAuthority` is the registry-resolved form of one revision's
amortization election for one tax year.  :func:`schedule_charge` turns it into
a cents-emitted forecast for a half-open covered interval.  Every method
charges the amortizable basis (allocated basis less residual value, RIS art.
3.2), keeps intermediate arithmetic in exact ``Decimal`` and caps the emitted
charge at the remaining lawful basis.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from .election import FREE_AMOUNT_METHODS, AmortizationMethod, DigitOrder, LowValueElection
from .errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError, ActividadAssetValidationError
from .lifecycle import ActivityAssetRevision, AssetKind, OpeningHistoryStatus

_RATE_METHODS: frozenset[AmortizationMethod] = frozenset(
    {
        AmortizationMethod.LINEAR,
        AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE,
        AmortizationMethod.GOODWILL,
        AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING,
        AmortizationMethod.CONSTANT_PERCENTAGE,
    },
)
_FROM_START_METHODS: frozenset[AmortizationMethod] = frozenset(
    {AmortizationMethod.CONSTANT_PERCENTAGE, AmortizationMethod.SUM_OF_DIGITS},
)
_HEX64 = r"^[0-9a-f]{64}$"

type _Cumulative = Callable[[_ChargeContext, date], Decimal]
"""Exact method amortization from in-service up to a date."""


class AssetScheduleHistory(BaseModel):
    """Effective recorded history the schedule needs for one asset and tax year.

    Amounts are effective (non-superseded) claims.  Election fingerprints name
    the elections of the revisions those claims were recorded under, so a
    change of method can be judged without the schedule reading storage.
    """

    model_config = STRICT_FROZEN_CONFIG

    accumulated_before_tax_year: Decimal = Decimal("0")
    accumulated_in_tax_year: Decimal = Decimal("0")
    taxpayer_low_value_claimed_in_tax_year: Decimal = Decimal("0")
    election_fingerprints_before_tax_year: tuple[str, ...] = ()
    election_fingerprints_in_tax_year: tuple[str, ...] = ()

    @field_validator(
        "accumulated_before_tax_year",
        "accumulated_in_tax_year",
        "taxpayer_low_value_claimed_in_tax_year",
    )
    @classmethod
    def _require_finite_nonnegative(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0"):
            raise ValueError("accumulated claim amounts must be finite and non-negative")
        return value


class ScheduleAuthority(BaseModel):
    """Registry-selected facts that fix one asset's charge for one tax year."""

    model_config = STRICT_FROZEN_CONFIG

    tax_year: int = Field(ge=2025, le=2025)
    asset_kind: AssetKind
    method: AmortizationMethod
    election_fingerprint: str = Field(pattern=_HEX64)
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
    annual_rate: Decimal | None = None
    useful_life_ends_on: date | None = None
    sum_of_digits_period_years: int | None = Field(default=None, ge=1, le=100)
    digit_order: DigitOrder | None = None
    plan_annual_amount: Decimal | None = None
    plan_total: Decimal | None = None
    free_depreciation_unit_threshold: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None
    low_value: LowValueElection | None = None

    @field_validator("annual_rate")
    @classmethod
    def _require_rate_fraction(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or not Decimal("0") < value <= Decimal("1")):
            raise ValueError("annual_rate must be a finite Decimal in (0, 1]")
        return value

    @field_validator(
        "plan_annual_amount",
        "plan_total",
        "free_depreciation_unit_threshold",
        "free_depreciation_annual_cap",
    )
    @classmethod
    def _require_positive_cents_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value <= Decimal("0") or value != round_to_cents(value)):
            raise ValueError("schedule authority amounts must be positive Decimal amounts rounded to euro cents")
        return value

    @model_validator(mode="after")
    def _validate_method_shape(self) -> Self:
        method = self.method
        expected = {
            "annual_rate": method in _RATE_METHODS,
            "useful_life_ends_on": method
            in {AmortizationMethod.CONSTANT_PERCENTAGE, AmortizationMethod.INTANGIBLE_USEFUL_LIFE},
            "sum_of_digits_period_years": method is AmortizationMethod.SUM_OF_DIGITS,
            "digit_order": method is AmortizationMethod.SUM_OF_DIGITS,
            "plan_annual_amount": method is AmortizationMethod.APPROVED_PLAN,
            "plan_total": method is AmortizationMethod.APPROVED_PLAN,
            "free_depreciation_unit_threshold": method is AmortizationMethod.LOW_VALUE_FREE,
            "free_depreciation_annual_cap": method is AmortizationMethod.LOW_VALUE_FREE,
            "low_value": method is AmortizationMethod.LOW_VALUE_FREE,
        }
        for field_name, required in expected.items():
            present = getattr(self, field_name) is not None
            if present != required:
                state = "requires" if required else "cannot carry"
                raise ValueError(f"{method.value} schedule authority {state} {field_name}")
        if method is AmortizationMethod.LOW_VALUE_FREE and self.asset_kind is not AssetKind.MATERIAL:
            raise ValueError("low-value free depreciation is limited to material assets")
        return self

    @property
    def fingerprint(self) -> str:
        """Return a stable digest of the governing authority selection."""
        return content_hash_hex(self.model_dump(mode="json"))


class ScheduledAmortizationCharge(BaseModel):
    """A cents-emitted forecast for one half-open covered service interval."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: str = Field(pattern=_HEX64)
    tax_year: int = Field(ge=2025, le=2025)
    covered_from: date
    covered_until: date
    service_days: int = Field(ge=0)
    calendar_days: int = Field(ge=365, le=366)
    amount: Decimal
    schedule_fingerprint: str = Field(pattern=_HEX64)
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
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
    def _validate_interval(self) -> Self:
        if self.covered_until <= self.covered_from:
            raise ValueError("covered_until must be after covered_from")
        if self.calendar_days != calendar_days_in_tax_year(self.tax_year):
            raise ValueError("calendar_days must match the tax year's actual day count")
        low_value_facts = (
            self.free_depreciation_election_reference,
            self.free_depreciation_new_material_evidence_reference,
            self.free_depreciation_unit_acquisition_value,
            self.free_depreciation_annual_cap,
        )
        if self.method is AmortizationMethod.LOW_VALUE_FREE:
            if any(value is None for value in low_value_facts):
                raise ValueError("free-depreciation schedule requires election and annual-cap provenance")
        elif any(value is not None for value in low_value_facts):
            raise ValueError("only the low-value method carries free-depreciation election facts")
        return self


def schedule_charge(
    revision: ActivityAssetRevision,
    authority: ScheduleAuthority,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    """Forecast a filing-grade cents charge for a half-open covered interval."""
    if authority.asset_kind is not revision.asset_kind:
        raise ActividadAssetValidationError("schedule authority asset kind does not match asset revision")
    if authority.election_fingerprint != revision.amortization.fingerprint:
        raise ActividadAssetValidationError("schedule authority was resolved for a different amortization election")
    if revision.opening_history.status is OpeningHistoryStatus.MISSING:
        raise ActividadAssetIncompleteError("opening amortization history is missing")
    if covered_until <= covered_from:
        raise ActividadAssetValidationError("covered interval must be half-open and non-empty")
    require_method_continuity(authority.method, authority.election_fingerprint, history)
    require_opening_method(revision, authority.method)
    _require_free_amount_shape(authority.method, requested_free_amount)

    year_start = date(authority.tax_year, 1, 1)
    year_end = date(authority.tax_year + 1, 1, 1)
    if not year_start <= covered_from < covered_until <= year_end:
        raise ActividadAssetValidationError("covered interval must stay inside the authority's tax year")
    opening_amount = revision.opening_history.accumulated_amount
    if opening_amount is None:  # defensive: status validation proves unreachable
        raise ActividadAssetIncompleteError("known opening amortization history lacks an amount")
    amortizable_basis = revision.amortizable_basis()
    pending_at_year_start = amortizable_basis - opening_amount - history.accumulated_before_tax_year
    remaining_base = pending_at_year_start - history.accumulated_in_tax_year
    if remaining_base < Decimal("0"):
        raise ActividadAssetValidationError("opening and effective claims exceed the lawful amortizable basis")

    window_start = max(revision.in_service_date, year_start)
    window_end = min(revision.out_of_service_date or year_end, year_end, _amortization_end(revision, authority))
    interval_start = max(covered_from, window_start)
    interval_end = min(covered_until, window_end)
    if interval_end <= interval_start:
        raise ActividadAssetUnsupportedError("covered interval has no amortizable in-service days in the tax year")

    context = _ChargeContext(
        revision=revision,
        authority=authority,
        amortizable_basis=amortizable_basis,
        pending_at_year_start=pending_at_year_start,
        remaining_base=remaining_base,
        year_start=year_start,
        year_end=year_end,
        interval_start=interval_start,
        interval_end=interval_end,
    )
    amount = _method_amount(context, history=history, requested_free_amount=requested_free_amount)
    amount = min(amount, round_to_cents(remaining_base))
    schedule_fingerprint = content_hash_hex(
        {
            "asset_id": revision.asset_id,
            "asset_revision_id": revision.revision_id,
            "authority_fingerprint": authority.fingerprint,
            "tax_year": authority.tax_year,
            "amortizable_basis": str(amortizable_basis),
            "opening_amount": str(opening_amount),
            "method": authority.method.value,
        },
    )
    low_value = authority.low_value
    return ScheduledAmortizationCharge(
        asset_id=revision.asset_id,
        asset_revision_id=revision.revision_id,
        tax_year=authority.tax_year,
        covered_from=interval_start,
        covered_until=interval_end,
        service_days=(interval_end - interval_start).days,
        calendar_days=calendar_days_in_tax_year(authority.tax_year),
        amount=amount,
        schedule_fingerprint=schedule_fingerprint,
        authority_generation=authority.authority_generation,
        source_reference=authority.source_reference,
        method=authority.method,
        free_depreciation_election_reference=low_value.election_reference if low_value is not None else None,
        free_depreciation_new_material_evidence_reference=(
            low_value.new_material_evidence_reference if low_value is not None else None
        ),
        free_depreciation_unit_acquisition_value=low_value.unit_acquisition_value if low_value is not None else None,
        free_depreciation_annual_cap=authority.free_depreciation_annual_cap,
    )


@dataclass(frozen=True, slots=True)
class _ChargeContext:
    revision: ActivityAssetRevision
    authority: ScheduleAuthority
    amortizable_basis: Decimal
    pending_at_year_start: Decimal
    remaining_base: Decimal
    year_start: date
    year_end: date
    interval_start: date
    interval_end: date


def require_method_continuity(
    method: AmortizationMethod,
    election_fingerprint: str,
    history: AssetScheduleHistory,
) -> None:
    """Refuse a change of method inside a tax year or into a from-start method.

    Forecasts and the claim write both apply this one rule, so a claim can
    never be persisted under an election its forecast would have refused.
    """
    current = election_fingerprint
    if any(fingerprint != current for fingerprint in history.election_fingerprints_in_tax_year):
        raise ActividadAssetValidationError(
            "an asset's amortization election can change only at a tax-year boundary",
        )
    if method in _FROM_START_METHODS and any(
        fingerprint != current for fingerprint in history.election_fingerprints_before_tax_year
    ):
        raise ActividadAssetUnsupportedError(
            "constant percentage and sum of digits run from the start of amortization (RIS arts. 5.1 and 6.1); "
            "an asset already charged under another election cannot adopt them",
        )


def require_opening_method(revision: ActivityAssetRevision, method: AmortizationMethod) -> None:
    """Refuse a from-start method over an opening amount charged under another method.

    Constant percentage and sum of digits run from the start of amortization,
    so an amount amortized before onboarding counts only when it is attested
    to have been charged under the same method (RIS arts. 5.1 and 6.1).
    """
    opening = revision.opening_history
    if method not in _FROM_START_METHODS or not opening.accumulated_amount:
        return
    if opening.amortization_method is not method:
        raise ActividadAssetUnsupportedError(
            "a non-zero opening amount must attest the same from-start method before constant percentage or "
            "sum of digits can continue it (RIS arts. 5.1 and 6.1)",
        )


def _require_free_amount_shape(method: AmortizationMethod, requested_free_amount: Decimal | None) -> None:
    if method in FREE_AMOUNT_METHODS:
        if requested_free_amount is None:
            raise ActividadAssetIncompleteError("a free-depreciation method requires an elected amount")
        if (
            not requested_free_amount.is_finite()
            or requested_free_amount <= Decimal("0")
            or requested_free_amount != round_to_cents(requested_free_amount)
        ):
            raise ActividadAssetValidationError("elected free-depreciation amount must be positive euro cents")
    elif requested_free_amount is not None:
        raise ActividadAssetValidationError("only a free-depreciation method accepts an elected amount")


def _amortization_end(revision: ActivityAssetRevision, authority: ScheduleAuthority) -> date:
    """Return the first day after the method's useful life, or the far future."""
    if authority.method is AmortizationMethod.SUM_OF_DIGITS:
        period = authority.sum_of_digits_period_years
        if period is None:  # defensive: authority validation proves unreachable
            raise ActividadAssetValidationError("sum-of-digits authority lacks its period")
        return add_years(revision.in_service_date, period)
    if authority.useful_life_ends_on is not None:
        return authority.useful_life_ends_on
    return date.max


def _method_amount(
    context: _ChargeContext,
    *,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None,
) -> Decimal:
    method = context.authority.method
    if method in FREE_AMOUNT_METHODS:
        return _free_amount(context, history=history, requested_free_amount=requested_free_amount)
    if method is AmortizationMethod.CONSTANT_PERCENTAGE:
        return _constant_percentage_amount(context)
    if method is AmortizationMethod.SUM_OF_DIGITS:
        return _cumulative_difference(context, _sum_of_digits_cumulative)
    if method is AmortizationMethod.INTANGIBLE_USEFUL_LIFE:
        return _cumulative_difference(context, _useful_life_cumulative)
    if method is AmortizationMethod.APPROVED_PLAN:
        return _approved_plan_amount(context)
    if method in _RATE_METHODS:
        return _linear_amount(context)
    raise ActividadAssetUnsupportedError(f"{method.value} has no enrolled schedule arithmetic")


def _annual_rate(context: _ChargeContext) -> Decimal:
    rate = context.authority.annual_rate
    if rate is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError(f"{context.authority.method.value} authority lacks an annual rate")
    return rate


def _linear_amount(context: _ChargeContext) -> Decimal:
    """Apply the lifecycle rule: basis x rate x service days / tax-year days."""
    days = Decimal((context.interval_end - context.interval_start).days)
    year_days = Decimal(calendar_days_in_tax_year(context.authority.tax_year))
    return round_to_cents(context.amortizable_basis * _annual_rate(context) * days / year_days)


def _constant_percentage_amount(context: _ChargeContext) -> Decimal:
    """Apply RIS art. 5.1 to the value pending at the start of the tax year.

    In the tax year in which the useful life concludes, the whole pending
    value is spread over the days from the year's first in-service day to
    that conclusion, so the final period amortizes what remains.
    """
    life_end = context.authority.useful_life_ends_on
    if life_end is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError("constant-percentage authority lacks its useful-life conclusion")
    if life_end <= context.year_end:
        final_start = max(context.revision.in_service_date, context.year_start)
        final_days = Decimal((life_end - final_start).days)
        if final_days <= Decimal("0"):  # defensive: a non-empty interval proves a positive span
            raise ActividadAssetValidationError("final constant-percentage window has no days")

        def cumulative(point: date) -> Decimal:
            return context.pending_at_year_start * Decimal((point - final_start).days) / final_days

        # Rounding the cumulative curve, not each interval, lets contiguous
        # final-year claims reach exactly the pending value.
        return round_to_cents(cumulative(context.interval_end)) - round_to_cents(cumulative(context.interval_start))
    days = Decimal((context.interval_end - context.interval_start).days)
    year_days = Decimal(calendar_days_in_tax_year(context.authority.tax_year))
    return round_to_cents(context.pending_at_year_start * _annual_rate(context) * days / year_days)


def _approved_plan_amount(context: _ChargeContext) -> Decimal:
    """Spread the plan's approved annual amount over that year's service days."""
    plan_total = context.authority.plan_total
    annual_amount = context.authority.plan_annual_amount
    if plan_total is None or annual_amount is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError("approved-plan authority lacks its distribution")
    if plan_total > context.amortizable_basis:
        raise ActividadAssetValidationError("approved plan distributes more than the amortizable basis")
    window_start = max(context.revision.in_service_date, context.year_start)
    whole_days = Decimal((context.year_end - window_start).days)

    def cumulative(point: date) -> Decimal:
        return annual_amount * Decimal((point - window_start).days) / whole_days

    return round_to_cents(cumulative(context.interval_end)) - round_to_cents(cumulative(context.interval_start))


def _cumulative_difference(context: _ChargeContext, cumulative: _Cumulative) -> Decimal:
    """Emit the difference of rounded cumulative amortization at the interval ends.

    Rounding each endpoint of a lifetime cumulative curve, rather than each
    interval, makes contiguous claims telescope to exactly the amortizable
    basis at the end of the useful life.
    """
    end = round_to_cents(cumulative(context, context.interval_end))
    start = round_to_cents(cumulative(context, context.interval_start))
    return end - start


def _sum_of_digits_cumulative(context: _ChargeContext, point: date) -> Decimal:
    """Accumulate RIS art. 6 digit quotas over life years that start at in-service."""
    period = context.authority.sum_of_digits_period_years
    order = context.authority.digit_order
    if period is None or order is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError("sum-of-digits authority lacks its period or order")
    digit_sum = Decimal(period * (period + 1) // 2)
    in_service = context.revision.in_service_date
    total = Decimal("0")
    for life_year in range(1, period + 1):
        year_start = add_years(in_service, life_year - 1)
        if point <= year_start:
            break
        year_end = add_years(in_service, life_year)
        digit = period - life_year + 1 if order is DigitOrder.DESCENDING else life_year
        quota = context.amortizable_basis * Decimal(digit) / digit_sum
        elapsed = Decimal((min(point, year_end) - year_start).days)
        total += quota * elapsed / Decimal((year_end - year_start).days)
    return total


def _useful_life_cumulative(context: _ChargeContext, point: date) -> Decimal:
    """Accumulate a definite-life intangible straight-line by days."""
    life_end = context.authority.useful_life_ends_on
    if life_end is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError("definite-life authority lacks its useful-life end")
    in_service = context.revision.in_service_date
    life_days = Decimal((life_end - in_service).days)
    elapsed = Decimal((min(point, life_end) - in_service).days)
    return context.amortizable_basis * elapsed / life_days


def _free_amount(
    context: _ChargeContext,
    *,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None,
) -> Decimal:
    if requested_free_amount is None:  # defensive: shape validation proves unreachable
        raise ActividadAssetIncompleteError("a free-depreciation method requires an elected amount")
    if requested_free_amount > context.remaining_base:
        raise ActividadAssetValidationError("elected free depreciation exceeds the asset's remaining lawful basis")
    if context.authority.method is AmortizationMethod.LOW_VALUE_FREE:
        _require_low_value_election(context, history=history, requested_free_amount=requested_free_amount)
    return requested_free_amount


def _require_low_value_election(
    context: _ChargeContext,
    *,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal,
) -> None:
    """Validate the elected LIS art. 12.3.e branch without consuming its annual cap."""
    authority = context.authority
    election = authority.low_value
    threshold = authority.free_depreciation_unit_threshold
    annual_cap = authority.free_depreciation_annual_cap
    if election is None or threshold is None or annual_cap is None:  # defensive: authority validation proves this
        raise ActividadAssetValidationError("free-depreciation authority is incomplete")
    if context.revision.in_service_date.year != authority.tax_year:
        raise ActividadAssetUnsupportedError(
            "low-value free depreciation requires a new asset placed in service in tax year",
        )
    if election.unit_acquisition_value > threshold:
        raise ActividadAssetUnsupportedError("asset unit acquisition value exceeds the enrolled low-value threshold")
    if election.unit_acquisition_value < context.revision.basis.deductible_basis():
        raise ActividadAssetValidationError("free-depreciation unit value cannot be below the allocated asset basis")
    if history.taxpayer_low_value_claimed_in_tax_year + requested_free_amount > annual_cap:
        raise ActividadAssetUnsupportedError(
            "free-depreciation election exceeds the annual cap; submit an explicit compliant election amount",
        )


def add_years(start: date, years: int) -> date:
    """Return the same calendar day ``years`` later, folding 29 February to the 28th."""
    target_year = start.year + years
    day = min(start.day, calendar.monthrange(target_year, start.month)[1])
    return date(target_year, start.month, day)


def add_fractional_years(start: date, years: Decimal) -> date:
    """Return the instant a possibly fractional number of years after ``start``.

    Whole years advance by calendar anniversary; the fraction is that share of
    the following life year's days, rounded half-up to a whole day.
    """
    if not years.is_finite() or years <= Decimal("0"):
        raise ActividadAssetValidationError("a useful life must be a positive finite number of years")
    whole = int(years)
    anniversary = add_years(start, whole)
    following = add_years(start, whole + 1)
    fraction_days = ((years - Decimal(whole)) * Decimal((following - anniversary).days)).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return anniversary + timedelta(days=int(fraction_days))


def calendar_days_in_tax_year(tax_year: int) -> int:
    """Return the actual calendar-day denominator for a filing year."""
    return 366 if calendar.isleap(tax_year) else 365


__all__ = [
    "AssetScheduleHistory",
    "ScheduleAuthority",
    "ScheduledAmortizationCharge",
    "add_fractional_years",
    "add_years",
    "calendar_days_in_tax_year",
    "require_method_continuity",
    "require_opening_method",
    "schedule_charge",
]
