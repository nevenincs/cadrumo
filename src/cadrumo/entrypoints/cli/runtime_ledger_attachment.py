"""Registered worker bridge for ``ledger attach`` and ``ledger detach``."""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import ValidationError

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationResult,
    LedgerAttachmentProjection,
    LedgerAttachmentValidationRefusedError,
    LedgerAttachRequest,
    LedgerDetachRequest,
)
from ...application.ledger.notices import stale_finalized_revision_notices
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...core.i18n.render import tr
from ...core.json_contract import OutputSchema
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._ledger_payloads import TransactionPayload
from ._ledger_support import ledger_validation_bad
from .common import emit_envelope
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def run_ledger_attach(
    ctx: typer.Context,
    *,
    transaction_id: str,
    purchase_invoice_evidence_id: str | None,
    attachment_ids: tuple[str, ...],
    actor: str | None,
) -> LedgerAttachmentProjection:
    """Submit canonical attachment under the caller's retained profile session."""
    client = bound_profile_client(ctx)
    try:
        request = LedgerAttachRequest(
            profile_id=client.profile_id,
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            attachment_ids=attachment_ids,
            actor=actor if actor else None,
        )
    except ValidationError as error:
        raise ledger_validation_bad(error) from error
    return _submit(
        client,
        request,
        definition_id=LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    )


def run_ledger_detach(
    ctx: typer.Context,
    *,
    transaction_id: str,
    attachment_ids: tuple[str, ...],
    actor: str | None,
) -> LedgerAttachmentProjection:
    """Submit canonical detachment under the caller's retained profile session."""
    client = bound_profile_client(ctx)
    try:
        request = LedgerDetachRequest(
            profile_id=client.profile_id,
            transaction_id=transaction_id,
            attachment_ids=attachment_ids,
            actor=actor if actor else None,
        )
    except ValidationError as error:
        raise ledger_validation_bad(error) from error
    return _submit(
        client,
        request,
        definition_id=LEDGER_DETACH_OPERATION_DEFINITION_ID,
    )


def _submit(
    client: RuntimeFrontendClient,
    request: LedgerAttachRequest | LedgerDetachRequest,
    *,
    definition_id: str,
) -> LedgerAttachmentProjection:
    """Submit one mutation and check either its typed refusal or terminal effect."""
    profile_id = request.profile_id
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerAttachmentOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    result = completed.projection
    if result.outcome == "validation_error":
        raise_ledger_attachment_refusal(completed, result, client.profile_id, definition_id)
    projection = result.result
    if projection is None:
        raise invalid_completion_error(completed)
    transaction = projection.transaction
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    prefix = request.transaction_id.strip().lower()
    attachment_set = set(transaction.attachment_ids)
    requested_attachment_ids = {value.strip() for value in request.attachment_ids if value.strip()}
    invalid = (
        invalid_attachment_receipt(
            completed, result, projection, transaction, expected_effect, profile_id, definition_id, prefix
        )
        or invalid_attachment_selection(request, definition_id, transaction, requested_attachment_ids, attachment_set)
        or invalid_detachment_selection(request, definition_id, requested_attachment_ids, attachment_set)
    )
    if invalid:
        raise invalid_completion_error(completed)
    return projection


def emit_ledger_attachment_result[ResultSchema: OutputSchema](
    ctx: typer.Context,
    projection: LedgerAttachmentProjection,
    *,
    command: str,
    result_schema: type[ResultSchema],
) -> None:
    """Preserve the established ledger mutation quintet and stale-revision notices."""
    transaction_payload = TransactionPayload.model_validate_json(projection.transaction.model_dump_json())
    result = result_schema.model_validate(
        {
            "bucket_id": str(projection.profile_id),
            "transaction_id": transaction_payload.transaction_id,
            "bucket_event_ids": list(projection.bucket_event_ids),
            "review_status": projection.review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        }
    )
    emit_envelope(
        ctx,
        command=command,
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{transaction_payload.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{projection.review_status}",
        ],
        notices=stale_finalized_revision_notices(projection.stale_finalized_revisions),
    )


__all__ = [
    "emit_ledger_attachment_result",
    "run_ledger_attach",
    "run_ledger_detach",
]


def raise_ledger_attachment_refusal(
    completed: RegisteredOperationCompletion[LedgerAttachmentOperationResult],
    result: LedgerAttachmentOperationResult,
    profile_id: UUID,
    definition_id: str,
) -> Never:
    """Release validation messages only after correlating a no-effect refusal."""
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.refusal_code != LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE
        or completed.effect is not OperationEffect.NONE
        or result.profile_id != profile_id
        or result.operation_id != definition_id
        or not result.validation_messages
    ):
        raise invalid_completion_error(completed)
    raise LedgerAttachmentValidationRefusedError(result.validation_messages) from None


def invalid_attachment_receipt(
    completed: RegisteredOperationCompletion[LedgerAttachmentOperationResult],
    result: LedgerAttachmentOperationResult,
    projection: LedgerAttachmentProjection,
    transaction: LedgerTransactionProjection,
    expected_effect: OperationEffect,
    profile_id: UUID,
    definition_id: str,
    prefix: str,
) -> bool:
    """Correlate the completed effect, profile, definition, and transaction."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (result.outcome != "updated")
        or (result.profile_id != profile_id)
        or (result.operation_id != definition_id)
        or (projection.profile_id != profile_id)
        or (projection.operation_id != definition_id)
        or (not transaction.transaction_id.startswith(prefix))
    )


def invalid_attachment_selection(
    request: LedgerAttachRequest | LedgerDetachRequest,
    definition_id: str,
    transaction: LedgerTransactionProjection,
    requested_attachment_ids: set[str],
    attachment_set: set[str],
) -> bool:
    """Check that the attach result contains every requested evidence link."""
    return definition_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID and (
        not isinstance(request, LedgerAttachRequest)
        or (
            request.purchase_invoice_evidence_id is not None
            and transaction.purchase_invoice_evidence_id != request.purchase_invoice_evidence_id.strip()
        )
        or (not requested_attachment_ids <= attachment_set)
        or (request.purchase_invoice_evidence_id is None and (not request.attachment_ids))
    )


def invalid_detachment_selection(
    request: LedgerAttachRequest | LedgerDetachRequest,
    definition_id: str,
    requested_attachment_ids: set[str],
    attachment_set: set[str],
) -> bool:
    """Check that no requested detached identifier remains on the transaction."""
    return definition_id == LEDGER_DETACH_OPERATION_DEFINITION_ID and (
        not isinstance(request, LedgerDetachRequest) or bool(requested_attachment_ids & attachment_set)
    )
