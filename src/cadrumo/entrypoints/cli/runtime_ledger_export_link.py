"""Authenticated CLI bridges for the canonical ledger export and link actions."""

from __future__ import annotations

from pathlib import Path
from typing import Never

import typer

from ...application.export.tabular import ExportSerializationFormat
from ...application.ledger.export_operation import (
    LEDGER_EXPORT_OPERATION_DEFINITION_ID,
    LedgerExportProjection,
    LedgerExportRequest,
)
from ...application.ledger.link_operation import (
    LEDGER_LINK_OPERATION_DEFINITION_ID,
    LEDGER_LINK_VALIDATION_REFUSAL_CODE,
    LedgerLinkOperationResult,
    LedgerLinkRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid[ProjectionT: LedgerExportProjection | LedgerLinkOperationResult](
    completed: RegisteredOperationCompletion[ProjectionT],
) -> Never:
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def export_ledger_for_cli(
    ctx: typer.Context,
    *,
    output: Path,
    export_format: ExportSerializationFormat,
    include_inactive: bool,
    period: Period | None,
    actor: str | None,
) -> LedgerExportProjection:
    """Publish one export through the immutable profile client and correlate its report."""
    client = bound_profile_client(ctx)
    output_path = str(output.absolute())
    public_period = PublicPeriod.from_period(period) if period is not None else None
    request = LedgerExportRequest(
        profile_id=client.profile_id,
        output_path=output_path,
        export_format=export_format,
        include_inactive=include_inactive,
        period=public_period,
        actor=actor or str(client.profile_id),
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerExportProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or projection.bucket_id != str(client.profile_id)
        or projection.output_path != output_path
        or projection.export_format is not export_format
        or projection.row_count != len(projection.rows)
        or len(projection.bucket_event_ids) != 1
        or any(row.bucket_id != str(client.profile_id) for row in projection.rows)
    ):
        _invalid(completed)
    return projection


def link_ledger_invoice_for_cli(
    ctx: typer.Context,
    *,
    transaction_id: str,
    invoice_id: str,
    actor: str | None,
) -> LedgerLinkOperationResult:
    """Resolve and atomically link an invoice in the exact profile worker."""
    client = bound_profile_client(ctx)
    actor_label = (actor or "operator").strip() or "operator"
    request = LedgerLinkRequest(
        profile_id=client.profile_id,
        transaction_id=transaction_id,
        invoice_id=invoice_id,
        actor=actor_label,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_LINK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerLinkOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or result.transaction_id != transaction_id
        or result.invoice_id != invoice_id
    ):
        _invalid(completed)

    if result.outcome == "refused":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.effect is not OperationEffect.NONE
            or completed.refusal_code != LEDGER_LINK_VALIDATION_REFUSAL_CODE
            or result.reason not in {"missing_invoice", "cross_bucket_invoice"}
            or result.projection is not None
        ):
            _invalid(completed)
        return result

    projection = result.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or projection is None
        or projection.profile_id != client.profile_id
        or projection.bucket_id != str(client.profile_id)
        or projection.invoice_id != invoice_id
        or projection.actor != actor_label
        or not projection.transaction_id.startswith(transaction_id.strip().lower())
        or projection.transaction.transaction_id != projection.transaction_id
        or projection.transaction.invoice_id != invoice_id
        or len(projection.bucket_event_ids) != 1
    ):
        _invalid(completed)
    return result


__all__ = ["export_ledger_for_cli", "link_ledger_invoice_for_cli"]
