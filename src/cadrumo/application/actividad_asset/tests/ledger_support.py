"""Real ledger rows and an in-memory ledger port for activity-asset acquisition tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


def acquisition_transaction(
    *,
    provider_id: str = "acquisition-1",
    amount: Decimal = Decimal("2420.00"),
    taxable_base: Decimal | None = Decimal("2000.00"),
    iva_amount: Decimal | None = Decimal("420.00"),
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    currency: str = "EUR",
    value_in_eur: Decimal | None = None,
) -> Transaction:
    """Build one valid ledger row whose content-derived id an asset revision can name."""
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 1, 10),
        value_date=date(2025, 1, 10),
        amount=amount,
        currency=currency,
        counterparty="Proveedor",
        description=f"acquisition {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2025, 1, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )
    converted: dict[str, object] = {}
    if value_in_eur is not None:
        converted = {"fx_rate": value_in_eur / amount, "value_in_eur": value_in_eur}
    # Row validation resolves governed IVA vocabulary, so it runs inside one leased authority generation.
    with bundled_indexed_authority().operation():
        return Transaction.model_validate(
            {
                "raw": raw,
                "direction": direction,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
                "group_label": None,
                "category_id": "material_oficina",
                "taxable_base": taxable_base,
                "iva_rate": Decimal("0.21") if iva_amount is not None else None,
                "iva_amount": iva_amount,
                "classified_at": datetime(2025, 1, 11, 13, 0, tzinfo=UTC),
                "classified_by": "manual",
                **converted,
            },
        )


class MemoryLedger:
    """Serve the supplied rows through the ledger read port."""

    def __init__(self, *transactions: Transaction) -> None:
        """Hold the rows by their content-derived identifiers."""
        self._transactions = {item.transaction_id: item for item in transactions}

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Return the held rows addressed by ``transaction_ids``."""
        with bundled_indexed_authority().operation():
            return TransactionCatalogue.from_transactions(
                [self._transactions[item] for item in transaction_ids if item in self._transactions],
            )
