"""Corporate-tax helpers for Modelo 200 worked examples.

The registered Modelo 200 rulesets verify the page-14 arithmetic printed
on the declaration. This module supplies the statutory inputs that feed
that page: tax-rate selection, BIN compensation caps, LIS art. 12 lineal
amortization, and LIS art. 30 bis minimum liquid quota checks.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .modelo_100 import LIS_ART_12_LINEAL_TABLE, AssetClass

_MONEY = Decimal("0.01")
_RATE = Decimal("0.01")
_ONE_HUNDRED = Decimal("100")
_MICRO_BAND = Decimal("50000.00")
_BIN_FLOOR = Decimal("1000000.00")


class Modelo200TaxRegime(StrEnum):
    """Common-state rate regimes exercised by Modelo 200 page-14 examples."""

    GENERAL = "general"
    MICROENTERPRISE = "microenterprise"
    REDUCED_SIZE = "reduced_size"
    NEW_ENTITY = "new_entity"
    FINANCIAL_OR_HYDROCARBON = "financial_or_hydrocarbon"
    ZEC = "zec"


class Modelo200DepreciableAsset(BaseModel):
    """One LIS art. 12 asset used to derive a deductible amortization line."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    asset_class: AssetClass
    acquisition_cost: Decimal = Field(ge=Decimal("0.00"))
    land_value: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))

    @model_validator(mode="after")
    def _validate_values(self) -> Modelo200DepreciableAsset:
        if self.land_value > self.acquisition_cost:
            raise ValueError("land_value cannot exceed acquisition_cost")
        return self

    @property
    def depreciable_base(self) -> Decimal:
        """Return acquisition cost net of non-depreciable land value."""
        return self.acquisition_cost - self.land_value


def modelo_200_tax_due(
    *,
    taxable_base: Decimal,
    year: int,
    regime: Modelo200TaxRegime,
    period_days: int = 365,
    zec_eligible_base: Decimal = Decimal("0.00"),
) -> Decimal:
    """Return cuota íntegra before deductions for a statutory rate case."""
    _validate_common_inputs(taxable_base=taxable_base, year=year, period_days=period_days)
    if zec_eligible_base < 0:
        raise ValueError("zec_eligible_base cannot be negative")
    if zec_eligible_base > taxable_base:
        raise ValueError("zec_eligible_base cannot exceed taxable_base")

    if regime is Modelo200TaxRegime.MICROENTERPRISE:
        return _round_money(_tiered_microenterprise_tax(taxable_base=taxable_base, year=year, period_days=period_days))
    if regime is Modelo200TaxRegime.ZEC:
        common_base = taxable_base - zec_eligible_base
        return _round_money(_percent(zec_eligible_base, Decimal("4.00")) + _percent(common_base, Decimal("25.00")))
    return _round_money(_percent(taxable_base, _flat_rate_for(year=year, regime=regime)))


def modelo_200_effective_rate(
    *,
    taxable_base: Decimal,
    year: int,
    regime: Modelo200TaxRegime,
    period_days: int = 365,
    zec_eligible_base: Decimal = Decimal("0.00"),
) -> Decimal:
    """Return the whole-percent rate that makes casilla 00562 verify."""
    if taxable_base == 0:
        return Decimal("0.00")
    tax_due = modelo_200_tax_due(
        taxable_base=taxable_base,
        year=year,
        regime=regime,
        period_days=period_days,
        zec_eligible_base=zec_eligible_base,
    )
    return ((tax_due / taxable_base) * _ONE_HUNDRED).quantize(_RATE, rounding=ROUND_HALF_UP)


def modelo_200_bin_compensation_cap(
    *,
    base_before_bin: Decimal,
    pending_bin: Decimal,
    period_days: int = 365,
    new_entity_first_positive_periods: bool = False,
    extinction_period: bool = False,
) -> Decimal:
    """Return deductible BIN compensation under LIS art. 26."""
    if base_before_bin < 0 or pending_bin < 0:
        raise ValueError("base_before_bin and pending_bin must be non-negative")
    _validate_period_days(period_days)
    if base_before_bin == 0 or pending_bin == 0:
        return Decimal("0.00")
    if new_entity_first_positive_periods or extinction_period:
        return _round_money(min(base_before_bin, pending_bin))

    prorated_floor = _BIN_FLOOR * Decimal(period_days) / Decimal(365)
    statutory_cap = max(base_before_bin * Decimal("0.70"), prorated_floor)
    return _round_money(min(base_before_bin, pending_bin, statutory_cap))


