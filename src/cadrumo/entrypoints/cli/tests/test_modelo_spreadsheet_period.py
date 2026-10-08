"""Period boundary tests for ``config google sync calc`` commands."""

from __future__ import annotations

import pytest

from ....application.operations.public_period import PublicPeriod
from ....core.period import Period
from ..errors import CliRefusedBoundaryError
from ..modelo_spreadsheet_cli import filing_period_or_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_modelo_spreadsheet_cli_converts_the_filing_coordinate_to_a_closed_period() -> None:
    """The registered request receives the same canonical period the CLI parsed."""

    period = filing_period_or_refusal(modelo="303", period="1T", year=2026)
    public_period = PublicPeriod.from_period(period)

    assert period == Period.from_year_and_code(2026, "1T")
    assert public_period.filing_year == period.filing_year
    assert public_period.code == period.registry_token


def test_modelo_spreadsheet_cli_period_refuses_combined_shape() -> None:
    """Calendar-shaped period input refuses before registry snapshot lookup."""
    year = 2026
    combined_period = f"{year}Q1"

    with pytest.raises(CliRefusedBoundaryError) as raised:
        filing_period_or_refusal(modelo="303", period=combined_period, year=year)

    refusal = raised.value
    assert refusal.context is not None
    assert refusal.context["period"] == combined_period
    assert refusal.context["year"] == year
