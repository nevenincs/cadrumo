"""Domestic zero-rated and general sales shared by the unroutable IVA base category suites."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_NOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC)


def domestic_zero_sale() -> Transaction:
    """A zero-rated domestic sale: zero cuota by law, a real base by law.

    ``IvaCategory.DOMESTIC_ZERO`` is the canonical proof this screen exists
    for: cuota-less BY LAW (so Screen 1/2's cuota-side reasoning never fires
    on it), while the base is a real declared amount M303 currently has no
    ``base_amount_sum`` binding for at all.
    """
    raw = RawTransaction(
        provider_transaction_id="zero-rated-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("500.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo cero",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "zero-rated-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("500.00"),
            "iva_rate": Decimal("0.00"),
            "iva_amount": Decimal("0.00"),
            "iva_category": IvaCategory("domestic_zero"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def domestic_general_sale() -> Transaction:
    """A fully-covered domestic sale, the negative control."""
    raw = RawTransaction(
        provider_transaction_id="general-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("1210.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo general",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "general-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("domestic_general"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )
