"""Legal Modelo 303 annual-settlement timing for IVA regularisations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.period import Period
from ..m303_settlement import (
    is_m303_annual_settlement_period,
    m303_annual_settlement_order_key,
    m303_annual_settlement_period_order,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("token", "expected_order"),
    (
        pytest.param("4T", 0, id="quarterly-year-close"),
        pytest.param("0A", 1, id="annual-only-year-close"),
        pytest.param("1T", None, id="first-quarter-is-not-settlement"),
        pytest.param("3T", None, id="midyear-quarter-is-not-settlement"),
        pytest.param("12", None, id="monthly-last-period-is-not-this-regularisation"),
    ),
)
def test_m303_annual_settlement_policy_is_narrower_than_generic_last_period(
    token: str,
    expected_order: int | None,
) -> None:
    period = Period.from_year_and_code(2026, token)

    assert m303_annual_settlement_period_order(period) == expected_order
    assert is_m303_annual_settlement_period(period) is (expected_order is not None)


def test_m303_annual_settlement_order_key_prioritises_legal_form_then_capture_time() -> None:
    earlier = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
    later = datetime(2026, 1, 30, 10, 0, tzinfo=UTC)
    quarterly = Period.from_year_and_code(2025, "4T")
    annual = Period.from_year_and_code(2025, "0A")

    annual_earlier = m303_annual_settlement_order_key(annual, earlier)
    quarterly_later = m303_annual_settlement_order_key(quarterly, later)
    quarterly_earlier = m303_annual_settlement_order_key(quarterly, earlier)
    assert annual_earlier is not None
    assert quarterly_later is not None
    assert quarterly_earlier is not None
    assert annual_earlier > quarterly_later
    assert quarterly_later > quarterly_earlier
