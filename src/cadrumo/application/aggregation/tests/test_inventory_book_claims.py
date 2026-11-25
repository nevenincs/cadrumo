"""An inventory purchase claiming its ledger row: the row leaves the ledger expenses, and the book's rows wait on claims.

A claimed row is withheld from every ledger expense destination, because the book
carries the purchase into casilla 0181. A claim that does not stand, or a purchase
that states nothing while the year holds ledger expense rows, holds the book's rows
back rather than letting the purchase be deducted twice or not at all.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.aggregation.tests.test_inventory_source import inventory_ledger

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.tipos_actividad import TipoActividad
from ....domain.contribuyente.inventory.ledger_claims import InventoryPurchaseClaim
from ....domain.contribuyente.inventory.records import (
    InventoryLedger,
    MovementRecord,
    PurchaseLedgerRow,
)
from ...modelo.calculation_notes import note_fact_text
from ..activity_asset_expense_reconciliation import (
    LedgerRentaExpenseTreatment,
    book_claimed_purchase_diagnostics,
    classify_ledger_expenses_against_asset_register,
    register_acquisition_transaction_ids,
)
from ..source_mesh import CalculationSourceResolution
from .inventory_book_claims_support import YEAR, claim_ledger_row, expense_row, resolve_book, resolve_books

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_CLAIMED = "a" * 64
_UNCLAIMED = "b" * 64


def _claim(transaction_id: str = _CLAIMED) -> InventoryPurchaseClaim:
    return InventoryPurchaseClaim(
        actividad_id="comercio", year=YEAR, movement_id="BUY-1", transaction_id=transaction_id
    )


def _treatment(transaction_id: str) -> LedgerRentaExpenseTreatment:
    return LedgerRentaExpenseTreatment(
        transaction_id=transaction_id,
        category="compras_mercaderias",
        tax_year=YEAR,
        booked_on=date(YEAR, 2, 10),
        deductible_amount=Decimal("121.00"),
        amortization_labelled=False,
    )


def test_a_claimed_row_leaves_the_ledger_expenses_and_an_unclaimed_row_stays() -> None:
    classified = classify_ledger_expenses_against_asset_register(
        (), (_treatment(_CLAIMED), _treatment(_UNCLAIMED)), inventory_claims=(_claim(),)
    )

    assert [row.transaction_id for row in classified.book_claimed] == [_CLAIMED]
    assert classified.book_claimed[0].movement_id == "BUY-1"
    assert classified.excluded_transaction_ids == {_CLAIMED}
    assert classified.withheld == ()
    assert register_acquisition_transaction_ids((), (_claim(),)) == {_CLAIMED}


def test_without_claims_the_purchase_stays_in_the_expenses_as_modelo_130_needs() -> None:
    classified = classify_ledger_expenses_against_asset_register((), (_treatment(_CLAIMED),))

    assert classified.book_claimed == ()
    assert classified.excluded_transaction_ids == frozenset()


def test_the_book_claimed_note_names_the_row_and_renders_in_every_language() -> None:
    classified = classify_ledger_expenses_against_asset_register(
        (), (_treatment(_CLAIMED),), inventory_claims=(_claim(),)
    )

    (diagnostic,) = book_claimed_purchase_diagnostics(
        classified.book_claimed, source_kind="ledger_renta_gastos_estimacion_directa_aggregation", resolver_id="test"
    )

    assert diagnostic.reason == "inventory_book_claimed_purchase"
    assert diagnostic.source_ref == f"transaction:{_CLAIMED}"
    assert "121.00" in diagnostic.message
    assert diagnostic.fact is not None
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        text = note_fact_text(diagnostic.fact, locale=language)
        assert text
        assert "{" not in text
        assert _CLAIMED not in text


def _stating_no_ledger_row(ledger: InventoryLedger) -> InventoryLedger:
    (purchase,) = ledger.period_movements
    stated = MovementRecord.model_validate({**purchase.model_dump(), "ledger_row": PurchaseLedgerRow.NONE})
    return ledger.model_copy(update={"period_movements": (stated,)})


def _states(resolution: CalculationSourceResolution) -> list[str]:
    return [diagnostic.message.split(":")[0] for diagnostic in resolution.diagnostics]


def test_an_unstated_purchase_holds_the_rows_back_while_the_year_has_ledger_expense_rows() -> None:
    resolution = resolve_book(inventory_ledger("comercio"), expense_row(base="100.00"))

    assert resolution.row_binding_values == {}
    assert set(resolution.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    assert _states(resolution) == ["inventory source purchase_ledger_row_unstated"]
    assert all(diagnostic.remedy for diagnostic in resolution.diagnostics)


def test_an_unstated_purchase_stands_when_the_year_has_no_ledger_expense_rows() -> None:
    resolution = resolve_book(inventory_ledger("comercio"))

    assert resolution.row_binding_values[("inventory-0181", 1)] == Decimal("100.00")


def test_a_standing_claim_lets_the_book_carry_the_purchase_into_0181() -> None:
    row = expense_row(base="100.00")

    resolution = resolve_book(claim_ledger_row(inventory_ledger("comercio"), row.transaction_id), row)

    assert resolution.row_binding_values[("inventory-0181", 1)] == Decimal("100.00")
    assert resolution.unresolved_binding_ids == ()


def test_a_claim_that_does_not_match_its_row_holds_the_rows_back() -> None:
    row = expense_row(base="100.01")

    resolution = resolve_book(claim_ledger_row(inventory_ledger("comercio"), row.transaction_id), row)

    assert resolution.row_binding_values == {}
    assert _states(resolution) == ["inventory source purchase_ledger_claim_refused"]


_RETAIL = TipoActividad.A03_RESTO_EMPRESARIALES
_CRAFT = TipoActividad.A05_PROFESIONALES


def test_a_book_is_held_back_by_the_ledger_rows_of_another_activity() -> None:
    """No typed link ties a book to an activity, so a row of any activity holds an unstated purchase back."""
    retail = inventory_ledger(_RETAIL.value)
    craft = _stating_no_ledger_row(inventory_ledger(_CRAFT.value))

    resolution = resolve_books((retail, craft), expense_row(base="100.00", activity=_CRAFT))

    assert resolution.row_binding_values == {}
    assert _states(resolution) == ["inventory source purchase_ledger_row_unstated"]
    (diagnostic,) = resolution.diagnostics
    assert diagnostic.fact is not None
    assert diagnostic.fact.values == (("count", "1"), ("year", str(YEAR)))
