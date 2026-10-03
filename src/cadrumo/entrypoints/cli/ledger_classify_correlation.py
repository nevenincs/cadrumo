"""Canonical ledger classify correlation for exact-profile classification."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.classify_requests import (
    LedgerClassifyM210Options,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
)
from ...application.ledger.classify_result_contracts import (
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerClassifyOperationResult,
)
from ...application.ledger.operator_iva_contracts import (
    LedgerOperatorIvaResult,
)
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.transactions.enums import BusinessClassification
from .ledger_classify_fields import classification_selected_fields_match
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error


def classification_fields_mismatch(
    completed: RegisteredOperationCompletion[LedgerClassifyOperationResult],
    projection: LedgerClassifyOperationResult,
    profile_id: UUID,
    expected_effect: OperationEffect,
    transaction: LedgerTransactionProjection,
    prefix: str,
    expected_classification: str,
    expected_business_pct: str | None,
    wire_patch: LedgerClassifyPatch,
    selected_patch_fields: tuple[LedgerClassifyPatchField, ...],
    m210: LedgerClassifyM210Options | None,
    reaffirm: bool,
) -> bool:
    """Classification fields mismatch."""
    invalid = classification_receipt_mismatch(completed, projection, profile_id, expected_effect) or (
        (not transaction.transaction_id.startswith(prefix))
        or (transaction.business_classification != expected_classification)
        or (transaction.business_pct != expected_business_pct)
        or (
            not classification_selected_fields_match(
                patch=wire_patch,
                fields=selected_patch_fields,
                m210=m210,
                result=projection,
            )
        )
        or (reaffirm and not projection.bucket_event_ids)
    )
    return invalid


def operator_iva_expected_effect(result: LedgerOperatorIvaResult) -> OperationEffect:
    """Operator iva expected effect."""
    expected_effect = (
        OperationEffect.UPDATED
        if result.classification is not None and result.classification.bucket_event_ids
        else OperationEffect.NONE
    )
    return expected_effect


def correlate_classification_success(
    completed: RegisteredOperationCompletion[LedgerClassifyOperationResult],
    projection: LedgerClassifyOperationResult,
    profile_id: UUID,
    transaction_id: str,
    classification: BusinessClassification,
    business_pct: Decimal | None,
    wire_patch: LedgerClassifyPatch,
    selected_patch_fields: tuple[LedgerClassifyPatchField, ...],
    m210: LedgerClassifyM210Options | None,
    reaffirm: bool,
) -> None:
    """Correlate classification success."""
    transaction = projection.transaction
    if transaction is None or projection.review_status is None:
        raise invalid_completion_error(completed)
    prefix = transaction_id.strip().lower()
    expected_classification = classification.value
    expected_business_pct = (
        display_decimal(business_pct)
        if classification is BusinessClassification.MIXED and business_pct is not None
        else None
    )
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    invalid = classification_fields_mismatch(
        completed,
        projection,
        profile_id,
        expected_effect,
        transaction,
        prefix,
        expected_classification,
        expected_business_pct,
        wire_patch,
        selected_patch_fields,
        m210,
        reaffirm,
    )
    if invalid:
        raise invalid_completion_error(completed)


def correlate_classification_refusal(
    completed: RegisteredOperationCompletion[LedgerClassifyOperationResult],
    projection: LedgerClassifyOperationResult,
    profile_id: UUID,
) -> None:
    """Require the exact validation refusal without recorded mutation effects."""
    invalid_refusal = (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.refusal_code != LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
        or completed.effect is not OperationEffect.NONE
        or projection.profile_id != profile_id
        or not projection.validation_messages
    )
    if invalid_refusal:
        raise invalid_completion_error(completed)
    if completed.effect is not OperationEffect.NONE or projection.bucket_event_ids:
        raise invalid_completion_error(completed)


def classification_receipt_mismatch(
    completed: RegisteredOperationCompletion[LedgerClassifyOperationResult],
    projection: LedgerClassifyOperationResult,
    profile_id: UUID,
    expected_effect: OperationEffect,
) -> bool:
    """Correlate the truthful settled receipt before selected-field readback."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or projection.profile_id != profile_id
    )
