"""Wording for operation request field kinds and input problems."""

from __future__ import annotations

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.request_faults import request_fault_line
from .request_form import RequestFieldKind, RequestFieldProblem


def kind_hint(kind: RequestFieldKind) -> str:
    """Say how one kind of value is entered, as the field's placeholder."""
    if kind is RequestFieldKind.INTEGER:
        return tr("tui.operations.form.hint.integer")
    if kind is RequestFieldKind.NUMBER:
        return tr("tui.operations.form.hint.number")
    if kind is RequestFieldKind.DECIMAL:
        return tr("tui.operations.form.hint.decimal")
    if kind is RequestFieldKind.DATE:
        return tr("tui.operations.form.hint.date")
    if kind is RequestFieldKind.DATETIME:
        return tr("tui.operations.form.hint.datetime")
    if kind is RequestFieldKind.UUID:
        return tr("tui.operations.form.hint.uuid")
    if kind is RequestFieldKind.PATH:
        return tr("tui.operations.form.hint.path")
    return tr("tui.operations.form.hint.text")


def problem_text(problem: RequestFieldProblem) -> str:
    """Word why a field's text could not be read."""
    if problem is RequestFieldProblem.INTEGER:
        return tr("tui.operations.form.error.integer")
    if problem is RequestFieldProblem.NUMBER:
        return tr("tui.operations.form.error.number")
    if problem is RequestFieldProblem.JSON:
        return tr("tui.operations.form.error.json")
    return tr("tui.operations.form.error.choice")


_UNKNOWN_OUTCOME_CODES = frozenset({RefusalCode.TIMEOUT, RefusalCode.CONNECTION_CLOSED})


def failure_text(error: CadrumoError) -> str:
    """Explain a submission refusal and any unresolved outcome."""
    message = resolve_error_message(error)
    if isinstance(error, RefusalError) and error.reason in _UNKNOWN_OUTCOME_CODES:
        return f"{tr('tui.operations.run.unknown')}\n{message}"
    if isinstance(error, FrontendRefusedError) and error.request_faults:
        # The runtime's request model refused a payload the form's own check let through.
        return "\n".join((message, *(request_fault_line(fault) for fault in error.request_faults)))
    if isinstance(error, FrontendRefusedError) and error.holder_operation_id is not None:
        # A busy subject names the unsettled operation holding it, so the person can follow it.
        return f"{message}\n{tr('tui.operations.run.busy_holder', operation_id=error.holder_operation_id)}"
    return message
