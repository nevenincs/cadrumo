"""An unanswered binding names no box the filer typed, and still names every other box it feeds.

Modelo 130 box 05 carries the earlier quarters' pagos fraccionados from the
returns filed for them. With none held, the binding that feeds box 05 is
unanswered. A typed box 05 is that box's value, so the binding row would call a
valued box empty; an untyped box 05 stays a gap and keeps its row. Read over the
published registry and its printed boxes, in every supported filing year.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import sole_bound_casilla
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ..printed_boxes import snapshot_printed_boxes
from ..projection_unresolved import unresolved_binding_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_CARRY_BINDING = "modelo-130-pagos-fraccionados-anteriores"
_CARRY_BOX = "05"


def _supported_years() -> tuple[int, ...]:
    supported = published_supported_filing_years()
    assert supported is not None
    return tuple(supported.years)


@pytest.mark.parametrize("filing_year", _supported_years())
def test_a_typed_box_drops_only_the_row_of_the_binding_that_feeds_it(
    filing_year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    snapshot = published_snapshot("130", filing_year=filing_year, period="3T")
    boxes = snapshot_printed_boxes(authority_operation, snapshot)
    binding_ids = tuple(binding.id for binding in snapshot.revision.bindings)
    assert sole_bound_casilla(snapshot.revision, _CARRY_BINDING) == _CARRY_BOX

    untyped = unresolved_binding_rows(binding_ids, (), snapshot.revision, boxes)
    typed = unresolved_binding_rows(binding_ids, (), snapshot.revision, boxes, typed_casilla_ids={_CARRY_BOX})

    carry_rows = [row for row in untyped if row.binding_id == _CARRY_BINDING]
    assert [(row.casilla_id, row.box) for row in carry_rows] == [(_CARRY_BOX, boxes.number(_CARRY_BOX))]
    assert _CARRY_BOX not in {row.casilla_id for row in typed}
    assert typed == tuple(row for row in untyped if row.casilla_id != _CARRY_BOX)
