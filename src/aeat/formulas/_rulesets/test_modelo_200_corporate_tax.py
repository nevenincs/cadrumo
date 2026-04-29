"""Unit tests for Modelo 200 corporate-tax statutory helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .modelo_100 import AssetClass
from .modelo_200_corporate_tax import (
    Modelo200DepreciableAsset,
    Modelo200TaxRegime,
    modelo_200_bin_compensation_cap,
    modelo_200_effective_rate,
    modelo_200_max_lineal_amortization,
    modelo_200_minimum_liquid_quota,
    modelo_200_tax_due,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


@pytest.mark.parametrize(
    ("year", "regime", "base", "expected_tax", "expected_rate"),
    [
        (2024, Modelo200TaxRegime.GENERAL, Decimal("100000.00"), Decimal("25000.00"), Decimal("25.00")),
        (2024, Modelo200TaxRegime.MICROENTERPRISE, Decimal("100000.00"), Decimal("23000.00"), Decimal("23.00")),
        (2025, Modelo200TaxRegime.REDUCED_SIZE, Decimal("100000.00"), Decimal("24000.00"), Decimal("24.00")),
        (2025, Modelo200TaxRegime.MICROENTERPRISE, Decimal("125000.00"), Decimal("27000.00"), Decimal("21.60")),
        (2026, Modelo200TaxRegime.REDUCED_SIZE, Decimal("100000.00"), Decimal("23000.00"), Decimal("23.00")),
        (2026, Modelo200TaxRegime.MICROENTERPRISE, Decimal("125000.00"), Decimal("25250.00"), Decimal("20.20")),
        (2026, Modelo200TaxRegime.NEW_ENTITY, Decimal("100000.00"), Decimal("15000.00"), Decimal("15.00")),
    ],
)
def test_modelo_200_rate_regimes_derive_tax_and_printed_effective_rate(
    year: int,
    regime: Modelo200TaxRegime,
    base: Decimal,
    expected_tax: Decimal,
    expected_rate: Decimal,
) -> None:
    """LIS art. 29 and DT 44 rate cases produce casilla 00558/00562 inputs."""
    assert modelo_200_tax_due(taxable_base=base, year=year, regime=regime) == expected_tax
    assert modelo_200_effective_rate(taxable_base=base, year=year, regime=regime) == expected_rate


def test_modelo_200_zec_rate_applies_only_to_zec_eligible_base() -> None:
    """LIS art. 29.7 + Ley 19/1994 art. 43 apply 4% only to ZEC base."""
    tax_due = modelo_200_tax_due(
        taxable_base=Decimal("300000.00"),
        year=2026,
        regime=Modelo200TaxRegime.ZEC,
        zec_eligible_base=Decimal("80000.00"),
    )
    assert tax_due == Decimal("58200.00")
    assert modelo_200_effective_rate(
        taxable_base=Decimal("300000.00"),
        year=2026,
        regime=Modelo200TaxRegime.ZEC,
        zec_eligible_base=Decimal("80000.00"),
    ) == Decimal("19.40")


@pytest.mark.parametrize(
    ("base", "pending", "expected"),
    [
        (Decimal("900000.00"), Decimal("900000.00"), Decimal("900000.00")),
        (Decimal("2000000.00"), Decimal("2000000.00"), Decimal("1400000.00")),
        (Decimal("2000000.00"), Decimal("100000.00"), Decimal("100000.00")),
    ],
)
def test_modelo_200_bin_compensation_cap_general_rule(
    base: Decimal,
    pending: Decimal,
    expected: Decimal,
) -> None:
    """LIS art. 26 allows 70% of base, with a 1,000,000 EUR floor."""
    assert modelo_200_bin_compensation_cap(base_before_bin=base, pending_bin=pending) == expected


def test_modelo_200_bin_compensation_cap_short_period_and_new_entity_cases() -> None:
    """LIS art. 26 prorates the floor and excludes new entities for early years."""
    assert modelo_200_bin_compensation_cap(
        base_before_bin=Decimal("600000.00"),
        pending_bin=Decimal("600000.00"),
        period_days=183,
    ) == Decimal("501369.86")
    assert modelo_200_bin_compensation_cap(
        base_before_bin=Decimal("600000.00"),
        pending_bin=Decimal("600000.00"),
        new_entity_first_positive_periods=True,
    ) == Decimal("600000.00")


@pytest.mark.parametrize(
    ("asset", "expected"),
    [
        (
            Modelo200DepreciableAsset(
                asset_class=AssetClass.EDIFICIOS_INDUSTRIALES,
                acquisition_cost=Decimal("500000.00"),
                land_value=Decimal("125000.00"),
            ),
            Decimal("11250.00"),
        ),
        (
            Modelo200DepreciableAsset(
                asset_class=AssetClass.MAQUINARIA_GENERAL,
                acquisition_cost=Decimal("80000.00"),
            ),
            Decimal("9600.00"),
        ),
        (
            Modelo200DepreciableAsset(
                asset_class=AssetClass.ELECTRONICA_INFORMATICA,
                acquisition_cost=Decimal("24000.00"),
            ),
            Decimal("6000.00"),
        ),
    ],
)
def test_modelo_200_lis_art_12_lineal_amortization_examples(
    asset: Modelo200DepreciableAsset,
    expected: Decimal,
) -> None:
    """Representative M200 assets use the shared LIS art. 12 lineal table."""
    assert modelo_200_max_lineal_amortization(asset) == expected


def test_modelo_200_depreciable_asset_rejects_land_above_cost() -> None:
    """The amortization base cannot be negative."""
    with pytest.raises(ValidationError):
        Modelo200DepreciableAsset(
            asset_class=AssetClass.EDIFICIOS_COMERCIALES,
            acquisition_cost=Decimal("100000.00"),
            land_value=Decimal("100000.01"),
        )


@pytest.mark.parametrize(
    ("year", "regime", "base", "expected"),
    [
        (2026, Modelo200TaxRegime.GENERAL, Decimal("1000000.00"), Decimal("150000.00")),
        (2026, Modelo200TaxRegime.NEW_ENTITY, Decimal("1000000.00"), Decimal("100000.00")),
        (2026, Modelo200TaxRegime.FINANCIAL_OR_HYDROCARBON, Decimal("1000000.00"), Decimal("180000.00")),
        (2025, Modelo200TaxRegime.REDUCED_SIZE, Decimal("1000000.00"), Decimal("150000.00")),
        (2026, Modelo200TaxRegime.REDUCED_SIZE, Decimal("1000000.00"), Decimal("140000.00")),
        (2026, Modelo200TaxRegime.MICROENTERPRISE, Decimal("125000.00"), Decimal("15750.00")),
    ],
)
def test_modelo_200_minimum_liquid_quota_lis_art_30_bis(
    year: int,
    regime: Modelo200TaxRegime,
    base: Decimal,
    expected: Decimal,
) -> None:
    """LIS art. 30 bis floors are available when the taxpayer is in scope."""
    assert (
        modelo_200_minimum_liquid_quota(
            taxable_base=base,
            year=year,
            regime=regime,
            minimum_tax_applies=True,
        )
        == expected
    )


def test_modelo_200_minimum_liquid_quota_excludes_zec_base() -> None:
    """LIS art. 30 bis removes ZEC-eligible base from the minimum-tax base."""
    assert modelo_200_minimum_liquid_quota(
        taxable_base=Decimal("300000.00"),
        year=2026,
        regime=Modelo200TaxRegime.GENERAL,
        minimum_tax_applies=True,
        zec_eligible_base=Decimal("80000.00"),
    ) == Decimal("33000.00")
    assert modelo_200_minimum_liquid_quota(
        taxable_base=Decimal("300000.00"),
        year=2026,
        regime=Modelo200TaxRegime.GENERAL,
        minimum_tax_applies=False,
        zec_eligible_base=Decimal("80000.00"),
    ) == Decimal("0.00")
