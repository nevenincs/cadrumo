"""Immutable transaction catalogue surface for the financial pipeline.

Public surface — callers must import transaction models, errors, and
service functions exclusively from ``aeat.financial.transactions`` and
must not reach into the private underscore modules inside this package.
"""

from __future__ import annotations

from ._enums import BusinessClassification, TransactionDirection
from ._errors import (
    TransactionCatalogueError,
    TransactionError,
    TransactionNotFoundError,
    TransactionPersistenceError,
)
from ._models import Transaction, TransactionCatalogue
from ._service import (
    find_transaction,
    link_invoice,
    load_transactions,
    save_transactions,
    set_classification,
)

__all__ = [
    "BusinessClassification",
    "Transaction",
    "TransactionCatalogue",
    "TransactionCatalogueError",
    "TransactionDirection",
    "TransactionError",
    "TransactionNotFoundError",
    "TransactionPersistenceError",
    "find_transaction",
    "link_invoice",
    "load_transactions",
    "save_transactions",
    "set_classification",
]
