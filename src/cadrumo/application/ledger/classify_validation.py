"""Bounded, non-sensitive refusal classification for ledger classify inputs."""

from __future__ import annotations

from pydantic import ValidationError

from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.transactions.errors import TransactionValidationError
from .classify_result_contracts import (
    LEDGER_CLASSIFY_MAX_VALIDATION_MESSAGES,
    LedgerClassifyValidationKind,
    LedgerClassifyValidationMessages,
)
from .validation_messages import bounded_validation_messages

LEDGER_CLASSIFY_VALIDATION_ERRORS = (ValidationError, TransactionValidationError, RegistryValidationError)


def classify_validation_kind(error: Exception) -> LedgerClassifyValidationKind:
    """Retain the two user-actionable M210 refusal categories without raw context."""
    if not isinstance(error, TransactionValidationError):
        return "input"
    context = error.context or {}
    if "required_direction" in context:
        return "m210_incoming_only"
    if "missing" in context:
        return "m210_required_options"
    return "input"


def classify_validation_messages(error: Exception) -> LedgerClassifyValidationMessages:
    """Retain only bounded field locations and user-actionable messages."""
    return bounded_validation_messages(
        error,
        limit=LEDGER_CLASSIFY_MAX_VALIDATION_MESSAGES,
        fallback="ledger classify values did not satisfy transaction validation",
    )
