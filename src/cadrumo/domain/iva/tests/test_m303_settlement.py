"""Legal Modelo 303 annual-settlement timing for IVA regularisations."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from ....core.period import Period
from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.errors import RegistryValidationError
from ..m303_settlement import (
    is_m303_annual_settlement_period,
    m303_annual_settlement_order_key,
    m303_annual_settlement_period_order,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module", autouse=True)
def _registry_authority_scope() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


@pytest.mark.parametrize(
    ("year", "token", "expected_order"),
    (
        pytest.param(2026, "4T", 0, id="quarterly-final-quarter-settles"),
        pytest.param(2026, "1T", None, id="quarterly-first-quarter-does-not-settle"),
        pytest.param(2026, "3T", None, id="quarterly-midyear-quarter-does-not-settle"),
        pytest.param(2026, "12", 0, id="monthly-final-month-settles"),
        pytest.param(2026, "01", None, id="monthly-first-month-does-not-settle"),
        pytest.param(2026, "11", None, id="monthly-penultimate-month-does-not-settle"),
        pytest.param(2024, "1T", None, id="split-year-early-design-quarter-does-not-settle"),
        pytest.param(2024, "4T", 0, id="split-year-late-design-final-quarter-settles"),
        pytest.param(2024, "08", None, id="split-year-early-design-month-does-not-settle"),
        pytest.param(2024, "12", 0, id="split-year-late-design-final-month-settles"),
    ),
)
def test_m303_settlement_is_the_final_declared_period_of_the_filers_cadence(
    year: int,
    token: str,
    expected_order: int | None,
) -> None:
    period = Period.from_year_and_code(year, token)

    assert m303_annual_settlement_period_order(period) == expected_order
    assert is_m303_annual_settlement_period(period) is (expected_order is not None)


@pytest.mark.parametrize(
    "token",
    (
        pytest.param("0A", id="annual-token-belongs-to-modelo-390"),
        pytest.param("4P", id="instalment-token-has-no-liquidation-span"),
    ),
)
def test_m303_settlement_refuses_non_liquidation_periods(token: str) -> None:
    period = Period.from_year_and_code(2026, token)

    with pytest.raises(RegistryValidationError, match="quarterly or monthly liquidation period"):
        m303_annual_settlement_period_order(period)


def test_m303_annual_settlement_order_key_orders_settlement_captures_by_time() -> None:
    earlier = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
    later = datetime(2026, 1, 30, 10, 0, tzinfo=UTC)
    quarterly = Period.from_year_and_code(2025, "4T")
    monthly = Period.from_year_and_code(2025, "12")

    quarterly_later = m303_annual_settlement_order_key(quarterly, later)
    quarterly_earlier = m303_annual_settlement_order_key(quarterly, earlier)
    monthly_earlier = m303_annual_settlement_order_key(monthly, earlier)
    assert quarterly_later is not None
    assert quarterly_earlier is not None
    assert monthly_earlier is not None
    assert quarterly_later > quarterly_earlier
    assert m303_annual_settlement_order_key(Period.from_year_and_code(2025, "2T"), later) is None
    assert m303_annual_settlement_order_key(Period.from_year_and_code(2025, "06"), later) is None
