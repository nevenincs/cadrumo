"""Domain exceptions for ``aeat.domain.transactions``."""

from __future__ import annotations

from ...core.errors import AeatError


class TransactionError(AeatError):
    """Base error for every transaction-catalogue failure."""


class TransactionCatalogueError(TransactionError):
    """Raised when a transaction catalogue is invalid or inconsistent."""


class TransactionPersistenceError(TransactionCatalogueError):
    """Raised when catalogue persistence cannot be completed."""


class TransactionNotFoundError(TransactionCatalogueError):
    """Raised when a catalogue lookup targets a missing transaction."""


class LLMClassifierError(TransactionError):
    """Raised when an LLM classification attempt fails."""


class TransactionValidationError(TransactionError, ValueError):
    """Raised on invalid transaction field values. Inherits from ValueError for Pydantic."""
