"""Completeness and independence gates for activity-asset acceptance evidence."""

from __future__ import annotations

from decimal import Decimal

import pytest

from dev.acceptance.assets.evidence import (
    ASSET_ACCEPTANCE_EVIDENCE,
    AcceptanceStatus,
    annual_linear_charge_oracle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_every_assets_scenario_has_one_truthful_terminal_state() -> None:
    assert tuple(item.scenario for item in ASSET_ACCEPTANCE_EVIDENCE) == tuple(f"AS{number}" for number in range(1, 13))
    assert all(item.evidence for item in ASSET_ACCEPTANCE_EVIDENCE)
    assert all(
        (item.blocker is not None) == (item.status is AcceptanceStatus.BLOCKED) for item in ASSET_ACCEPTANCE_EVIDENCE
    )


def test_full_year_oracle_is_independent_and_pins_the_repaired_two_thousand_euro_case() -> None:
    assert annual_linear_charge_oracle(
        allocated_basis=Decimal("2000.00"),
        annual_rate=Decimal("0.26"),
    ) == Decimal("520.00")