def modelo_200_max_lineal_amortization(asset: Modelo200DepreciableAsset) -> Decimal:
    """Return maximum annual lineal amortization under LIS art. 12.1.a)."""
    category = next(row for row in LIS_ART_12_LINEAL_TABLE if row.asset_class is asset.asset_class)
    return _round_money(asset.depreciable_base * category.coef_max_pct / _ONE_HUNDRED)


def modelo_200_minimum_liquid_quota(
    *,
    taxable_base: Decimal,
    year: int,
    regime: Modelo200TaxRegime,
    minimum_tax_applies: bool,
    period_days: int = 365,
    zec_eligible_base: Decimal = Decimal("0.00"),
) -> Decimal:
    """Return the LIS art. 30 bis minimum liquid quota floor."""
    _validate_common_inputs(taxable_base=taxable_base, year=year, period_days=period_days)
    if not minimum_tax_applies or taxable_base == 0:
        return Decimal("0.00")
    if zec_eligible_base < 0 or zec_eligible_base > taxable_base:
        raise ValueError("zec_eligible_base must be between zero and taxable_base")

    minimum_base = taxable_base - zec_eligible_base
    if regime is Modelo200TaxRegime.NEW_ENTITY:
        return _round_money(_percent(minimum_base, Decimal("10.00")))
    if regime is Modelo200TaxRegime.FINANCIAL_OR_HYDROCARBON:
        return _round_money(_percent(minimum_base, Decimal("18.00")))
    if regime is Modelo200TaxRegime.MICROENTERPRISE:
        return _round_money(
            _tiered_microenterprise_tax(
                taxable_base=minimum_base,
                year=year,
                period_days=period_days,
                minimum_tax_scale=True,
            )
        )
    if regime is Modelo200TaxRegime.REDUCED_SIZE:
        return _round_money(_percent(minimum_base, _minimum_tax_rate(_flat_rate_for(year=year, regime=regime))))
    return _round_money(_percent(minimum_base, Decimal("15.00")))


def _flat_rate_for(*, year: int, regime: Modelo200TaxRegime) -> Decimal:
    if regime is Modelo200TaxRegime.GENERAL:
        return Decimal("25.00")
    if regime is Modelo200TaxRegime.NEW_ENTITY:
        return Decimal("15.00")
    if regime is Modelo200TaxRegime.FINANCIAL_OR_HYDROCARBON:
        return Decimal("30.00")
    if regime is Modelo200TaxRegime.REDUCED_SIZE:
        if year == 2025:
            return Decimal("24.00")
        if year == 2026:
            return Decimal("23.00")
        return Decimal("25.00")
    if regime is Modelo200TaxRegime.ZEC:
        return Decimal("4.00")
    raise ValueError(f"{regime.value!r} is not a flat-rate regime")


def _tiered_microenterprise_tax(
    *,
    taxable_base: Decimal,
    year: int,
    period_days: int,
    minimum_tax_scale: bool = False,
) -> Decimal:
    first_rate, rest_rate = _microenterprise_rates(year)
    if minimum_tax_scale:
        first_rate = _minimum_tax_rate(first_rate)
        rest_rate = _minimum_tax_rate(rest_rate)
    first_band = min(taxable_base, _MICRO_BAND * Decimal(period_days) / Decimal(365))
    rest = taxable_base - first_band
    return _percent(first_band, first_rate) + _percent(rest, rest_rate)


def _microenterprise_rates(year: int) -> tuple[Decimal, Decimal]:
    if year == 2025:
        return Decimal("21.00"), Decimal("22.00")
    if year == 2026:
        return Decimal("19.00"), Decimal("21.00")
    return Decimal("23.00"), Decimal("23.00")


def _minimum_tax_rate(rate: Decimal) -> Decimal:
    return (rate * Decimal("15") / Decimal("25")).quantize(Decimal("1"), rounding=ROUND_CEILING)


def _percent(base: Decimal, rate: Decimal) -> Decimal:
    return base * rate / _ONE_HUNDRED


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _validate_common_inputs(*, taxable_base: Decimal, year: int, period_days: int) -> None:
    if taxable_base < 0:
        raise ValueError("taxable_base cannot be negative")
    if year not in {2024, 2025, 2026}:
        raise ValueError("Modelo 200 helper covers only 2024, 2025, and 2026")
    _validate_period_days(period_days)


def _validate_period_days(period_days: int) -> None:
    if period_days < 1 or period_days > 365:
        raise ValueError("period_days must be between 1 and 365")
