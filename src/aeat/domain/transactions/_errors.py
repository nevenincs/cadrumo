"""Domain exceptions for ``aeat.domain.transactions``."""

from __future__ import annotations

from ...core.errors import AeatError


class TransactionError(AeatError):
    """Base error for every transaction-catalogue failure."""


class TransactionCatalogueError(TransactionError):
    """Raised when a transaction catalogue is invalid or inconsistent."""


class TransactionPersistenceError(TransactionCatalogueError):
    """Raised when catalogue persistence cannot be completed."""


class LedgerStorageError(TransactionPersistenceError):
    """Raised when bucket-scoped ledger storage cannot be resolved or used."""


class LedgerNoActiveBucketError(LedgerStorageError):
    """Raised when a ledger operation requires an active profile bucket."""


class TransactionNotFoundError(TransactionCatalogueError):
    """Raised when a catalogue lookup targets a missing transaction."""


class TransactionIdPrefixError(TransactionCatalogueError):
    """Raised when a transaction-id prefix matches zero or multiple transactions."""


class LLMClassifierError(TransactionError):
    """Raised when an LLM classification attempt fails."""


class TransactionValidationError(TransactionError, ValueError):
    """Raised on invalid transaction field values. Inherits from ValueError for Pydantic."""


class LedgerLinkError(TransactionError):
    """Raised when linking a ledger transaction to a modelo binding fails."""


class LedgerCheckError(TransactionError):
    """Raised when a ledger consistency check surfaces a blocking finding."""


class LedgerPreflightError(TransactionError):
    """Raised when ledger preflight rejects a modelo run as un-fileable."""
