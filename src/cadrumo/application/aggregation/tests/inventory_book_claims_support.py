"""Inventory books, expense rows and resolution helpers shared by the inventory purchase-claim tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.aggregation import BindingAggregation, BindingAggregationOp
from ....core.period import Period
from ....core.tipos_actividad import TipoActividad
from ....domain.calculations.registry.inventory_bindings import InventoryProjectionOperation
from ....domain.calculations.registry.schema import BindingDefinition
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import published_snapshot
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
from ..inventory import InventorySourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .withholding_filer_profile_support import published_work_profile_declaring_activities

YEAR = newest_authored_edition("100")


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


def inventory_context(*, activities: int = 1) -> CalculationSourceContext:
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
        profile=published_work_profile_declaring_activities(activities),
    )


def expense_row(*, base: str, activity: TipoActividad | None = None) -> Transaction:
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
            "tipo_actividad": activity,
        },
    )


def claim_ledger_row(ledger: InventoryLedger, transaction_id: str) -> InventoryLedger:
    (purchase,) = ledger.period_movements
    claimed = MovementRecord.model_validate(
        {
            **purchase.model_dump(),
            "ledger_row": PurchaseLedgerRow.CLAIMED,
            "claimed_transaction_id": transaction_id,
        }
    )
    return ledger.model_copy(update={"period_movements": (claimed,)})


class InventoryBooks:
    def __init__(self, *ledgers: InventoryLedger) -> None:
        self.document = InventoryLedgerDocument(ledgers=ledgers)

    def load(self) -> InventoryLedgerDocument:
        return self.document


def resolve_book(ledger: InventoryLedger, *rows: Transaction) -> CalculationSourceResolution:
    return resolve_books((ledger,), *rows)


def resolve_books(ledgers: tuple[InventoryLedger, ...], *rows: Transaction) -> CalculationSourceResolution:
    catalogue = TransactionCatalogue.from_transactions(list(rows))
    reads = InventoryClaimLedgerReads(transactions=lambda: catalogue, asset_revisions=tuple)
    return InventorySourceResolver(inventory_repository=InventoryBooks(*ledgers), claim_reads=reads).resolve(
        inventory_context(activities=len(ledgers))
    )
