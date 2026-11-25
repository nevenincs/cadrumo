"""The one activity's inventory book fills the return's activity casillas 0177, 0181 and 0182.

The gastos total sums those casillas, so a book's purchases and stock variation
reach it only through them. With several activities no book's row is the
return's one activity, and each casilla stays unresolved instead of a sum or zero.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.aggregation.tests.test_inventory_source import inventory_ledger
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    published_work_profile_declaring_activities,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ..inventory import InventorySourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

YEAR = newest_authored_edition("100")
_ACTIVITY_CASILLAS = {validated_casilla_id(casilla) for casilla in ("0177", "0181", "0182")}


class _Books:
    def __init__(self, *activities: str) -> None:
        self.document = InventoryLedgerDocument(ledgers=tuple(inventory_ledger(activity) for activity in activities))

    def load(self) -> InventoryLedgerDocument:
        return self.document


def _resolve(*activities: str) -> CalculationSourceResolution:
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=YEAR,
        period=Period.from_year_and_code(YEAR, "0A"),
        revision=published_snapshot("100", filing_year=YEAR, period="0A").revision,
        profile=published_work_profile_declaring_activities(len(activities)),
    )
    return InventorySourceResolver(inventory_repository=_Books(*activities)).resolve(context)


def test_the_one_activity_book_fills_its_activity_casillas_from_its_row() -> None:
    resolution = _resolve("comercio")

    # The book opens at 100.00, buys 100.00 and closes on its movements at 200.00.
    assert dict(resolution.bound_inputs_by_casilla_id) == {
        validated_casilla_id("0177"): Decimal("100.00"),
        validated_casilla_id("0181"): Decimal("100.00"),
        validated_casilla_id("0182"): Decimal("0.00"),
    }
    assert resolution.unresolved_binding_ids == ()
    assert [row.contributor_source_kind for row in resolution.provenance] == [BindingSourceKind.INVENTORY.value]


def test_several_activities_keep_their_rows_and_leave_the_activity_casillas_unresolved() -> None:
    resolution = _resolve("alpha", "zeta")

    assert dict(resolution.bound_inputs_by_casilla_id) == {}
    assert len(resolution.row_binding_values) == 6
    unresolved = [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unresolved_binding"]
    assert {diagnostic.casilla_id for diagnostic in unresolved} == _ACTIVITY_CASILLAS
    assert all(diagnostic.binding_id is not None and diagnostic.remedy for diagnostic in unresolved)
