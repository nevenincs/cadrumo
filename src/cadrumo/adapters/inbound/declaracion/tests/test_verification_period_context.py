"""Period-context contracts used by declaration verification fixtures."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.period import PeriodError
from ._verification_chain_support import _period_to_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize(
    ("period", "expected"),
    (
        ("1T", date(2026, 3, 31)),
        ("EXT-1T", date(2026, 3, 31)),
        ("2P", date(2026, 10, 31)),
    ),
)
def test_verification_period_context_uses_typed_calculation_date(period: str, expected: date) -> None:
    assert _period_to_date(2026, period) == expected


def test_verification_period_context_rejects_unknown_registry_tokens() -> None:
    with pytest.raises(PeriodError, match="cannot build a period"):
        _period_to_date(2026, "not-a-period")
