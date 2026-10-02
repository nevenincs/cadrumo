"""CLI transport bridge for worker-owned ledger transaction correction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import cast

import typer

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.models import ManualLedgerTransactionPatch
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...application.ledger.update_operation import (
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LEDGER_UPDATE_VALIDATION_REFUSAL_CODE,
    LedgerUpdateOperationResult,
    LedgerUpdatePatch,
    LedgerUpdatePatchField,
    LedgerUpdateRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def run_ledger_update(
    ctx: typer.Context,
    *,
    transaction_id: str,
    patch: ManualLedgerTransactionPatch,
    actor: str | None,
) -> LedgerUpdateOperationResult:
    """Run one exact-profile update and correlate its full result and effect."""
    client = bound_profile_client(ctx)
    patch_fields: tuple[LedgerUpdatePatchField, ...] = tuple(
        sorted(cast(LedgerUpdatePatchField, field) for field in patch.model_fields_set)
    )
    worker_patch = LedgerUpdatePatch.model_validate(
        {field: _wire_patch_value(getattr(patch, field)) for field in patch_fields},
    )
    request = LedgerUpdateRequest(
        profile_id=client.profile_id,
        transaction_id=transaction_id,
        patch=worker_patch,
        patch_fields=patch_fields,
        actor=actor if actor else None,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerUpdateOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "validation_error":
        invalid_refusal = (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_UPDATE_VALIDATION_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
            or projection.profile_id != client.profile_id
            or not projection.validation_messages
        )
        if invalid_refusal:
            raise submitted_operation_error(
                completed.operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=completed.terminal_condition,
                effect=completed.effect,
                refusal_code=completed.refusal_code,
            )
        return projection

    transaction = projection.transaction
    if transaction is None or projection.review_status is None:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    prefix = transaction_id.strip().lower()
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or projection.profile_id != client.profile_id
        or not transaction.transaction_id.startswith(prefix)
        or not _matches_patch(worker_patch, patch_fields, transaction, projection.group_label)
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return projection


def _wire_patch_value(value: object) -> object:
    """Render one already-validated CLI value as stable JSON wire text."""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return display_decimal(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _matches_patch(
    patch: LedgerUpdatePatch,
    fields: tuple[LedgerUpdatePatchField, ...],
    transaction: LedgerTransactionProjection,
    group_label: str | None,
) -> bool:
    """Correlate every projected fact whose canonical meaning is in the request."""
    for field in fields:
        value = getattr(patch, field)
        if field == "booked_date" and transaction.booked_date != value:
            return False
        if field == "value_date" and transaction.value_date != value:
            return False
        if field == "amount" and transaction.amount != value:
            return False
        if field == "direction" and transaction.direction != value:
            return False
        if field == "currency" and (value is None or transaction.currency != value):
            return False
        if field == "counterparty" and transaction.counterparty != (value or ""):
            return False
        if field == "description" and transaction.description != value:
            return False
        if field == "taxable_base" and transaction.taxable_base != value:
            return False
        if field == "iva_rate" and transaction.iva_rate != value:
            return False
        if field == "iva_amount" and transaction.iva_amount != value:
            return False
        if field == "irpf_category" and transaction.irpf_category != value:
            return False
        if field == "notes" and transaction.notes != (value or ""):
            return False
        if field == "group_label" and group_label != value:
            return False
    return True


__all__ = ["run_ledger_update"]
