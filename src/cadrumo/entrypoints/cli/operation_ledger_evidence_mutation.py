"""CLI transport bridges for registered purchase-invoice evidence mutations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.evidence import PurchaseInvoiceEvidencePatch
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceNotFoundError
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
from ...application.ledger.evidence_verify_operation import (
    LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE,
    LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
    LedgerEvidenceVerifyChecked,
    LedgerEvidenceVerifyProjection,
    LedgerEvidenceVerifyRefusal,
    LedgerEvidenceVerifyRequest,
)
from ...application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject

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
    invalid = _evidence_update_receipt_invalid(
        completed, projection, client.profile_id, evidence_id, expected_effect, worker_patch, patch_fields
    )
    if invalid:
        raise invalid_completion_error(completed)
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
        raise invalid_completion_error(completed)
    return projection


def run_ledger_evidence_verify(ctx: typer.Context, *, evidence_id: str) -> LedgerEvidenceVerifyChecked:
    """Check one evidence record's stored bytes and correlate the finding the worker kept.

    Raises:
        PurchaseInvoiceEvidenceNotFoundError: When the profile holds no record of that id.
    """
    client = bound_profile_client(ctx)
    completed = run_registered_operation(
        client,
        LedgerEvidenceVerifyRequest(profile_id=client.profile_id, evidence_id=evidence_id),
        definition_id=LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEvidenceVerifyProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    outcome = projection.outcome
    if isinstance(outcome, LedgerEvidenceVerifyRefusal):
        if (
            projection.profile_id != client.profile_id
            or completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
        ):
            raise invalid_completion_error(completed)
        raise PurchaseInvoiceEvidenceNotFoundError(
            translated_message="errors.refused.refused_ledger_evidence_not_found",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
                facts={"evidence_record_present": outcome.evidence_record_present},
            ),
            context={
                "operation_id": str(completed.operation_id),
                "refusal_code": completed.refusal_code,
                "terminal_condition": completed.terminal_condition.value,
                "effect": completed.effect.value,
            },
        )
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.profile_id != client.profile_id
        or outcome.record.bucket_id != str(client.profile_id)
        or outcome.record.evidence_id != evidence_id
        or outcome.record.readability == "unchecked"
    )
    if invalid:
        raise invalid_completion_error(completed)
    return outcome


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


__all__ = ["run_ledger_evidence_remove", "run_ledger_evidence_update", "run_ledger_evidence_verify"]


def _evidence_update_receipt_invalid(
    completed: RegisteredOperationCompletion[LedgerEvidenceUpdateProjection],
    projection: LedgerEvidenceUpdateProjection,
    profile_id: UUID,
    evidence_id: str,
    expected_effect: OperationEffect,
    worker_patch: LedgerEvidenceUpdatePatch,
    patch_fields: tuple[LedgerEvidenceUpdateField, ...],
) -> bool:
    """Correlate evidence identity, requested patch fields, event count, and mutation effect."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (projection.profile_id != profile_id)
        or (projection.record.bucket_id != str(profile_id))
        or (projection.record.evidence_id != evidence_id)
        or (len(projection.bucket_event_ids) != (1 if patch_fields else 0))
        or (not _matches_patch(worker_patch, patch_fields, projection))
    )
