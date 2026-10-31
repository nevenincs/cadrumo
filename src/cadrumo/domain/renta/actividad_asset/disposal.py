"""The baja of an activity asset and the one calculation of its gain or loss.

A baja is a record on a superseding revision.  Its calculation is pure: the caller
states the element's allocated acquisition value, its amortizable value and, year
by year, what was claimed and what the minimum and the maximum table coefficient
allow.  Nothing here reads storage or knows a form.

The reduction of cost follows RIRPF art. 40: the minimum reduces cost whether or
not it was claimed, so a missing claim is a finding and never a refusal.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from .election import require_euro_cents
from .errors import ActividadAssetUnsupportedError, ActividadAssetValidationError

DisposalTaxYear = Annotated[int, Field(ge=1900, le=9999)]
"""A service year, which can predate every filing year the registry knows."""


class ActivityAssetDisposalReason(StrEnum):
    """Why an element leaves the register.

    ``DONATION`` is typed so that its refusal is explicit rather than an unknown
    token; no record ever carries it.
    """

    SALE = "sale"
    PART_EXCHANGE = "part_exchange"
    THEFT = "theft"
    DESTRUCTION = "destruction"
    SCRAPPING = "scrapping"
    WITHDRAWAL = "withdrawal"
    DONATION = "donation"


REFUSED_DISPOSAL_REASONS: Final[Mapping[ActivityAssetDisposalReason, str]] = MappingProxyType(
    {ActivityAssetDisposalReason.DONATION: "ledger.actividad_asset.errors.disposal_donation_refused"},
)
"""The reasons a baja is refused, each with the catalogue key of its refusal; no record carries one."""

ADMITTED_DISPOSAL_REASONS: Final[tuple[ActivityAssetDisposalReason, ...]] = tuple(
    reason for reason in ActivityAssetDisposalReason if reason not in REFUSED_DISPOSAL_REASONS
)
"""The reasons a baja is accepted with, in declaration order; what a form offers is this and nothing else."""

TRANSMISSION_REASONS: frozenset[ActivityAssetDisposalReason] = frozenset(
    {ActivityAssetDisposalReason.SALE, ActivityAssetDisposalReason.PART_EXCHANGE},
)
"""The reasons that transmit the element, whose gain or loss belongs to the ahorro base (LIRPF art. 46.b)."""

BAJA_WITHOUT_TRANSMISSION_REASONS: frozenset[ActivityAssetDisposalReason] = frozenset(
    {
        ActivityAssetDisposalReason.THEFT,
        ActivityAssetDisposalReason.DESTRUCTION,
        ActivityAssetDisposalReason.SCRAPPING,
    },
)
"""The reasons with no transmission, whose gain or loss belongs to the general base (LIRPF art. 45)."""


class PriorFreeDepreciationRegime(StrEnum):
    """The attested prior free depreciation that LIRPF DA 30.2 carves out at transmission."""

    TRLIS_DA_11 = "trlis_da_11"
    TRLIS_DT_37 = "trlis_dt_37"


def require_admissible_disposal(
    reason: ActivityAssetDisposalReason,
    *,
    proceeds: Decimal,
    transmission_costs: Decimal,
    market_value: Decimal | None,
) -> None:
    """Refuse a baja its reason cannot carry.

    The record applies this too, but a validator can only report a shape error,
    so an operation owing the registered refusal calls this before building one.
    """
    refusal_key = REFUSED_DISPOSAL_REASONS.get(reason)
    if refusal_key is not None:
        raise ActividadAssetUnsupportedError(context={"reason": reason.value}, translated_message=refusal_key)
    if reason is ActivityAssetDisposalReason.SCRAPPING and proceeds != Decimal("0"):
        raise ActividadAssetValidationError(
            context={"proceeds": proceeds},
            translated_message="ledger.actividad_asset.errors.disposal_scrapping_with_proceeds",
        )
    if reason is ActivityAssetDisposalReason.WITHDRAWAL and (
        proceeds != Decimal("0") or transmission_costs != Decimal("0") or market_value is not None
    ):
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.disposal_withdrawal_with_amounts",
        )


class ActivityAssetDisposal(BaseModel):
    """One element's baja, carried by the revision that records it.

    Amounts are stated for the whole element, except under a business-allocated
    basis, and take the same shares as its cost in the calculation.
    ``later_affectation_on`` attests the day a privately held element was later
    affected to the activity, because a sale within the period LIRPF art. 28.3
    sets after it changes the route.
    """

    model_config = STRICT_FROZEN_CONFIG

    disposal_date: date
    reason: ActivityAssetDisposalReason
    proceeds: Decimal
    transmission_costs: Decimal
    market_value: Decimal | None = None
    prior_free_depreciation_regime: PriorFreeDepreciationRegime | None = None
    later_affectation_on: date | None = None

    @field_validator("proceeds", "transmission_costs")
    @classmethod
    def _require_cents(cls, value: Decimal) -> Decimal:
        return require_euro_cents(value, allow_zero=True, label="disposal amount")

    @field_validator("market_value")
    @classmethod
    def _require_optional_cents(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else require_euro_cents(value, allow_zero=True, label="market value")

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_reason(self) -> Self:
        require_admissible_disposal(
            self.reason,
            proceeds=self.proceeds,
            transmission_costs=self.transmission_costs,
            market_value=self.market_value,
        )
        return self

    @property
    def boundary(self) -> date:
        """Return the exclusive end of the charge window: the disposal date is the last service day."""
        return self.disposal_date + timedelta(days=1)


class ActivityAssetDisposalYearFacts(BaseModel):
    """What one service year contributes to the reduction of cost.

    ``minimum`` and ``maximum_charge`` are that year's exact figures, or ``None``
    when no maximum period, fixed percentage or table class supplies one.
    ``minimum_unresolved`` says the year has a minimum the registry cannot state,
    because no edition covers it, as distinct from a year the law gives none.
    """

    model_config = STRICT_FROZEN_CONFIG

    tax_year: DisposalTaxYear
    claims: Decimal = Field(ge=Decimal("0"))
    minimum: Decimal | None = Field(default=None, ge=Decimal("0"))
    maximum_charge: Decimal | None = Field(default=None, ge=Decimal("0"))
    claim_gap: bool = False
    minimum_unresolved: bool = False


class ActivityAssetDisposalFacts(BaseModel):
    """Everything the calculation reads, in amounts already allocated to this taxpayer's activity."""

    model_config = STRICT_FROZEN_CONFIG

    disposal: ActivityAssetDisposal
    acquisition_value: Decimal = Field(ge=Decimal("0"))
    allocation_share: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    amortizable_value: Decimal = Field(ge=Decimal("0"))
    opening_amount: Decimal = Field(ge=Decimal("0"))
    opening_covered_through: DisposalTaxYear | None = None
    """The last tax year the opening amount covers; a later year with no claim is a gap."""
    years: tuple[ActivityAssetDisposalYearFacts, ...]
    excess_applies: bool = False
    later_affectation_period_years: int | None = Field(default=None, gt=0)
    """The years after a later affectation in which a sale changes the route; ``None`` when no edition states them."""

    @model_validator(mode="after")
    def _require_ordered_years(self) -> Self:
        numbers = [year.tax_year for year in self.years]
        if numbers != sorted(set(numbers)):
            raise ValueError("disposal years must be unique and in order")
        return self


