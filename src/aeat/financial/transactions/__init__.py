"""Immutable transaction catalogue surface for the financial pipeline.

Public surface — callers must import transaction models, errors, and
service functions exclusively from ``aeat.financial.transactions`` and
must not reach into the private underscore modules inside this package.
"""

from __future__ import annotations

from ._enums import CLASSIFIED_STATES, BusinessClassification, TransactionDirection, is_classified
from ._errors import (
    TransactionCatalogueError,
    TransactionError,
    TransactionNotFoundError,
    TransactionPersistenceError,
)
from ._models import ClassificationHistoryEntry, Transaction, TransactionCatalogue
from ._service import (
    find_transaction,
    link_invoice,
    load_transactions,
    save_transactions,
    set_classification,
    snapshot_classification_state,
)

__all__ = [
    "CLASSIFIED_STATES",
    "BusinessClassification",
    "ClassificationHistoryEntry",
    "Transaction",
    "TransactionCatalogue",
    "TransactionCatalogueError",
    "TransactionDirection",
    "TransactionError",
    "TransactionNotFoundError",
    "TransactionPersistenceError",
    "find_transaction",
    "is_classified",
    "link_invoice",
    "load_transactions",
    "save_transactions",
    "set_classification",
    "snapshot_classification_state",
]
