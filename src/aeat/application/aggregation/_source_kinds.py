"""Shared source-kind taxonomy for aggregation modules."""

from __future__ import annotations

from enum import StrEnum


class AggregationSourceKind(StrEnum):
    """Accepted source-kind taxonomy for per-modelo aggregation providers."""

    LEDGER_TRANSACTION = "ledger_transaction"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"
