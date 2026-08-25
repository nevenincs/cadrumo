"""Period boundary tests for ``config google sync calc`` commands."""

from __future__ import annotations

import pytest

from ....core import Period
from .._config._google_sync_calc import filing_period_or_refusal, load_snapshot
from ..errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_google_sync_calc_snapshot_loader_accepts_typed_period() -> None:
    """The local snapshot loader receives a typed Period, not raw year/period text."""

    period = filing_period_or_refusal(modelo="303", period="1T", year=2026)

    snapshot = load_snapshot("303", period)

    assert period == Period.from_year_and_code(2026, "1T")
    assert snapshot.filing_period == period
    assert snapshot.filing_year == period.filing_year
    assert snapshot.period == period.registry_token


def test_google_sync_calc_period_refuses_combined_shape() -> None:
    """Calendar-shaped period input refuses before registry snapshot lookup."""
    year = 2026
    combined_period = f"{year}Q1"

    with pytest.raises(CliRefusedBoundaryError) as raised:
        filing_period_or_refusal(modelo="303", period=combined_period, year=year)

    refusal = raised.value
    assert refusal.context is not None
    assert refusal.context["period"] == combined_period
    assert refusal.context["year"] == year
