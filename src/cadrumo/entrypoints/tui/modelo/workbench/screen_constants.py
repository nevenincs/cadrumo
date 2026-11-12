"""Constants and locale keys used by the Modelo workbench screen."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from weakref import WeakSet

from .....application.modelo.operation_shared import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from .....application.modelo.work_form_header import ModeloFormDeadlineTone
from .....application.modelo.work_form_next_step import ModeloFormNextAction
from .....domain.modelos.verification_report import VerificationCompletenessStatus
from ...components.theme import CADRUMO_CSS_TOKENS
from .page_items import WorkbenchFilter

NARROW: Final[int] = 110
SHORT: Final[int] = 30
"""Below this many rows the list shows one line per box and the help band one line, so ten or more boxes fit."""
DOCKED_FROM: Final[int] = SHORT
"""From this many rows the box panel docks in place of the help band; below it, it opens as the centred dialog."""
FOLLOWING_LINES: Final[int] = 2
"""Lines of the list kept in view after the box being edited, so its neighbours show beside the docked panel."""
GUTTERS: Final[int] = 2 * int(CADRUMO_CSS_TOKENS["cadrumo-gutter"])
NEXT_GAP: Final[int] = int(CADRUMO_CSS_TOKENS["cadrumo-section"])
FOOTER_KEY_GAP: Final[int] = 1
NO_BREAK_SPACE: Final[str] = "\u00a0"
PALETTE_FRAME: Final[int] = 2
"""The command palette key's rule on its left and its gap on its right, beside its words, in the compact footer."""
FOOTER_PRIORITY: Final[tuple[str, ...]] = (
    "enter",
    "up",
    "n",
    "question_mark",
    "escape",
    "f8",
    "R",
    "s",
    "slash",
    "g",
    "o",
    "left_square_bracket",
    "right_square_bracket",
    "f",
    "i",
    "c",
    "e",
    "b",
    "a",
)
"""Footer keys, most needed first; the footer shows as many as fit and the expanded help names them all."""
HELP_ONLY_KEYS: Final[tuple[str, ...]] = ("space",)
"""Keys the help and the legend name that the footer never shows."""
CHANGE_KEYS: Final[frozenset[str]] = frozenset({"R", "a", "b", "c", "f8", "n"})
"""Footer keys that change a declaration or lead to what is left to do; a declaration recorded as filed shows none."""
NONE_TO_CONFIRM_LOCALE_KEYS: Final[Mapping[bool, str]] = {
    True: "workspace.modelo.bulk_confirm.none_in_section",
    False: "workspace.modelo.bulk_confirm.none_on_page",
}
"""What ``b`` says with nothing assumed in the section under the cursor (``True``) or on the page."""
VALUE_CHANGING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {str(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID), str(MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID)}
)
"""Operations after which the workbench shows which boxes now read differently."""
SELF_REPORTING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {str(MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID), str(MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID)}
)
"""Operations whose notice says what they concluded, read from the declaration once it is read again."""
NAV_MIN_LABEL: Final[int] = 12
DIALOG_FRAME: Final[int] = 4
"""Cells a full-width confirmation dialog's border and padding take across, around its message."""
FRAGMENT_SEPARATOR: Final[str] = " … "
FILTER_ORDER: Final[tuple[WorkbenchFilter, ...]] = (
    WorkbenchFilter.ALL,
    WorkbenchFilter.ATTENTION,
    WorkbenchFilter.MINE,
    WorkbenchFilter.RECORDS,
    WorkbenchFilter.CALCULATED,
    WorkbenchFilter.AMOUNT,
)
NEXT_KEYS: Final[Mapping[ModeloFormNextAction, str]] = {
    ModeloFormNextAction.APPLY: "R",
    ModeloFormNextAction.FILL: "n",
    ModeloFormNextAction.CONFIRM: "n",
    ModeloFormNextAction.RESOLVE: "i",
    ModeloFormNextAction.CALCULATE: "F8",
    ModeloFormNextAction.RECALCULATE: "c",
    ModeloFormNextAction.VERIFY: "F8",
    ModeloFormNextAction.EXPORT: "e",
    ModeloFormNextAction.EXPORT_AGAIN: "e",
    ModeloFormNextAction.RECORD_AFTER_FILE: "F8",
    ModeloFormNextAction.RECORDED: "",
}
FINDINGS_KEY: Final[str] = NEXT_KEYS[ModeloFormNextAction.RESOLVE]
"""The key the next-action line names when the findings list leads to what is left, whichever step it is."""
CHECKED_LOCALE_KEYS: Final[Mapping[VerificationCompletenessStatus, str]] = {
    VerificationCompletenessStatus.COMPLETE: "workspace.modelo.operation.checked.complete",
    VerificationCompletenessStatus.INCOMPLETE: "workspace.modelo.operation.checked.incomplete",
    VerificationCompletenessStatus.BLOCKED: "workspace.modelo.operation.checked.blocked",
}
DEADLINE_TONE_CLASSES: Final[Mapping[ModeloFormDeadlineTone, str]] = {
    ModeloFormDeadlineTone.NORMAL: "-normal",
    ModeloFormDeadlineTone.SOON: "-soon",
    ModeloFormDeadlineTone.URGENT: "-urgent",
    ModeloFormDeadlineTone.MUTED: "-muted",
}
SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "left_square_bracket": "workspace.modelo.key.previous_page",
    "right_square_bracket": "workspace.modelo.key.next_page",
    "f": "workspace.modelo.key.filter",
    "question_mark": "workspace.modelo.key.help",
    "escape": "workspace.modelo.key.back",
    "R": "workspace.modelo.key.review",
    "f8": "workspace.modelo.key.next_step",
    "c": "workspace.modelo.key.calculate",
    "e": "workspace.modelo.key.export",
    "i": "workspace.modelo.key.issues",
    "n": "workspace.modelo.key.next_attention",
    "slash": "workspace.modelo.key.search",
    "g": "workspace.modelo.key.go_to",
    "o": "workspace.modelo.key.sort",
    "b": "workspace.modelo.bulk_confirm.title",
    "a": "tui.modelo.statements.key",
    "space": "workspace.modelo.key.fold",
}
LIST_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "enter": "workspace.modelo.key.edit",
    "s": "workspace.modelo.key.sources",
    "up": "workspace.modelo.key.scroll",
}
RECORDED_ENTER_LOCALE_KEY: Final[str] = "workspace.modelo.sources.key.go"
"""What Enter does on a declaration recorded as filed: it opens the box, to read it, never to edit it."""
CLOSE_LOCALE_KEY: Final[str] = "workspace.modelo.key.close"
EMPTY_LOCALE_KEY: Final[str] = "workspace.modelo.filter.empty"
EMPTY_NEXT_LOCALE_KEY: Final[str] = "workspace.modelo.filter.empty_next"
CRUMB_SEPARATOR: Final[str] = " · "
LEGEND_KEYS: Final[frozenset[str]] = frozenset({"escape"})
SCROLL_LOCALE_KEY: Final[str] = "workspace.modelo.key.scroll"
"""The only keys the footer shows while the symbols panel is open."""
GREETED: Final[WeakSet[object]] = WeakSet()
"""The applications whose filer has already been told once where to find what the symbols mean."""