class ActivityAssetDisposalFindingKind(StrEnum):
    """What a calculation tells the operator without stopping it."""

    CLAIM_GAP = "claim_gap"
    MINIMUM_EXCEEDED_DEDUCTION = "minimum_exceeded_deduction"
    NO_MINIMUM_AUTHORITY = "no_minimum_authority"
    MINIMUM_UNRESOLVED = "minimum_unresolved"
    EXEMPTION_NOT_COMPUTED = "exemption_not_computed"


class ActivityAssetDisposalFinding(BaseModel):
    """One non-blocking finding; ``effect_on_cost`` is what the minimum added to the reduction."""

    model_config = STRICT_FROZEN_CONFIG

    kind: ActivityAssetDisposalFindingKind
    tax_year: DisposalTaxYear | None = None
    effect_on_cost: Decimal | None = None


class ActivityAssetDisposalYear(BaseModel):
    """One year's cumulative figures; ``minimum_through`` is ``None`` once a year's minimum is unresolved."""

    model_config = STRICT_FROZEN_CONFIG

    tax_year: DisposalTaxYear
    claims: Decimal
    deducted_through: Decimal
    minimum_through: Decimal | None
    reduction_through: Decimal


class ActivityAssetDisposalCalculation(BaseModel):
    """The result of one baja, in euro cents.

    ``result`` is ``None`` for a withdrawal, which computes no gain (LIRPF art.
    28.3); otherwise a positive result is a gain and a negative one a loss.
    ``minimum`` is ``None`` when a contributing year's is unresolved.  The reduction
    and the result then rest on the years that are known, and a finding names each
    year left out, so the reduction may be understated.
    """

    model_config = STRICT_FROZEN_CONFIG

    acquisition_value: Decimal
    deducted: Decimal
    minimum: Decimal | None
    reduction: Decimal
    excess: Decimal
    net_value: Decimal
    transmission_value: Decimal | None
    transmission_costs: Decimal | None
    result: Decimal | None
    route_changed_by_later_affectation: bool
    years: tuple[ActivityAssetDisposalYear, ...]
    findings: tuple[ActivityAssetDisposalFinding, ...]

    @property
    def net_transmission_value(self) -> Decimal | None:
        """Return what the form calls the value of transmission: the amount less its costs (LIRPF art. 35.2)."""
        if self.transmission_value is None or self.transmission_costs is None:
            return None
        return self.transmission_value - self.transmission_costs


