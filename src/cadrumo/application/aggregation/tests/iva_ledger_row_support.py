"""Run one ledger row through the real IVA ledger classifier."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.period import Period
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .iva_authority_support import aggregate_iva_ledger_observations


def aggregate_row(transaction: Transaction, period: Period) -> tuple[Sequence[IvaLedgerObservation], list[str]]:
    """Return the observations the classifier produced and the reasons it refused rows."""
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    aggregation = aggregate_iva_ledger_observations(catalogue, period=period)
    return aggregation.observations, [issue.reason.value for issue in aggregation.issues]


def uncategorised_sale_row(
    row_id: str,
    *,
    booked: date,
    base: Decimal,
    iva_rate: Decimal | None,
    iva_amount: Decimal,
    recargo_amount: Decimal | None = None,
) -> Transaction:
    """One classified incoming business sale with no IVA category, whose gross is base, cuota and recargo."""
    return _uncategorised_row(
        row_id,
        direction=TransactionDirection.INCOMING,
        booked=booked,
        base=base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
    )


def uncategorised_purchase_row(
    row_id: str,
    *,
    booked: date,
    base: Decimal,
    iva_rate: Decimal,
    iva_amount: Decimal,
    recargo_amount: Decimal | None = None,
) -> Transaction:
    """One classified outgoing business purchase with no IVA category, whose gross is base, cuota and recargo."""
    return _uncategorised_row(
        row_id,
        direction=TransactionDirection.OUTGOING,
        booked=booked,
        base=base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
    )


def _uncategorised_row(
    row_id: str,
    *,
    direction: TransactionDirection,
    booked: date,
    base: Decimal,
    iva_rate: Decimal | None,
    iva_amount: Decimal,
    recargo_amount: Decimal | None,
) -> Transaction:
    gross = base + iva_amount + (recargo_amount or Decimal("0"))
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=row_id,
                booked_date=booked,
                value_date=booked,
                amount=gross,
                currency="EUR",
                counterparty="Cliente",
                description=f"venta {row_id}",
                provenance=RawProvenance(
                    source_path=Path("ledger.csv"),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(1980, 12, 1, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "taxable_base": base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "recargo_amount": recargo_amount,
            "iva_category": None,
            "exemption_article": None,
            "art_104_tres_exclusion": None,
            "prorrata_reference": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "fx_rate": None,
            "value_in_eur": None,
            "classified_at": datetime(1980, 12, 2, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
