"""Submit canonical ledger selections through exact-profile runtime custody."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.list_operation import (
    LEDGER_LIST_OPERATION_DEFINITION_ID,
    LedgerListProjection,
    LedgerListRequest,
)
from ...application.review.filter import LedgerReviewFilterSpec
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_ledger_list_for_cli(
    ctx: typer.Context,
    *,
    spec: LedgerReviewFilterSpec,
    group: str | None,
    by_group: bool,
    limit: int | None,
    offset: int,
    sort_by: LedgerSortField | None,
    sort_order: LedgerSortOrder,
    exclude_llm_rejected: bool,
) -> LedgerListProjection:
    """Keep private filter text in encrypted request storage and correlate the result."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        LedgerListRequest(
            profile_id=client.profile_id,
            filters=tuple(f"{clause.key}={clause.value}" for clause in spec.clauses),
            group=group,
            by_group=by_group,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            exclude_llm_rejected=exclude_llm_rejected,
        ),
        definition_id=LEDGER_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerListProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or result.offset != offset
        or result.limit != limit
        or result.by_group != by_group
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return result
