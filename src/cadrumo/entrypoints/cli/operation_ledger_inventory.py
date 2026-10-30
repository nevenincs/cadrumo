"""Authenticated CLI bridge for profile-owned inventory operations."""

from __future__ import annotations

import json
from typing import Never, TypeVar, cast
from uuid import UUID

import typer
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.inventory.registered_evidence_operation import (
    INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    InventoryEvidenceAddProjection,
    InventoryEvidenceAddRequest,
)
from ...application.inventory.registered_options_operation import (
    INVENTORY_OPTIONS_OPERATION_DEFINITION_ID,
    InventoryOptionsProjection,
    InventoryOptionsRequest,
)
from ...application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryInspectProjection,
    InventoryLedgerChangeProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryRefusalProjection,
    InventoryValuationOperationProjection,
)
from ...application.inventory.registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityRecordRequest,
    InventoryClosingValueRecordRequest,
    InventoryCorrectRequest,
    InventoryCreateRequest,
    InventoryDescribeRequest,
    InventoryInspectRequest,
    InventoryLedgerChangeRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryMovementCorrectRequest,
    InventoryMovementReverseRequest,
    InventoryRestoreRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.contribuyente.inventory.corrections import (
    INVENTORY_CORRECTION_REFUSAL_REASONS,
    inventory_refusal_key,
)
from .ledger_business_payloads import (
    InventoryClosingAuthorityRecordResult,
    InventoryCreateResult,
    InventoryEvidenceAddResult,
    InventoryInspectResult,
    InventoryLedgerChangeResult,
    InventoryListResult,
    InventoryMovementAddResult,
    InventoryOptionsResult,
    InventoryValuationPreviewPayload,
)

ProjectionT = TypeVar("ProjectionT", bound=BaseModel)

type _JsonValue = bool | int | float | str | list[_JsonValue] | dict[str, _JsonValue] | None

_REFUSAL_LOCALE_KEYS = {
    "activity_conflict": "cli.app.ledger.inventory.refusal_activity_conflict",
    "activity_not_found": "cli.app.ledger.inventory.refusal_activity_not_found",
    "invalid_valuation_method": "application.inventory.service.errors.invalid_valuation_method",
    "duplicate_movement_id": "cli.app.ledger.inventory.refusal_duplicate_movement_id",
    "inventory_validation": "errors.refused.refused_profile_inventory_validation",
    "closing_authority_conflict": "application.inventory.service.errors.closing_authority_conflict",
    "closing_authority_invalid": "errors.refused.refused_profile_inventory_validation",
    "evidence_file_not_admitted": inventory_refusal_key("evidence_file_not_admitted"),
    **{reason: inventory_refusal_key(reason) for reason in INVENTORY_CORRECTION_REFUSAL_REASONS},
}

_LEDGER_CHANGE_DEFINITION_IDS: dict[type[InventoryLedgerChangeRequest], str] = {
    InventoryDescribeRequest: INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    InventoryCorrectRequest: INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    InventoryMovementCorrectRequest: INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    InventoryMovementReverseRequest: INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    InventoryRetireRequest: INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    InventoryRestoreRequest: INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
}


def _client_for_request(ctx: typer.Context, request: BaseModel) -> FrontendClient:
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise InternalInvariantError("inventory request has no typed profile identity")
    return require_profile_client(ctx, expected_profile_id=profile_id)


def _run[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
    allow_refusal_detail: bool,
) -> RegisteredOperationCompletion[ProjectionT]:
    client = _client_for_request(ctx, request)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=allow_refusal_detail,
    )
    projection_profile = getattr(completed.projection, "profile_id", None)
    if projection_profile is not None and projection_profile != client.profile_id:
        raise invalid_completion_error(completed)
    return completed


def _raise_registered_refusal[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
    refusal: InventoryRefusalProjection,
) -> Never:
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != refusal.code
        or refusal.reason not in _REFUSAL_LOCALE_KEYS
    ):
        raise invalid_completion_error(completed)
    context: dict[str, str] = {
        **{fact.key: fact.value for fact in refusal.reason_facts},
        "operation_id": str(completed.operation_id),
        "terminal_condition": completed.terminal_condition.value,
        "effect": completed.effect.value,
        "refusal_code": refusal.code,
        "reason": refusal.reason,
    }
    if refusal.actividad_id is not None:
        context["actividad_id"] = refusal.actividad_id
    if refusal.year is not None:
        context["year"] = str(refusal.year)
    if refusal.movement_id is not None:
        context["movement_id"] = refusal.movement_id
    if refusal.valuation_method is not None:
        context["valuation_method"] = refusal.valuation_method
    raise CliRefusedBoundaryError(
        translated_message=_REFUSAL_LOCALE_KEYS[refusal.reason],
        context=context,
    )


