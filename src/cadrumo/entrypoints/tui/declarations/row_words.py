"""Declaration portfolio rows in the filer's words, offering only the steps this workspace may take."""

from __future__ import annotations

from ....application.modelo.declarations_list import (
    DeclarationListNextStep,
    DeclarationListRow,
    next_step,
    next_step_words,
    opens_local_work,
    result_words,
    state_words,
)
from ....application.modelo.work_form_wording import date_text, modelo_title, period_words
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr


def _next_action_lines(
    row: DeclarationListRow, language: OutputLanguage, *, can_open: bool, can_create: bool
) -> list[str]:
    """The row's step, when this workspace may open its local work or start it."""
    step = next_step(row)
    if step is None:
        return []
    if step is DeclarationListNextStep.START and not can_create:
        return []
    if opens_local_work(step) and not can_open:
        return []
    return [next_step_words(row, step, language)]


def row_lines(
    row: DeclarationListRow, language: OutputLanguage, *, can_open: bool, can_create: bool
) -> tuple[list[str], list[str]]:
    """Keep the declaration's own result separate from an external AEAT filing."""
    left = [modelo_title(row.modelo, language)]
    if row.period is not None:
        left.append(period_words(row.period))
    if row.deadline is not None and row.state != "aeat_unlinked":
        left.append(tr("workspace.declarations.list.column.deadline") + ": " + date_text(row.deadline, language))
    right = [state_words(row, language)]
    result = result_words(row, language)
    if result is not None:
        right.append(result)
    if row.advice is not None:
        right.append(tr("workspace.declarations.list.advice." + row.advice.value))
    right.extend(_next_action_lines(row, language, can_open=can_open, can_create=can_create))
    return left, right
