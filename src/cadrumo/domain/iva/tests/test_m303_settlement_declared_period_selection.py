"""Modelo 303 annual settlement follows the periods its selected revisions declare."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....core.period import Period
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.errors import RegistryValidationError
from ..m303_settlement import is_m303_annual_settlement_period, m303_annual_settlement_period_order

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.mark.parametrize(
    ("filing_year", "token", "is_settlement"),
    (
        pytest.param(2026, "4T", True, id="2026-terminal-quarter"),
        pytest.param(2026, "1T", False, id="2026-first-quarter"),
        pytest.param(2026, "3T", False, id="2026-midyear-quarter"),
        pytest.param(2025, "4T", True, id="2025-terminal-quarter"),
        pytest.param(2024, "2T", False, id="2024-split-design-early-revision-last-quarter"),
        pytest.param(2024, "4T", True, id="2024-split-design-terminal-quarter"),
    ),
)
def test_quarterly_settlement_is_the_terminal_quarter_the_year_declares(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
    token: str,
    is_settlement: bool,
) -> None:
    period = Period.from_year_and_code(filing_year, token)

    assert is_m303_annual_settlement_period(period, authority=authority_operation) is is_settlement
    assert m303_annual_settlement_period_order(period, authority=authority_operation) == (0 if is_settlement else None)


def test_modelo_390_annual_token_is_refused_rather_than_ordered(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(RegistryValidationError, match="quarterly or monthly liquidation period"):
        m303_annual_settlement_period_order(Period.from_year_and_code(2026, "0A"), authority=authority_operation)