def calculate_disposal(facts: ActivityAssetDisposalFacts) -> ActivityAssetDisposalCalculation:
    """Work out the reduction of cost, any excess and the gain or loss of one baja.

    Returns:
        The figures with their year-by-year trace and non-blocking findings.

    Raises:
        ActividadAssetUnsupportedError: When an excess needs a counterfactual
            that a year has no table class for.
    """
    disposal = facts.disposal
    withdrawal = disposal.reason is ActivityAssetDisposalReason.WITHDRAWAL
    with_excess = facts.excess_applies and not withdrawal
    if with_excess:
        rows, findings, maximum = _excess_rows(facts)
    else:
        rows, findings = _ordinary_rows(facts)
        maximum = Decimal("0")
    opening = round_to_cents(facts.opening_amount)
    deducted = rows[-1].deducted_through if rows else opening
    reduction = rows[-1].reduction_through if rows else min(opening, round_to_cents(facts.amortizable_value))
    excess = max(Decimal("0"), deducted - maximum) if with_excess else Decimal("0.00")
    acquisition_value = round_to_cents(facts.acquisition_value)
    net_value = acquisition_value - reduction
    transmission_value, costs, result = _transmission_result(facts, net_value)
    if result is not None and result > Decimal("0"):
        findings = (
            *findings,
            ActivityAssetDisposalFinding(kind=ActivityAssetDisposalFindingKind.EXEMPTION_NOT_COMPUTED),
        )
    return ActivityAssetDisposalCalculation(
        acquisition_value=acquisition_value,
        deducted=deducted,
        minimum=rows[-1].minimum_through if rows else Decimal("0.00"),
        reduction=reduction,
        excess=excess,
        net_value=net_value,
        transmission_value=transmission_value,
        transmission_costs=costs,
        result=result,
        route_changed_by_later_affectation=_within_later_affectation_period(
            disposal,
            period_years=facts.later_affectation_period_years,
        ),
        years=rows,
        findings=findings,
    )


