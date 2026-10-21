"""Word a settled operation's receipt, typed result and recorded stop for the run screen.

The result is the registered result model's own JSON, formatted and cut into
pages a terminal can hold. A refused or failed operation is worded from the
detail it recorded: its registered code, its message with the recorded context,
and the precondition verdict that says what would let it proceed.
"""

from __future__ import annotations

import json
from typing import Final

from pydantic import BaseModel

from ....application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....core.errors.error_codes import render_error_text
from ....core.errors.hierarchy import RecordedRegisteredError
from ....core.i18n.render import tr
from .projection import build_operation_modal_view_model
from .refusal_explanation import recorded_remedy_line

RESULT_PAGE_LINES: Final = 200
"""How many formatted lines one result page shows before the next is asked for."""


def result_pages(result: BaseModel) -> tuple[str, ...]:
    """Return the typed result as formatted JSON, one bounded page of lines at a time."""
    lines = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2).splitlines()
    return tuple(
        "\n".join(lines[start : start + RESULT_PAGE_LINES]) for start in range(0, len(lines), RESULT_PAGE_LINES)
    )


def receipt_text(projection: OperationPublicProjectionV1) -> str:
    """Return what the settled operation's public receipt says, one fact a line."""
    view_model = build_operation_modal_view_model(projection)
    lines = [f"{tr('tui.operations.receipt.operation')}: {projection.operation_id}"]
    if view_model.terminal_copy_key is not None:
        lines.append(f"{tr('tui.operations.receipt.outcome')}: {tr(view_model.terminal_copy_key)}")
    lines.append(f"{tr('tui.operations.receipt.effect')}: {projection.effect.value}")
    if projection.result_ref is not None:
        lines.append(f"{tr('operation.modal.detail.receipt_result')}: {projection.result_ref}")
    if projection.refusal_ref is not None:
        lines.append(f"{tr('operation.modal.detail.receipt_refusal')}: {projection.refusal_ref}")
    if projection.failure_error_code is not None:
        lines.append(f"{tr('tui.operations.stopped.code')}: {projection.failure_error_code}")
    if projection.diagnostic_ref is not None:
        lines.append(f"{tr('operation.modal.detail.diagnostic')}: {projection.diagnostic_ref}")
    return "\n".join(lines)


def stopped_operation_text(detail: OperationErrorDetailV1 | None) -> str:
    """Return the recorded code, message and remedy of a refused or failed operation.

    An operation that recorded no detail, or recorded a fault of its own
    records, has nothing to add to the code its receipt already carries.
    """
    if detail is None or detail.kind is not OperationErrorDetailKind.REGISTERED_ERROR or detail.error_code is None:
        return ""
    error = RecordedRegisteredError(
        detail.error_code, context=detail.context_mapping(), translated_message=detail.message_key
    )
    lines = [f"{tr('tui.operations.stopped.code')}: {detail.error_code}", render_error_text(error).rstrip()]
    if detail.precondition_verdict_json is not None:
        verdict = json.dumps(json.loads(detail.precondition_verdict_json), ensure_ascii=False, indent=2)
        lines.append(f"{tr('tui.operations.stopped.remedy')}:\n{verdict}")
        remedy = recorded_remedy_line(detail)
        if remedy is not None:
            lines.append(remedy)
    return "\n".join(lines)


__all__ = ["RESULT_PAGE_LINES", "receipt_text", "result_pages", "stopped_operation_text"]
