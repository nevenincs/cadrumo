"""Which movement kinds bring stock in at an acquisition cost."""

from __future__ import annotations

import pytest

from ..records import MovementKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("kind", "adds_costed_stock"),
    [
        (MovementKind.OPENING, True),
        (MovementKind.PURCHASE, True),
        (MovementKind.COGS, False),
        (MovementKind.COUNT, False),
    ],
)
def test_only_opening_and_purchase_movements_add_costed_stock(kind: MovementKind, adds_costed_stock: bool) -> None:
    assert kind.adds_costed_stock is adds_costed_stock


def test_every_movement_kind_is_classified() -> None:
    assert {kind for kind in MovementKind if kind.adds_costed_stock} == {MovementKind.OPENING, MovementKind.PURCHASE}
