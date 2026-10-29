"""Localized public operation log, progress and phase wording."""

from __future__ import annotations

from ....core.i18n.render import tr
from ....core.operator_notice_messages import operation_notice_message
from .logs import OperationModalLogRowV1


def log_row_text(row: OperationModalLogRowV1) -> str:
    """Render one log row, as the operator's own prompt when its notice asks them to act."""
    if row.completed is not None and row.total is not None:
        return progress_text(row.completed, row.total, row.unit_code, row.subject_code)
    if row.phase_code is not None:
        return phase_text(row.phase_code)
    if row.notice_code is not None:
        prompt = operation_notice_message(row.notice_code, row.display_code)
        if prompt is not None:
            return prompt
    code = row.notice_code or row.code
    return f"{tr(code)}: {row.display_code}" if row.display_code is not None else tr(code)


def progress_text(completed: int, total: int, unit_code: str | None, subject_code: str | None) -> str:
    """Word the runtime's measured progress with its subject and unit."""
    subject = "" if subject_code is None else f"{tr(subject_code)}: "
    unit = "" if unit_code is None else f" {tr(unit_code)}"
    return f"{subject}{completed:,} / {total:,}{unit} ({completed * 100 // total}%)"


def phase_text(code: str) -> str:
    """Word an operation phase coordinate."""
    return tr(code)
