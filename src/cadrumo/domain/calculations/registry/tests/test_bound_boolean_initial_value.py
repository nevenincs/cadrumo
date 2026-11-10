"""A bound yes/no box answers from its profile fact, and an unstated fact is no answer at all."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import validated_casilla_id
from ..authority import PinnedAuthorityOperation
from ..formula_initial_values import initial_values
from ..ids import BindingId
from .authored_editions import newest_authored_edition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_BOX = validated_casilla_id("0169")
_BINDING: BindingId = "renta-profile-activity-cash-criterion-0169"
_YEAR = newest_authored_edition("100")
_PERIOD = "0A"


def _seed(operation: PinnedAuthorityOperation, *, stated: bool | None, supplied: Decimal | None = None):
    revision = operation.snapshot("100", filing_year=_YEAR, period=_PERIOD).revision
    only_the_box = tuple(casilla for casilla in revision.casillas if casilla.id == _BOX)
    return initial_values(
        revision.model_copy(update={"casillas": only_the_box}),
        {} if supplied is None else {_BOX: supplied},
        binding_values={},
        target_period=_PERIOD,
        boolean_binding_values={} if stated is None else {_BINDING: stated},
    )


@pytest.mark.parametrize(("stated", "encoded"), [(True, Decimal(1)), (False, Decimal(0))])
def test_a_stated_fact_fills_the_box_in_the_record_encoding(
    operation: PinnedAuthorityOperation, stated: bool, encoded: Decimal
) -> None:
    seeded = _seed(operation, stated=stated)

    assert seeded.values[_BOX] == encoded
    assert _BOX not in seeded.absent_by_design_casilla_ids


def test_an_unstated_fact_leaves_the_box_absent_rather_than_no(operation: PinnedAuthorityOperation) -> None:
    seeded = _seed(operation, stated=None)

    assert seeded.values[_BOX] == Decimal(0)
    assert _BOX in seeded.absent_by_design_casilla_ids


def test_a_value_supplied_for_the_box_is_never_replaced(operation: PinnedAuthorityOperation) -> None:
    seeded = _seed(operation, stated=False, supplied=Decimal(1))

    assert seeded.values[_BOX] == Decimal(1)
    assert _BOX not in seeded.absent_by_design_casilla_ids
