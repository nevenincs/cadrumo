"""Canonical prefix validation and refusal projection for ledger runtime reads."""

from __future__ import annotations

from collections.abc import Mapping

from ...application.cli_exception_preconditions import (
    CliExceptionPrecondition,
    cli_exception_no_recovery_verdict,
)
from ...application.ledger.id_resolution import normalise_transaction_id_prefix
from ...core.errors.error_codes import get_registered_error_code
from ...domain.transactions.errors import TransactionIdPrefixError
from .common import attach_cli_policy_verdict
from .errors import CliRefusedBoundaryError


def _transaction_id_resolves_verdict():
    """Build the existing no-recovery verdict for an unresolved ledger handle."""
    return cli_exception_no_recovery_verdict(
        CliExceptionPrecondition.LEDGER_TRANSACTION_ID_RESOLVES,
        facts={"transaction_id_resolves": False},
    )


def normalise_ledger_transaction_id_prefix(prefix: str) -> str:
    """Validate a ledger handle before submitting an operation to the profile worker."""
    try:
        return normalise_transaction_id_prefix(prefix)
    except TransactionIdPrefixError as error:
        raise attach_cli_policy_verdict(error, verdict=_transaction_id_resolves_verdict()) from None


def attach_submitted_ledger_prefix_verdict(error: CliRefusedBoundaryError) -> CliRefusedBoundaryError:
    """Attach the same resolution verdict without replacing a worker refusal."""
    context = error.context
    if not isinstance(context, Mapping):
        return error
    prefix_error_code = get_registered_error_code(TransactionIdPrefixError).code
    if context.get("reason") != prefix_error_code:
        return error
    return attach_cli_policy_verdict(error, verdict=_transaction_id_resolves_verdict())


__all__ = ["attach_submitted_ledger_prefix_verdict", "normalise_ledger_transaction_id_prefix"]
