"""The two-instalment payment is a dated registry fact: which modelos admit it, from when, and the first share.

The expectations are RD 439/2007 art. 62.2 as the Orden approving the 2025
Modelo 100 and the Manual práctico de Renta 2025 restate it: 60 per cent on
filing, for the Modelo 100, from the 2025 ejercicio those sources cover.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..authority import PinnedAuthorityOperation
from ..payment_instalment_split import first_instalment_share, two_instalments_declared

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RENTA_2025 = date(2025, 12, 31)


def test_the_modelo_100_result_of_2025_may_be_split_sixty_forty(operation: PinnedAuthorityOperation) -> None:
    assert two_instalments_declared("100", period_day=_RENTA_2025, authority=operation)
    assert first_instalment_share("100", period_day=_RENTA_2025, authority=operation) == Decimal("0.60")


@pytest.mark.parametrize("modelo", ["303", "130", "200"])
def test_no_other_modelo_declares_the_split(operation: PinnedAuthorityOperation, modelo: str) -> None:
    assert not two_instalments_declared(modelo, period_day=_RENTA_2025, authority=operation)
    assert first_instalment_share(modelo, period_day=_RENTA_2025, authority=operation) is None


def test_a_period_before_the_fact_starts_declares_no_split(operation: PinnedAuthorityOperation) -> None:
    """The last day of 2024 lies before the variant the 2025 sources ground."""
    renta_2024 = date(2024, 12, 31)

    assert not two_instalments_declared("100", period_day=renta_2024, authority=operation)
    assert first_instalment_share("100", period_day=renta_2024, authority=operation) is None