def _collapse_public_decimal_objects(value: _JsonValue) -> _JsonValue:
    """Match the established inventory CLI wire by unwrapping tagged decimals."""
    if isinstance(value, list):
        return [_collapse_public_decimal_objects(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"decimal"} and isinstance(value.get("decimal"), str):
            return value["decimal"]
        return {key: _collapse_public_decimal_objects(item) for key, item in value.items()}
    return value


def _ledger_payload_json(ledger: InventoryLedgerProjection, *, outcome: str | None = None) -> str:
    # Pydantic serialized this strict projection; the standard decoder exposes its
    # result as Any, so restore the closed JSON value type at this boundary.
    payload = cast(_JsonValue, json.loads(ledger.model_dump_json()))
    if not isinstance(payload, dict):
        raise ValueError("inventory ledger projection did not produce a JSON object")
    collapsed = _collapse_public_decimal_objects(payload)
    if not isinstance(collapsed, dict):
        raise ValueError("inventory ledger projection did not produce an object")
    if outcome is not None:
        collapsed["outcome"] = outcome
    return json.dumps(collapsed)


def read_inventory_catalogue(
    ctx: typer.Context,
) -> tuple[RegisteredOperationCompletion[InventoryListProjection], InventoryListResult]:
    """Read the selected profile's list projection inside its bound worker."""
    client_profile = UUID(require_active_bucket_id())
    request = InventoryListRequest(profile_id=client_profile)
    completed = _run(
        ctx,
        request,
        definition_id=INVENTORY_LIST_OPERATION_DEFINITION_ID,
        result_type=InventoryListProjection,
        allow_refusal_detail=False,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    payload = InventoryListResult.model_validate(
        {
            "bucket_id": str(client_profile),
            "rows": [
                {
                    "actividad_id": row.actividad_id,
                    "year": row.year,
                    "valuation_method": row.valuation_method.value,
                    "opening_stock": row.opening_stock.decimal,
                    "advisories": [item.model_dump(mode="json") for item in row.advisories],
                    "movement_count": row.movement_count,
                    "label": row.label,
                    "retired": row.retired,
                    "retirement_reason": None if row.retirement_reason is None else row.retirement_reason.value,
                    "correction_count": row.correction_count,
                }
                for row in projection.rows
            ],
            "count": len(projection.rows),
        },
    )
    return completed, payload


def create_inventory_ledger(
    ctx: typer.Context,
    *,
    request: InventoryCreateRequest,
) -> tuple[RegisteredOperationCompletion[InventoryCreateProjection], InventoryCreateResult]:
    """Create one ledger through the request's exact profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
        result_type=InventoryCreateProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_registered_refusal(completed, projection.refusal)
    ledger = projection.ledger
    if (
        projection.outcome != "created"
        or ledger is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or len(projection.bucket_event_ids) != 1
        or not ledger.bucket_event_ids
    ):
        raise invalid_completion_error(completed)
    payload = InventoryCreateResult.model_validate_json(_ledger_payload_json(ledger))
    return completed, payload


def add_inventory_movement(
    ctx: typer.Context,
    *,
    request: InventoryMovementAddRequest,
) -> tuple[RegisteredOperationCompletion[InventoryMovementAddProjection], InventoryMovementAddResult]:
    """Append one typed movement through the request's exact profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
        result_type=InventoryMovementAddProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_registered_refusal(completed, projection.refusal)
    ledger = projection.ledger
    if (
        projection.outcome != "added"
        or ledger is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or len(projection.bucket_event_ids) != 1
        or not ledger.bucket_event_ids
    ):
        raise invalid_completion_error(completed)
    return completed, InventoryMovementAddResult.model_validate_json(_ledger_payload_json(ledger))


def inspect_inventory_ledger(
    ctx: typer.Context,
    *,
    request: InventoryInspectRequest,
) -> tuple[RegisteredOperationCompletion[InventoryInspectProjection], InventoryInspectResult]:
    """Read one ledger with its movements and retained history through the exact profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
        result_type=InventoryInspectProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_registered_refusal(completed, projection.refusal)
    ledger = projection.ledger
    if (
        ledger is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return completed, InventoryInspectResult.model_validate_json(_ledger_payload_json(ledger))


def apply_inventory_ledger_change(
    ctx: typer.Context,
    *,
    request: InventoryLedgerChangeRequest,
) -> tuple[RegisteredOperationCompletion[InventoryLedgerChangeProjection], InventoryLedgerChangeResult]:
    """Run one edit, rectification, retirement or restoration through the exact profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=_LEDGER_CHANGE_DEFINITION_IDS[type(request)],
        result_type=InventoryLedgerChangeProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_registered_refusal(completed, projection.refusal)
    ledger = projection.ledger
    expected_effect = OperationEffect.UPDATED if projection.outcome == "applied" else OperationEffect.NONE
    if (
        ledger is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return completed, InventoryLedgerChangeResult.model_validate_json(
        _ledger_payload_json(ledger, outcome=projection.outcome)
    )


def preview_inventory_valuation(
    ctx: typer.Context,
    *,
    request: InventoryValuationPreviewRequest,
) -> tuple[RegisteredOperationCompletion[InventoryValuationOperationProjection], InventoryValuationPreviewPayload]:
    """Run and audit a valuation preview through the exact profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
        result_type=InventoryValuationOperationProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_registered_refusal(completed, projection.refusal)
    preview = projection.preview
    if (
        projection.outcome != "previewed"
        or preview is None
        or preview.profile_id != request.profile_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or len(preview.bucket_event_ids) != 1
    ):
        raise invalid_completion_error(completed)
    return completed, InventoryValuationPreviewPayload(
        actividad_id=preview.actividad_id,
        year=preview.year,
        valuation_method=preview.valuation_method.value,
        derived_closing_value=preview.derived_closing_value.decimal,
        cogs=preview.cogs.decimal,
        bucket_event_ids=list(preview.bucket_event_ids),
    )


def record_inventory_closing_authority(
    ctx: typer.Context,
    *,
    request: InventoryClosingAuthorityRecordRequest,
) -> tuple[
    RegisteredOperationCompletion[InventoryClosingAuthorityOperationProjection],
    InventoryClosingAuthorityRecordResult,
]:
    """Persist one immutable authority record through the exact profile worker."""
    return _record_closing(ctx, request, definition_id=INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID)


def read_inventory_options(ctx: typer.Context, *, request: InventoryOptionsRequest) -> InventoryOptionsResult:
    """Read the inventory form vocabularies through the exact profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=INVENTORY_OPTIONS_OPERATION_DEFINITION_ID,
        result_type=InventoryOptionsProjection,
        allow_refusal_detail=False,
    )
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return InventoryOptionsResult.model_validate(completed.projection.model_dump(mode="json", exclude={"profile_id"}))


def add_inventory_evidence(ctx: typer.Context, *, request: InventoryEvidenceAddRequest) -> InventoryEvidenceAddResult:
    """Store one purchase document through the exact profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        result_type=InventoryEvidenceAddProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.refusal is not None:
        _raise_registered_refusal(completed, projection.refusal)
    if (
        projection.reference is None
        or projection.content_digest is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return InventoryEvidenceAddResult(reference=projection.reference, content_digest=str(projection.content_digest))


def record_inventory_closing_value(
    ctx: typer.Context,
    *,
    request: InventoryClosingValueRecordRequest,
) -> tuple[
    RegisteredOperationCompletion[InventoryClosingAuthorityOperationProjection],
    InventoryClosingAuthorityRecordResult,
]:
    """Persist one closing value derived from plain facts through the exact profile worker."""
    return _record_closing(ctx, request, definition_id=INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID)


def _record_closing(
    ctx: typer.Context,
    request: InventoryClosingAuthorityRecordRequest | InventoryClosingValueRecordRequest,
    *,
    definition_id: str,
) -> tuple[
    RegisteredOperationCompletion[InventoryClosingAuthorityOperationProjection],
    InventoryClosingAuthorityRecordResult,
]:
    completed = _run(
        ctx,
        request,
        definition_id=definition_id,
        result_type=InventoryClosingAuthorityOperationProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_registered_refusal(completed, projection.refusal)
    record = projection.record
    expected_effect = OperationEffect.UPDATED if record is not None and record.changed else OperationEffect.NONE
    if (
        projection.outcome != "recorded"
        or record is None
        or record.profile_id != request.profile_id
        or _inventory_authority_receipt_invalid(completed, expected_effect)
    ):
        raise invalid_completion_error(completed)
    return completed, InventoryClosingAuthorityRecordResult(
        actividad_id=record.actividad_id,
        year=record.year,
        authority_record_fingerprint=record.authority_record_fingerprint,
        decision_fingerprint=record.decision_fingerprint,
        physical_observation_fingerprint=record.physical_observation_fingerprint,
        prior_closing_link_fingerprint=record.prior_closing_link_fingerprint,
    )


__all__ = [
    "add_inventory_evidence",
    "add_inventory_movement",
    "apply_inventory_ledger_change",
    "create_inventory_ledger",
    "inspect_inventory_ledger",
    "preview_inventory_valuation",
    "read_inventory_catalogue",
    "read_inventory_options",
    "record_inventory_closing_authority",
    "record_inventory_closing_value",
]


def _inventory_authority_receipt_invalid(
    completed: RegisteredOperationCompletion[InventoryClosingAuthorityOperationProjection],
    expected_effect: OperationEffect,
) -> bool:
    """Require the expected inventory authority mutation effect and successful terminal receipt."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
    )
