"""``aeat app ledger invoice match``: which movement settles which invoice, without linking anything."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import ValidationError

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.invoices.payment_match_operation import (
    LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID,
    LedgerInvoiceMatchRequest,
    LedgerInvoiceMatchResult,
    LedgerInvoiceMatchStagedLink,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.invoices.errors import InvoiceValidationError
from .common import emit_envelope
from .ledger_results import LedgerInvoiceMatchEnvelope


def _staged_link(text: str) -> LedgerInvoiceMatchStagedLink:
    transaction_id, separator, invoice_id = text.partition(":")
    if not separator:
        raise ValueError("a staged link names a movement and an invoice")
    return LedgerInvoiceMatchStagedLink(transaction_id=transaction_id, invoice_id=invoice_id)


def _request(
    profile_id: UUID,
    invoice_id: str | None,
    transaction_id: str | None,
    staged: tuple[str, ...],
    judge: tuple[str, ...],
) -> LedgerInvoiceMatchRequest:
    try:
        return LedgerInvoiceMatchRequest(
            profile_id=profile_id,
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            staged=tuple(_staged_link(text) for text in staged),
            judge=tuple(_staged_link(text) for text in judge),
        )
    except (ValueError, ValidationError) as exc:
        raise InvoiceValidationError(tr("cli.app.ledger.invoice.match_invalid")) from exc


def invoice_match(
    ctx: typer.Context,
    invoice_id: str | None = None,
    transaction_id: str | None = None,
    staged: tuple[str, ...] = (),
    judge: tuple[str, ...] = (),
) -> None:
    """Answer which movement settles which invoice, and the choices for a by-hand link."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        _request(client.profile_id, invoice_id, transaction_id, staged, judge),
        definition_id=LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerInvoiceMatchResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=False,
    )
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or completed.projection.profile_id != client.profile_id
    ):
        raise invalid_completion_error(completed)
    answer = completed.projection
    shown = answer.model_dump(mode="json", exclude={"profile_id"})
    for judgement in shown["judgements"]:
        for mismatch in judgement["mismatches"]:
            if mismatch["difference"] is not None:
                mismatch["difference"] = mismatch["difference"]["decimal"]
    emit_envelope(
        ctx,
        command="ledger.invoice.match",
        result=LedgerInvoiceMatchEnvelope.model_validate(shown),
        lines=tuple(f"{found.transaction_id[:12]} {found.invoice_id[:12]}" for found in answer.suggestions),
    )


__all__ = ["invoice_match"]
