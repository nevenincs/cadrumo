"""Core aggregation taxonomy shared across application and adapter layers."""

from __future__ import annotations

from enum import StrEnum

from .logging import get_logger

_log = get_logger(__name__)


class AggregationSourceKind(StrEnum):
    """Accepted source-kind taxonomy for per-modelo aggregation providers."""

    LEDGER_TRANSACTION = "ledger_transaction"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"
