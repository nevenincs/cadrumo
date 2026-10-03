"""Worded states, deadlines and locale figures for declaration portfolio rows."""

from __future__ import annotations

from decimal import Decimal

from ....application.modelo.declarations_list import DeclarationListRow
from ....application.modelo.value_presentation import format_casilla_value
from ....application.modelo.work_form_models import ModeloFormResult, ModeloFormResultDirection
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.schema_base import CasillaDataType
from ..modelo.workbench.wording import date_text, modelo_title, period_words

_DIRECTION_WORDS = {
    ModeloFormResultDirection.TO_PAY: "to_pay",
    ModeloFormResultDirection.TO_REFUND: "to_refund",
    ModeloFormResultDirection.TO_CARRY_FORWARD: "to_carry_forward",
    ModeloFormResultDirection.TO_DEDUCT_LATER: "negative_carried",
    ModeloFormResultDirection.NIL: "zero",
    ModeloFormResultDirection.NEGATIVE: "negative",
    ModeloFormResultDirection.UNKNOWN: "unknown",
}


def _state_words(row: DeclarationListRow, language: OutputLanguage, local_draft: bool) -> str:
    """State words."""
    if row.state == "aeat_unlinked" and row.calendar is not None and row.calendar.aeat_submitted_at is not None:
        state = tr(
            "tui.declarations.list.state.aeat_unlinked_on", date=date_text(row.calendar.aeat_submitted_at, language)
        )
    elif row.state == "recorded":
        state = tr("tui.declarations.list.group.recorded")
    elif row.state == "discarded":
        state = tr("tui.declarations.work_state.descartado")
    elif row.state == "maybe":
        state = tr("tui.declarations.list.maybe.help")
    elif local_draft:
        state = tr("tui.declarations.list.state.local_draft")
    else:
        state = ("▲ " if row.state == "blocked" else "") + tr("tui.declarations.list.state." + row.state)
    return state


def _result_lines(row: DeclarationListRow, language: OutputLanguage) -> list[str]:
    """Result lines."""
    right: list[str] = []
    summary = None if row.declaration is None else row.declaration.summary
    result = None if summary is None else summary.result
    if result is not None and result.value is not None:
        right.append(_valued_result_words(result, result.value, language))
    elif row.state not in {"not_started", "maybe", "aeat_unlinked"}:
        not_calculated = (
            row.state == "draft"
            and row.declaration is not None
            and not row.declaration.has_current_calculation
            and not row.declaration.has_current_filing
        )
        right.append(
            tr("tui.modelo.workbench.origin.not_calculated_yet")
            if not_calculated
            else tr("tui.declarations.value.result_unknown")
        )
    return right


def _valued_result_words(result: ModeloFormResult, value: Decimal, language: OutputLanguage) -> str:
    """Preserve the settled sign and election wording for a known amount."""
    shown_value = value if result.direction is ModeloFormResultDirection.UNKNOWN else abs(value)
    amount = format_casilla_value(shown_value, data_type=CasillaDataType.MONEY, language=language)
    key = "tui.modelo.workbench.header.result." + _DIRECTION_WORDS[result.direction]
    if result.election_may_change:
        key = "tui.modelo.workbench.header.result.choice_pending"
    if result.direction is ModeloFormResultDirection.TO_DEDUCT_LATER:
        return tr(key, amount=amount)
    if result.direction in {ModeloFormResultDirection.NIL, ModeloFormResultDirection.NEGATIVE}:
        return tr(key)
    return tr(key) + " · " + amount


def _local_next_action(state: str, local_draft: bool) -> str:
    """Choose the local work action after route admission."""
    if local_draft:
        return "open_local_draft"
    if state == "checked":
        return "create_file"
    if state in {"recorded", "superseded", "discarded"}:
        return "none"
    return "continue"


def _next_action_lines(row: DeclarationListRow, local_draft: bool, can_open: bool, can_create: bool) -> list[str]:
    """Next action lines."""
    right: list[str] = []
    summary = None if row.declaration is None else row.declaration.summary
    if row.state == "blocked":
        right.append(tr("tui.declarations.list.next.fix", count=0 if summary is None else summary.blocking_count or 0))
    elif row.state == "not_started" and can_create:
        right.append(tr("tui.declarations.list.next.start"))
    elif row.declaration is not None and can_open and row.state != "unreadable":
        key = _local_next_action(row.state, local_draft)
        right.append(tr("tui.declarations.list.next." + key))
    return right


def is_unlinked_local_draft(row: DeclarationListRow) -> bool:
    """Identify original local work beside confirmed external completion."""
    return (
        row.declaration is not None
        and row.calendar is not None
        and row.calendar.aeat_submission_state is not None
        and row.calendar.aeat_submission_state.value != "not_observed"
        and not row.calendar.evidence_conflicted
        and not row.calendar.aeat_needs_check
        and row.state in {"draft", "calculated", "checked"}
        and (row.declaration.summary is None or not row.declaration.summary.is_correction)
    )


def row_lines(
    row: DeclarationListRow, language: OutputLanguage, *, can_open: bool, can_create: bool
) -> tuple[list[str], list[str]]:
    """Keep the declaration's own result separate from an external AEAT filing."""
    left = [modelo_title(row.modelo, language)]
    local_draft = is_unlinked_local_draft(row)
    if row.period is not None:
        left.append(period_words(row.period))
    if row.deadline is not None and row.state != "aeat_unlinked":
        left.append(tr("tui.declarations.list.column.deadline") + ": " + date_text(row.deadline, language))
    state = _state_words(row, language, local_draft)
    right = [state]
    right.extend(_result_lines(row, language))
    if row.advice is not None:
        right.append(tr("tui.declarations.list.advice." + row.advice.value))
    right.extend(_next_action_lines(row, local_draft, can_open, can_create))
    return left, right
