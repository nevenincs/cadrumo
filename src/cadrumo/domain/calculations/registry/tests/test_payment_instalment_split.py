"""The two-instalment payment is a dated registry fact: which modelos admit it, from when, and the first share.

The expectations are RD 439/2007 art. 62.2 as the Orden approving the Modelo
100 of each ejercicio and the Manual práctico de Renta of that ejercicio
restate it: 60 per cent on filing, for the Modelo 100, in every ejercicio the
registry supports. The years come from the registry's support envelope, never
from a list here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..authority import PinnedAuthorityOperation
from ..payment_instalment_split import first_instalment_share, two_instalments_declared

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _supported_years(operation: PinnedAuthorityOperation) -> range:
    support = operation.supported_filing_years()
    return range(support.floor, support.horizon + 1)


def test_the_modelo_100_result_of_every_supported_year_may_be_split_sixty_forty(
    operation: PinnedAuthorityOperation,
) -> None:
    years = _supported_years(operation)
    assert len(years) > 1

    for year in years:
        period_day = date(year, 12, 31)
        assert two_instalments_declared("100", period_day=period_day, authority=operation), year
        assert first_instalment_share("100", period_day=period_day, authority=operation) == Decimal("0.60"), year


def test_the_split_is_declared_on_the_first_and_the_last_day_of_the_floor_year(
    operation: PinnedAuthorityOperation,
) -> None:
    """The variant of an ejercicio starts on its first day and holds to its last, with no gap at the floor."""
    floor = operation.supported_filing_years().floor

    for day in (date(floor, 1, 1), date(floor, 12, 31)):
        assert two_instalments_declared("100", period_day=day, authority=operation), day


def test_a_year_above_the_horizon_carries_the_split_forward(operation: PinnedAuthorityOperation) -> None:
    """The newest ejercicio's variant has no end, as the newest revision is carried forward above the horizon."""
    above = date(operation.supported_filing_years().horizon + 5, 12, 31)

    assert two_instalments_declared("100", period_day=above, authority=operation)
    assert first_instalment_share("100", period_day=above, authority=operation) == Decimal("0.60")


@pytest.mark.parametrize("modelo", ["303", "130", "200"])
def test_no_other_modelo_declares_the_split(operation: PinnedAuthorityOperation, modelo: str) -> None:
    for year in _supported_years(operation):
        period_day = date(year, 12, 31)
        assert not two_instalments_declared(modelo, period_day=period_day, authority=operation)
        assert first_instalment_share(modelo, period_day=period_day, authority=operation) is None
