"""An inventory purchase claiming its ledger row: the row leaves the ledger expenses, and the book's rows wait on claims.

A claimed row is withheld from every ledger expense destination, because the book
carries the purchase into casilla 0181. A claim that does not stand, or a purchase
that states nothing while the year holds ledger expense rows, holds the book's rows
back rather than letting the purchase be deducted twice or not at all.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.aggregation.tests.test_inventory_source import inventory_ledger
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    published_work_profile_declaring_activities,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import BindingAggregation, BindingAggregationOp
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.period import Period
from ....domain.calculations.registry.inventory_bindings import InventoryProjectionOperation
from ....domain.calculations.registry.schema import BindingDefinition
from ....domain.contribuyente.inventory.ledger_claims import InventoryPurchaseClaim
from ....domain.contribuyente.inventory.records import (
    InventoryLedger,
    InventoryLedgerDocument,
    MovementRecord,
    PurchaseLedgerRow,
)
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...inventory.movement_claim_checks import InventoryClaimLedgerReads
from ...modelo.calculation_notes import note_fact_text
from ..activity_asset_expense_reconciliation import (
    LedgerRentaExpenseTreatment,
    book_claimed_purchase_diagnostics,
    classify_ledger_expenses_against_asset_register,
    register_acquisition_transaction_ids,
)
from ..inventory import InventorySourceResolver
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

YEAR = newest_authored_edition("100")
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


def _binding(operation: InventoryProjectionOperation, target: str) -> BindingDefinition:
    return BindingDefinition(
        id=f"inventory-{target}",
        provider={
            "kind": "inventory",
            "modelo": "100",
            "temporal": {"kind": "same_target_context"},
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": operation,
            "target_casilla_id": target,
        },
        value={"data_type": "money", "channel": "row_set"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-manual",),
    )


def _context() -> CalculationSourceContext:
    revision = published_snapshot("100", filing_year=YEAR, period="0A").revision.model_copy(
        update={
            "bindings": (
                _binding("complete_acquisition_cost", "0181"),
                _binding("closing_minus_opening_positive", "0177"),
                _binding("opening_minus_closing_positive", "0182"),
            )
        }
    )
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=YEAR,
        period=Period.from_year_and_code(YEAR, "0A"),
        revision=revision,
        profile=published_work_profile_declaring_activities(1),
    )


def _expense_row(*, base: str) -> Transaction:
    gross = Decimal(base) + Decimal("21.00")
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="row-1",
                booked_date=date(YEAR, 2, 1),
                value_date=date(YEAR, 2, 1),
                amount=gross,
                currency="EUR",
                counterparty="Mayorista SL",
                description="Compra de existencias",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(YEAR, 2, 2, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": "Compra de existencias"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal(base),
            "iva_amount": Decimal("21.00"),
        },
    )


def _claiming(ledger: InventoryLedger, transaction_id: str) -> InventoryLedger:
    (purchase,) = ledger.period_movements
    claimed = MovementRecord.model_validate(
        {
            **purchase.model_dump(),
            "ledger_row": PurchaseLedgerRow.CLAIMED,
            "claimed_transaction_id": transaction_id,
        }
    )
    return ledger.model_copy(update={"period_movements": (claimed,)})


class _Books:
    def __init__(self, ledger: InventoryLedger) -> None:
        self.document = InventoryLedgerDocument(ledgers=(ledger,))

    def load(self) -> InventoryLedgerDocument:
        return self.document


def _resolve(ledger: InventoryLedger, *rows: Transaction):
    catalogue = TransactionCatalogue.from_transactions(list(rows))
    reads = InventoryClaimLedgerReads(transactions=lambda: catalogue, asset_revisions=tuple)
    return InventorySourceResolver(inventory_repository=_Books(ledger), claim_reads=reads).resolve(_context())


def _states(resolution) -> list[str]:
    return [diagnostic.message.split(":")[0] for diagnostic in resolution.diagnostics]


def test_an_unstated_purchase_holds_the_rows_back_while_the_year_has_ledger_expense_rows() -> None:
    resolution = _resolve(inventory_ledger("comercio"), _expense_row(base="100.00"))

    assert resolution.row_binding_values == {}
    assert set(resolution.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    assert _states(resolution) == ["inventory source purchase_ledger_row_unstated"]
    assert all(diagnostic.remedy for diagnostic in resolution.diagnostics)


def test_an_unstated_purchase_stands_when_the_year_has_no_ledger_expense_rows() -> None:
    resolution = _resolve(inventory_ledger("comercio"))

    assert resolution.row_binding_values[("inventory-0181", 1)] == Decimal("100.00")


def test_a_standing_claim_lets_the_book_carry_the_purchase_into_0181() -> None:
    row = _expense_row(base="100.00")

    resolution = _resolve(_claiming(inventory_ledger("comercio"), row.transaction_id), row)

    assert resolution.row_binding_values[("inventory-0181", 1)] == Decimal("100.00")
    assert resolution.unresolved_binding_ids == ()


def test_a_claim_that_does_not_match_its_row_holds_the_rows_back() -> None:
    row = _expense_row(base="100.01")

    resolution = _resolve(_claiming(inventory_ledger("comercio"), row.transaction_id), row)

    assert resolution.row_binding_values == {}
    assert _states(resolution) == ["inventory source purchase_ledger_claim_refused"]
