"""Period-context contracts used by declaration verification fixtures."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.period import PeriodError
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .verification_chain_support import period_to_date

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_EXERCISE = filing_year_envelope().horizon


@pytest.mark.parametrize(
    ("period", "expected"),
    (
        ("1T", date(_EXERCISE, 3, 31)),
        ("EXT-1T", date(_EXERCISE, 3, 31)),
        ("2P", date(_EXERCISE, 10, 31)),
    ),
)
def test_verification_period_context_uses_typed_calculation_date(period: str, expected: date) -> None:
    assert period_to_date(_EXERCISE, period) == expected


def test_verification_period_context_rejects_unknown_registry_tokens() -> None:
    with pytest.raises(PeriodError, match="cannot build a period"):
        period_to_date(_EXERCISE, "not-a-period")
