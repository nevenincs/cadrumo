"""The multi-year scenario oracle agrees with hand arithmetic on its own facts.

Expected values are worked by hand from the scenario's published bases and the
21 % general rate, never read back from the functions under test, so a change to
the scenario that moves a total has to move these numbers deliberately.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..scenario import (
    ASSETS,
    IVA_INVESTMENT_GOOD_FLOOR,
    QUARTERS,
    YEARS,
    WithholdingDuty,
    build_year,
    m303_quarter,
    m303_results_with_compensation,
    withholding_practised,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_first_quarter_2022_input_iva_is_current_because_the_laptop_is_below_the_investment_floor() -> None:
    # Issued base 3000 x 21 % = 630.00. Received: material 150 + software 60 +
    # adviser 300 + rent 900 = 1410 x 21 % = 296.10, laptop 1500 x 21 % = 315.00,
    # exempt insurance 0.00.
    quarter = m303_quarter(2022, "1T")

    assert quarter.devengado == Decimal("630.00")
    assert quarter.deducible_current == Decimal("611.10")
    assert quarter.deducible_investment == Decimal("0")


def test_furniture_above_the_floor_is_the_only_investment_input_and_opens_a_compensation_chain() -> None:
    # 2023 2T: issued 1000 x 21 % = 210.00; current 296.10 + training 2000 x 21 % = 420.00;
    # furniture 3600 x 21 % = 756.00 investment. 1T 315.00 - 296.10 = 18.90;
    # 2T 210.00 - 1472.10 = -1262.10 carried; 3T 924.00 - 296.10 - 1262.10 = -634.20
    # carried; 4T 945.00 - 296.10 - 634.20 = 14.70.
    second = m303_quarter(2023, "2T")

    assert second.deducible_current == Decimal("716.10")
    assert second.deducible_investment == Decimal("756.00")
    assert m303_results_with_compensation(2023) == (
        Decimal("18.90"),
        Decimal("0"),
        Decimal("0"),
        Decimal("14.70"),
    )


def test_every_scenario_year_closes_its_fourth_quarter_without_a_cross_year_carry() -> None:
    for year in YEARS:
        assert len(m303_results_with_compensation(year)) == len(QUARTERS)


def test_only_tangible_assets_above_the_floor_are_iva_investment_goods() -> None:
    investment = {asset.asset_id for asset in ASSETS if asset.is_iva_investment_good}

    assert investment == {"furniture-2023"}
    assert all(
        asset.basis > IVA_INVESTMENT_GOOD_FLOOR and asset.kind == "material"
        for asset in ASSETS
        if asset.asset_id in investment
    )


def test_quarterly_professional_withholding_is_fifteen_percent_of_one_adviser() -> None:
    base, withholding, recipients = withholding_practised(2025, "3T", WithholdingDuty.PROFESSIONAL)

    assert (base, withholding, recipients) == (Decimal("300.00"), Decimal("45.00"), 1)


def test_rent_withholding_is_nineteen_percent_every_quarter() -> None:
    for period in QUARTERS:
        base, withholding, recipients = withholding_practised(2024, period, WithholdingDuty.URBAN_RENT)
        assert (base, withholding, recipients) == (Decimal("900.00"), Decimal("171.00"), 1)


def test_the_exempt_insurance_premium_carries_no_iva() -> None:
    insurance = next(item for item in build_year(2022).received if item.key == "insurance-2022")

    assert insurance.iva == Decimal("0")
    assert insurance.base == Decimal("480.00")
