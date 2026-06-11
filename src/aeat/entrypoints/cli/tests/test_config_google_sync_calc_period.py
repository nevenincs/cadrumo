"""Period boundary tests for ``config google sync calc`` commands."""

from __future__ import annotations

import pytest

from ....core import Period
from .._config._google_sync_calc import _filing_period_or_refusal, _load_snapshot
from .._errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_google_sync_calc_snapshot_loader_accepts_typed_period() -> None:
    """The local snapshot loader receives a typed Period, not raw year/period text."""

    period = _filing_period_or_refusal(modelo="303", period="1T", year=2026)

    snapshot = _load_snapshot("303", period)

    assert period == Period.from_year_and_code(2026, "1T")
    assert snapshot.filing_period == period
    assert snapshot.filing_year == period.filing_year
    assert snapshot.period == period.registry_token


def test_google_sync_calc_period_refuses_combined_shape() -> None:
    """Calendar-shaped period input refuses before registry snapshot lookup."""

    with pytest.raises(CliRefusedBoundaryError) as raised:
        _filing_period_or_refusal(modelo="303", period="2026Q1", year=2026)

    refusal = raised.value
    assert refusal.context is not None
    assert refusal.context["period"] == "2026Q1"
    assert refusal.context["year"] == 2026
