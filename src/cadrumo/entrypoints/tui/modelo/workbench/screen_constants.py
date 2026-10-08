"""Constants and locale keys used by the Modelo workbench screen."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from weakref import WeakSet

from .....application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from .....domain.modelos.verification_report import VerificationCompletenessStatus
from ...components.theme import CADRUMO_CSS_TOKENS
from .header import DeadlineTone
from .page_items import WorkbenchFilter
from .progress import NextAction

_NARROW: Final[int] = 110
_SHORT: Final[int] = 30
"""Below this many rows the list shows one line per box and the help band one line, so ten or more boxes fit."""
_DOCKED_FROM: Final[int] = _SHORT
"""From this many rows the box panel docks in place of the help band; below it, it opens as the centred dialog."""
_FOLLOWING_LINES: Final[int] = 2
"""Lines of the list kept in view after the box being edited, so its neighbours show beside the docked panel."""
_GUTTERS: Final[int] = 2 * int(CADRUMO_CSS_TOKENS["cadrumo-gutter"])
_NEXT_GAP: Final[int] = int(CADRUMO_CSS_TOKENS["cadrumo-section"])
_FOOTER_KEY_GAP: Final[int] = 1
_NO_BREAK_SPACE: Final[str] = "\u00a0"
_PALETTE_FRAME: Final[int] = 2
"""The command palette key's rule on its left and its gap on its right, beside its words, in the compact footer."""
_FOOTER_PRIORITY: Final[tuple[str, ...]] = (
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
)
"""Footer keys, most needed first; the footer shows as many as fit and the expanded help names them all."""
_HELP_ONLY_KEYS: Final[tuple[str, ...]] = ("space",)
"""Keys the help and the legend name that the footer never shows."""
_CHANGE_KEYS: Final[frozenset[str]] = frozenset({"R", "b", "c", "f8", "n"})
"""Footer keys that change a declaration or lead to what is left to do; a declaration recorded as filed shows none."""
_NONE_TO_CONFIRM_LOCALE_KEYS: Final[Mapping[bool, str]] = {
    True: "tui.modelo.workbench.bulk_confirm.none_in_section",
    False: "tui.modelo.workbench.bulk_confirm.none_on_page",
}
"""What ``b`` says with nothing assumed in the section under the cursor (``True``) or on the page."""
_VALUE_CHANGING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {str(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID), str(MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID)}
)
"""Operations after which the workbench shows which boxes now read differently."""
_SELF_REPORTING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {str(MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID), str(MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID)}
)
"""Operations whose notice says what they concluded, read from the declaration once it is read again."""
_NAV_MIN_LABEL: Final[int] = 12
_DIALOG_FRAME: Final[int] = 4
"""Cells a full-width confirmation dialog's border and padding take across, around its message."""
_FRAGMENT_SEPARATOR: Final[str] = " … "
_FILTER_ORDER: Final[tuple[WorkbenchFilter, ...]] = (
    WorkbenchFilter.ALL,
    WorkbenchFilter.ATTENTION,
    WorkbenchFilter.MINE,
    WorkbenchFilter.RECORDS,
    WorkbenchFilter.CALCULATED,
    WorkbenchFilter.AMOUNT,
)
_NEXT_KEYS: Final[Mapping[NextAction, str]] = {
    NextAction.APPLY: "R",
    NextAction.FILL: "n",
    NextAction.CONFIRM: "n",
    NextAction.RESOLVE: "i",
    NextAction.CALCULATE: "F8",
    NextAction.RECALCULATE: "c",
    NextAction.VERIFY: "F8",
    NextAction.EXPORT: "e",
    NextAction.EXPORT_AGAIN: "e",
    NextAction.RECORD_AFTER_FILE: "F8",
    NextAction.RECORDED: "",
}
_FINDINGS_KEY: Final[str] = _NEXT_KEYS[NextAction.RESOLVE]
"""The key the next-action line names when the findings list leads to what is left, whichever step it is."""
_CHECKED_LOCALE_KEYS: Final[Mapping[VerificationCompletenessStatus, str]] = {
    VerificationCompletenessStatus.COMPLETE: "tui.modelo.workbench.operation.checked.complete",
    VerificationCompletenessStatus.INCOMPLETE: "tui.modelo.workbench.operation.checked.incomplete",
    VerificationCompletenessStatus.BLOCKED: "tui.modelo.workbench.operation.checked.blocked",
}
_DEADLINE_TONE_CLASSES: Final[Mapping[DeadlineTone, str]] = {
    DeadlineTone.NORMAL: "-normal",
    DeadlineTone.SOON: "-soon",
    DeadlineTone.URGENT: "-urgent",
    DeadlineTone.MUTED: "-muted",
}
_SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "left_square_bracket": "tui.modelo.workbench.key.previous_page",
    "right_square_bracket": "tui.modelo.workbench.key.next_page",
    "f": "tui.modelo.workbench.key.filter",
    "question_mark": "tui.modelo.workbench.key.help",
    "escape": "tui.modelo.workbench.key.back",
    "R": "tui.modelo.workbench.key.review",
    "f8": "tui.modelo.workbench.key.next_step",
    "c": "tui.modelo.workbench.key.calculate",
    "e": "tui.modelo.workbench.key.export",
    "i": "tui.modelo.workbench.key.issues",
    "n": "tui.modelo.workbench.key.next_attention",
    "slash": "tui.modelo.workbench.key.search",
    "g": "tui.modelo.workbench.key.go_to",
    "o": "tui.modelo.workbench.key.sort",
    "b": "tui.modelo.workbench.bulk_confirm.title",
    "space": "tui.modelo.workbench.key.fold",
}
_LIST_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "enter": "tui.modelo.workbench.key.edit",
    "s": "tui.modelo.workbench.key.sources",
    "up": "tui.modelo.workbench.key.scroll",
}
_RECORDED_ENTER_LOCALE_KEY: Final[str] = "tui.modelo.workbench.sources.key.go"
"""What Enter does on a declaration recorded as filed: it opens the box, to read it, never to edit it."""
_CLOSE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.key.close"
_EMPTY_LOCALE_KEY: Final[str] = "tui.modelo.workbench.filter.empty"
_EMPTY_NEXT_LOCALE_KEY: Final[str] = "tui.modelo.workbench.filter.empty_next"
_CRUMB_SEPARATOR: Final[str] = " · "
_FILE_OUT_OF_DATE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.record.refused_file_out_of_date"
"""Why recording the filing is refused while the latest file was made from an earlier calculation."""
_WITHHELD_LOCALE_KEY: Final[str] = "tui.modelo.workbench.export.confirm_first"
"""Why neither the file for the AEAT nor recording the filing is offered while an assumed value remains."""
_BLOCKED_LOCALE_KEY: Final[str] = "tui.modelo.workbench.export.resolve_first"
"""Why neither is offered while something blocks filing."""
_LEGEND_KEYS: Final[frozenset[str]] = frozenset({"escape"})
_SCROLL_LOCALE_KEY: Final[str] = "tui.modelo.workbench.key.scroll"
"""The only keys the footer shows while the symbols panel is open."""
_GREETED: Final[WeakSet[object]] = WeakSet()
"""The applications whose filer has already been told once where to find what the symbols mean."""
