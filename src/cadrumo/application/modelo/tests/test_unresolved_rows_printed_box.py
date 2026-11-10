"""A box left without a figure is named by the number its form prints, never by its internal id.

A working figure such as Modelo 130's negative balance carried to later
periods prints no number on the form, so its row serves no box; a printed box
serves the number the form prints. Both read through the same printed-box
reader the work form uses, over the published registry and its layout.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..printed_boxes import snapshot_printed_boxes
from ..projection_unresolved import (
    unresolved_binding_rows,
    unresolved_casilla_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_WORKING_FIGURE = "saldo-negativo-fin-periodo"


def test_a_working_figure_serves_no_box_and_a_printed_box_serves_its_number(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot = published_snapshot("130", filing_year=filing_year_envelope().horizon, period="1T")
    boxes = snapshot_printed_boxes(authority_operation, snapshot)
    nothing_worked_out = RegistryCalculationResult(modelo=snapshot.modelo.id, revision=snapshot.revision.id)

    rows = {row.casilla_id: row for row in unresolved_casilla_rows(nothing_worked_out, snapshot.revision, boxes)}

    assert _WORKING_FIGURE in rows
    assert rows[_WORKING_FIGURE].box is None
    printed = [row for row in rows.values() if boxes.prints(row.casilla_id)]
    assert printed
    for row in printed:
        assert row.box == boxes.number(row.casilla_id)
        assert row.box is not None and row.box.isdigit()


def test_an_unresolved_binding_serves_the_number_of_the_box_it_feeds(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot = published_snapshot("130", filing_year=filing_year_envelope().horizon, period="1T")
    boxes = snapshot_printed_boxes(authority_operation, snapshot)
    binding_ids = tuple(binding.id for binding in snapshot.revision.bindings)

    rows = unresolved_binding_rows(binding_ids, (), snapshot.revision, boxes)

    assert rows
    for row in rows:
        assert row.box == boxes.number(row.casilla_id)
