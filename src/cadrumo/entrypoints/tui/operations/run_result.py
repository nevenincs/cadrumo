"""Word a settled operation's receipt and typed result for the run screen.

The result is the registered result model's own JSON, formatted and cut into
pages a terminal can hold. A refused or failed operation's own refusal is
shown by the refusal panel, from what it served.
"""

from __future__ import annotations

import json
from typing import Final

from pydantic import BaseModel

from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....core.i18n.render import tr
from ....core.operations import OperationTerminalCondition
from .projection import build_operation_modal_view_model

RESULT_PAGE_LINES: Final = 200
"""How many formatted lines one result page shows before the next is asked for."""


def result_is_readable(projection: OperationPublicProjectionV1) -> bool:
    """Require a successful result or an admitted refusal-detail receipt."""
    condition = projection.terminal_condition
    return (condition is OperationTerminalCondition.SUCCEEDED and projection.result_ref is not None) or (
        condition is OperationTerminalCondition.REFUSED
        and projection.refusal_ref in projection.definition_contract.refusal_detail_codes
    )


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


__all__ = ["RESULT_PAGE_LINES", "receipt_text", "result_is_readable", "result_pages"]