def _transmission_result(
    facts: ActivityAssetDisposalFacts, net_value: Decimal
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    disposal = facts.disposal
    if disposal.reason is ActivityAssetDisposalReason.WITHDRAWAL:
        return None, None, None
    stated = max(disposal.proceeds, disposal.market_value or Decimal("0"))
    transmission_value = round_to_cents(stated * facts.allocation_share)
    costs = round_to_cents(disposal.transmission_costs * facts.allocation_share)
    return transmission_value, costs, transmission_value - costs - net_value


def _within_later_affectation_period(disposal: ActivityAssetDisposal, *, period_years: int | None) -> bool:
    """Say whether the sale may leave the ordinary route: with no stated period, the route stays open."""
    affected = disposal.later_affectation_on
    if affected is None or disposal.reason not in TRANSMISSION_REASONS:
        return False
    if period_years is None:
        return True
    target_year = affected.year + period_years
    last_day = calendar.monthrange(target_year, affected.month)[1]
    return disposal.disposal_date < date(target_year, affected.month, min(affected.day, last_day))


def _ordinary_rows(
    facts: ActivityAssetDisposalFacts,
) -> tuple[tuple[ActivityAssetDisposalYear, ...], tuple[ActivityAssetDisposalFinding, ...]]:
    """Apply R(y) = max(R(y-1) + claims(y), M through y), with the unclaimed first years as one opening span."""
    opening = round_to_cents(facts.opening_amount)
    cap = round_to_cents(facts.amortizable_value)
    first_claim = next((year.tax_year for year in facts.years if year.claims > Decimal("0")), None)
    rows: list[ActivityAssetDisposalYear] = []
    findings: list[ActivityAssetDisposalFinding] = []
    reduction = min(opening, cap)
    deducted = opening
    minimum = Decimal("0")
    unresolved = False
    for position, year in enumerate(facts.years):
        minimum += year.minimum or Decimal("0")
        minimum_through = round_to_cents(minimum)
        unresolved = unresolved or year.minimum_unresolved
        deducted += year.claims
        before_minimum, span_ends = _ordinary_before_minimum(facts.years, position, first_claim, opening, reduction)
        reduction = min(cap, max(before_minimum, minimum_through))
        rows.append(
            ActivityAssetDisposalYear(
                tax_year=year.tax_year,
                claims=year.claims,
                deducted_through=deducted,
                minimum_through=None if unresolved else minimum_through,
                reduction_through=reduction,
            ),
        )
        findings.extend(_year_findings(year, opening_covered_through=facts.opening_covered_through))
        if span_ends and reduction > before_minimum:
            findings.append(
                ActivityAssetDisposalFinding(
                    kind=ActivityAssetDisposalFindingKind.MINIMUM_EXCEEDED_DEDUCTION,
                    tax_year=year.tax_year,
                    effect_on_cost=reduction - before_minimum,
                ),
            )
    return tuple(rows), tuple(findings)


def _ordinary_before_minimum(
    years: tuple[ActivityAssetDisposalYearFacts, ...],
    position: int,
    first_claim: int | None,
    opening: Decimal,
    reduction: Decimal,
) -> tuple[Decimal, bool]:
    year = years[position]
    if first_claim is None or year.tax_year < first_claim:
        return opening, position + 1 == len(years) or years[position + 1].tax_year == first_claim
    return reduction + year.claims, True


def _excess_rows(
    facts: ActivityAssetDisposalFacts,
) -> tuple[tuple[ActivityAssetDisposalYear, ...], tuple[ActivityAssetDisposalFinding, ...], Decimal]:
    """Apply R(y) = max(min(D, C), M) where C is the cumulative charge at the maximum table coefficient."""
    opening = round_to_cents(facts.opening_amount)
    cap = round_to_cents(facts.amortizable_value)
    rows: list[ActivityAssetDisposalYear] = []
    findings: list[ActivityAssetDisposalFinding] = []
    deducted = opening
    minimum = Decimal("0")
    maximum = Decimal("0")
    maximum_through = Decimal("0.00")
    unresolved = False
    for year in facts.years:
        if year.maximum_charge is None:
            raise ActividadAssetUnsupportedError(
                context={"tax_year": year.tax_year},
                translated_message="ledger.actividad_asset.errors.disposal_excess_without_table_class",
            )
        maximum += year.maximum_charge
        maximum_through = min(cap, round_to_cents(maximum))
        minimum += year.minimum or Decimal("0")
        minimum_through = round_to_cents(minimum)
        unresolved = unresolved or year.minimum_unresolved
        deducted += year.claims
        rows.append(
            ActivityAssetDisposalYear(
                tax_year=year.tax_year,
                claims=year.claims,
                deducted_through=deducted,
                minimum_through=None if unresolved else minimum_through,
                reduction_through=min(cap, max(min(deducted, maximum_through), minimum_through)),
            ),
        )
        findings.extend(_year_findings(year, opening_covered_through=facts.opening_covered_through))
    return tuple(rows), tuple(findings), maximum_through


def _year_findings(
    year: ActivityAssetDisposalYearFacts,
    *,
    opening_covered_through: int | None,
) -> tuple[ActivityAssetDisposalFinding, ...]:
    found: list[ActivityAssetDisposalFinding] = []
    opening_covers = opening_covered_through is not None and year.tax_year <= opening_covered_through
    if year.claim_gap and not opening_covers:
        found.append(
            ActivityAssetDisposalFinding(kind=ActivityAssetDisposalFindingKind.CLAIM_GAP, tax_year=year.tax_year)
        )
    if year.minimum_unresolved:
        found.append(
            ActivityAssetDisposalFinding(
                kind=ActivityAssetDisposalFindingKind.MINIMUM_UNRESOLVED, tax_year=year.tax_year
            ),
        )
    elif year.minimum is None:
        found.append(
            ActivityAssetDisposalFinding(
                kind=ActivityAssetDisposalFindingKind.NO_MINIMUM_AUTHORITY, tax_year=year.tax_year
            ),
        )
    return tuple(found)


__all__ = [
    "ADMITTED_DISPOSAL_REASONS",
    "BAJA_WITHOUT_TRANSMISSION_REASONS",
    "REFUSED_DISPOSAL_REASONS",
    "TRANSMISSION_REASONS",
    "ActivityAssetDisposal",
    "ActivityAssetDisposalCalculation",
    "ActivityAssetDisposalFacts",
    "ActivityAssetDisposalFinding",
    "ActivityAssetDisposalFindingKind",
    "ActivityAssetDisposalReason",
    "ActivityAssetDisposalYear",
    "ActivityAssetDisposalYearFacts",
    "PriorFreeDepreciationRegime",
    "calculate_disposal",
    "require_admissible_disposal",
]
