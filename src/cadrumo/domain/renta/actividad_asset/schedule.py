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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Self, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex
from ....core.hex import Hex64Str
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from .election import (
    FREE_AMOUNT_METHODS,
    WORKFORCE_CONDITIONED_METHODS,
    AcquiredCondition,
    AmortizationMethod,
    DigitOrder,
    ElectionReference,
    EvidenceReference,
    LowValueElection,
    require_euro_cents,
    require_free_depreciation_facts,
)
from .errors import (
    ActividadAssetIncompleteError,
    ActividadAssetPeriodElapsedError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
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

type _Cumulative = Callable[[_ChargeContext, date], Decimal]
"""Exact method amortization from in-service up to a date."""


class AssetScheduleHistory(BaseModel):
    """Effective recorded history the schedule needs for one asset and tax year.

    Amounts are effective (non-superseded) claims.  Election fingerprints name
    the elections of the revisions those claims were recorded under, so a
    change of method can be judged without the schedule reading storage.
    ``same_incentive_investment_of_other_assets`` is the investment every
    other asset's current revision places under the same workforce-conditioned
    incentive and entry year, which shares one investment cap with this asset.
    ``accumulated_after_tax_year`` is what later years have already claimed: it
    leaves this year's charge unchanged except by capping it at the lawful basis.
    """

    model_config = STRICT_FROZEN_CONFIG

    accumulated_before_tax_year: Decimal = Decimal("0")
    accumulated_in_tax_year: Decimal = Decimal("0")
    accumulated_after_tax_year: Decimal = Decimal("0")
    taxpayer_low_value_claimed_in_tax_year: Decimal = Decimal("0")
    same_incentive_investment_of_other_assets: Decimal = Decimal("0")
    election_fingerprints_before_tax_year: tuple[str, ...] = ()
    election_fingerprints_in_tax_year: tuple[str, ...] = ()

    @field_validator(
        "accumulated_before_tax_year",
        "accumulated_in_tax_year",
        "accumulated_after_tax_year",
        "taxpayer_low_value_claimed_in_tax_year",
        "same_incentive_investment_of_other_assets",
    )
    @classmethod
    def _require_finite_nonnegative(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0"):
            raise ValueError("accumulated claim amounts must be finite and non-negative")
        return value


class ScheduleAuthority(BaseModel):
    """Registry-selected facts that fix one asset's charge for one tax year."""

    model_config = STRICT_FROZEN_CONFIG

    tax_year: FilingYear
    asset_kind: AssetKind
    method: AmortizationMethod
    election_fingerprint: Hex64Str
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
    annual_rate: Decimal | None = None
    useful_life_ends_on: date | None = None
    maximum_period_ends_on: date | None = None
    sum_of_digits_period_years: int | None = Field(default=None, ge=1, le=100)
    digit_order: DigitOrder | None = None
    plan_annual_amount: Decimal | None = None
    plan_total: Decimal | None = None
    free_depreciation_unit_threshold: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None
    free_depreciation_investment_cap: Decimal | None = None
    low_value: LowValueElection | None = None
    original_price_basis: Decimal | None = None
    """The allocated originating price a used element's rate applies to instead of its own basis."""

    @field_validator("original_price_basis")
    @classmethod
    def _require_positive_original_price_basis(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value <= Decimal("0")):
            raise ValueError("original_price_basis must be a finite positive Decimal")
        return value

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
        "free_depreciation_investment_cap",
    )
    @classmethod
    def _require_positive_cents_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        return require_euro_cents(value, allow_zero=False, label="schedule authority amount")

    @model_validator(mode="after")
    def _validate_method_shape(self) -> Self:
        method = self.method
        expected = {
            "annual_rate": method in _RATE_METHODS,
            "useful_life_ends_on": method
            in {AmortizationMethod.CONSTANT_PERCENTAGE, AmortizationMethod.INTANGIBLE_USEFUL_LIFE},
            "maximum_period_ends_on": method
            in {AmortizationMethod.LINEAR, AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING},
            "sum_of_digits_period_years": method is AmortizationMethod.SUM_OF_DIGITS,
            "digit_order": method is AmortizationMethod.SUM_OF_DIGITS,
            "plan_annual_amount": method is AmortizationMethod.APPROVED_PLAN,
            "plan_total": method is AmortizationMethod.APPROVED_PLAN,
            "free_depreciation_unit_threshold": method is AmortizationMethod.LOW_VALUE_FREE,
            "free_depreciation_annual_cap": method is AmortizationMethod.LOW_VALUE_FREE,
            "free_depreciation_investment_cap": method in WORKFORCE_CONDITIONED_METHODS,
            "low_value": method is AmortizationMethod.LOW_VALUE_FREE,
        }
        for field_name, required in expected.items():
            present = getattr(self, field_name) is not None
            if present != required:
                state = "requires" if required else "cannot carry"
                raise ValueError(f"{method.value} schedule authority {state} {field_name}")
        if self.original_price_basis is not None and method is not AmortizationMethod.LINEAR:
            raise ValueError(f"{method.value} schedule authority cannot carry original_price_basis")
        if method is AmortizationMethod.LOW_VALUE_FREE and self.asset_kind is not AssetKind.MATERIAL:
            raise ValueError("low-value free depreciation is limited to material assets")
        return self

    @property
    def fingerprint(self) -> str:
        """Return a digest of what the law resolves to for this election and tax year.

        The generation and the source references say where those facts came from.
        A new publication that resolves to the same facts charges the same amounts,
        so neither takes part, and a figure's scale does not either.
        """
        facts = self.model_dump(mode="python", exclude={"authority_generation", "source_reference"}, exclude_none=True)
        return content_hash_hex(_canonical_facts(facts))


class ScheduledAmortizationCharge(BaseModel):
    """A cents-emitted forecast for one half-open covered service interval."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: Hex64Str
    tax_year: FilingYear
    covered_from: date
    covered_until: date
    service_days: int = Field(ge=0)
    calendar_days: int = Field(ge=365, le=366)
    amount: Decimal
    schedule_fingerprint: Hex64Str
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
    method: AmortizationMethod = AmortizationMethod.LINEAR
    annual_rate: Decimal | None = None
    free_depreciation_election_reference: ElectionReference | None = None
    free_depreciation_new_material_evidence_reference: EvidenceReference | None = None
    free_depreciation_unit_acquisition_value: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None

    @field_validator("amount")
    @classmethod
    def _require_cents_amount(cls, value: Decimal) -> Decimal:
        return require_euro_cents(value, allow_zero=True)

    @field_validator("free_depreciation_unit_acquisition_value", "free_depreciation_annual_cap")
    @classmethod
    def _require_optional_positive_cents_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        return require_euro_cents(value, allow_zero=False, label="free-depreciation schedule amount")

    @model_validator(mode="after")
    def _validate_interval(self) -> Self:
        if self.covered_until <= self.covered_from:
            raise ValueError("covered_until must be after covered_from")
        if self.calendar_days != calendar_days_in_tax_year(self.tax_year):
            raise ValueError("calendar_days must match the tax year's actual day count")
        require_free_depreciation_facts(
            self.method,
            (
                self.free_depreciation_election_reference,
                self.free_depreciation_new_material_evidence_reference,
                self.free_depreciation_unit_acquisition_value,
                self.free_depreciation_annual_cap,
            ),
            subject="schedule",
        )
        return self


def _canonical_amount(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _canonical_facts(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(name): _canonical_facts(item) for name, item in cast("Mapping[object, object]", value).items()}
    if isinstance(value, Decimal):
        return _canonical_amount(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value


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
    _validate_charge_scope(
        revision,
        authority,
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )
    year_start = date(authority.tax_year, 1, 1)
    year_end = date(authority.tax_year + 1, 1, 1)
    opening_amount, amortizable_basis, pending_at_year_start, remaining_base = _charge_bases(revision, history)
    interval_start, interval_end = _charge_interval(
        revision,
        authority,
        covered_from=covered_from,
        covered_until=covered_until,
        year_start=year_start,
        year_end=year_end,
    )

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
    method_amount = _method_amount(context, history=history, requested_free_amount=requested_free_amount)
    amount_limit = round_to_cents(remaining_base)
    amount = min(method_amount, amount_limit)
    low_value = authority.low_value
    schedule_fingerprint = _charge_fingerprint(
        context,
        opening_amount=opening_amount,
        capped_at=amount_limit if method_amount > amount_limit else None,
    )
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
        annual_rate=authority.annual_rate,
        free_depreciation_election_reference=low_value.election_reference if low_value is not None else None,
        free_depreciation_new_material_evidence_reference=(
            low_value.new_material_evidence_reference if low_value is not None else None
        ),
        free_depreciation_unit_acquisition_value=(revision.basis.acquisition_cost() if low_value is not None else None),
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


def _charge_fingerprint(
    context: _ChargeContext,
    *,
    opening_amount: Decimal,
    capped_at: Decimal | None,
) -> str:
    """Hash exactly what this charge's amount rests on, so equal digests mean equal figures.

    The revision's identity stays out, because a revision that changes none of these
    facts changes no charge.  What earlier years consumed takes part only where it
    moves the figure: the pending value a constant percentage runs on, and the limit
    of a charge that reached the remaining basis.  A claim's identity carries this
    digest and its own revision, so it remains exact.
    """
    authority = context.authority
    facts: dict[str, str] = {
        "asset_id": context.revision.asset_id,
        "authority": authority.fingerprint,
        "in_service_date": context.revision.in_service_date.isoformat(),
        "covered_from": context.interval_start.isoformat(),
        "covered_until": context.interval_end.isoformat(),
        "amortizable_basis": _canonical_amount(context.amortizable_basis),
        "opening_amount": _canonical_amount(opening_amount),
    }
    if authority.method is AmortizationMethod.CONSTANT_PERCENTAGE:
        facts["pending_at_year_start"] = _canonical_amount(context.pending_at_year_start)
    if capped_at is not None:
        facts["capped_at"] = _canonical_amount(capped_at)
    if authority.low_value is not None:
        facts["unit_acquisition_value"] = _canonical_amount(context.revision.basis.acquisition_cost())
    return content_hash_hex(facts)


def _validate_charge_scope(
    revision: ActivityAssetRevision,
    authority: ScheduleAuthority,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None,
) -> None:
    if authority.asset_kind is not revision.asset_kind:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.schedule_authority_kind_mismatch"
        )
    if authority.election_fingerprint != revision.amortization.fingerprint:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.schedule_authority_election_mismatch"
        )
    if revision.opening_history.status is OpeningHistoryStatus.MISSING:
        raise ActividadAssetIncompleteError(translated_message="ledger.actividad_asset.errors.opening_history_missing")
    if covered_until <= covered_from:
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.covered_interval_empty")
    require_method_continuity(authority.method, authority.election_fingerprint, history)
    require_opening_method(revision, authority.method)
    _require_free_amount_shape(authority.method, requested_free_amount)
    year_start = date(authority.tax_year, 1, 1)
    year_end = date(authority.tax_year + 1, 1, 1)
    if not year_start <= covered_from < covered_until <= year_end:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.covered_interval_outside_tax_year"
        )


def _charge_bases(
    revision: ActivityAssetRevision,
    history: AssetScheduleHistory,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    opening_amount = revision.opening_history.accumulated_amount
    if opening_amount is None:  # defensive: status validation proves unreachable
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.opening_history_amount_missing"
        )
    amortizable_basis = revision.amortizable_basis()
    pending_at_year_start = max(amortizable_basis - opening_amount - history.accumulated_before_tax_year, Decimal("0"))
    remaining_base = (
        revision.amortizable_ceiling()
        - opening_amount
        - history.accumulated_before_tax_year
        - history.accumulated_in_tax_year
        - history.accumulated_after_tax_year
    )
    if remaining_base < Decimal("0"):
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.claims_exceed_amortizable_basis"
        )
    return opening_amount, amortizable_basis, pending_at_year_start, remaining_base


def _charge_interval(
    revision: ActivityAssetRevision,
    authority: ScheduleAuthority,
    *,
    covered_from: date,
    covered_until: date,
    year_start: date,
    year_end: date,
) -> tuple[date, date]:
    window_start = max(revision.in_service_date, year_start)
    amortization_end = _amortization_end(revision, authority)
    window_end = min(revision.out_of_service_date or year_end, year_end, amortization_end)
    interval_start = max(covered_from, window_start)
    interval_end = min(covered_until, window_end)
    if interval_end <= interval_start:
        if interval_start >= amortization_end:
            raise ActividadAssetPeriodElapsedError(
                context={"ended_on": amortization_end.isoformat()},
                translated_message="ledger.actividad_asset.errors.amortization_period_elapsed",
            )
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.covered_interval_without_service_days"
        )
    return interval_start, interval_end


def require_method_continuity(
    method: AmortizationMethod,
    election_fingerprint: str,
    history: AssetScheduleHistory,
) -> None:
    """Refuse a change of method inside a tax year, into a from-start method, or behind a later claim.

    Forecasts and the claim write both apply this one rule, so a claim can
    never be persisted under an election its forecast would have refused.  A
    missing earlier year can be claimed behind a later one only where its charge
    does not depend on what those later claims consumed: constant percentage and
    sum of digits follow the pending value, and free depreciation not taken in
    its own year cannot be taken for that year afterwards.
    """
    current = election_fingerprint
    if history.accumulated_after_tax_year > Decimal("0"):
        if method in _FROM_START_METHODS:
            raise ActividadAssetUnsupportedError(
                context={"method": method.value},
                translated_message="ledger.actividad_asset.errors.earlier_year_depends_on_pending_value",
            )
        if method in FREE_AMOUNT_METHODS:
            raise ActividadAssetUnsupportedError(
                context={"method": method.value},
                translated_message="ledger.actividad_asset.errors.earlier_year_free_depreciation_not_taken",
            )
    if any(fingerprint != current for fingerprint in history.election_fingerprints_in_tax_year):
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.election_changes_only_at_year_boundary"
        )
    if method in _FROM_START_METHODS and any(
        fingerprint != current for fingerprint in history.election_fingerprints_before_tax_year
    ):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.from_start_method_after_other_election"
        )


def require_opening_method(revision: ActivityAssetRevision, method: AmortizationMethod) -> None:
    """Refuse a from-start method over an opening amount charged under another method.

    Constant percentage and sum of digits run from the start of amortization,
    so an amount amortized before onboarding counts only when it is attested
    to have been charged under the same method (RIS arts. 5.1 and 6.1).
    """
    opening = revision.opening_history
    if method not in _FROM_START_METHODS or not (opening.accumulated_amount is not None and opening.accumulated_amount):
        return
    if opening.amortization_method is not method:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.opening_amount_must_attest_from_start_method"
        )


def require_claim_after_opening_year(revision: ActivityAssetRevision, claim_tax_year: int) -> None:
    """Refuse a claim recorded for a year the opening amount already covers."""
    covered_through = revision.opening_history.covered_through_tax_year
    if covered_through is not None and claim_tax_year <= covered_through:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.claim_year_not_after_opening_year",
            context={"claim_tax_year": claim_tax_year, "opening_tax_year": covered_through},
        )


def parse_requested_free_amount(raw: str | None) -> Decimal | None:
    """Read an operator-typed elected free-depreciation amount.

    ``None`` elects no amount; whether a blank form field means ``None`` is the
    frontend's decision. Present text must follow the canonical decimal grammar;
    sign and cent precision stay with the schedule's own shape check, so every
    frontend reports them the same way.

    Raises:
        ActividadAssetValidationError: When present text is not a canonical decimal.
    """
    if raw is None:
        return None
    parsed = try_parse_canonical_decimal(raw)
    if parsed is None:
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.free_amount_not_decimal")
    return parsed


def _require_free_amount_shape(method: AmortizationMethod, requested_free_amount: Decimal | None) -> None:
    if method in FREE_AMOUNT_METHODS:
        if requested_free_amount is None:
            raise ActividadAssetIncompleteError(translated_message="ledger.actividad_asset.errors.free_amount_required")
        if (
            not requested_free_amount.is_finite()
            or requested_free_amount <= Decimal("0")
            or requested_free_amount != round_to_cents(requested_free_amount)
        ):
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.free_amount_not_positive_cents"
            )
    elif requested_free_amount is not None:
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.free_amount_not_accepted")


def _amortization_end(revision: ActivityAssetRevision, authority: ScheduleAuthority) -> date:
    """Return the first day after the method's useful life, or the far future."""
    if authority.method is AmortizationMethod.SUM_OF_DIGITS:
        period = authority.sum_of_digits_period_years
        if period is None:  # defensive: authority validation proves unreachable
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
        return add_years(revision.in_service_date, period)
    if authority.useful_life_ends_on is not None:
        return authority.useful_life_ends_on
    if authority.maximum_period_ends_on is not None:
        return authority.maximum_period_ends_on
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
    raise ActividadAssetUnsupportedError(
        context={"method": method.value},
        translated_message="ledger.actividad_asset.errors.method_without_schedule_arithmetic",
    )


def _annual_rate(context: _ChargeContext) -> Decimal:
    rate = context.authority.annual_rate
    if rate is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
    return rate


def _linear_amount(context: _ChargeContext) -> Decimal:
    """Apply the lifecycle rule: basis x rate x service days / tax-year days.

    A used element whose originating price is the base (RIS art. 4.3.b-c)
    applies the rate to that price; the charge still stops at what remains of
    the element's own basis.
    """
    base = context.authority.original_price_basis
    if base is None:
        base = context.amortizable_basis
    return _tax_year_cumulative_difference(context, base * _annual_rate(context))


def _tax_year_cumulative_difference(context: _ChargeContext, annual_charge: Decimal) -> Decimal:
    """Spread an annual charge by days, rounding the tax year's cumulative curve.

    Rounding each endpoint rather than each interval makes contiguous claims
    sum exactly to the annual figure, whichever periods the operator records.
    """
    window_start = max(context.revision.in_service_date, context.year_start)
    year_days = Decimal(calendar_days_in_tax_year(context.authority.tax_year))

    def cumulative(point: date) -> Decimal:
        return annual_charge * Decimal((point - window_start).days) / year_days

    return round_to_cents(cumulative(context.interval_end)) - round_to_cents(cumulative(context.interval_start))


def _constant_percentage_amount(context: _ChargeContext) -> Decimal:
    """Apply RIS art. 5.1 to the value pending at the start of the tax year.

    In the tax year in which the useful life concludes, the whole pending
    value is spread over the days from the year's first in-service day to
    that conclusion, so the final period amortizes what remains.
    """
    life_end = context.authority.useful_life_ends_on
    if life_end is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
    if life_end <= context.year_end:
        final_start = max(context.revision.in_service_date, context.year_start)
        final_days = Decimal((life_end - final_start).days)
        if final_days <= Decimal("0"):  # defensive: a non-empty interval proves a positive span
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")

        def cumulative(point: date) -> Decimal:
            return context.pending_at_year_start * Decimal((point - final_start).days) / final_days

        # Rounding the cumulative curve, not each interval, lets contiguous
        # final-year claims reach exactly the pending value.
        return round_to_cents(cumulative(context.interval_end)) - round_to_cents(cumulative(context.interval_start))
    return _tax_year_cumulative_difference(context, context.pending_at_year_start * _annual_rate(context))


def _approved_plan_amount(context: _ChargeContext) -> Decimal:
    """Spread the plan's approved annual amount over that year's service days."""
    plan_total = context.authority.plan_total
    annual_amount = context.authority.plan_annual_amount
    if plan_total is None or annual_amount is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
    if plan_total > context.amortizable_basis:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.approved_plan_exceeds_basis"
        )
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
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
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
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
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
        raise ActividadAssetIncompleteError(translated_message="ledger.actividad_asset.errors.free_amount_required")
    if requested_free_amount > context.remaining_base:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.free_amount_exceeds_remaining_basis"
        )
    if context.authority.method is AmortizationMethod.LOW_VALUE_FREE:
        _require_low_value_election(context, history=history, requested_free_amount=requested_free_amount)
    if context.authority.method in WORKFORCE_CONDITIONED_METHODS:
        _require_investment_within_cap(context, history=history)
    return requested_free_amount


