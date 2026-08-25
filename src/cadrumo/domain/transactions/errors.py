"""Canonical domain exceptions for ``cadrumo.domain.transactions``."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from ...core.errors import CadrumoError, get_registered_error_code


class TransactionError(CadrumoError):
    """Base error for every transaction-catalogue failure."""


class TransactionCatalogueError(TransactionError):
    """Raised when a transaction catalogue is invalid or inconsistent."""


class TransactionPersistenceError(TransactionCatalogueError):
    """Raised when catalogue persistence cannot be completed."""


class StoredTransactionDriftError(TransactionPersistenceError):
    """Raised when a persisted transaction catalogue fails schema validation on load.

    Mirrors :class:`~cadrumo.domain.user_profile.errors.StoredProfileDriftError`:
    the catalogue was valid when written; schema evolution or an
    out-of-band edit caused the on-disk envelope payload to drift from
    the current :class:`~cadrumo.domain.transactions.TransactionCatalogue`
    schema. The original :exc:`pydantic.ValidationError` is preserved
    on ``original_exception`` so callers can inspect the typed
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
            context={"bucket_id": bucket_id},
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
        translated_message: str | None = None,
    ) -> None:
        """Initialise a financial-ledger storage failure with structured metadata.

        ``translated_message`` falls back to the *constructed* class's own
        registered key, not to a literal spelled here. A literal default is
        inherited verbatim by every subclass, so a bare
        :class:`LedgerNoActiveBucketError` rendered this class's
        ``FAIL_FINANCIAL_LEDGER_STORAGE`` key in place of its own registered
        ``REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET`` key -- an authored value
        silently displacing the registry's. Resolving through the registry
        keeps each subclass on its own key and cannot drift from it.
        """
        super().__init__(
            message,
            context=context,
            translated_message=translated_message or get_registered_error_code(type(self)).message_key,
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
