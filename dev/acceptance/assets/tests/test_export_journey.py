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
