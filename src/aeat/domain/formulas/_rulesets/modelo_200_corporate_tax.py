"""Corporate-tax helpers for Modelo 200 worked examples.

The registered Modelo 200 rulesets verify the page-14 arithmetic printed
on the declaration. This module supplies the statutory inputs that feed
that page: tax-rate selection, BIN (bases imponibles negativas)
compensation caps, LIS art. 12 lineal amortization, and LIS art. 30 bis
minimum-liquid-quota checks.

Public surface:

- :class:`Modelo200TaxRegime` enumerates the rate-selection cases
  supported by the helpers.
- :class:`Modelo200DepreciableAsset` models a single LIS art. 12 asset.
- :func:`modelo_200_tax_due`, :func:`modelo_200_effective_rate`,
  :func:`modelo_200_bin_compensation_cap`,
  :func:`modelo_200_max_lineal_amortization`, and
  :func:`modelo_200_minimum_liquid_quota` derive the values that the
  caller pre-computes before invoking
  :class:`aeat.domain.formulas.Engine` against the
  Modelo 200 ruleset.

All monetary results are quantised to two decimal places using
:data:`decimal.ROUND_HALF_UP`.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .modelo_100 import LIS_ART_12_LINEAL_TABLE, AssetClass

_MONEY = Decimal("0.01")
"""Quantum used by :func:`_round_money` to round monetary values to cents."""

_RATE = Decimal("0.01")
"""Quantum used by :func:`modelo_200_effective_rate` to round whole-percent rates."""

_ONE_HUNDRED = Decimal("100")
"""Constant divisor that converts whole-percent rates to fractions."""

_MICRO_BAND = Decimal("50000.00")
"""First-band cap (euros, per 365 days) for the microempresa tiered scale."""

_BIN_FLOOR = Decimal("1000000.00")
"""Statutory minimum BIN-compensation floor (euros, prorated by ``period_days``)."""


class Modelo200TaxRegime(StrEnum):
    """Common-state rate regimes exercised by Modelo 200 page-14 examples.

    Members map to the statutory cases that
    :func:`modelo_200_tax_due` and
    :func:`modelo_200_minimum_liquid_quota` recognise. Foral regimes and
    region-specific overlays are out of scope and not represented here.

    Attributes:
        GENERAL: Standard 25 % rate (LIS art. 29.1).
        MICROENTERPRISE: Tiered rate for microempresas; uses
            :data:`_MICRO_BAND` as the first-band cap.
        REDUCED_SIZE: Reduced rate for empresas de reducida dimensión
            (LIS art. 29.1, second paragraph) — value depends on year.
        NEW_ENTITY: 15 % rate for entidades de nueva creación
            (LIS art. 29.1, third paragraph).
        FINANCIAL_OR_HYDROCARBON: 30 % rate for entidades de crédito
            and entidades dedicadas a hidrocarburos (LIS art. 29.6).
        ZEC: Zona Especial Canaria 4 % preferential rate, applied to
            the eligible base only (Ley 19/1994).
    """

    GENERAL = "general"
    MICROENTERPRISE = "microenterprise"
    REDUCED_SIZE = "reduced_size"
    NEW_ENTITY = "new_entity"
    FINANCIAL_OR_HYDROCARBON = "financial_or_hydrocarbon"
    ZEC = "zec"


class Modelo200DepreciableAsset(BaseModel):
    """One LIS art. 12 asset used to derive a deductible amortization line.

    Frozen pydantic model consumed by
    :func:`modelo_200_max_lineal_amortization` to look up the maximum
    annual lineal amortization coefficient for the asset's
    :class:`aeat.domain.formulas._rulesets.modelo_100.AssetClass`.

    Attributes:
        asset_class: LIS art. 12.1.a asset category that selects the
            applicable row in
            :data:`aeat.domain.formulas._rulesets.modelo_100.LIS_ART_12_LINEAL_TABLE`.
        acquisition_cost: Total acquisition cost in euros, including any
            non-depreciable land component.
        land_value: Non-depreciable land component in euros (must not
            exceed ``acquisition_cost``); subtracted from
            ``acquisition_cost`` to derive :attr:`depreciable_base`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    asset_class: AssetClass
    acquisition_cost: Decimal = Field(ge=Decimal("0.00"))
    land_value: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))

    @model_validator(mode="after")
    def _validate_values(self) -> Modelo200DepreciableAsset:
        """Reject configurations where land value would yield a negative depreciable base."""
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
    """Return cuota íntegra before deductions for a statutory rate case.

    Selects the applicable rate from
    :class:`Modelo200TaxRegime`, applies the microempresa tiered scale
    when relevant, and splits the base for ZEC-eligible filings.

    Args:
        taxable_base: Base imponible in euros (must be non-negative).
        year: Fiscal year (one of 2024, 2025, or 2026).
        regime: Rate regime selector.
        period_days: Length of the fiscal period; prorates band caps and
            BIN floors. Must be in ``[1, 365]``.
        zec_eligible_base: Subset of ``taxable_base`` that benefits from
            the ZEC 4 % rate (Ley 19/1994). Must be non-negative and not
            exceed ``taxable_base``.

    Returns:
        Cuota íntegra in euros, quantised to two decimals.

    Raises:
        ValueError: If any input is out of range or inconsistent.
    """
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
    """Return the whole-percent rate that makes casilla 00562 verify.

    Convenience wrapper around :func:`modelo_200_tax_due` that back-computes
    the effective rate the caller should report in casilla 00558. Returns
    ``0.00`` when ``taxable_base`` is zero to avoid a division by zero.

    Args:
        taxable_base: Base imponible in euros.
        year: Fiscal year (one of 2024, 2025, or 2026).
        regime: Rate regime selector (see :class:`Modelo200TaxRegime`).
        period_days: Length of the fiscal period in days.
        zec_eligible_base: Subset of ``taxable_base`` taxed under ZEC.

    Returns:
        Effective rate as a whole-percent :class:`~decimal.Decimal` (for
        example ``Decimal("25.00")`` for the GENERAL regime), quantised
        to two decimals.
    """
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
    """Return deductible BIN compensation under LIS art. 26.

    Applies the lesser of (a) ``base_before_bin``, (b) ``pending_bin``,
    and (c) the statutory cap, where the cap is ``max(70 % of base, 1 M €
    prorated by ``period_days``)``. New-entity first-positive periods and
    extinction periods are uncapped, returning ``min(base, pending)``.

    Args:
        base_before_bin: Base imponible prior to BIN compensation, in
            euros (must be non-negative).
        pending_bin: Pending BIN balance available for compensation, in
            euros (must be non-negative).
        period_days: Length of the fiscal period in days; prorates the
            1 M € statutory floor.
        new_entity_first_positive_periods: When ``True``, removes the cap
            (LIS art. 26.3, first-positive-base entities).
        extinction_period: When ``True``, removes the cap (LIS art. 26.3,
            extinction period).

    Returns:
        Deductible BIN compensation in euros, quantised to two decimals.

    Raises:
        ValueError: If any monetary input is negative or ``period_days``
            is out of range.
    """
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
    """Return maximum annual lineal amortization under LIS art. 12.1.a).

    Looks up the asset's category in
    :data:`aeat.domain.formulas._rulesets.modelo_100.LIS_ART_12_LINEAL_TABLE`
    and applies the maximum coefficient to the asset's depreciable base.

    Args:
        asset: A :class:`Modelo200DepreciableAsset` whose
            :attr:`Modelo200DepreciableAsset.depreciable_base` is the
            base to which the coefficient is applied.

    Returns:
        Annual lineal amortization in euros, quantised to two decimals.
    """
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
    """Return the LIS art. 30 bis minimum liquid quota floor.

    The floor is 15 % of the non-ZEC base for most regimes, with regime
    overrides: 10 % for new entities, 18 % for financial / hydrocarbon,
    and the microempresa tiered scale (re-derived under
    :func:`_minimum_tax_rate`) for that regime. Returns ``0`` when
    ``minimum_tax_applies`` is ``False`` or ``taxable_base`` is zero.

    Args:
        taxable_base: Base imponible in euros.
        year: Fiscal year (one of 2024, 2025, or 2026).
        regime: Rate regime selector.
        minimum_tax_applies: When ``False``, the helper short-circuits to
            ``Decimal("0.00")`` (LIS art. 30 bis exemptions).
        period_days: Length of the fiscal period in days.
        zec_eligible_base: Subset of ``taxable_base`` taxed under ZEC,
            excluded from the minimum-quota base.

    Returns:
        Minimum liquid quota in euros, quantised to two decimals.

    Raises:
        ValueError: If any input is out of range or inconsistent.
    """
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
    """Return the whole-percent flat rate for a non-tiered regime / year."""
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
    """Apply the year-specific microempresa first-band / rest-band rate scale."""
    first_rate, rest_rate = _microenterprise_rates(year)
    if minimum_tax_scale:
        first_rate = _minimum_tax_rate(first_rate)
        rest_rate = _minimum_tax_rate(rest_rate)
    first_band = min(taxable_base, _MICRO_BAND * Decimal(period_days) / Decimal(365))
    rest = taxable_base - first_band
    return _percent(first_band, first_rate) + _percent(rest, rest_rate)


