"""Localized public operation log, progress and phase wording."""

from __future__ import annotations

from ....application.modelo.value_presentation import format_casilla_value
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
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
    language = OutputLanguage(output_language())
    done = format_casilla_value(completed, data_type="integer", language=language)
    of = format_casilla_value(total, data_type="integer", language=language)
    return f"{subject}{done} / {of}{unit} ({completed * 100 // total}%)"


def phase_text(code: str) -> str:
    """Word an operation phase coordinate."""
    return tr(code)
