"""Output emitters for Modelo 145 communication CLI commands.

Renderers for the local payer communication command group. They project
application Modelo 145 records, validation reports, and export results into the
central CLI envelope format for both text and JSON output.

See Also:
    :mod:`~entrypoints.cli._modelo_m145_cli`
        Typer command group that calls these emitters.
    :mod:`~entrypoints.cli._modelo_payloads_m145`
        Typed payload classes returned by the JSON envelope.
    :func:`~entrypoints.cli._common.emit_envelope`
        Shared CLI output path used by each emitter in this module.
    :class:`~application.modelo.M145CommunicationRecord`
        Application record rendered by record mutation emitters.
    :class:`~application.modelo.M145CommunicationValidationResult`
        Application validation result rendered by validation emitters.
    :class:`~application.modelo.M145CommunicationExportResult`
        Application export result rendered by export emitters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import typer

from ._common import emit_envelope
from ._modelo_payloads_m145 import (
    M145CommunicationExportResultPayload,
    M145CommunicationRecordPayload,
    M145CommunicationRecordResult,
    M145CommunicationValidationResultPayload,
)

if TYPE_CHECKING:
    from ...application.modelo import (
        M145CommunicationExportResult,
        M145CommunicationRecord,
        M145CommunicationValidationResult,
    )

type M145RecordOperation = Literal[
    "modelo.m145.create",
    "modelo.m145.mark_delivered_to_payer",
    "modelo.m145.mark_locally_completed",
]


def m145_record_result_payload(
    *,
    operation: M145RecordOperation,
    record: M145CommunicationRecord,
) -> M145CommunicationRecordResult:
    """Project one communication record mutation into its JSON payload."""
    return M145CommunicationRecordResult(
        operation=operation,
        record=M145CommunicationRecordPayload.from_record(record),
    )


def m145_record_result_lines(
    *,
    operation: M145RecordOperation,
    record: M145CommunicationRecord,
) -> list[str]:
    """Project one communication record mutation into text output lines."""
    lines = [
        f"operation\t{operation}",
        f"communication_record_id\t{record.communication_record_id}",
        f"bucket_id\t{record.bucket_id}",
        f"modelo\t{record.modelo}",
        f"communication_year\t{record.communication_year}",
        f"period\t{record.period_token.value}",
        f"revision_id\t{record.revision_id}",
        f"state\t{record.state.value}",
        f"created_at\t{record.created_at.isoformat()}",
    ]
    if record.delivered_to_payer_at is not None:
        lines.append(f"delivered_to_payer_at\t{record.delivered_to_payer_at.isoformat()}")
    if record.locally_completed_at is not None:
        lines.append(f"locally_completed_at\t{record.locally_completed_at.isoformat()}")
    if record.note is not None:
        lines.append(f"note\t{record.note}")
    return lines


def emit_m145_record_result(
    ctx: typer.Context,
    *,
    operation: M145RecordOperation,
    record: M145CommunicationRecord,
) -> None:
    """Emit one communication record mutation through the central envelope."""
    emit_envelope(
        ctx,
        command=operation,
        result=m145_record_result_payload(operation=operation, record=record),
        lines=m145_record_result_lines(operation=operation, record=record),
    )


def m145_validation_result_payload(
    result: M145CommunicationValidationResult,
) -> M145CommunicationValidationResultPayload:
    """Project one validation result into its JSON payload."""
    return M145CommunicationValidationResultPayload.from_result(result)


def m145_validation_result_lines(result: M145CommunicationValidationResult) -> list[str]:
    """Project one validation result into text output lines."""
    lines = [
        "operation\tmodelo.m145.validate",
        f"communication_record_id\t{result.communication_record_id}",
        f"valid\t{result.valid}",
        f"issue_count\t{result.issue_count}",
    ]
    for issue in result.issues:
        lines.append(f"issue\t{issue.kind.value}\t{issue.casilla_id or ''}\t{issue.message}")
    return lines


def emit_m145_validation_result(
    ctx: typer.Context,
    *,
    result: M145CommunicationValidationResult,
) -> None:
    """Emit one validation result through the central envelope."""
    emit_envelope(
        ctx,
        command="modelo.m145.validate",
        result=m145_validation_result_payload(result),
        lines=m145_validation_result_lines(result),
    )


def m145_export_result_payload(result: M145CommunicationExportResult) -> M145CommunicationExportResultPayload:
    """Project one export result into its JSON payload."""
    return M145CommunicationExportResultPayload.from_result(result)


def m145_export_result_lines(
    result: M145CommunicationExportResult,
    *,
    payload: M145CommunicationExportResultPayload | None = None,
) -> list[str]:
    """Project one export result into text output lines."""
    output_payload = payload or m145_export_result_payload(result)
    return [
        "operation\tmodelo.m145.export",
        f"communication_record_id\t{result.communication_record_id}",
        f"export_layout_id\t{result.export_layout_id}",
        f"encoding\t{result.encoding}",
        f"record_count\t{result.record_count}",
        f"byte_length\t{result.byte_length}",
        f"payload_sha256\t{result.payload_sha256}",
        f"payload_text\t{output_payload.payload_text}",
    ]


def emit_m145_export_result(
    ctx: typer.Context,
    *,
    result: M145CommunicationExportResult,
) -> None:
    """Emit one export result through the central envelope."""
    payload = m145_export_result_payload(result)
    emit_envelope(
        ctx,
        command="modelo.m145.export",
        result=payload,
        lines=m145_export_result_lines(result, payload=payload),
    )


__all__ = [
    "M145RecordOperation",
    "emit_m145_export_result",
    "emit_m145_record_result",
    "emit_m145_validation_result",
    "m145_export_result_lines",
    "m145_export_result_payload",
    "m145_record_result_lines",
    "m145_record_result_payload",
    "m145_validation_result_lines",
    "m145_validation_result_payload",
]