def _microenterprise_rates(year: int) -> tuple[Decimal, Decimal]:
    """Return the ``(first_band_rate, rest_band_rate)`` pair for the microempresa scale."""
    if year == 2025:
        return Decimal("21.00"), Decimal("22.00")
    if year == 2026:
        return Decimal("19.00"), Decimal("21.00")
    return Decimal("23.00"), Decimal("23.00")


def _minimum_tax_rate(rate: Decimal) -> Decimal:
    """Scale a flat rate to the LIS art. 30 bis 15/25 minimum-quota rate, rounded up."""
    return (rate * Decimal("15") / Decimal("25")).quantize(Decimal("1"), rounding=ROUND_CEILING)


def _percent(base: Decimal, rate: Decimal) -> Decimal:
    """Multiply ``base`` by a whole-percent ``rate`` (i.e., divide by :data:`_ONE_HUNDRED`)."""
    return base * rate / _ONE_HUNDRED


def _round_money(value: Decimal) -> Decimal:
    """Quantise ``value`` to two decimals with :data:`decimal.ROUND_HALF_UP`."""
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _validate_common_inputs(*, taxable_base: Decimal, year: int, period_days: int) -> None:
    """Reject negative bases, unsupported years, and out-of-range period lengths."""
    if taxable_base < 0:
        raise ValueError("taxable_base cannot be negative")
    if year not in {2024, 2025, 2026}:
        raise ValueError("Modelo 200 helper covers only 2024, 2025, and 2026")
    _validate_period_days(period_days)


def _validate_period_days(period_days: int) -> None:
    """Reject ``period_days`` values outside the inclusive ``[1, 365]`` range."""
    if period_days < 1 or period_days > 365:
        raise ValueError("period_days must be between 1 and 365")
