"""CLI transport bridge for worker-owned ledger transaction correction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import cast
from uuid import UUID

import typer

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.models import ManualLedgerTransactionPatch
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...application.ledger.update_contracts import (
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LEDGER_UPDATE_VALIDATION_REFUSAL_CODE,
    LedgerUpdateOperationResult,
    LedgerUpdatePatch,
    LedgerUpdatePatchField,
    LedgerUpdateRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def ledger_update_validation_refusal(
    completed: RegisteredOperationCompletion[LedgerUpdateOperationResult], profile_id: UUID
) -> LedgerUpdateOperationResult | None:
    """Ledger update validation refusal."""
    projection = completed.projection
    if projection.outcome == "validation_error":
        invalid_refusal = (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_UPDATE_VALIDATION_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
            or projection.profile_id != profile_id
            or not projection.validation_messages
        )
        if invalid_refusal:
            raise invalid_completion_error(completed)
        return projection
    return None


def require_ledger_update_correlation(
    completed: RegisteredOperationCompletion[LedgerUpdateOperationResult],
    profile_id: UUID,
    transaction_id: str,
    worker_patch: LedgerUpdatePatch,
    patch_fields: tuple[LedgerUpdatePatchField, ...],
    transaction: LedgerTransactionProjection,
) -> None:
    """Require ledger update correlation."""
    projection = completed.projection
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    prefix = transaction_id.strip().lower()
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or projection.profile_id != profile_id
        or projection.source_transaction_id is None
        or not projection.source_transaction_id.startswith(prefix)
        or (expected_effect is OperationEffect.NONE and transaction.transaction_id != projection.source_transaction_id)
        or not _matches_patch(worker_patch, patch_fields, transaction, projection)
    )
    if invalid:
        raise invalid_completion_error(completed)


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
    if (refused := ledger_update_validation_refusal(completed, client.profile_id)) is not None:
        return refused

    transaction = projection.transaction
    if transaction is None or projection.review_status is None:
        raise invalid_completion_error(completed)
    require_ledger_update_correlation(
        completed, client.profile_id, transaction_id, worker_patch, patch_fields, transaction
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
    projection: LedgerUpdateOperationResult,
) -> bool:
    """Correlate every selected patch field with its projected canonical meaning."""
    for field in fields:
        value = getattr(patch, field)
        if field == "own_account_id":
            if projection.own_account_id != value:
                return False
        elif not ledger_update_field_matches(field, value, transaction, projection.group_label):
            return False
    return True


def ledger_update_field_matches(
    field: LedgerUpdatePatchField,
    value: object,
    transaction: LedgerTransactionProjection,
    group_label: str | None,
) -> bool:
    """Compare nullable text, required currency, grouping, or a direct wire field."""
    if field == "currency":
        return value is not None and transaction.currency == value
    if field in {"counterparty", "notes"}:
        return bool(getattr(transaction, field) == (value or ""))
    if field == "group_label":
        return group_label == value
    if field in {
        "booked_date",
        "value_date",
        "amount",
        "direction",
        "description",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "irpf_category",
    }:
        return bool(getattr(transaction, field) == value)
    return True


__all__ = ["run_ledger_update"]
