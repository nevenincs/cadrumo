"""A baja's amounts on the command line are read with the canonical euro grammar.

``1.000`` is how Spanish writes one thousand; a parser that takes it as one
euro states proceeds a thousand times too small, so it is refused like every
other hand-typed euro amount, as are scientific and comma forms.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import typer

from ....core.time.clock import today_madrid
from ..actividad_asset_commands import _disposal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _dispose(*, proceeds: str = "0.00", costs: str = "0.00", market_value: str | None = None):
    return _disposal(
        today_madrid().isoformat(),
        "sale",
        proceeds,
        costs,
        market_value,
        None,
        None,
    )


@pytest.mark.parametrize("written", ["1500", "1500.5", "1500.50", "0.00"])
def test_a_canonical_amount_is_read_as_written(written: str) -> None:
    snapshot = _dispose(proceeds=written, costs=written, market_value=written)

    assert Decimal(snapshot.proceeds.decimal) == Decimal(written)
    assert Decimal(snapshot.transmission_costs.decimal) == Decimal(written)
    assert snapshot.market_value is not None
    assert Decimal(snapshot.market_value.decimal) == Decimal(written)


@pytest.mark.parametrize("written", ["1.000", "1e3", "1.234,50", "1,5", "-10.00", "NaN"])
@pytest.mark.parametrize("field", ["proceeds", "costs", "market_value"])
def test_a_non_canonical_amount_is_refused_in_every_disposal_field(field: str, written: str) -> None:
    with pytest.raises(typer.BadParameter):
        _dispose(**{field: written})