def _require_investment_within_cap(context: _ChargeContext, *, history: AssetScheduleHistory) -> None:
    """Refuse when this asset's investment takes its incentive past the investment cap.

    LIS art. 102.1 and DA 17a.1 cap the investment that may benefit, not the
    period's charge.  An asset that would cross the cap is refused whole:
    splitting one asset between free and ordinary amortization is not
    supported, so no part of an over-cap investment is charged freely.
    """
    investment_cap = context.authority.free_depreciation_investment_cap
    if investment_cap is None:  # defensive: authority validation proves unreachable
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
    investment = history.same_incentive_investment_of_other_assets + context.revision.basis.deductible_basis()
    if investment > investment_cap:
        raise ActividadAssetUnsupportedError(
            context={
                "entry_year": context.revision.in_service_date.year,
                "method": context.authority.method.value,
                "investment": str(investment),
                "investment_cap": str(investment_cap),
            },
            translated_message="ledger.actividad_asset.errors.investment_cap_exceeded",
        )


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
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
    if (
        context.revision.acquired_condition is not AcquiredCondition.NEW
        or context.revision.in_service_date.year != authority.tax_year
    ):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.low_value_requires_entry_year"
        )
    unit_value = context.revision.basis.acquisition_cost()
    if unit_value != round_to_cents(unit_value):
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.low_value_unit_value_not_cents"
        )
    if unit_value > threshold:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.low_value_threshold_exceeded"
        )
    if history.taxpayer_low_value_claimed_in_tax_year + requested_free_amount > annual_cap:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.free_amount_exceeds_annual_cap"
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
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.useful_life_not_positive")
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
    "require_claim_after_opening_year",
    "require_method_continuity",
    "require_opening_method",
    "schedule_charge",
]
