"""CLI bridges for exact-profile filed-register list and discover reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.filed_data import FiledDataListingRow
from ...application.live.filed_data_capture import (
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryReport,
)
from ...application.live.filed_read_operation import (
    FILED_DISCOVER_DEFINITION_ID,
    FILED_LIST_DEFINITION_ID,
    FiledDiscoverPublicResultV1,
    FiledDiscoverRequest,
    FiledListingFailurePublicV1,
    FiledListingRowPublicV1,
    FiledListPublicResultV1,
    FiledListRequest,
)
from ...application.live.remote_state_models import FiledDataCaptureFailureRow
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


@dataclass(frozen=True, slots=True)
class FiledListRead:
    """Keep the list receipt with reconstructed canonical register rows."""

    completion: RegisteredOperationCompletion[FiledListPublicResultV1]
    projection: FiledListPublicResultV1
    rows: tuple[FiledDataListingRow, ...]
    failures: tuple[FiledDataCaptureFailureRow, ...]


@dataclass(frozen=True, slots=True)
class FiledDiscoverRead:
    """Keep the discovery receipt with its reconstructed canonical report."""

    completion: RegisteredOperationCompletion[FiledDiscoverPublicResultV1]
    projection: FiledDiscoverPublicResultV1
    report: FiledHistoryDiscoveryReport


def _period(year: int, token: str | None) -> Period | None:
    return None if token is None else Period.from_year_and_code(year, token)


def _listing_row(row: FiledListingRowPublicV1) -> FiledDataListingRow:
    return FiledDataListingRow(
        modelo=row.modelo,
        year=row.year,
        period=Period.from_year_and_code(row.year, row.period),
        expediente_id=row.expediente_id,
        status=row.status,
        presented_at=row.presented_at,
        has_submitted_file=row.has_submitted_file,
        has_declaration_copy=row.has_declaration_copy,
        has_justificante=row.has_justificante,
    )


def _listing_failure(row: FiledListingFailurePublicV1) -> FiledDataCaptureFailureRow:
    return FiledDataCaptureFailureRow(
        modelo=row.modelo,
        year=row.year,
        period=_period(row.year, row.period),
        expediente_id=row.expediente_id,
        error_type=row.error_type,
        message=row.message,
    )


def _read_list_projection(
    projection: FiledListPublicResultV1,
    *,
    request: FiledListRequest,
) -> tuple[tuple[FiledDataListingRow, ...], tuple[FiledDataCaptureFailureRow, ...]]:
    if _filed_listing_request_differs(projection, request):
        raise ValueError("filed-list result does not match its submitted scope")
    rows = tuple(_listing_row(row) for row in projection.rows)
    failures = tuple(_listing_failure(row) for row in projection.failures)
    if projection.row_count != len(rows) or projection.failed_count != len(failures):
        raise ValueError("filed-list counts do not match their reconstructed rows")
    if any(_filed_listing_scope_invalid(row, request) for row in rows):
        raise ValueError("filed-list row falls outside its submitted scope")
    if any(_filed_listing_scope_invalid(row, request) for row in failures):
        raise ValueError("filed-list failure falls outside its submitted scope")
    return rows, failures


def _filed_listing_request_differs(projection: FiledListPublicResultV1, request: FiledListRequest) -> bool:
    """Correlate the projected model and year bounds with the exact submitted scope."""
    return (
        projection.modelo_filter != request.modelo
        or projection.year_from != request.year_from
        or projection.year_to != request.year_to
    )


def _discover_report(projection: FiledDiscoverPublicResultV1) -> FiledHistoryDiscoveryReport:
    return FiledHistoryDiscoveryReport(
        pairs=tuple(
            FiledHistoryDiscoveryPair(
                modelo=pair.modelo,
                ejercicio=pair.ejercicio,
                signals=pair.signals,
            )
            for pair in projection.pairs
        ),
        profile_year_span_determined=projection.profile_year_span_determined,
        register_options_read=projection.register_options_read,
        scoping_signal=projection.scoping_signal,
    )


def _require_settled_none(
    completed: RegisteredOperationCompletion[FiledListPublicResultV1]
    | RegisteredOperationCompletion[FiledDiscoverPublicResultV1],
) -> None:
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
    ):
        raise ValueError("filed read result disagrees with its settled receipt")


def read_filed_list_for_cli(
    ctx: typer.Context,
    *,
    modelo: str | None,
    year_from: int,
    year_to: int,
) -> FiledListRead:
    """Read one exact-profile listing through its registered worker."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = FiledListRequest(
        profile_id=profile_id,
        modelo=modelo,
        year_from=year_from,
        year_to=year_to,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=FILED_LIST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=FiledListPublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, FiledListPublicResultV1):
            raise ValueError("filed-list projection has an invalid type")
        rows, failures = _read_list_projection(projection, request=request)
        _require_settled_none(completed)
    except Exception:
        raise invalid_completion_error(completed) from None
    return FiledListRead(completion=completed, projection=projection, rows=rows, failures=failures)


def read_filed_discover_for_cli(ctx: typer.Context) -> FiledDiscoverRead:
    """Read exact-profile filing discovery through its registered worker."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = FiledDiscoverRequest(profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=FILED_DISCOVER_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=FiledDiscoverPublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, FiledDiscoverPublicResultV1):
            raise ValueError("filed-discover projection has an invalid type")
        report = _discover_report(projection)
        _require_settled_none(completed)
    except Exception:
        raise invalid_completion_error(completed) from None
    return FiledDiscoverRead(completion=completed, projection=projection, report=report)


__all__ = [
    "FiledDiscoverRead",
    "FiledListRead",
    "read_filed_discover_for_cli",
    "read_filed_list_for_cli",
]


def _filed_listing_scope_invalid(
    row: FiledDataListingRow | FiledDataCaptureFailureRow, request: FiledListRequest
) -> bool:
    """Require each reconstructed row or failure to remain within the submitted scope."""
    return not request.year_from <= row.year <= request.year_to or (
        request.modelo is not None and row.modelo != request.modelo
    )
