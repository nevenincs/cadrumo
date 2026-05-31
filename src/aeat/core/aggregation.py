"""Core aggregation taxonomy shared across application and adapter layers."""

from __future__ import annotations

from enum import StrEnum

from .logging import get_logger

_log = get_logger(__name__)


class AggregationSourceKind(StrEnum):
    """Accepted source-kind taxonomy for per-modelo aggregation providers."""

    INVOICE = "invoice"
    LEDGER_TRANSACTION = "ledger_transaction"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"


class PeriodKind(StrEnum):
    """Authoritative period cadences shared across aggregation and deadline layers.

    Placed in :mod:`aeat.core` (cross-layer home) so the deadline domain and
    application aggregation layer can both import without violating the
    hexagonal direction (domain → core is always legal; domain → application
    is forbidden).
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class RowSetGroupingKind(StrEnum):
    """Canonical row-set source-kind discriminators for detail-record assembly.

    Placed in :mod:`aeat.core` (cross-layer home) because both the application
    assembly layer and the domain registry schema reference these values, and
    domain → application imports are forbidden under the hexagonal contract.
    """

    WITHHOLDING = "withholding"
    RELATED_PARTY = "related_party"
    FOREIGN_ASSET = "foreign_asset"
    ATRIBUCION = "atribucion"
    REFUND = "refund"
