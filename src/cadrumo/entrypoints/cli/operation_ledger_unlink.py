"""Authenticated CLI bridge for ``aeat app ledger unlink``.

The command removes one movement's link to one invoice. The transaction and
invoice the person named are first resolved exactly as ``aeat app ledger
view`` and the invoice reads resolve them, so the write's ``expected_*``
fields are the modification time and links the person actually saw, never a
value the command invents.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer
from pydantic import ValidationError

from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.ledger.invoice_unlink import InvoiceUnlinkRefusedError
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...application.ledger.unlink_operation import (
    LEDGER_UNLINK_OPERATION_DEFINITION_ID,
    LEDGER_UNLINK_REFUSAL_CODE,
    LedgerUnlinkRequest,
)
from ...application.ledger.unlink_operation import LedgerUnlinkResult as LedgerUnlinkOperationResult
from ...application.review.filter import LedgerReviewStatus
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .ledger_support import ledger_validation_bad
from .operation_invoice_catalogue import view_invoice_catalogue
from .operation_ledger_view import read_ledger_view_for_cli


@dataclass(frozen=True, slots=True)
class UnlinkedLedgerInvoice:
    """A correlated unlink: the worker's result with the unlinked movement and its review status."""

    result: LedgerUnlinkOperationResult
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus


def unlink_ledger_invoice_for_cli(
    ctx: typer.Context,
    *,
    transaction_id: str,
    invoice_id: str,
    actor: str | None,
) -> UnlinkedLedgerInvoice:
    """Resolve both records as the person last saw them, then remove the link.

    Raises:
        InvoiceUnlinkRefusedError: When the worker refused the removal before any write.
    """
    client = bound_profile_client(ctx)
    actor_label = (actor or "operator").strip() or "operator"
    view = read_ledger_view_for_cli(ctx, transaction_id=transaction_id)
    invoice_read = view_invoice_catalogue(ctx, invoice_id=invoice_id)
    try:
        request = LedgerUnlinkRequest(
            profile_id=client.profile_id,
            transaction_id=view.transaction.transaction_id,
            invoice_id=invoice_read.invoice.invoice_id,
            expected_modified_at=view.transaction.modified_at,
            expected_invoice_linked_transaction_ids=invoice_read.invoice.linked_transaction_ids,
            actor=actor_label,
            output_language=OutputLanguage(active_output_language()),
        )
    except ValidationError as error:
        raise ledger_validation_bad(error) from error
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_UNLINK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerUnlinkOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or result.invoice_id != invoice_read.invoice.invoice_id
        or not result.transaction_id.startswith(transaction_id.strip().lower())
    ):
        raise invalid_completion_error(completed)
    if result.outcome == "refused":
        refusal = result.refusal
        if (
            refusal is None
            or completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_UNLINK_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
        ):
            raise invalid_completion_error(completed)
        raise InvoiceUnlinkRefusedError(refusal.cause)
    transaction = result.transaction
    review_status = result.review_status
    if transaction is None or review_status is None or result.actor is None or len(result.bucket_event_ids) != 1:
        raise invalid_completion_error(completed)
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or transaction.invoice_id is not None
        or transaction.transaction_id in result.invoice_linked_transaction_ids
        or result.actor != actor_label
    )
    if invalid:
        raise invalid_completion_error(completed)
    return UnlinkedLedgerInvoice(result=result, transaction=transaction, review_status=review_status)


__all__ = ["UnlinkedLedgerInvoice", "unlink_ledger_invoice_for_cli"]
