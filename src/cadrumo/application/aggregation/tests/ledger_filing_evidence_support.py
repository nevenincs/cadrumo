"""Ledger transaction shared by the filing evidence suites."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_YEAR = filing_year_envelope().horizon

FILING_EVIDENCE_NOW = datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC)


def filing_evidence_transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="provider-row-evidence",
        booked_date=date(_YEAR, 2, 10),
        value_date=date(_YEAR, 2, 11),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="Compra material oficina",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=FILING_EVIDENCE_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Compra material oficina"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "iva_category": IvaCategory("domestic_general"),
            "category_id": "material_oficina",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": FILING_EVIDENCE_NOW,
            "classified_by": "manual",
        },
    )
