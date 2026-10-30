"""Independent fixture-oracle checks for the asset export acceptance runner."""

from __future__ import annotations

from decimal import Decimal

import pytest

from dev.acceptance.assets.export_journey import _asset_overlay_oracle

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_export_oracle_overlays_one_asset_claim_on_the_proven_income_control() -> None:
    """The fixture preserves control facts and asserts only the €300 asset delta."""
    oracle = _asset_overlay_oracle()

    assert oracle.control.annual_oracle.activity_income == Decimal("12000.00")
    assert oracle.control.annual_oracle.deductible_expenses == Decimal("2400.00")
    assert oracle.m130_q4_control_expenses == "2400.00"
    assert oracle.m130_q4_asset_expenses == "2700.00"
    assert oracle.m100_control_total_expenses == "2400.00"
    assert oracle.m100_asset_total_expenses == "2700.00"
    assert oracle.m100_control_material == "0.00"
    assert oracle.m100_asset_material == "300.00"
    assert oracle.m100_intangible == "0.00"


def test_export_oracle_accrues_the_element_by_days_to_each_quarter_end() -> None:
    """Hand-worked: 300.00 x 90, 181, 273 and 365 days over 365, rounded to cents."""
    oracle = _asset_overlay_oracle()

    assert oracle.m130_asset_accrual_by_period == (
        ("1T", "73.97"),
        ("2T", "148.77"),
        ("3T", "224.38"),
        ("4T", "300.00"),
    )
