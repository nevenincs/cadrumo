"""Canonical result and receipt projections for ledger lifecycle operations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ..operations.models import (
    OperationTerminalReceipt,
    refused_receipt_references_hold,
    require_succeeded_terminal_receipt,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_common import display_decimal
from .actions_manual import ledger_transaction_result_payload
from .lifecycle_contracts import (
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
    LEDGER_LIFECYCLE_MAX_RECOVERY_TRANSACTION_IDS,
    LEDGER_LIFECYCLE_MAX_RESULT_BYTES,
    LEDGER_LIFECYCLE_MAX_VALIDATION_MESSAGE_LENGTH,
    LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LedgerLifecycleBlockerProjection,
    LedgerLifecycleExecutionResult,
    LedgerLifecycleMutationProjection,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
    LedgerLifecycleReplacedStateProjection,
    LedgerLifecycleReversalOperationId,
    LedgerLifecycleValidationProjection,
)
from .models import LedgerTransactionResultPayload, ManualLedgerTransactionResult
from .transaction_projection import LedgerTransactionProjection


def _reversal_operations(
    operation_id: LedgerLifecycleOperationId,
    replaced: Transaction,
) -> tuple[LedgerLifecycleReversalOperationId, ...]:
    """Name, in order, the registered operations that return the row to its replaced state."""
    if operation_id == LEDGER_EXCLUDE_OPERATION_DEFINITION_ID:
        return ("ledger.classify.single",)
    from_stash = replaced.lifecycle_state is TransactionLifecycleState.STASHED
    if operation_id == LEDGER_RESTORE_OPERATION_DEFINITION_ID:
        return ("ledger.stash",) if from_stash else ("ledger.archive",)
    # A restore always lands on active, so a row archived out of the stash is stashed again after it.
    return ("ledger.restore", "ledger.stash") if from_stash else ("ledger.restore",)


def project_lifecycle_mutation_from_action(
    profile_id: UUID,
    operation_id: LedgerLifecycleOperationId,
    result: ManualLedgerTransactionResult,
    replaced: Transaction | None,
) -> LedgerLifecycleMutationProjection:
    """Project the canonical action result after checking profile and row identity.

    ``replaced`` is the stored row the action read before it wrote. The result
    states what that row carried, so a caller can tell the person what the
    mutation set aside and how to put it back.
    """
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.transaction.transaction_id != canonical.transaction_id
        or replaced is None
        or replaced.transaction_id != canonical.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerLifecycleMutationProjection(
        profile_id=profile_id,
        operation_id=operation_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
        replaced=LedgerLifecycleReplacedStateProjection(
            lifecycle_state=replaced.lifecycle_state,
            business_classification=replaced.business_classification,
            business_pct=None if replaced.business_pct is None else display_decimal(replaced.business_pct),
            classified_by=replaced.classified_by,
            reversed_by=_reversal_operations(operation_id, replaced),
        ),
    )


def lifecycle_validation_result(
    profile_id: UUID,
    operation_id: LedgerLifecycleOperationId,
    validation: LedgerLifecycleValidationProjection,
) -> LedgerLifecycleOperationResult:
    """Bind one pre-write validation refusal to its exact profile and operation."""
    return LedgerLifecycleOperationResult(
        outcome="validation_error",
        profile_id=profile_id,
        operation_id=operation_id,
        validation=validation,
    )


def _bounded_validation_message(error: Exception) -> str:
    raw_message = str(error).strip()
    return raw_message[:LEDGER_LIFECYCLE_MAX_VALIDATION_MESSAGE_LENGTH] or (
        "ledger lifecycle values did not satisfy canonical validation"
    )


def _transaction_recovery_facts(context: dict[str, object] | None) -> tuple[tuple[str, ...], int]:
    raw_transaction_ids = context.get("transaction_ids") if context is not None else None
    if not isinstance(raw_transaction_ids, str):
        return (), 0
    all_transaction_ids = tuple(value for value in raw_transaction_ids.split(",") if value)
    transaction_ids = all_transaction_ids[:LEDGER_LIFECYCLE_MAX_RECOVERY_TRANSACTION_IDS]
    omitted_count = max(0, len(all_transaction_ids) - len(transaction_ids))
    return transaction_ids, omitted_count


def _blocker_projection_from_context(
    context: dict[str, object],
) -> tuple[LedgerLifecycleBlockerProjection | None, int | None]:
    required = ("work_unit_id", "calculation_revision_id", "modelo", "filing_year", "period")
    if not all(key in context for key in required):
        return None, None
    filing_year = context["filing_year"]
    count = context.get("blocking_reference_count")
    if (
        not isinstance(filing_year, str)
        or not filing_year.isdigit()
        or not isinstance(count, str)
        or not count.isdigit()
    ):
        return None, None
    # The canonical lifecycle guard publishes blocker locators and count, but not
    # its revision state. Preserve that value only when another guard supplies it.
    blocker = LedgerLifecycleBlockerProjection.model_validate(
        {
            "work_unit_id": context["work_unit_id"],
            "calculation_revision_id": context["calculation_revision_id"],
            "modelo": context["modelo"],
            "filing_year": int(filing_year),
            "period": context["period"],
            **({"revision_state": context["revision_state"]} if isinstance(context.get("revision_state"), str) else {}),
        },
    )
    return blocker, int(count)


def project_lifecycle_validation_from_error(
    error: Exception,
    *,
    transaction_id: str | None,
) -> LedgerLifecycleValidationProjection:
    """Keep bounded validation text and allowlisted recovery facts from the error."""
    message = _bounded_validation_message(error)
    context = error.context if isinstance(error, CadrumoError) else None
    transaction_ids, omitted_count = _transaction_recovery_facts(context)
    blocker: LedgerLifecycleBlockerProjection | None = None
    blocker_count: int | None = None
    if context is not None:
        blocker, blocker_count = _blocker_projection_from_context(context)

    return LedgerLifecycleValidationProjection(
        messages=(message,),
        transaction_id=transaction_id,
        transaction_ids=transaction_ids,
        transaction_ids_omitted_count=omitted_count,
        blocking_reference=blocker,
        blocking_reference_count=blocker_count,
    )


def require_lifecycle_result_size(result: LedgerLifecycleExecutionResult) -> None:
    """Reject an encrypted lifecycle result that exceeds its registered byte limit."""
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > LEDGER_LIFECYCLE_MAX_RESULT_BYTES - 128:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _lifecycle_receipt_identity_matches(
    projected: LedgerLifecycleOperationResult,
    receipt: OperationTerminalReceipt,
) -> bool:
    return (
        receipt.identity.definition_id == projected.operation_id
        and receipt.identity.subject_ref == profile_operation_subject(str(projected.profile_id))
    )


def _lifecycle_refusal_receipt_matches(receipt: OperationTerminalReceipt) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.refusal_ref == LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE
        and receipt.refusal_detail_ref is not None
        and refused_receipt_references_hold(receipt)
        and receipt.diagnostic_ref is None
        and receipt.effect is OperationEffect.NONE
    )


def project_lifecycle_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only a lifecycle result whose operation, subject, condition, and effect match."""
    if type(result) is not LedgerLifecycleExecutionResult:
        raise ValueError("invalid ledger lifecycle execution result")
    projected = result.result
    if not _lifecycle_receipt_identity_matches(projected, receipt):
        raise ValueError("ledger lifecycle result belongs to another operation or profile")
    if projected.outcome == "validation_error":
        if not _lifecycle_refusal_receipt_matches(receipt):
            raise ValueError("lifecycle refusal has an incompatible terminal receipt")
        return projected
    message = "lifecycle success has an incompatible terminal receipt"
    if projected.result is None:
        raise ValueError(message)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=projected.operation_id,
        subject_ref=profile_operation_subject(str(projected.profile_id)),
        effect=OperationEffect.UPDATED,
        message=message,
    )
    return projected


__all__ = [
    "lifecycle_validation_result",
    "project_lifecycle_mutation_from_action",
    "project_lifecycle_operation_result",
    "project_lifecycle_validation_from_error",
    "require_lifecycle_result_size",
]
