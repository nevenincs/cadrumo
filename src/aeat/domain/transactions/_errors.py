"""Domain exceptions for ``aeat.domain.transactions``."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from ...core.errors import AeatError


class TransactionError(AeatError):
    """Base error for every transaction-catalogue failure."""


class TransactionCatalogueError(TransactionError):
    """Raised when a transaction catalogue is invalid or inconsistent."""


class TransactionPersistenceError(TransactionCatalogueError):
    """Raised when catalogue persistence cannot be completed."""


class StoredTransactionDriftError(TransactionPersistenceError):
    """Raised when a persisted transaction catalogue fails schema validation on load.

    Mirrors :class:`~aeat.domain.user_profile.StoredProfileDriftError`:
    the catalogue was valid when written; schema evolution or an
    out-of-band edit caused the on-disk envelope payload to drift from
    the current :class:`~aeat.domain.transactions.TransactionCatalogue`
    schema. The original :exc:`pydantic.ValidationError` is preserved
    on :attr:`original_exception` so callers can inspect the typed
    field errors without losing the deserialization detail.

    Attributes:
        bucket_id: Identifier of the bucket whose catalogue drifted.
        original_exception: The underlying :exc:`pydantic.ValidationError`.
    """

    def __init__(self, bucket_id: str, error: ValidationError) -> None:
        """Initialise the drift error with bucket identity and the validation failure.

        Args:
            bucket_id: Identifier of the bucket whose catalogue failed validation.
            error: The underlying :exc:`pydantic.ValidationError` from deserialization.
        """
        super().__init__(
            translated_message="errors.storage.stored_data_validation_boundary",
            context={"bucket_id": bucket_id, "recovery": "aeat config repair --help"},
            suggestion="aeat config repair --help",
        )
        self.bucket_id = bucket_id
        self.original_exception = error


class LedgerStorageError(TransactionPersistenceError):
    """Raised when bucket-scoped ledger storage cannot be resolved or used."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str = "errors.fail.fail_financial_ledger_storage",
    ) -> None:
        """Initialise a financial-ledger storage failure with structured metadata."""
        super().__init__(
            message,
            context=context,
            suggestion=suggestion,
            translated_message=translated_message,
        )


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


class ClassificationRuleError(TransactionError, ValueError):
    """Raised when a ledger classification rule is invalid.

    Inherits from :exc:`ValueError` so Pydantic field validators can
    raise it directly from ``@field_validator`` without wrapping.
    """
