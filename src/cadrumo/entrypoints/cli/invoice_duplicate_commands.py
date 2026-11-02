"""``aeat app ledger invoice duplicate``: the stored invoice a document may already be."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import ValidationError

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.commands.secure_input import (
    MachineSecretPayload,
    read_machine_secret_payload,
    select_machine_secret_channel,
)

from ...application.invoices.duplicate_check_operation import (
    LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID,
    LedgerInvoiceDuplicateRequest,
    LedgerInvoiceDuplicateResult,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.iva.schema import InvoiceKind
from .common import emit_envelope
from .ledger_results import LedgerInvoiceDuplicateEnvelope


class InvoiceDuplicateSecrets(MachineSecretPayload):
    """Machine-channel facts a document states; blank is not stated."""

    invoice_number: str = ""
    counterparty_tax_id: str = ""
    invoice_date: str = ""
    grand_total: str = ""


def _request(profile_id: UUID, kind: str, facts: InvoiceDuplicateSecrets) -> LedgerInvoiceDuplicateRequest:
    try:
        return LedgerInvoiceDuplicateRequest(
            profile_id=profile_id,
            kind=InvoiceKind(kind),
            invoice_number=facts.invoice_number or None,
            counterparty_tax_id=facts.counterparty_tax_id or None,
            invoice_date=facts.invoice_date or None,
            grand_total=facts.grand_total or None,
        )
    except (ValueError, ValidationError) as exc:
        # The values are private facts, so the refusal names the shape and not the input.
        raise InvoiceValidationError(tr("cli.app.ledger.invoice.duplicate_invalid")) from exc


def invoice_duplicate(
    ctx: typer.Context,
    kind: str,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Answer which stored invoice a document may already be."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    facts = (
        read_machine_secret_payload(InvoiceDuplicateSecrets, selection=selection)
        if selection is not None
        else InvoiceDuplicateSecrets()
    )
    completed = run_registered_operation(
        client,
        _request(client.profile_id, kind, facts),
        definition_id=LEDGER_INVOICE_DUPLICATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerInvoiceDuplicateResult,
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
    emit_envelope(
        ctx,
        command="ledger.invoice.duplicate",
        result=LedgerInvoiceDuplicateEnvelope.model_validate(answer.model_dump(mode="json", exclude={"profile_id"})),
        lines=(answer.invoice_id[:12] if answer.invoice_id else "none",),
    )


__all__ = ["InvoiceDuplicateSecrets", "invoice_duplicate"]
