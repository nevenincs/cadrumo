"""A ledger row an inventory purchase claims leaves casilla 0183 only where the edition gives the book a casilla.

The book carries a purchase into 0181 through the edition's inventory bindings. An
edition that declares none of them would receive the purchase nowhere, so the
claimed row stays among the ledger expenses there.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.contribuyente.inventory.records import (
    InventoryLedger,
    InventoryLedgerDocument,
    MovementRecord,
    PurchaseLedgerRow,
)
from ....domain.prorrata_register.register import ProrrataRegister
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..inventory import revision_carries_inventory_purchases
from ..modelo_bindings_renta_expenses import LedgerRentaGastosEstimacionDirectaAggregationSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    EmptyActivityAssetHistoryRepository,
    InMemoryInvoiceCatalogueRepository,
    InMemoryTransactionCatalogueRepository,
    cash_criterion_profile,
    filing_years,
    m100_revision,
    machine_acquisition_transaction,
    prorrata_repository_holding,
    renta_expense_binding_id,
)
from .test_inventory_source import inventory_ledger

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _purchase_row(year: int) -> Transaction:
    """A wholesaler purchase the ledger routes to 0183, 1.000,00 base plus 210,00 IVA."""
    return machine_acquisition_transaction("suministros_cliente_directos", provider_id="wholesaler-1", year=year)


def _claiming(ledger: InventoryLedger, transaction_id: str) -> InventoryLedger:
    (purchase,) = ledger.period_movements
    claimed = MovementRecord.model_validate(
        {**purchase.model_dump(), "ledger_row": PurchaseLedgerRow.CLAIMED, "claimed_transaction_id": transaction_id}
    )
    return ledger.model_copy(update={"period_movements": (claimed,)})


def _without_inventory_bindings(revision: ModeloRevision) -> ModeloRevision:
    """The same edition as one whose design gives the book no casilla: no inventory binding, its casillas manual."""
    inventory = {binding.id for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY}
    assert inventory, "the published edition declares the inventory bindings"
    return revision.model_copy(
        update={
            "bindings": tuple(binding for binding in revision.bindings if binding.id not in inventory),
            "casillas": tuple(
                casilla.model_copy(update={"input_kind": InputKind.MANUAL, "binding": None})
                if casilla.binding in inventory
                else casilla
                for casilla in revision.casillas
            ),
        }
    )


class _Books:
    def __init__(self, ledger: InventoryLedger) -> None:
        self._document = InventoryLedgerDocument(ledgers=(ledger,))

    def load(self) -> InventoryLedgerDocument:
        return self._document


def _resolve(revision: ModeloRevision, year: int) -> CalculationSourceResolution:
    row = _purchase_row(year)
    transactions = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    transactions.save(TransactionCatalogue.from_transactions([row]))
    return LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        ports=InvoiceCatalogueReadPorts(
            invoice_reader=InMemoryInvoiceCatalogueRepository(),
            transaction_reader=transactions,
        ),
        prorrata_register_repository=prorrata_repository_holding(ProrrataRegister()),
        usage_ratio_profile_loader=lambda *, bucket_id, operation: UsageRatioProfile(),
        activity_asset_history_repository=EmptyActivityAssetHistoryRepository(),
        inventory_repository=_Books(_claiming(inventory_ledger("comercio", year=year), row.transaction_id)),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=revision,
            profile=cash_criterion_profile(year),
        ),
    )


def _box_0183(revision: ModeloRevision, resolution: CalculationSourceResolution) -> Decimal:
    return resolution.binding_values.get(renta_expense_binding_id(revision, "0183"), Decimal("0.00"))


@pytest.mark.parametrize("supported_m100_year", filing_years())
def test_a_claimed_row_leaves_0183_where_the_edition_binds_the_book(supported_m100_year: int) -> None:
    revision = m100_revision(supported_m100_year)

    assert revision_carries_inventory_purchases(revision)
    assert _box_0183(revision, _resolve(revision, supported_m100_year)) == Decimal("0.00")


@pytest.mark.parametrize("supported_m100_year", filing_years())
def test_a_claimed_row_stays_in_0183_where_the_edition_gives_the_book_no_casilla(supported_m100_year: int) -> None:
    revision = _without_inventory_bindings(m100_revision(supported_m100_year))

    assert not revision_carries_inventory_purchases(revision)
    assert _box_0183(revision, _resolve(revision, supported_m100_year)) == Decimal("1000.00")
