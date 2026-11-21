"""Registered worker bridge for ``aeat app ledger evidence release``."""

from __future__ import annotations

from dataclasses import dataclass

import typer
from pydantic import ValidationError

from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.ledger.purchase_evidence_release import (
    PurchaseEvidenceDisposition,
    PurchaseEvidenceReleaseRefusedError,
)
from ...application.ledger.purchase_evidence_release_operation import (
    LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
    LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE,
    LedgerPurchaseEvidenceReleaseRequest,
    LedgerPurchaseEvidenceReleaseResult,
)
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...application.review.filter import LedgerReviewStatus
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .ledger_support import ledger_validation_bad


@dataclass(frozen=True, slots=True)
class ReleasedPurchaseEvidence:
    """A correlated release: the worker's result with the released movement and its review status."""

    result: LedgerPurchaseEvidenceReleaseResult
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus


def run_ledger_purchase_evidence_release(
    ctx: typer.Context,
    *,
    transaction_id: str,
    expected_evidence_id: str,
    expected_modified_at: str,
    disposition: PurchaseEvidenceDisposition,
) -> ReleasedPurchaseEvidence:
    """Release one movement's linked purchase evidence and correlate the released row.

    Raises:
        PurchaseEvidenceReleaseRefusedError: When the worker refused the release before any write.
    """
    client = bound_profile_client(ctx)
    try:
        request = LedgerPurchaseEvidenceReleaseRequest(
            profile_id=client.profile_id,
            transaction_id=transaction_id,
            expected_purchase_invoice_evidence_id=expected_evidence_id,
            expected_modified_at=expected_modified_at,
            disposition=disposition,
            output_language=OutputLanguage(active_output_language()),
        )
    except ValidationError as error:
        raise ledger_validation_bad(error) from error
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerPurchaseEvidenceReleaseResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    result = completed.projection
    if result.profile_id != client.profile_id or result.disposition != disposition:
        raise invalid_completion_error(completed)
    if result.outcome == "refused":
        refusal = result.refusal
        if (
            refusal is None
            or completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
        ):
            raise invalid_completion_error(completed)
        raise PurchaseEvidenceReleaseRefusedError(refusal.cause, invoice_ids=refusal.invoice_ids)
    transaction = result.transaction
    review_status = result.review_status
    if transaction is None or review_status is None:
        raise invalid_completion_error(completed)
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or result.released_evidence_id != expected_evidence_id
        or not transaction.transaction_id.startswith(transaction_id.strip().lower())
        or transaction.purchase_invoice_evidence_id is not None
        or not result.bucket_event_ids
    )
    if invalid:
        raise invalid_completion_error(completed)
    return ReleasedPurchaseEvidence(result=result, transaction=transaction, review_status=review_status)


__all__ = ["ReleasedPurchaseEvidence", "run_ledger_purchase_evidence_release"]
