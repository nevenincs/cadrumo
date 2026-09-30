"""CLI transport bridges for registered purchase-invoice evidence mutations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import cast

import typer

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.evidence import PurchaseInvoiceEvidencePatch
from ...application.ledger.evidence_mutation_operation import (
    LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateField,
    LedgerEvidenceUpdatePatch,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error

_UPDATE_FIELD_NAMES = frozenset(
    {"supplier", "invoice_number", "invoice_date", "taxable_base", "iva_rate", "iva_amount", "notes"}
)


def run_ledger_evidence_update(
    ctx: typer.Context,
    *,
    evidence_id: str,
    patch: PurchaseInvoiceEvidencePatch,
) -> LedgerEvidenceUpdateProjection:
    """Run one exact-profile evidence update and correlate every requested field."""
    client = bound_profile_client(ctx)
    patch_fields = cast(
        tuple[LedgerEvidenceUpdateField, ...],
        tuple(
            sorted(
                field
                for field in patch.model_fields_set
                if field in _UPDATE_FIELD_NAMES and getattr(patch, field) is not None
            ),
        ),
    )
    wire_values = {field: _wire_patch_value(getattr(patch, field)) for field in patch_fields}
    worker_patch = LedgerEvidenceUpdatePatch.model_validate(wire_values)
    request = LedgerEvidenceUpdateRequest(
        profile_id=client.profile_id,
        evidence_id=evidence_id,
        patch=worker_patch,
        patch_fields=patch_fields,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEvidenceUpdateProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    expected_effect = OperationEffect.UPDATED if patch_fields else OperationEffect.NONE
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or projection.profile_id != client.profile_id
        or projection.record.bucket_id != str(client.profile_id)
        or projection.record.evidence_id != evidence_id
        or len(projection.bucket_event_ids) != (1 if patch_fields else 0)
        or not _matches_patch(worker_patch, patch_fields, projection)
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


def run_ledger_evidence_remove(ctx: typer.Context, *, evidence_id: str) -> LedgerEvidenceRemoveProjection:
    """Run one exact-profile evidence removal and correlate its full result."""
    client = bound_profile_client(ctx)
    request = LedgerEvidenceRemoveRequest(profile_id=client.profile_id, evidence_id=evidence_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEvidenceRemoveProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.profile_id != client.profile_id
        or projection.record.bucket_id != str(client.profile_id)
        or projection.record.evidence_id != evidence_id
        or len(projection.bucket_event_ids) != 1
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
    """Render a canonical CLI patch value as stable bounded wire text."""
    if isinstance(value, Decimal):
        return display_decimal(value)
    return value


def _matches_patch(
    patch: LedgerEvidenceUpdatePatch,
    fields: tuple[LedgerEvidenceUpdateField, ...],
    projection: LedgerEvidenceUpdateProjection,
) -> bool:
    """Correlate all requested values with the canonical returned record."""
    record = projection.record
    for field in fields:
        requested = getattr(patch, field)
        projected = getattr(record, field)
        if field in {"taxable_base", "iva_rate", "iva_amount"}:
            try:
                matches = projected is not None and display_decimal(Decimal(projected)) == requested
            except InvalidOperation:
                matches = False
        else:
            matches = projected == requested
        if not matches:
            return False
    return True


__all__ = ["run_ledger_evidence_remove", "run_ledger_evidence_update"]
