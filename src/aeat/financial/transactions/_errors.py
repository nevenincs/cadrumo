"""Domain exceptions for ``aeat.financial.transactions``."""

from __future__ import annotations

from aeat.errors import AeatError


class TransactionError(AeatError):
    """Base error for every transaction-catalogue failure."""


class TransactionCatalogueError(TransactionError):
    """Raised when a transaction catalogue is invalid or inconsistent."""


class TransactionPersistenceError(TransactionCatalogueError):
    """Raised when catalogue persistence cannot be completed."""


class TransactionNotFoundError(TransactionCatalogueError):
    """Raised when a catalogue lookup targets a missing transaction."""
